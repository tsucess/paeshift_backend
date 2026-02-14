
# ==
# 📌 Python Standard Library
# ==
import logging
import uuid
import hmac
import hashlib
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Optional

# ==
# 📌 Django & Third-Party
# ==
import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Router
from ninja.responses import Response
from ninja.errors import HttpError
from django.http import HttpResponse

# ==
# 📌 Local Models & Tasks
# ==
from accounts.models import CustomUser as User
from accounts.models import Profile
from .models import Payment, Wallet, Transaction, PaymentStatusEnum
from jobs.models import Job
from .schemas import *
from .tasks import verify_payment_status
# from payment.models import PaymentStatusEnum

# Import error handling and logging utilities
from core.exceptions import (
    ResourceNotFoundError,
    InternalServerError,
    ValidationError as PaeshiftValidationError,
    InsufficientFundsError,
)
from core.logging_utils import log_endpoint, logger as core_logger, api_logger

# Import caching utilities for Phase 2.2c
from core.cache_utils import (
    cache_query_result,
    cache_api_response,
    invalidate_cache,
    CACHE_TTL_PAYMENTS,
)

# ==
# 📌 Scheduling
# ==
# Temporarily commented out - django_q has pkg_resources issue
# from django_q.tasks import schedule
# from django_q.models import Schedule

logger = logging.getLogger(__name__)
payments_router = Router(tags=["Payments"])




# ==
# 📌 Utility Functions
# ==
def _get_time_range(filter: str) -> tuple[datetime, Optional[datetime]]:
    """Calculate time range for filters"""
    now = timezone.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Calculate first day of current month
    first_day_of_month = today.replace(day=1)

    # Calculate first day of previous month
    if first_day_of_month.month == 1:  # January
        first_day_of_last_month = first_day_of_month.replace(year=first_day_of_month.year - 1, month=12)
    else:
        first_day_of_last_month = first_day_of_month.replace(month=first_day_of_month.month - 1)

    # Calculate first day of current year
    first_day_of_year = today.replace(month=1, day=1)

    # Calculate first day of last year
    first_day_of_last_year = first_day_of_year.replace(year=first_day_of_year.year - 1)

    # Calculate last day of last year
    last_day_of_last_year = first_day_of_year - timedelta(days=1)

    ranges = {
        "today": (today, None),
        "yesterday": (today - timedelta(days=1), today),
        "this_week": (today - timedelta(days=today.weekday()), None),
        "last_week": (
            today - timedelta(days=today.weekday() + 7),
            today - timedelta(days=today.weekday()),
        ),
        "this_month": (first_day_of_month, None),
        "last_month": (first_day_of_last_month, first_day_of_month),
        "this_year": (first_day_of_year, None),
        "last_year": (first_day_of_last_year, first_day_of_year),
    }

    return ranges.get(filter, (None, None))


# ==
# 📌 Payment Endpoints
# ==

# ==
# 📌 Wallet Transaction Endpoints
# ==
@log_endpoint(core_logger)
@payments_router.get(
    "/users/{user_id}/wallet/transactions",
    response={200: dict, 404: dict},
    summary="List wallet transactions",
    description="Retrieve wallet transactions with optional time filtering",
)
def list_wallet_transactions(
    request, user_id: int, filter: str = "all", limit: int = 100, offset: int = 0
):
    """
    Get paginated wallet transactions with optional time filter.

    Args:
        user_id: User ID
        filter: Time filter (all, today, yesterday, this_week, last_week, this_month)
        limit: Maximum number of results to return
        offset: Offset for pagination

    Returns:
        List of wallet transactions
    """
    try:
        # Get user
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise ResourceNotFoundError("User", user_id)

        # Get or create wallet
        wallet, created = Wallet.objects.get_or_create(
            user=user,
            defaults={"balance": Decimal("0.00")}
        )

        if created:
            core_logger.info(f"Created new wallet for user {user_id}")

        # Get transactions
        transactions = Transaction.objects.filter(wallet=wallet).order_by("-created_at")

        # Apply time filter
        if filter != "all":
            start, end = _get_time_range(filter)
            if start:
                if end:
                    transactions = transactions.filter(created_at__range=(start, end))
                else:
                    transactions = transactions.filter(created_at__gte=start)

            # Log the filter being applied
            core_logger.debug(f"Applied filter '{filter}' with date range: {start} to {end}")

        # Get total count before pagination
        total_count = transactions.count()

        # Apply pagination
        paginated = transactions[offset:offset + limit]

        # Create response
        response = {
            "status": "success",
            "message": "Wallet transactions retrieved successfully",
            "data": {
                "count": total_count,
                "wallet_balance": str(wallet.balance),
                "results": [
                    {
                        "id": t.id,
                        "amount": str(t.amount),
                        "transaction_type": t.transaction_type,
                        "debit_or_credit": t.transaction_type,  # Explicit for frontend
                        "status": t.status,
                        "reference": t.reference,
                        "description": t.description,
                        "created_at": t.created_at.isoformat(),
                    }
                    for t in paginated
                ],
            }
        }

        # Log successful retrieval
        core_logger.info(
            "Wallet transactions retrieved",
            user_id=user_id,
            transaction_count=total_count,
            filter=filter
        )

        return response

    except ResourceNotFoundError:
        raise
    except Exception as e:
        core_logger.error(f"Error retrieving wallet transactions: {str(e)}", exc_info=True)
        raise InternalServerError("Failed to retrieve wallet transactions")





@log_endpoint(core_logger)
@payments_router.post(
    "/users/wallet/withdraw",
    response={200: dict, 400: dict, 404: dict, 500: dict},
    summary="Withdraw funds from wallet",
    description="Withdraw funds from user's wallet",
)
def withdraw_funds(request, payload: WalletWithdrawSchema):
    """
    Withdraw funds from a user's wallet.
    """
    user_id = payload.user_id
    amount = payload.amount

    try:
        # Validate amount
        if amount <= 0:
            raise PaeshiftValidationError("Amount must be greater than 0", {"amount": str(amount)})

        # Get user
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise ResourceNotFoundError("User", user_id)

        # Get or create wallet
        wallet, created = Wallet.objects.get_or_create(user=user)
        if created:
            core_logger.info(f"Wallet created for user {user_id}")

        # Check sufficient funds
        if wallet.balance < amount:
            raise InsufficientFundsError(
                f"Insufficient funds. Available: {wallet.balance}, Requested: {amount}"
            )

        # Atomic withdrawal
        with transaction.atomic():
            wallet.deduct_funds(amount)

            transaction_ref = Transaction.generate_reference()
            transaction_obj = Transaction.objects.create(
                wallet=wallet,
                amount=amount,
                transaction_type=Transaction.Type.DEBIT,
                status=Transaction.Status.COMPLETED,
                reference=transaction_ref,
                description="Wallet withdrawal",
                metadata={
                    "user_id": user.id,
                    "withdrawal_method": "bank_transfer",
                }
            )

        # Notify user (optional)
        # try:
        #     from notifications.models import Notification
        #     Notification.objects.create(
        #         user=user,
        #         category="wallet_withdrawal",
        #         message=f"Your withdrawal of {amount} NGN has been processed.",
        #         is_read=False
        #     )
        # except Exception as e:
        #     logger.warning(f"Notification error: {e}")

        # Log successful withdrawal
        api_logger.log_payment(
            user_id=user_id,
            payment_id=transaction_obj.id,
            amount=float(amount),
            status="completed",
            message="Wallet withdrawal successful"
        )
        core_logger.info(
            "Wallet withdrawal completed",
            user_id=user_id,
            amount=str(amount),
            new_balance=str(wallet.balance)
        )

        return {
            "status": "success",
            "message": "Withdrawal successful",
            "data": {
                "transaction_id": transaction_obj.id,
                "reference": transaction_obj.reference,
                "amount": str(transaction_obj.amount),
                "new_balance": str(wallet.balance),
                "transaction_date": transaction_obj.created_at.isoformat(),
            }
        }

    except (ResourceNotFoundError, PaeshiftValidationError, InsufficientFundsError):
        raise
    except Exception as e:
        core_logger.error(f"Error withdrawing funds: {str(e)}", exc_info=True)
        raise InternalServerError("Failed to process withdrawal")









@log_endpoint(core_logger)
@cache_api_response(timeout=CACHE_TTL_PAYMENTS, prefix='payments:user')
@payments_router.get(
    "/users/{user_id}/payments",
    response={200: StandardResponse, 404: dict, 500: dict},
    summary="List user payments",
    description="Retrieve payments with optional time filtering",
)
def list_payments(
    request, user_id: int, filter: str = "all", limit: int = 100, offset: int = 0
):
    """
    Get paginated payments with optional time filter.

    This endpoint uses Redis caching to improve performance with:
    1. Function-level caching with the redis_cache decorator
    2. Individual payment caching for better cache hit rates
    3. Telemetry logging for monitoring cache performance
    """
    try:
        # Get user
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise ResourceNotFoundError("User", user_id)

        # Optimize query with select_related() for related objects
        payments = Payment.objects.select_related(
            'payer__profile',
            'recipient__profile',
            'job'
        ).filter(payer=user).order_by("-created_at")

        if filter != "all":
            start, end = _get_time_range(filter)
            if start:
                if end:
                    payments = payments.filter(created_at__range=(start, end))
                else:
                    payments = payments.filter(created_at__gte=start)

            core_logger.debug(f"Applied filter '{filter}' with date range: {start} to {end}")

        total_count = payments.count()
        paginated = payments[offset : offset + limit]

        response = {
            "status": "success",
            "message": "Payments retrieved successfully",
            "data": {
                "count": total_count,
                "results": [
                    {
                        "id": p.id,
                        "amount": str(p.original_amount),
                        "status": p.status,
                        "created_at": p.created_at.isoformat(),
                        "payment_method": p.payment_method,
                        "reference": p.pay_code,
                    }
                    for p in paginated
                ],
            }
        }

        # Log successful retrieval
        core_logger.info(
            "Payment history retrieved",
            user_id=user_id,
            payment_count=total_count,
            filter=filter
        )

        return response

    except ResourceNotFoundError:
        raise
    except Exception as e:
        core_logger.error(f"Error retrieving payment history: {str(e)}", exc_info=True)
        raise InternalServerError("Failed to retrieve payment history")

def strip_non_ascii(text):
    return ''.join(c for c in text if ord(c) < 128)

# =====





# def verify_payment_by_reference(reference: str) -> Payment:
#     """Check payment by reference, mark paid if not paid, and return Payment instance."""
#     try:
#         payment = Payment.objects.get(pay_code=reference)
#     except Payment.DoesNotExist:
#         raise ValueError("Payment not found")

#     # Here you can add real verification with Paystack or Flutterwave if needed
#     # For now, it just marks as successful if not paid
#     if payment.status != "paid":
#         payment.mark_as_successful()  # ensure this method updates payment & job status properly
#         payment.save()

#     return payment


def verify_payment_by_reference(reference: str) -> Payment:
    """Verify payment by reference, mark as successful if verified, and return the payment."""
    try:
        payment = Payment.objects.get(pay_code=reference)
    except Payment.DoesNotExist:
        raise ValueError("Payment not found")

    # For now, simulate verification success (you can call Paystack/Flutterwave verify API here)
    if payment.status != PaymentStatusEnum.SUCCESSFUL:
        payment.mark_as_successful()
        payment.save(update_fields=["status", "updated_at", "verified_at"])
        # ✅ mark_as_successful() also updates job.status and job.payment_status

    return payment



# def verify_payment_by_reference(reference: str) -> Payment:
#     """
#     Check payment by reference, verify via gateway, and mark as successful if confirmed.
#     """
#     try:
#         payment = Payment.objects.get(pay_code=reference)
#     except Payment.DoesNotExist:
#         raise ValueError("Payment not found")

#     # ✅ Call actual Paystack/Flutterwave API here to verify
#     verified = check_gateway_payment(reference, payment.payment_method)

#     if verified and payment.status != "successful":
#         payment.mark_as_successful()
#         payment.save()

#     return payment






@log_endpoint(core_logger)
@payments_router.post("/payments", response={200: dict, 400: dict, 500: dict}, summary="Initiate payment", auth=None)
def initiate_payment(request, payload: InitiatePaymentSchema):
    try:
        # 1. Validate payment method
        if payload.payment_method not in ("paystack", "flutterwave"):
            raise PaeshiftValidationError(
                "Unsupported payment method",
                {"payment_method": payload.payment_method}
            )

        # 2. Calculate amounts
        try:
            total = Decimal(str(payload.total))
        except InvalidOperation:
            raise PaeshiftValidationError("Invalid amount format", {"amount": str(payload.total)})

        if total <= 0:
            raise PaeshiftValidationError("Amount must be greater than 0", {"amount": str(total)})

        service_fee = (total * Decimal("0.10")).quantize(Decimal("0.00"))
        final_amount = (total + service_fee).quantize(Decimal("0.00"))

        # 3. Load user & job
        try:
            user = User.objects.get(id=payload.user_id)
        except User.DoesNotExist:
            raise ResourceNotFoundError("User", payload.user_id)

        job = None
        if payload.job_id:
            try:
                job = Job.objects.get(id=payload.job_id)
            except Job.DoesNotExist:
                raise ResourceNotFoundError("Job", payload.job_id)

        # 4. Create pending payment
        with transaction.atomic():
            pay_code = str(uuid.uuid4())
            payment = Payment.objects.create(
                payer=user,
                job=job,
                recipient=job.selected_applicant if job else None,
                original_amount=total,
                service_fee=service_fee,
                final_amount=final_amount,
                pay_code=pay_code,
                payment_method=payload.payment_method,
                status="pending",
            )


        # 5. Initialize gateway
        try:
            if payload.payment_method == "paystack":
                auth_url = _process_paystack(payment, payload)
            else:
                auth_url = _process_flutterwave(payment, payload)
        except Exception as e:
            logger.error(f"Payment processing failed for {payment.pay_code}: {e}", exc_info=True)
            payment.status = "failed"
            payment.save(update_fields=["status"])
            raise HttpError(400, f"Payment processing failed: {e}")

        # 6. Return success
        return {
            "status": "success",
            "message": "Payment initiated successfully",
            "data": {
                "payment_id": payment.id,
                "authorization_url": auth_url,
                "expires_at": (timezone.now() + timedelta(minutes=30)).isoformat(),
                "original_amount": float(total),
                "service_fee": float(service_fee),
                "reference": pay_code,
                "final_amount": float(final_amount),
            },
        }
    except (PaeshiftValidationError, ResourceNotFoundError):
        raise
    except Exception as e:
        core_logger.error(f"Error initiating payment: {str(e)}", exc_info=True)
        raise InternalServerError("Failed to initiate payment")


def _process_paystack(payment: Payment, payload: InitiatePaymentSchema) -> str:
    """Process payment via Paystack"""
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }

    data = {
        "reference": payment.pay_code,
        "email": f"{strip_non_ascii(payload.first_name.lower())}@user.com",
        "amount": int(payment.original_amount * 100),
        "callback_url": f"{settings.BASE_URL}/payment/verify/?gateway=paystack",

        "metadata": {
            "payment_id": payment.id,
            "user_id": payment.payer.id,
        },
    }

    try:
        resp = requests.post(
            "https://api.paystack.co/transaction/initialize",
            headers=headers,
            json=data,
            timeout=10,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        detail = getattr(e.response, "text", str(e))
        raise RuntimeError(f"Paystack init error: {detail}")

    result = resp.json()
    if not result.get("status") or not result["data"].get("authorization_url"):
        msg = result.get("message") or repr(result)
        raise RuntimeError(f"Paystack processing failed: {msg}")

    return result["data"]["authorization_url"]


def _process_flutterwave(payment: Payment, payload: InitiatePaymentSchema) -> str:
    """Process payment via Flutterwave"""
    # Use the correct settings variable for the secret key
    if not hasattr(settings, "FLUTTERWAVE_SECRET_KEY") or not settings.FLUTTERWAVE_SECRET_KEY:
        raise ValueError("Flutterwave secret key not configured")

    headers = {
        "Authorization": f"Bearer {settings.FLUTTERWAVE_SECRET_KEY}",
        "Content-Type": "application/json",
    }

    data = {
        "tx_ref": payment.pay_code,
        "amount": str(payment.original_amount),
        "currency": "NGN",
        "redirect_url": f"{settings.BASE_URL}/payment/verify/?gateway=flutterwave",
        "payment_options": "card",
        "customer": {
            "email": f"{payload.first_name.lower()}@user.com",
            "name": f"{payload.first_name} {payload.last_name}",
            "phonenumber": payload.phone
        },
        "customizations": {
            "title": "Payshift Payment",
            "description": "Payment for service",
        },
        "meta": {
            "payment_id": payment.id,
            "user_id": payment.payer.id,
        }
    }

    try:
        response = requests.post(
            "https://api.flutterwave.com/v3/payments",
            headers=headers,
            json=data,
            timeout=10
        )
        response.raise_for_status()

        result = response.json()
        if result.get("status") != "success" or not result["data"].get("link"):
            raise ValueError(result.get("message", "Flutterwave processing failed"))

        # Schedule payment verification
        # schedule(
        #     'payment.tasks.verify_flutterwave_payment',
        #     payment.pay_code,
        #     schedule_type='O',  # Run once
        #     next_run=timezone.now() + timedelta(minutes=5)
        # )

        return result["data"]["link"]
    except requests.exceptions.RequestException as e:
        logger.error(f"Flutterwave payment failed: {str(e)}")
        raise ValueError(f"Payment processing failed: {str(e)}")



# ==
# 📌 Payment Webhook Endpoints
# ==



# @payments_router.post("/webhook/flutterwave/")
# def flutterwave_webhook(request):
#     secret = settings.FLUTTERWAVE_SECRET_KEY.encode('utf-8')
#     signature = request.headers.get('x-flutterwave-signature')

#     if not signature:
#         logger.warning("Missing Flutterwave webhook signature")
#         return HttpResponse(status=400)

#     body = request.body
#     # Flutterwave signature verification logic (if required)
#     # computed_signature = ...
#     # if not hmac.compare_digest(computed_signature, signature):
#     #     logger.warning("Invalid Flutterwave webhook signature")
#     #     return HttpResponse(status=400)

#     try:
#         event = request.json()
#     except Exception as e:
#         logger.error(f"Failed to parse webhook JSON: {e}")
#         return HttpResponse(status=400)

#     if event.get("event") == "charge.completed":
#         reference = event["data"].get("tx_ref")
#         if not reference:
#             logger.warning("No tx_ref in Flutterwave webhook data")
#             return HttpResponse(status=400)

#         try:
#             verify_payment_status.delay(reference)
#             logger.info(f"Triggered Celery verification task for Flutterwave payment: {reference}")
#         except Exception as e:
#             logger.error(f"Failed to trigger Celery task: {e}")
#             return HttpResponse(status=500)

#     return HttpResponse(status=200)


# @payments_router.post("/webhook/paystack/")
# def paystack_webhook(request):
#     secret = settings.PAYSTACK_SECRET_KEY.encode('utf-8')
#     signature = request.headers.get('x-paystack-signature')

#     if not signature:
#         logger.warning("Missing Paystack webhook signature")
#         return HttpResponse(status=400)

#     body = request.body
#     computed_signature = hmac.new(secret, body, hashlib.sha512).hexdigest()
#     if not hmac.compare_digest(computed_signature, signature):
#         logger.warning("Invalid Paystack webhook signature")
#         return HttpResponse(status=400)

#     try:
#         event = request.json()
#     except Exception as e:
#         logger.error(f"Failed to parse webhook JSON: {e}")
#         return HttpResponse(status=400)

#     if event.get("event") == "charge.success":
#         reference = event["data"].get("reference")
#         if not reference:
#             logger.warning("No reference in Paystack webhook data")
#             return HttpResponse(status=400)

#         try:
#             # Call Celery async task
#             verify_payment_status.delay(reference)
#             logger.info(f"Triggered Celery verification task for payment: {reference}")
#         except Exception as e:
#             logger.error(f"Failed to trigger Celery task: {e}")
#             return HttpResponse(status=500)

#     return HttpResponse(status=200)


# ==
# 📌 Payment Verification Endpoint
# ==
@log_endpoint(core_logger)
@payments_router.post("/payments/verify", response={200: PaymentResponseSchema, 404: dict, 500: dict})
def verify_payment(request, payload: VerifyPaymentSchema):
    try:
        from decimal import Decimal
        try:
            payment = verify_payment_by_reference(payload.reference)
        except ValueError:
            core_logger.warning(f"Payment not found: reference={payload.reference}")
            raise ResourceNotFoundError("Payment", payload.reference)

        # Calculate service_fee if it's 0 (for backward compatibility)
        service_fee = payment.service_fee
        if service_fee == Decimal("0.00") and payment.original_amount:
            service_fee = (payment.original_amount * Decimal("0.10")).quantize(Decimal("0.00"))

        # Log successful verification
        api_logger.log_payment(
            payment.payer.id,
            payment.id,
            float(payment.final_amount),
            payment.status,
            "Payment verified"
        )
        core_logger.info(
            "Payment verified successfully",
            payment_id=payment.id,
            user_id=payment.payer.id,
            amount=float(payment.final_amount)
        )

        return {
            "id": payment.id,
            "reference": payment.pay_code,
            "amount": float(payment.original_amount),
            "service_fee": float(service_fee),
            "final_amount": float(payment.final_amount),
            "status": payment.status,
            "user_id": payment.payer.id,
            "payment_method": payment.payment_method,
            "created_at": payment.created_at.isoformat(),
            "verified_at": payment.verified_at.isoformat() if payment.verified_at else None,
            "recipient": payment.recipient.email if payment.recipient else None,
            "job_id": payment.job.id if payment.job else None,
            "job_title": payment.job.title if payment.job else None,
        }
    except (ResourceNotFoundError, PaeshiftValidationError):
        raise
    except Exception as e:
        core_logger.error(f"Payment verification error: {str(e)}", exc_info=True)
        raise InternalServerError("Failed to verify payment")


# ==
# 📌 Signature Verification Utilities
# ==
def verify_paystack_signature(request):
    secret = settings.PAYSTACK_SECRET_KEY.encode('utf-8')
    signature = request.headers.get('x-paystack-signature')
    body = request.body

    computed_signature = hmac.new(secret, body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(computed_signature, signature)











# ==
# 📌 User Payment History
# ==
@payments_router.get(
    "/users/{user_id}/payments",
    response={200: dict, 404: dict, 500: dict},
    summary="Get user payment history",
    description="Get payment history for a specific user",
)
def get_user_payments(request, user_id: int):
    """
    Get payment history for a specific user without caching.

    Query Parameters:
        status: Filter by payment status (optional)
        from_date: Filter by start date (optional)
        to_date: Filter by end date (optional)
        limit: Maximum number of results to return (optional)
        page: Page number for pagination (optional)
        payment_method: Filter by payment method (optional)
    """
    try:
        # Check if user exists
        User = get_user_model()
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return 404, {"status": "error", "message": "User not found"}

        # Get query parameters
        status = request.query_params.get('status')
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        limit = int(request.query_params.get('limit', 50))
        page = int(request.query_params.get('page', 1))
        payment_method = request.query_params.get('payment_method')

        # Calculate offset for pagination
        offset = (page - 1) * limit

        # Build query
        query = Q(payer=user)

        if status:
            query &= Q(status=status)

        if payment_method:
            query &= Q(payment_method=payment_method)

        if from_date:
            try:
                from_date = datetime.strptime(from_date, "%Y-%m-%d").date()
                query &= Q(created_at__gte=from_date)
            except ValueError:
                return 400, {"status": "error", "message": "Invalid from_date format. Use YYYY-MM-DD"}

        if to_date:
            try:
                to_date = datetime.strptime(to_date, "%Y-%m-%d").date()
                query &= Q(created_at__lte=to_date)
            except ValueError:
                return 400, {"status": "error", "message": "Invalid to_date format. Use YYYY-MM-DD"}

        # Get total count for pagination
        total_count = Payment.objects.filter(query).count()

        # Calculate pagination info
        total_pages = (total_count + limit - 1) // limit  # Ceiling division
        has_next = page < total_pages
        has_previous = page > 1

        # Execute query with pagination
        payments = Payment.objects.filter(query).order_by('-created_at')[offset:offset + limit]

        # Format response
        from decimal import Decimal
        payment_data = []
        for payment in payments:
            # Calculate service_fee if it's 0 (for backward compatibility)
            service_fee = payment.service_fee
            if service_fee == Decimal("0.00") and payment.original_amount:
                service_fee = (payment.original_amount * Decimal("0.10")).quantize(Decimal("0.00"))

            payment_data.append({
                "id": payment.id,
                "reference": payment.pay_code,
                "amount": float(payment.original_amount),
                "service_fee": float(service_fee),
                "final_amount": float(payment.final_amount),
                "status": payment.status,
                "payment_method": payment.payment_method,
                "created_at": payment.created_at.isoformat(),
                "verified_at": payment.verified_at.isoformat() if hasattr(payment, 'verified_at') and payment.verified_at else None,
                "recipient": payment.recipient.email if payment.recipient else None,
                "job_id": payment.job.id if payment.job else None,
                "job_title": payment.job.title if payment.job else None,
            })

        return 200, {
            "status": "success",
            "message": "Payment history retrieved successfully",
            "data": {
                "user_id": user_id,
                "total_count": total_count,
                "total_pages": total_pages,
                "current_page": page,
                "has_next": has_next,
                "has_previous": has_previous,
                "next_page": page + 1 if has_next else None,
                "previous_page": page - 1 if has_previous else None,
                "payments": payment_data,
            }
        }

    except Exception as e:
        logger.error(f"Error getting payment history for user {user_id}: {str(e)}", exc_info=True)
        return 500, {"status": "error", "message": f"An error occurred: {str(e)}"}

@log_endpoint(core_logger)
@payments_router.post("/initialize", response={200: dict}, tags=["Payment"])
def initialize_payment_view(request, payload: PaymentInitSchema):
    try:
        from .utils import initialize_payment

        if not request.user.is_authenticated:
            api_logger.log_authentication(None, False, "Unauthenticated payment initialization attempt")
            raise PaeshiftValidationError("User not authenticated")

        # Validate amount
        try:
            amount = Decimal(str(payload.amount))
            if amount <= 0:
                raise PaeshiftValidationError("Amount must be greater than 0", {"amount": str(amount)})
        except (InvalidOperation, ValueError):
            raise PaeshiftValidationError("Invalid amount format", {"amount": str(payload.amount)})

        result = initialize_payment(
            amount=float(amount),
            email=request.user.email,
            callback_url=payload.callback_url
        )

        payment = Payment.objects.create(
            user=request.user,
            amount=amount,
            reference=result.get('data', {}).get('reference', ''),
            payment_type='flutterwave',
            status='pending'
        )

        # Log successful initialization
        api_logger.log_payment(
            request.user.id,
            payment.id,
            float(amount),
            'pending',
            "Payment initialized"
        )
        core_logger.info(
            "Payment initialized successfully",
            payment_id=payment.id,
            user_id=request.user.id,
            amount=float(amount)
        )

        return {
            "status": "success",
            "data": {
                "payment_id": payment.id,
                "authorization_url": result.get('data', {}).get('authorization_url'),
                "reference": payment.reference
            }
        }

    except (PaeshiftValidationError, ResourceNotFoundError):
        raise
    except Exception as e:
        core_logger.error(f"Payment initialization failed: {str(e)}", exc_info=True)
        raise InternalServerError("Payment initialization failed")


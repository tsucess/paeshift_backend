
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
from .models import Payment, Wallet, Transaction
from jobs.models import Job
from .schemas import *
from .tasks import verify_payment_status

# ==
# 📌 Scheduling
# ==
from django_q.tasks import schedule
from django_q.models import Schedule

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
    # ...existing code...

    # ...existing code...

    try:
        # Get user
        user = get_object_or_404(User, id=user_id)

        # Get or create wallet
        wallet, created = Wallet.objects.get_or_create(
            user=user,
            defaults={"balance": Decimal("0.00")}
        )

        if created:
            logger.info(f"Created new wallet for user {user_id}")

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
            logger.debug(f"Applied filter '{filter}' with date range: {start} to {end}")

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

        # ...existing code...

        return response

    except User.DoesNotExist:
        return {
            "status": "error",
            "message": "User not found",
        }
    except Wallet.DoesNotExist:
        return {
            "status": "error",
            "message": "Wallet not found for this user",
        }
    except Exception as e:
        logger.error(f"Error retrieving wallet transactions: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": f"An error occurred: {str(e)}",
        }





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
        if amount <= 0:
            return 400, {
                "status": "error",
                "message": "Amount must be positive",
            }

        # Get user
        user = get_object_or_404(User, id=user_id)

        # Get or create wallet
        wallet, created = Wallet.objects.get_or_create(user=user)
        if created:
            print("Wallet created for user", user)
        if wallet.balance < amount:
            return 400, {
                "status": "error",
                "message": "Insufficient funds",
                "data": {
                    "wallet_balance": str(wallet.balance),
                    "requested_amount": str(amount),
                }
            }
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

    except User.DoesNotExist:
        return 404, {"status": "error", "message": "User not found"}
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        return 500, {
            "status": "error",
            "message": f"An error occurred: {str(e)}",
        }









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
    # ...existing code...

    # ...existing code...

    user = get_object_or_404(User, id=user_id)

    payments = Payment.objects.filter(payer=user).order_by("-created_at")

    if filter != "all":
        start, end = _get_time_range(filter)
        if start:
            if end:
                payments = payments.filter(created_at__range=(start, end))
            else:
                payments = payments.filter(created_at__gte=start)

        logger.debug(f"Applied filter '{filter}' with date range: {start} to {end}")

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
    return response

def strip_non_ascii(text):
    return ''.join(c for c in text if ord(c) < 128)

# =====





def verify_payment_by_reference(reference: str) -> Payment:
    """Check payment by reference, mark paid if not paid, and return Payment instance."""
    try:
        payment = Payment.objects.get(pay_code=reference)
    except Payment.DoesNotExist:
        raise ValueError("Payment not found")

    # Here you can add real verification with Paystack or Flutterwave if needed
    # For now, it just marks as successful if not paid
    if payment.status != "paid":
        payment.mark_as_successful()  # ensure this method updates payment & job status properly
        payment.save()

    return payment




# def verify_payment_by_reference(reference: str) -> Payment:
#     payment = Payment.objects.get(pay_code=reference)

#     # Only auto-mark successful if verified externally
#     if payment.status != "paid" and external_payment_is_confirmed(reference):
#         payment.mark_as_successful()
#         payment.save()

#     return payment




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






@payments_router.post("/payments", response={200: dict, 400: dict, 500: dict}, summary="Initiate payment", auth=None)
def initiate_payment(request, payload: InitiatePaymentSchema):
    # 1. Validate payment method
    if payload.payment_method not in ("paystack", "flutterwave"):
        raise HttpError(400, f"Unsupported payment method: {payload.payment_method}")

    # 2. Calculate amounts
    try:
        total = Decimal(str(payload.total))
    except InvalidOperation:
        raise HttpError(400, "Invalid amount format")
    service_fee = (total * Decimal("0.10")).quantize(Decimal("0.00"))
    final_amount = (total + service_fee).quantize(Decimal("0.00"))

    # 3. Load user & job
    user = get_object_or_404(User, id=payload.user_id)
    job = get_object_or_404(Job, id=payload.job_id) if payload.job_id else None

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


    # try:
    #     verify_payment_by_reference(payment.pay_code)
    # except Exception as e:
    #     print(f"Error verifying payment status: {e}")


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
        "callback_url": f"{settings.FRONTEND_URL}/dashboard/",
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
        "redirect_url": f"{getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')}/dashboard/",
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

@payments_router.post("/webhook/flutterwave/")
def flutterwave_webhook(request):
    secret = settings.FLUTTERWAVE_SECRET_KEY.encode('utf-8')
    signature = request.headers.get('x-flutterwave-signature')

    if not signature:
        logger.warning("Missing Flutterwave webhook signature")
        return HttpResponse(status=400)

    body = request.body
    # Flutterwave signature verification logic (if required)
    # computed_signature = ...
    # if not hmac.compare_digest(computed_signature, signature):
    #     logger.warning("Invalid Flutterwave webhook signature")
    #     return HttpResponse(status=400)

    try:
        event = request.json()
    except Exception as e:
        logger.error(f"Failed to parse webhook JSON: {e}")
        return HttpResponse(status=400)

    if event.get("event") == "charge.completed":
        reference = event["data"].get("tx_ref")
        if not reference:
            logger.warning("No tx_ref in Flutterwave webhook data")
            return HttpResponse(status=400)

        try:
            verify_payment_status.delay(reference)
            logger.info(f"Triggered Celery verification task for Flutterwave payment: {reference}")
        except Exception as e:
            logger.error(f"Failed to trigger Celery task: {e}")
            return HttpResponse(status=500)

    return HttpResponse(status=200)


@payments_router.post("/webhook/paystack/")
def paystack_webhook(request):
    secret = settings.PAYSTACK_SECRET_KEY.encode('utf-8')
    signature = request.headers.get('x-paystack-signature')

    if not signature:
        logger.warning("Missing Paystack webhook signature")
        return HttpResponse(status=400)

    body = request.body
    computed_signature = hmac.new(secret, body, hashlib.sha512).hexdigest()
    if not hmac.compare_digest(computed_signature, signature):
        logger.warning("Invalid Paystack webhook signature")
        return HttpResponse(status=400)

    try:
        event = request.json()
    except Exception as e:
        logger.error(f"Failed to parse webhook JSON: {e}")
        return HttpResponse(status=400)

    if event.get("event") == "charge.success":
        reference = event["data"].get("reference")
        if not reference:
            logger.warning("No reference in Paystack webhook data")
            return HttpResponse(status=400)

        try:
            # Call Celery async task
            verify_payment_status.delay(reference)
            logger.info(f"Triggered Celery verification task for payment: {reference}")
        except Exception as e:
            logger.error(f"Failed to trigger Celery task: {e}")
            return HttpResponse(status=500)

    return HttpResponse(status=200)


# ==
# 📌 Payment Verification Endpoint
# ==
# @payments_router.post("/payments/verify", response={200: PaymentResponseSchema, 404: dict, 500: dict})
# def verify_payment(request, payload: VerifyPaymentSchema):
#     try:
#         payment = verify_payment_by_reference(payload.reference)
#     except ValueError:
#         return 404, {"detail": "Payment not found"}

#     return {
#         "id": payment.id,
#         "reference": payment.pay_code,
#         "amount": float(payment.original_amount),
#         "service_fee": float(payment.service_fee),
#         "final_amount": float(payment.final_amount),
#         "status": payment.status,
#         "user_id": payment.payer.id,
#         "payment_method": payment.payment_method,
#         "created_at": payment.created_at.isoformat(),
#         "verified_at": payment.verified_at.isoformat() if payment.verified_at else None,
#         "recipient": payment.recipient.email if payment.recipient else None,
#         "job_id": payment.job.id if payment.job else None,
#         "job_title": payment.job.title if payment.job else None,
#     }


# @payments_router.post("/payments/verify", response={200: PaymentResponseSchema, 404: dict, 500: dict})
# def verify_payment(request, payload: VerifyPaymentSchema):
#     """
#     Verify payment reference without updating job status.
#     This endpoint is used by the frontend to check payment progress.
#     """
#     try:
#         # Fetch payment record
#         payment = Payment.objects.filter(pay_code=payload.reference).first()
#         if not payment:
#             return 404, {"detail": "Payment not found"}

#         # Optionally check gateway for live status
#         # (non-mutating)
#         from payment.services import PaystackService, FlutterwaveService

#         if payment.payment_method == "paystack":
#             service = PaystackService()
#             gateway_status = service.verify_payment(payment.pay_code)
#         elif payment.payment_method == "flutterwave":
#             service = FlutterwaveService()
#             gateway_status = service.verify_payment(payment.pay_code)
#         else:
#             gateway_status = {"status": "unknown"}

#         # Don't mark as successful — only report what gateway says
#         return {
#             "id": payment.id,
#             "reference": payment.pay_code,
#             "amount": float(payment.original_amount),
#             "service_fee": float(payment.service_fee),
#             "final_amount": float(payment.final_amount),
#             "status": payment.status,  # current DB status
#             "gateway_status": gateway_status.get("status"),
#             "user_id": payment.payer.id,
#             "payment_method": payment.payment_method,
#             "created_at": payment.created_at.isoformat(),
#             "verified_at": payment.verified_at.isoformat() if payment.verified_at else None,
#             "recipient": payment.recipient.email if payment.recipient else None,
#             "job_id": payment.job.id if payment.job else None,
#             "job_title": payment.job.title if payment.job else None,
#         }

#     except Exception as e:
#         return 500, {"detail": str(e)}


# payments/api.py

from .services import verify_payment_by_reference


@payments_router.post("/payments/verify", response={200: PaymentResponseSchema, 404: dict, 500: dict})
def verify_payment(request, payload: VerifyPaymentSchema):
    try:
        payment = verify_payment_by_reference(payload.reference)
    except ValueError:
        return 404, {"detail": "Payment not found"}

    return {
        "id": payment.id,
        "reference": payment.pay_code,
        "amount": float(payment.original_amount),
        "service_fee": float(payment.service_fee),
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
        payment_data = []
        for payment in payments:
            payment_data.append({
                "id": payment.id,
                "reference": payment.pay_code,
                "amount": float(payment.original_amount),
                "service_fee": float(payment.service_fee),
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

@payments_router.post("/initialize", response={200: dict}, tags=["Payment"])
def initialize_payment_view(request, payload: PaymentInitSchema):
    try:
        from .utils import initialize_payment
        
        if not request.user.is_authenticated:
            return {"status": "error", "message": "User not authenticated"}, 401

        result = initialize_payment(
            amount=float(payload.amount),
            email=request.user.email,
            callback_url=payload.callback_url
        )
        
        payment = Payment.objects.create(
            user=request.user,
            amount=Decimal(str(payload.amount)),
            reference=result.get('data', {}).get('reference', ''),
            payment_type='flutterwave',
            status='pending'
        )

        return {
            "status": "success",
            "data": {
                "payment_id": payment.id,
                "authorization_url": result.get('data', {}).get('authorization_url'),
                "reference": payment.reference
            }
        }
        
    except Exception as e:
        logger.error(f"Payment initialization failed: {str(e)}")
        return {"status": "error", "message": str(e)}, 400









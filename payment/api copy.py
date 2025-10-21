# == Python Standard Library ==
import logging
import uuid
import hmac
import hashlib
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Optional

# == Django & Third-Party ==
import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.http import HttpResponse
from ninja import Router
from ninja.errors import HttpError

# == Local Imports ==
from accounts.models import CustomUser as User, Profile
from .models import Payment, Wallet, Transaction
from jobs.models import Job
from .schemas import *
from .tasks import verify_payment_status
from django_q.tasks import schedule

# == Setup ==
logger = logging.getLogger(__name__)
payments_router = Router(tags=["Payments"])


# ============================================================
# 📌 Utility Functions
# ============================================================
def _get_time_range(filter: str) -> tuple[datetime, Optional[datetime]]:
    """Return date ranges for filters like today, this_week, etc."""
    now = timezone.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    first_day_of_month = today.replace(day=1)

    first_day_of_last_month = (
        first_day_of_month.replace(year=first_day_of_month.year - 1, month=12)
        if first_day_of_month.month == 1
        else first_day_of_month.replace(month=first_day_of_month.month - 1)
    )

    first_day_of_year = today.replace(month=1, day=1)
    first_day_of_last_year = first_day_of_year.replace(year=first_day_of_year.year - 1)

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


def strip_non_ascii(text: str) -> str:
    """Remove non-ASCII characters (useful for email/username sanitization)."""
    return "".join(c for c in text if ord(c) < 128)


# ============================================================
# 📌 Wallet Endpoints
# ============================================================
@payments_router.get(
    "/users/{user_id}/wallet/transactions",
    response={200: dict, 404: dict},
    summary="List wallet transactions",
    description="Retrieve wallet transactions with optional time filtering",
)
def list_wallet_transactions(request, user_id: int, filter: str = "all", limit: int = 100, offset: int = 0):
    """Retrieve paginated wallet transactions for a user."""
    try:
        user = get_object_or_404(User, id=user_id)
        wallet, _ = Wallet.objects.get_or_create(user=user, defaults={"balance": Decimal("0.00")})

        transactions = Transaction.objects.filter(wallet=wallet).order_by("-created_at")

        # Apply filter
        if filter != "all":
            start, end = _get_time_range(filter)
            if start:
                if end:
                    transactions = transactions.filter(created_at__range=(start, end))
                else:
                    transactions = transactions.filter(created_at__gte=start)

        total_count = transactions.count()
        paginated = transactions[offset:offset + limit]

        return {
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
                        "status": t.status,
                        "reference": t.reference,
                        "description": t.description,
                        "created_at": t.created_at.isoformat(),
                    }
                    for t in paginated
                ],
            },
        }

    except Exception as e:
        logger.error(f"Error retrieving wallet transactions: {e}", exc_info=True)
        return {"status": "error", "message": f"An error occurred: {str(e)}"}


@payments_router.post(
    "/users/wallet/withdraw",
    response={200: dict, 400: dict, 404: dict, 500: dict},
    summary="Withdraw funds from wallet",
)
def withdraw_funds(request, payload: WalletWithdrawSchema):
    """Withdraw funds from a user's wallet."""
    try:
        if payload.amount <= 0:
            return 400, {"status": "error", "message": "Amount must be positive"}

        user = get_object_or_404(User, id=payload.user_id)
        wallet, _ = Wallet.objects.get_or_create(user=user)

        if wallet.balance < payload.amount:
            return 400, {
                "status": "error",
                "message": "Insufficient funds",
                "data": {"wallet_balance": str(wallet.balance), "requested_amount": str(payload.amount)},
            }

        with transaction.atomic():
            wallet.deduct_funds(payload.amount)
            txn = Transaction.objects.create(
                wallet=wallet,
                amount=payload.amount,
                transaction_type=Transaction.Type.DEBIT,
                status=Transaction.Status.COMPLETED,
                reference=Transaction.generate_reference(),
                description="Wallet withdrawal",
                metadata={"user_id": user.id, "withdrawal_method": "bank_transfer"},
            )

        return {
            "status": "success",
            "message": "Withdrawal successful",
            "data": {
                "transaction_id": txn.id,
                "reference": txn.reference,
                "amount": str(txn.amount),
                "new_balance": str(wallet.balance),
                "transaction_date": txn.created_at.isoformat(),
            },
        }

    except Exception as e:
        logger.error(f"Withdrawal error: {e}", exc_info=True)
        return 500, {"status": "error", "message": str(e)}


# ============================================================
# 📌 Payment Processing
# ============================================================
def verify_payment_by_reference(reference: str) -> Payment:
    """Fetch payment by reference and mark as successful if not yet paid."""
    try:
        payment = Payment.objects.get(pay_code=reference)
    except Payment.DoesNotExist:
        raise ValueError("Payment not found")

    if payment.status != "paid":
        payment.mark_as_successful()
        payment.save()

    return payment


@payments_router.post("/payments", response={200: dict, 400: dict, 500: dict}, summary="Initiate payment")
def initiate_payment(request, payload: InitiatePaymentSchema):
    """Initialize a payment session for Paystack or Flutterwave."""
    if payload.payment_method not in ("paystack", "flutterwave"):
        raise HttpError(400, f"Unsupported payment method: {payload.payment_method}")

    try:
        total = Decimal(str(payload.total))
    except InvalidOperation:
        raise HttpError(400, "Invalid amount format")

    service_fee = (total * Decimal("0.10")).quantize(Decimal("0.00"))
    final_amount = (total + service_fee).quantize(Decimal("0.00"))
    user = get_object_or_404(User, id=payload.user_id)
    job = get_object_or_404(Job, id=payload.job_id) if payload.job_id else None

    with transaction.atomic():
        payment = Payment.objects.create(
            payer=user,
            job=job,
            recipient=job.selected_applicant if job else None,
            original_amount=total,
            service_fee=service_fee,
            final_amount=final_amount,
            pay_code=str(uuid.uuid4()),
            payment_method=payload.payment_method,
            status="pending",
        )

    try:
        auth_url = (
            _process_paystack(payment, payload)
            if payload.payment_method == "paystack"
            else _process_flutterwave(payment, payload)
        )
    except Exception as e:
        logger.error(f"Payment processing failed: {e}", exc_info=True)
        payment.status = "failed"
        payment.save(update_fields=["status"])
        raise HttpError(400, f"Payment processing failed: {e}")

    return {
        "status": "success",
        "message": "Payment initiated successfully",
        "data": {
            "payment_id": payment.id,
            "authorization_url": auth_url,
            "expires_at": (timezone.now() + timedelta(minutes=30)).isoformat(),
            "original_amount": float(total),
            "service_fee": float(service_fee),
            "reference": payment.pay_code,
            "final_amount": float(final_amount),
        },
    }


def _process_paystack(payment: Payment, payload: InitiatePaymentSchema) -> str:
    """Initialize Paystack transaction."""
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "reference": payment.pay_code,
        "email": f"{strip_non_ascii(payload.first_name.lower())}@user.com",
        "amount": int(payment.original_amount * 100),
        "callback_url": f"{settings.FRONTEND_URL}/dashboard/",
        "metadata": {"payment_id": payment.id, "user_id": payment.payer.id},
    }

    resp = requests.post("https://api.paystack.co/transaction/initialize", headers=headers, json=data, timeout=10)
    resp.raise_for_status()
    result = resp.json()

    if not result.get("status") or not result["data"].get("authorization_url"):
        raise RuntimeError(f"Paystack error: {result.get('message') or repr(result)}")

    return result["data"]["authorization_url"]


def _process_flutterwave(payment: Payment, payload: InitiatePaymentSchema) -> str:
    """Initialize Flutterwave transaction."""
    headers = {
        "Authorization": f"Bearer {settings.FLUTTERWAVE_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "tx_ref": payment.pay_code,
        "amount": str(payment.original_amount),
        "currency": "NGN",
        "redirect_url": f"{settings.FRONTEND_URL}/dashboard/",
        "payment_options": "card",
        "customer": {
            "email": f"{payload.first_name.lower()}@user.com",
            "name": f"{payload.first_name} {payload.last_name}",
            "phonenumber": payload.phone,
        },
        "customizations": {"title": "Payshift Payment", "description": "Payment for service"},
        "meta": {"payment_id": payment.id, "user_id": payment.payer.id},
    }

    response = requests.post("https://api.flutterwave.com/v3/payments", headers=headers, json=data, timeout=10)
    response.raise_for_status()
    result = response.json()

    if result.get("status") != "success" or not result["data"].get("link"):
        raise ValueError(result.get("message", "Flutterwave processing failed"))

    return result["data"]["link"]


# ============================================================
# 📌 Webhooks
# ============================================================
@payments_router.post("/webhook/paystack/")
def paystack_webhook(request):
    """Handle Paystack webhook events."""
    secret = settings.PAYSTACK_SECRET_KEY.encode("utf-8")
    signature = request.headers.get("x-paystack-signature")
    body = request.body

    computed_signature = hmac.new(secret, body, hashlib.sha512).hexdigest()
    if not hmac.compare_digest(computed_signature, signature or ""):
        logger.warning("Invalid Paystack webhook signature")
        return HttpResponse(status=400)

    try:
        event = request.json()
        if event.get("event") == "charge.success":
            reference = event["data"].get("reference")
            verify_payment_status.delay(reference)
    except Exception as e:
        logger.error(f"Paystack webhook error: {e}")
        return HttpResponse(status=400)

    return HttpResponse(status=200)

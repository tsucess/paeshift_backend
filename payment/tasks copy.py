import logging
from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from jobs.models import Job
from notifications.models import Notification
from .models import Payment
from .services import FlutterwaveService, PaystackService

logger = logging.getLogger(__name__)

@shared_task(
    name="payment.tasks.process_payment_webhook",
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def process_payment_webhook(reference, payment_method, status, raw_data):
    """
    Process payment webhook notification.

    Args:
        reference (str): Payment reference/code
        payment_method (str): 'paystack' or 'flutterwave'
        status (str): Payment status from webhook
        raw_data (dict): Complete webhook payload

    Returns:
        dict: Processing result
    """
    try:
        payment = Payment.objects.get(pay_code=reference)
    except Payment.DoesNotExist:
        logger.error(f"Payment with reference {reference} not found")
        return {"status": "error", "message": "Payment not found"}

    if payment.status in ["Completed", "Failed", "Refunded"]:
        logger.info(f"Payment {reference} already in final state: {payment.status}")
        return {"status": "skipped", "message": f"Payment {reference} already in state {payment.status}"}

    service = None
    if payment_method.lower() == "paystack":
        service = PaystackService()
    elif payment_method.lower() == "flutterwave":
        service = FlutterwaveService()
    else:
        logger.error(f"Invalid payment method: {payment_method}")
        return {"status": "error", "message": "Invalid payment method"}

    verification_result = service.verify_payment(reference)

    try:
        with transaction.atomic():
            if status.lower() == "success" and verification_result.get("status") == "success":
                payment.status = "Completed"
                payment.save(update_fields=["status"])

                if payment.job:
                    job = payment.job
                    job.payment_status = "paid"
                    job.save(update_fields=["payment_status"])

                Notification.objects.create(
                    user=payment.payer,
                    message=f"Your payment of {payment.original_amount} was successful.",
                    category="payment",
                )

                cache.delete(f"payment_{payment.id}")

                logger.info(f"Payment {reference} marked as completed")
                return {"status": "success", "message": "Payment completed"}

            else:
                payment.status = "Failed"
                payment.save(update_fields=["status"])

                Notification.objects.create(
                    user=payment.payer,
                    message=f"Your payment of {payment.original_amount} failed. Please try again.",
                    category="payment",
                )

                logger.warning(f"Payment {reference} marked as failed")
                return {"status": "failed", "message": "Payment failed"}

    except Exception as e:
        logger.exception(f"Error updating payment status for {reference}: {e}")
        raise e


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def verify_payment_status(self, reference):
    """
    Verify the payment status asynchronously and update if necessary.
    """
    try:
        payment = Payment.objects.get(pay_code=reference)
    except Payment.DoesNotExist:
        logger.error(f"Payment not found: {reference}")
        return

    if payment.status != "paid":
        try:
            payment.mark_as_successful()
            payment.verified_at = timezone.now()
            payment.save(update_fields=["status", "verified_at"])
            logger.info(f"Payment marked successful: {reference}")
        except Exception as e:
            logger.error(f"Error marking payment successful: {e}")
            raise self.retry(exc=e)
    else:
        logger.info(f"Payment already paid: {reference}")



def process_payment_webhook_q(reference, payment_method, status, raw_data):
    """
    Django Q fallback for processing payment webhooks.

    Args:
        reference (str): Payment reference/code
        payment_method (str): 'paystack' or 'flutterwave'
        status (str): Payment status from webhook
        raw_data (dict): Raw webhook payload

    Returns:
        dict: Processing result
    """
    try:
        payment = Payment.objects.get(pay_code=reference)
    except Payment.DoesNotExist:
        logger.error(f"[Django Q] Payment with reference {reference} not found")
        return {"status": "error", "message": "Payment not found"}

    if payment.status in ["Completed", "Failed", "Refunded"]:
        logger.info(f"[Django Q] Payment {reference} already in final state: {payment.status}")
        return {"status": "skipped", "message": f"Payment {reference} already in state {payment.status}"}

    service = None
    if payment_method.lower() == "paystack":
        service = PaystackService()
    elif payment_method.lower() == "flutterwave":
        service = FlutterwaveService()
    else:
        logger.error(f"[Django Q] Invalid payment method: {payment_method}")
        return {"status": "error", "message": "Invalid payment method"}

    verification_result = service.verify_payment(reference)

    with transaction.atomic():
        if status.lower() == "success" and verification_result.get("status") == "success":
            payment.status = "Completed"
            payment.save()

            if payment.job:
                job = payment.job
                job.payment_status = "paid"
                job.save()

            Notification.objects.create(
                user=payment.payer,
                message=f"Your payment of {payment.original_amount} was successful.",
                category="payment",
            )

            cache.delete(f"payment_{payment.id}")

            try:
                async_task(
                    "payment.tasks.update_payment_related_data",
                    payment.id,
                    task_name=f"update_payment_data_{payment.id}",
                    group="payment_processing",
                )
                logger.info(f"Queued payment data update task for payment {payment.id}")
            except Exception as e:
                logger.error(f"Failed to queue payment data update task: {e}")

            logger.info(f"[Django Q] Payment {reference} marked as completed")
            return {"status": "success", "message": "Payment completed"}

        else:
            payment.status = "Failed"
            payment.save()

            Notification.objects.create(
                user=payment.payer,
                message=f"Your payment of {payment.original_amount} failed. Please try again.",
                category="payment",
            )

            logger.warning(f"[Django Q] Payment {reference} marked as failed")
            return {"status": "failed", "message": "Payment failed"}



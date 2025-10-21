import logging
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

User = get_user_model()  # Default Django User model
from jobs.models import *

from .models import Payment, Wallet, Transaction

logger = logging.getLogger(__name__)

# In payments/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Payment
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Payment)
def update_job_status(sender, instance, created, **kwargs):
    """
    Update job status when payment is marked as paid
    """
    if instance.status == 'paid' and instance.job:
        job = instance.job
        try:
            with transaction.atomic():
                # Refresh the job to get latest state
                job.refresh_from_db()
                
                # Only update if payment_status isn't already PAID
                if job.payment_status != Job.PaymentStatus.PAID:
                    update_fields = ['payment_status']
                    if job.status == Job.Status.PENDING:
                        job.status = Job.Status.UPCOMING
                        update_fields.append('status')
                    
                    job.payment_status = Job.PaymentStatus.PAID
                    job.save(update_fields=update_fields)
                    
        except Exception as e:
            logger.error(f"Failed to update job status: {str(e)}")
            
@receiver(post_save, sender=Payment)
def payment_post_save(sender, instance, created, **kwargs):
    """
    Handle payment post-save operations.

    This signal handler:
    1. Caches payment data with short timeout
    2. Logs payment status changes
    3. Invalidates related caches
    """
    from payment.redis_cache import cache_payment, log_payment_status_change

    # Cache payment data (short timeout)
    payment_data = instance.to_dict()
    cache_payment(payment_data, timeout=60*15)  # 15 minutes

    # Log detailed payment information
    logger.info(
        f"Payment {instance.pay_code} saved: {instance.status}, "
        f"Amount: {instance.original_amount}, Method: {instance.payment_method}"
    )

    # If this is an update (not a new payment), check for status changes
    if not created and hasattr(instance, '_original_status') and instance._original_status != instance.status:
        # Log status change
        log_payment_status_change(
            instance.id,
            instance._original_status,
            instance.status,
            {
                "pay_code": instance.pay_code,
                "payment_method": instance.payment_method,
                "amount": str(instance.original_amount),
            }
        )


@receiver(pre_save, sender=Payment)
def payment_pre_save(sender, instance, **kwargs):
    """
    Handle payment pre-save operations.

    This signal handler:
    1. Stores the original status for comparison after save
    2. Logs payment status changes
    """
    # Store original status if this is an existing payment
    if instance.pk:
        try:
            original = Payment.objects.get(pk=instance.pk)
            instance._original_status = original.status
        except Payment.DoesNotExist:
            instance._original_status = None
    else:
        instance._original_status = None


@receiver(pre_save, sender=Wallet)
def wallet_pre_save(sender, instance, **kwargs):
    """
    Store original balance for comparison after save.
    """
    # Store original balance if this is an existing wallet
    if instance.pk:
        try:
            original = Wallet.objects.get(pk=instance.pk)
            instance._original_balance = original.balance
        except Wallet.DoesNotExist:
            instance._original_balance = None
    else:
        instance._original_balance = None


@receiver(post_save, sender=Wallet)
def wallet_post_save(sender, instance, created, **kwargs):
    """
    Handle wallet post-save operations.

    This signal handler:
    1. Invalidates user-related caches when wallet balance changes
    2. Logs wallet balance changes
    """
    # Check if balance has changed
    balance_changed = (
        hasattr(instance, '_original_balance') and
        instance._original_balance is not None and
        instance._original_balance != instance.balance
    )

    # If this is a new wallet or the balance has changed
    if created or balance_changed:
        # Invalidate user-related caches
        cache_keys = [
            f"user:{instance.user.id}",
            f"profile:{instance.user.id}",
            f"whoami:{instance.user.id}",
            f"hibernate:get_hibernated_user_response_by_id:{instance.user.id}",
        ]

        for key in cache_keys:
            cache.delete(key)

        # Log the balance change
        if balance_changed:
            logger.info(
                f"Wallet balance changed for user {instance.user.id}: "
                f"{instance._original_balance} -> {instance.balance}"
            )
        elif created:
            logger.info(f"New wallet created for user {instance.user.id} with balance {instance.balance}")


@receiver(post_save, sender=User)
def create_user_wallet(sender, instance, created, **kwargs):
    """
    Automatically create a wallet for each new user.
    """
    if created:
        try:
            Wallet.objects.get_or_create(user=instance)
            logger.info(f"Wallet created for new user {instance.id}")
        except Exception as e:
            logger.error(f"Failed to create wallet for user {instance.id}: {e}")


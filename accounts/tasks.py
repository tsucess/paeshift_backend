"""
Celery tasks for account management.

This module contains tasks for:
- Cleaning up expired OTPs
- Monitoring failed login attempts
- Other account-related background tasks
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone
from django.conf import settings

from .models import OTP

logger = logging.getLogger(__name__)


@shared_task(
    name="accounts.tasks.cleanup_expired_otps",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def cleanup_expired_otps(self):
    """
    Delete expired OTPs from the database.

    This task should be scheduled to run periodically to clean up
    expired OTPs and prevent database bloat.
    """
    try:
        # Use the model's cleanup method
        deleted_count, _ = OTP.cleanup_expired_otps()

        logger.info(f"Cleaned up {deleted_count} expired OTPs")
        return {"status": "success", "deleted_count": deleted_count}

    except Exception as e:
        logger.error(f"Error cleaning up expired OTPs: {str(e)}")
        # Retry the task with exponential backoff
        self.retry(exc=e)
        return {"status": "error", "message": str(e)}


@shared_task(
    name="accounts.tasks.cleanup_verified_otps",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def cleanup_verified_otps(self):
    """
    Delete OTPs that have been successfully verified.

    This task removes OTPs that have been successfully used,
    as they are no longer needed.
    """
    try:
        # Delete verified OTPs
        deleted_count, _ = OTP.objects.filter(is_verified=True).delete()

        logger.info(f"Cleaned up {deleted_count} verified OTPs")
        return {"status": "success", "deleted_count": deleted_count}

    except Exception as e:
        logger.error(f"Error cleaning up verified OTPs: {str(e)}")
        # Retry the task with exponential backoff
        self.retry(exc=e)
        return {"status": "error", "message": str(e)}


@shared_task(
    name="accounts.tasks.cleanup_old_otps",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def cleanup_old_otps(self, days=7):
    """
    Delete all OTPs older than the specified number of days.

    This task performs a more aggressive cleanup of old OTPs,
    regardless of their status.

    Args:
        days: Number of days to keep OTPs (default: 7)
    """
    try:
        # Calculate cutoff date
        cutoff_date = timezone.now() - timedelta(days=days)

        # Delete old OTPs
        deleted_count, _ = OTP.objects.filter(created_at__lt=cutoff_date).delete()

        logger.info(f"Cleaned up {deleted_count} OTPs older than {days} days")
        return {"status": "success", "deleted_count": deleted_count}

    except Exception as e:
        logger.error(f"Error cleaning up old OTPs: {str(e)}")
        # Retry the task with exponential backoff
        self.retry(exc=e)
        return {"status": "error", "message": str(e)}
"""
Celery tasks for account management.

This module contains tasks for:
- Cleaning up expired OTPs
- Monitoring failed login attempts
- Sending OTP emails asynchronously
- Other account-related background tasks
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model

from .models import OTP

logger = logging.getLogger(__name__)
User = get_user_model()


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


@shared_task(
    name="accounts.tasks.send_otp_email_async",
    bind=True,
    max_retries=2,
    default_retry_delay=5,
    acks_late=True,
)
def send_otp_email_async(self, user_id, otp_code):
    """
    Send OTP email asynchronously to a registered user.

    This task runs in the background and doesn't block the signup request.

    Args:
        user_id: ID of the user to send OTP to
        otp_code: The OTP code to send
    """
    try:
        from .utils import send_otp_email

        user = User.objects.get(id=user_id)
        logger.info(f"[ASYNC] Sending OTP email to {user.email}")

        result = send_otp_email(user, otp_code)

        if result:
            logger.info(f"[ASYNC] OTP email sent successfully to {user.email}")
            return {"status": "success", "email": user.email}
        else:
            logger.warning(f"[ASYNC] Failed to send OTP email to {user.email}")
            return {"status": "failed", "email": user.email}

    except User.DoesNotExist:
        logger.error(f"[ASYNC] User with ID {user_id} not found")
        return {"status": "error", "message": "User not found"}
    except Exception as e:
        logger.error(f"[ASYNC] Error sending OTP email: {str(e)}")
        # Retry with exponential backoff
        self.retry(exc=e)


@shared_task(
    name="accounts.tasks.send_registration_otp_email_async",
    bind=True,
    max_retries=2,
    default_retry_delay=5,
    acks_late=True,
)
def send_registration_otp_email_async(self, email, otp_code):
    """
    Send OTP email asynchronously to a non-user (during registration).

    This task runs in the background and doesn't block the signup request.

    Args:
        email: Email address to send OTP to
        otp_code: The OTP code to send
    """
    try:
        from .utils import send_mail_to_nonuser

        logger.info(f"[ASYNC] Sending registration OTP email to {email}")

        result = send_mail_to_nonuser(email, otp_code)

        if result:
            logger.info(f"[ASYNC] Registration OTP email sent successfully to {email}")
            return {"status": "success", "email": email}
        else:
            logger.warning(f"[ASYNC] Failed to send registration OTP email to {email}")
            return {"status": "failed", "email": email}

    except Exception as e:
        logger.error(f"[ASYNC] Error sending registration OTP email: {str(e)}")
        # Retry with exponential backoff
        self.retry(exc=e)


@shared_task(
    name="accounts.tasks.handle_new_user_notifications_async",
    bind=True,
    max_retries=2,
    default_retry_delay=5,
    acks_late=True,
)
def handle_new_user_notifications_async(self, user_id):
    """
    Create notifications for new user signup asynchronously.

    This task:
    1. Creates a welcome notification for the new user
    2. Creates notifications for all admin users

    This runs in the background and doesn't block the signup request.

    Args:
        user_id: ID of the newly created user
    """
    try:
        from notifications.models import Notification
        from django.db import transaction

        user = User.objects.get(id=user_id)
        logger.info(f"[ASYNC] Creating notifications for new user {user.email}")

        with transaction.atomic():
            # Create welcome notification for the user
            Notification.objects.create(
                user=user,
                title="[SUCCESS] Welcome Aboard!",
                message=f"Hi {user.get_full_name()}, we're thrilled you're here! Complete your profile to unlock all features.",
                notification_type="account_welcome",
                importance="high"
            )
            logger.info(f"[ASYNC] Created welcome notification for {user.email}")

            # Create notifications for all admins (using bulk_create for efficiency)
            admins = User.objects.filter(is_staff=True)
            admin_notifications = [
                Notification(
                    user=admin,
                    title="[INFO] New User Joined",
                    message=f"A new user, {user.get_full_name()} ({user.email}), just signed up!",
                    notification_type="admin_new_user",
                    importance="medium"
                )
                for admin in admins
            ]

            if admin_notifications:
                Notification.objects.bulk_create(admin_notifications)
                logger.info(f"[ASYNC] Created {len(admin_notifications)} admin notifications for new user {user.email}")

        return {"status": "success", "user_id": user_id}

    except User.DoesNotExist:
        logger.error(f"[ASYNC] User with ID {user_id} not found")
        return {"status": "error", "message": "User not found"}
    except Exception as e:
        logger.error(f"[ASYNC] Error creating notifications for user {user_id}: {str(e)}")
        # Retry with exponential backoff
        self.retry(exc=e)
        # Retry the task with exponential backoff
        self.retry(exc=e)
        return {"status": "error", "message": str(e)}
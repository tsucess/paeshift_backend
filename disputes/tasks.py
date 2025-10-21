"""
Celery tasks for dispute management.

This module contains tasks for:
- Assigning disputes to admins based on workload
- Sending notifications about dispute status changes
- Generating dispute reports
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from adminaccess.models import AdminProfile
from disputes.models import Dispute

User = get_user_model()
logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
    name="disputes.tasks.assign_dispute_to_admin",
)
def assign_dispute_to_admin(self, dispute_id):
    """
    Assign a dispute to the admin with the lowest current workload.

    Args:
        dispute_id: ID of the dispute to assign

    Returns:
        Dictionary with assignment result information
    """
    try:
        # Get the dispute
        try:
            dispute = Dispute.objects.get(id=dispute_id)
        except Dispute.DoesNotExist:
            logger.error(f"Dispute with ID {dispute_id} not found")
            return {
                "status": "error",
                "message": f"Dispute with ID {dispute_id} not found",
            }

        # Check if dispute is already assigned
        if dispute.status != Dispute.Status.OPEN:
            logger.info(
                f"Dispute {dispute_id} is already in status {dispute.status}, not assigning"
            )
            return {
                "status": "skipped",
                "message": f"Dispute already in status {dispute.status}",
                "dispute_id": dispute_id,
            }

        # Find available admins
        admin_profiles = AdminProfile.objects.filter(
            is_available=True, user__is_active=True
        ).select_related("user")

        if not admin_profiles.exists():
            logger.warning("No available admins found for dispute assignment")
            return {"status": "error", "message": "No available admins found"}

        # Find admin with lowest current dispute count
        admin_profile = admin_profiles.order_by("current_dispute_count").first()

        # Assign the dispute
        with transaction.atomic():
            # Lock the admin profile for update
            admin_profile = AdminProfile.objects.select_for_update().get(
                id=admin_profile.id
            )

            # Update the dispute
            dispute.assigned_admin = admin_profile.user
            dispute.status = Dispute.Status.ASSIGNED
            dispute.save(update_fields=["assigned_admin", "status"])

            # Update admin's dispute count
            admin_profile.increment_dispute_count()

        logger.info(
            f"Dispute {dispute_id} assigned to admin {admin_profile.user.username}"
        )

        return {
            "status": "success",
            "message": f"Dispute assigned to {admin_profile.user.username}",
            "dispute_id": dispute_id,
            "admin_id": admin_profile.user.id,
            "admin_username": admin_profile.user.username,
            "admin_dispute_count": admin_profile.current_dispute_count,
        }
    except Exception as exc:
        logger.exception(f"Error assigning dispute {dispute_id}: {str(exc)}")
        raise self.retry(exc=exc)


@shared_task(name="disputes.tasks.check_unassigned_disputes")
def check_unassigned_disputes():
    """
    Check for unassigned disputes and trigger assignment tasks.

    This task is meant to be run periodically to ensure no disputes
    remain unassigned.
    """
    # Find open disputes
    open_disputes = Dispute.objects.filter(
        status=Dispute.Status.OPEN, assigned_admin__isnull=True
    )

    count = open_disputes.count()
    if count == 0:
        logger.info("No unassigned disputes found")
        return {"status": "success", "message": "No unassigned disputes found"}

    # Assign each dispute
    for dispute in open_disputes:
        assign_dispute_to_admin.delay(dispute.id)

    logger.info(f"Triggered assignment for {count} unassigned disputes")
    return {
        "status": "success",
        "message": f"Triggered assignment for {count} unassigned disputes",
    }


@shared_task(name="disputes.tasks.update_dispute_metrics")
def update_dispute_metrics():
    """
    Update metrics for dispute resolution performance.

    This task calculates and updates:
    - Average resolution time
    - Resolution rate
    - Admin performance metrics
    """
    # Get resolved disputes in the last 30 days
    thirty_days_ago = timezone.now() - timedelta(days=30)
    resolved_disputes = Dispute.objects.filter(
        status=Dispute.Status.RESOLVED, resolved_at__gte=thirty_days_ago
    )

    # Calculate metrics for each admin
    admin_metrics = {}
    for dispute in resolved_disputes:
        if not dispute.resolved_by or not dispute.resolved_at or not dispute.created_at:
            continue

        admin_id = dispute.resolved_by.id
        if admin_id not in admin_metrics:
            admin_metrics[admin_id] = {"count": 0, "total_hours": 0}

        # Calculate resolution time in hours
        resolution_time = dispute.resolved_at - dispute.created_at
        hours = resolution_time.total_seconds() / 3600

        admin_metrics[admin_id]["count"] += 1
        admin_metrics[admin_id]["total_hours"] += hours

    # Update admin profiles
    for admin_id, metrics in admin_metrics.items():
        try:
            admin_profile = AdminProfile.objects.get(user_id=admin_id)
            avg_hours = metrics["total_hours"] / metrics["count"]
            admin_profile.update_resolution_time(avg_hours)
            logger.info(
                f"Updated metrics for admin {admin_id}: {avg_hours:.2f} hours avg resolution time"
            )
        except AdminProfile.DoesNotExist:
            logger.warning(f"Admin profile not found for user {admin_id}")

    return {
        "status": "success",
        "message": f"Updated metrics for {len(admin_metrics)} admins",
    }

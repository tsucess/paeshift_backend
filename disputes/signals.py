# disputes/signals.py

import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Dispute
from .tasks import assign_dispute_to_admin

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Dispute)
def handle_dispute_creation(sender, instance, created, **kwargs):
    """
    Handle dispute creation and status changes.

    - When a new dispute is created, trigger the assignment task
    - When a dispute is resolved, update metrics
    """
    # New dispute created
    if created:
        logger.info(f"New dispute created: {instance.id} - {instance.title}")
        # Trigger assignment task
        assign_dispute_to_admin.delay(instance.id)

    # Dispute resolved
    elif instance.status == Dispute.Status.RESOLVED and not instance.resolved_at:
        instance.resolved_at = timezone.now()
        # Use update to avoid triggering this signal again
        Dispute.objects.filter(id=instance.id).update(resolved_at=instance.resolved_at)

        # Update admin metrics if assigned
        if instance.assigned_admin and hasattr(
            instance.assigned_admin, "admin_profile"
        ):
            instance.assigned_admin.admin_profile.decrement_dispute_count()

        logger.info(f"Dispute {instance.id} resolved")


@receiver(pre_save, sender=Dispute)
def handle_dispute_status_change(sender, instance, **kwargs):
    """
    Track dispute status changes.
    """
    if instance.id:
        try:
            old_instance = Dispute.objects.get(id=instance.id)
            if old_instance.status != instance.status:
                logger.info(
                    f"Dispute {instance.id} status changed: {old_instance.status} -> {instance.status}"
                )

                # If newly assigned, ensure resolved_at is None
                if (
                    instance.status == Dispute.Status.ASSIGNED
                    and old_instance.status != Dispute.Status.ASSIGNED
                ):
                    instance.resolved_at = None
        except Dispute.DoesNotExist:
            pass

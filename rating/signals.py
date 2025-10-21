"""
Signal handlers for the rating application.

This module contains Django signal handlers for:
- Triggering sentiment analysis when reviews are created or updated
- Handling gamification events like XP earned, achievements, etc.
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver, Signal

from .models import Review
from .tasks import analyze_review_sentiment

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Review)
def trigger_sentiment_analysis(sender, instance, created, update_fields, **kwargs):
    """
    Trigger sentiment analysis when a review is created or its feedback is updated.

    Args:
        sender: The model class (Review)
        instance: The actual Review instance
        created: Boolean indicating if this is a new instance
        update_fields: List of fields that were updated (None if all fields were updated)
    """
    # Trigger on creation
    if created:
        logger.debug(f"Triggering sentiment analysis for new review {instance.id}")
        analyze_review_sentiment.delay(instance.id)
        return

    # Trigger when feedback is updated
    if update_fields is None or 'feedback' in update_fields:
        if instance.feedback:  # Only analyze if there's feedback to analyze
            logger.debug(f"Triggering sentiment analysis for updated review {instance.id}")
            analyze_review_sentiment.delay(instance.id)


# Define gamification signals
xp_earned = Signal()
achievement_unlocked = Signal()
badge_earned = Signal()
level_up = Signal()

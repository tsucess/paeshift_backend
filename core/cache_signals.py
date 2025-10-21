"""
Cache invalidation signal handlers for Phase 2.2c

Automatically invalidates cache when models are saved or deleted.
"""

import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from core.cache_utils import invalidate_cache

logger = logging.getLogger(__name__)


# ============================================================================
# Review/Rating Cache Invalidation
# ============================================================================

@receiver(post_save, sender='rating.Review')
def invalidate_review_cache_on_save(sender, instance, created, **kwargs):
    """Invalidate review cache when a review is saved"""
    try:
        # Invalidate reviewed user's reviews cache
        invalidate_cache(keys=[
            f"reviews:user:{instance.reviewed_id}:all",
            f"reviews:user:{instance.reviewed_id}:recent",
            f"reviews:user:{instance.reviewed_id}:unread",
        ])
        
        # Invalidate reviewer's reviews cache
        invalidate_cache(keys=[
            f"reviews:reviewer:{instance.reviewer_id}:all",
        ])
        
        logger.debug(f"Invalidated review cache for review {instance.id}")
    except Exception as e:
        logger.error(f"Error invalidating review cache: {str(e)}")


@receiver(post_delete, sender='rating.Review')
def invalidate_review_cache_on_delete(sender, instance, **kwargs):
    """Invalidate review cache when a review is deleted"""
    try:
        # Invalidate reviewed user's reviews cache
        invalidate_cache(keys=[
            f"reviews:user:{instance.reviewed_id}:all",
            f"reviews:user:{instance.reviewed_id}:recent",
            f"reviews:user:{instance.reviewed_id}:unread",
        ])
        
        # Invalidate reviewer's reviews cache
        invalidate_cache(keys=[
            f"reviews:reviewer:{instance.reviewer_id}:all",
        ])
        
        logger.debug(f"Invalidated review cache for deleted review {instance.id}")
    except Exception as e:
        logger.error(f"Error invalidating review cache on delete: {str(e)}")


# ============================================================================
# Payment Cache Invalidation
# ============================================================================

@receiver(post_save, sender='payment.Payment')
def invalidate_payment_cache_on_save(sender, instance, created, **kwargs):
    """Invalidate payment cache when a payment is saved"""
    try:
        # Invalidate payer's payments cache
        invalidate_cache(keys=[
            f"payments:user:{instance.payer_id}:all",
            f"payments:user:{instance.payer_id}:today",
            f"payments:user:{instance.payer_id}:this_week",
            f"payments:user:{instance.payer_id}:this_month",
        ])
        
        # Invalidate recipient's payments cache
        if instance.recipient_id:
            invalidate_cache(keys=[
                f"payments:recipient:{instance.recipient_id}:all",
            ])
        
        logger.debug(f"Invalidated payment cache for payment {instance.id}")
    except Exception as e:
        logger.error(f"Error invalidating payment cache: {str(e)}")


@receiver(post_delete, sender='payment.Payment')
def invalidate_payment_cache_on_delete(sender, instance, **kwargs):
    """Invalidate payment cache when a payment is deleted"""
    try:
        # Invalidate payer's payments cache
        invalidate_cache(keys=[
            f"payments:user:{instance.payer_id}:all",
            f"payments:user:{instance.payer_id}:today",
            f"payments:user:{instance.payer_id}:this_week",
            f"payments:user:{instance.payer_id}:this_month",
        ])
        
        # Invalidate recipient's payments cache
        if instance.recipient_id:
            invalidate_cache(keys=[
                f"payments:recipient:{instance.recipient_id}:all",
            ])
        
        logger.debug(f"Invalidated payment cache for deleted payment {instance.id}")
    except Exception as e:
        logger.error(f"Error invalidating payment cache on delete: {str(e)}")


# ============================================================================
# Profile Cache Invalidation
# ============================================================================

@receiver(post_save, sender='accounts.Profile')
def invalidate_profile_cache_on_save(sender, instance, created, **kwargs):
    """Invalidate profile cache when a profile is saved"""
    try:
        # Invalidate user profile cache
        invalidate_cache(keys=[
            f"profile:user:{instance.user_id}",
            f"account_details:user:{instance.user_id}",
        ])
        
        logger.debug(f"Invalidated profile cache for user {instance.user_id}")
    except Exception as e:
        logger.error(f"Error invalidating profile cache: {str(e)}")


@receiver(post_delete, sender='accounts.Profile')
def invalidate_profile_cache_on_delete(sender, instance, **kwargs):
    """Invalidate profile cache when a profile is deleted"""
    try:
        # Invalidate user profile cache
        invalidate_cache(keys=[
            f"profile:user:{instance.user_id}",
            f"account_details:user:{instance.user_id}",
        ])
        
        logger.debug(f"Invalidated profile cache for deleted user {instance.user_id}")
    except Exception as e:
        logger.error(f"Error invalidating profile cache on delete: {str(e)}")


# ============================================================================
# Job Cache Invalidation
# ============================================================================

@receiver(post_save, sender='jobs.Job')
def invalidate_job_cache_on_save(sender, instance, created, **kwargs):
    """Invalidate job cache when a job is saved"""
    try:
        # Invalidate job details cache
        invalidate_cache(keys=[
            f"job:detail:{instance.id}",
            f"job:detail:client:{instance.id}",
        ])
        
        # Invalidate client's jobs cache
        if instance.client_id:
            invalidate_cache(keys=[
                f"jobs:client:{instance.client_id}:all",
            ])
        
        logger.debug(f"Invalidated job cache for job {instance.id}")
    except Exception as e:
        logger.error(f"Error invalidating job cache: {str(e)}")


@receiver(post_delete, sender='jobs.Job')
def invalidate_job_cache_on_delete(sender, instance, **kwargs):
    """Invalidate job cache when a job is deleted"""
    try:
        # Invalidate job details cache
        invalidate_cache(keys=[
            f"job:detail:{instance.id}",
            f"job:detail:client:{instance.id}",
        ])
        
        # Invalidate client's jobs cache
        if instance.client_id:
            invalidate_cache(keys=[
                f"jobs:client:{instance.client_id}:all",
            ])
        
        logger.debug(f"Invalidated job cache for deleted job {instance.id}")
    except Exception as e:
        logger.error(f"Error invalidating job cache on delete: {str(e)}")


# ============================================================================
# Application Cache Invalidation
# ============================================================================

@receiver(post_save, sender='jobs.Application')
def invalidate_application_cache_on_save(sender, instance, created, **kwargs):
    """Invalidate application cache when an application is saved"""
    try:
        # Invalidate applicant's applications cache
        invalidate_cache(keys=[
            f"applications:applicant:{instance.applicant_id}:all",
        ])
        
        # Invalidate job's applications cache
        if instance.job_id:
            invalidate_cache(keys=[
                f"applications:job:{instance.job_id}:all",
            ])
        
        logger.debug(f"Invalidated application cache for application {instance.id}")
    except Exception as e:
        logger.error(f"Error invalidating application cache: {str(e)}")


@receiver(post_delete, sender='jobs.Application')
def invalidate_application_cache_on_delete(sender, instance, **kwargs):
    """Invalidate application cache when an application is deleted"""
    try:
        # Invalidate applicant's applications cache
        invalidate_cache(keys=[
            f"applications:applicant:{instance.applicant_id}:all",
        ])
        
        # Invalidate job's applications cache
        if instance.job_id:
            invalidate_cache(keys=[
                f"applications:job:{instance.job_id}:all",
            ])
        
        logger.debug(f"Invalidated application cache for deleted application {instance.id}")
    except Exception as e:
        logger.error(f"Error invalidating application cache on delete: {str(e)}")


def register_cache_signals():
    """Register all cache invalidation signals"""
    logger.info("Cache invalidation signals registered")


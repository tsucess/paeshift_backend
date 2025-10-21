"""
Scheduled tasks for Django Q.

This module defines scheduled tasks that can be run by Django Q.
"""

from django_q.tasks import schedule
from django_q.models import Schedule


def setup_scheduled_tasks():
    """
    Set up scheduled tasks for Django Q.
    
    This function should be called once during application startup.
    """
    # Schedule cache consistency check
    schedule(
        'godmode.tasks.cache_tasks.scheduled_consistency_check',
        schedule_type=Schedule.DAILY,
        name='daily_cache_consistency_check',
        repeats=-1,  # Repeat indefinitely
    )
    
    # Schedule cache reconciliation for all models
    schedule(
        'godmode.cache_sync.reconcile_all_caches',
        schedule_type=Schedule.WEEKLY,
        name='weekly_cache_reconciliation',
        repeats=-1,  # Repeat indefinitely
    )

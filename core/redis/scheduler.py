"""
Scheduler for periodic tasks.

This module contains the configuration for scheduled tasks using Django Q.
"""

import logging
from django_q.tasks import schedule
from django_q.models import Schedule
import sys

logger = logging.getLogger(__name__)

# Don't run scheduler during management commands
if 'manage.py' in sys.argv:
    def setup_scheduled_tasks():
        """Dummy implementation for management commands"""
        pass
else:
    def setup_scheduled_tasks():
        """
        Set up scheduled tasks for the application.

        This function is called during application startup to ensure that
        all scheduled tasks are properly configured.
        """
        # Set up cache warming task to run every hour
        _setup_task(
            name='warm_job_cache',
            func='jobs.tasks.warm_job_cache',
            schedule_type=Schedule.HOURLY,
            repeats=-1,  # Repeat indefinitely
        )

        # Set up cache reconciliation task to run daily
        _setup_task(
            name='reconcile_job_cache',
            func='jobs.tasks.reconcile_job_cache',
            schedule_type=Schedule.DAILY,
            repeats=-1,  # Repeat indefinitely
        )

        logger.info("Scheduled tasks setup complete")


def _setup_task(name, func, schedule_type, repeats=-1, **kwargs):
    """
    Helper function to set up a scheduled task.

    Args:
        name: The name of the task
        func: The function to call
        schedule_type: The schedule type (MINUTES, HOURLY, DAILY, WEEKLY, MONTHLY)
        repeats: Number of times to repeat (-1 for indefinitely)
        **kwargs: Additional arguments for the schedule
    """
    # Check if the task already exists
    if not Schedule.objects.filter(name=name).exists():
        # Create the task
        schedule(
            func,
            name=name,
            schedule_type=schedule_type,
            repeats=repeats,
            **kwargs
        )
        logger.info(f"Scheduled task '{name}' created")
    else:
        logger.debug(f"Scheduled task '{name}' already exists")


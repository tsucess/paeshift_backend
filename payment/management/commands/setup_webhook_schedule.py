"""
Management command to set up scheduled tasks for webhook processing.

This command sets up Django Q schedules for:
1. Processing webhook batches
2. Cleaning up the webhook queue
3. Monitoring webhook queue health
"""

import logging
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django_q.models import Schedule
from django_q.tasks import schedule as schedule_task

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Set up scheduled tasks for webhook processing"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force recreation of schedules even if they already exist",
        )

    def handle(self, *args, **options):
        force = options["force"]
        
        # Set up webhook batch processing schedule (every 1 minute)
        self._setup_schedule(
            name="Process Webhook Batch",
            func="payment.tasks.process_webhook_batch_task",
            schedule_type=Schedule.MINUTES,
            minutes=1,
            force=force,
        )
        
        # Set up webhook queue cleanup schedule (every 10 minutes)
        self._setup_schedule(
            name="Cleanup Webhook Queue",
            func="payment.tasks.cleanup_webhook_queue_task",
            schedule_type=Schedule.MINUTES,
            minutes=10,
            force=force,
        )
        
        self.stdout.write(self.style.SUCCESS("Webhook schedules set up successfully"))

    def _setup_schedule(self, name, func, schedule_type, force=False, **kwargs):
        """Set up a Django Q schedule."""
        # Check if schedule already exists
        existing = Schedule.objects.filter(name=name).first()
        
        if existing and not force:
            self.stdout.write(f"Schedule '{name}' already exists, skipping")
            return
        
        if existing and force:
            self.stdout.write(f"Removing existing schedule '{name}'")
            existing.delete()
        
        # Create schedule
        schedule_task(
            func=func,
            name=name,
            schedule_type=schedule_type,
            **kwargs
        )
        
        self.stdout.write(f"Created schedule '{name}' for {func}")

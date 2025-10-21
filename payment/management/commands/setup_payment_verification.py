"""
Management command to set up scheduled payment verification.

This command sets up a Django Q scheduled task to verify payment status
from Paystack and Flutterwave every 10 minutes.
"""

import logging
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django_q.models import Schedule
from django_q.tasks import schedule

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Set up scheduled payment verification every 10 minutes"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force recreation of the schedule even if it already exists",
        )

    def handle(self, *args, **options):
        force = options.get("force", False)

        # Check if schedule already exists
        existing_schedule = Schedule.objects.filter(name="payment_verification").first()
        
        if existing_schedule and not force:
            self.stdout.write(
                self.style.WARNING(
                    f"Payment verification schedule already exists: {existing_schedule}"
                )
            )
            
            # Update schedule
            existing_schedule.func = "payment.tasks.check_pending_payments"
            existing_schedule.schedule_type = Schedule.MINUTES
            existing_schedule.minutes = 10  # Run every 10 minutes
            existing_schedule.next_run = timezone.now() + timedelta(minutes=1)
            existing_schedule.save()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Updated payment verification schedule to run every 10 minutes"
                )
            )
        else:
            if existing_schedule and force:
                self.stdout.write(
                    self.style.WARNING(
                        f"Deleting existing schedule: {existing_schedule}"
                    )
                )
                existing_schedule.delete()
            
            # Create new schedule
            schedule(
                "payment.tasks.check_pending_payments",
                name="payment_verification",
                schedule_type=Schedule.MINUTES,
                minutes=10,  # Run every 10 minutes
                next_run=timezone.now() + timedelta(minutes=1),
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    "Scheduled payment verification to run every 10 minutes"
                )
            )
        
        # Show next run time
        next_schedule = Schedule.objects.filter(name="payment_verification").first()
        if next_schedule:
            self.stdout.write(f"Next run: {next_schedule.next_run}")
            
        self.stdout.write(
            self.style.SUCCESS(
                "Payment verification schedule set up successfully"
            )
        )

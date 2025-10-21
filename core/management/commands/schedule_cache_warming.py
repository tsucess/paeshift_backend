"""
Management command to schedule cache warming.

This command sets up a scheduled task to warm the Redis cache periodically.
"""

import logging
import time
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django_q.models import Schedule
from django_q.tasks import schedule

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Schedule cache warming to run periodically"

    def add_arguments(self, parser):
        parser.add_argument(
            "--models",
            type=str,
            nargs="+",
            help="List of models to cache in the format app_label.model_name",
            default=[
                "accounts.CustomUser",
                "jobs.Job",
                "jobs.JobApplication",
                "jobs.JobCategory",
                "jobs.JobIndustry",
                "jobs.JobSubcategory",
                "rating.Review",
            ],
        )
        parser.add_argument(
            "--interval",
            type=int,
            default=60,
            help="Interval in minutes between cache warming runs",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=1000,
            help="Maximum number of instances to cache per model",
        )
        parser.add_argument(
            "--recent",
            action="store_true",
            help="Only cache recently updated instances",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=7,
            help="Number of days to consider for recent instances",
        )

    def handle(self, *args, **options):
        models = options["models"]
        interval = options["interval"]
        limit = options["limit"]
        recent = options["recent"]
        days = options["days"]

        # Check if schedule already exists
        existing_schedule = Schedule.objects.filter(name="cache_warming").first()
        if existing_schedule:
            self.stdout.write(f"Cache warming schedule already exists: {existing_schedule}")
            
            # Update schedule
            existing_schedule.func = "django.core.management.call_command"
            existing_schedule.args = "warm_model_cache"
            existing_schedule.kwargs = {
                "models": models,
                "limit": limit,
                "recent": recent,
                "days": days,
            }
            existing_schedule.schedule_type = Schedule.MINUTES
            existing_schedule.minutes = interval
            existing_schedule.next_run = timezone.now() + timedelta(minutes=1)
            existing_schedule.save()
            
            self.stdout.write(self.style.SUCCESS(f"Updated cache warming schedule to run every {interval} minutes"))
        else:
            # Create new schedule
            schedule(
                "django.core.management.call_command",
                "warm_model_cache",
                models=models,
                limit=limit,
                recent=recent,
                days=days,
                name="cache_warming",
                schedule_type=Schedule.MINUTES,
                minutes=interval,
                next_run=timezone.now() + timedelta(minutes=1),
            )
            
            self.stdout.write(self.style.SUCCESS(f"Scheduled cache warming to run every {interval} minutes"))
            
        # Show next run time
        next_schedule = Schedule.objects.filter(name="cache_warming").first()
        if next_schedule:
            self.stdout.write(f"Next run: {next_schedule.next_run}")
            
        # Show models to be cached
        self.stdout.write("Models to be cached:")
        for model in models:
            self.stdout.write(f"  - {model}")
            
        # Show other settings
        self.stdout.write(f"Limit: {limit} instances per model")
        self.stdout.write(f"Recent only: {recent}")
        if recent:
            self.stdout.write(f"Days: {days}")
            
        self.stdout.write(self.style.SUCCESS("Cache warming schedule set up successfully"))

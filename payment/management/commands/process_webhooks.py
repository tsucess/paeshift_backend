"""
Management command to process payment webhooks in batches.

This command processes pending webhooks in the queue, with options for
continuous processing, batch size, and cleanup of stale webhooks.
"""

import logging
import time
from datetime import datetime

from django.core.management.base import BaseCommand

from payment.batch_processor import process_webhook_batch
from payment.webhook_queue import (
    cleanup_stale_processing,
    get_queue_stats,
    retry_failed_webhooks,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Process payment webhooks in batches"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=20,
            help="Number of webhooks to process in a batch",
        )
        parser.add_argument(
            "--continuous",
            action="store_true",
            help="Run continuously",
        )
        parser.add_argument(
            "--interval",
            type=int,
            default=5,
            help="Interval between processing batches in seconds (only used with --continuous)",
        )
        parser.add_argument(
            "--cleanup",
            action="store_true",
            help="Clean up stale processing webhooks",
        )
        parser.add_argument(
            "--retry-failed",
            action="store_true",
            help="Retry failed webhooks",
        )
        parser.add_argument(
            "--max-retries",
            type=int,
            default=100,
            help="Maximum number of failed webhooks to retry",
        )
        parser.add_argument(
            "--stats",
            action="store_true",
            help="Show queue statistics",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        continuous = options["continuous"]
        interval = options["interval"]
        cleanup = options["cleanup"]
        retry_failed = options["retry_failed"]
        max_retries = options["max_retries"]
        show_stats = options["stats"]

        # Show queue statistics if requested
        if show_stats:
            stats = get_queue_stats()
            self.stdout.write(self.style.SUCCESS("Webhook Queue Statistics:"))
            for key, value in stats.items():
                self.stdout.write(f"  {key}: {value}")
            return

        # Clean up stale processing webhooks if requested
        if cleanup:
            requeued_count = cleanup_stale_processing()
            self.stdout.write(
                self.style.SUCCESS(f"Requeued {requeued_count} stale processing webhooks")
            )

        # Retry failed webhooks if requested
        if retry_failed:
            requeued_count = retry_failed_webhooks(max_retries)
            self.stdout.write(
                self.style.SUCCESS(f"Requeued {requeued_count} failed webhooks")
            )

        # Process webhooks
        if continuous:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Starting continuous processing of webhooks (interval: {interval}s, batch size: {batch_size})"
                )
            )
            try:
                while True:
                    success_count, failure_count = process_webhook_batch(batch_size)
                    
                    if success_count > 0 or failure_count > 0:
                        self.stdout.write(
                            f"Processed {success_count + failure_count} webhooks: {success_count} succeeded, {failure_count} failed"
                        )
                    
                    # Sleep between batches
                    time.sleep(interval)
            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING("Interrupted by user"))
        else:
            success_count, failure_count = process_webhook_batch(batch_size)
            
            if success_count > 0 or failure_count > 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Processed {success_count + failure_count} webhooks: {success_count} succeeded, {failure_count} failed"
                    )
                )
            else:
                self.stdout.write(self.style.SUCCESS("No webhooks to process"))

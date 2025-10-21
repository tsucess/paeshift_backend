"""
Management command to process Redis data queues.

This command processes pending data in Redis queues, ensuring data consistency
before it is stored in the database.
"""

import logging
import time
from datetime import datetime

from django.core.management.base import BaseCommand

from core.redis_data_manager import (
    JobDataManager,
    PaymentDataManager,
    UserDataManager,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Process pending data in Redis queues"

    def add_arguments(self, parser):
        parser.add_argument(
            "--queue",
            type=str,
            choices=["job", "user", "payment", "all"],
            default="all",
            help="Queue to process",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Number of items to process in a batch",
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
            help="Clean up stale processing data",
        )
        parser.add_argument(
            "--retry-failed",
            action="store_true",
            help="Retry failed data",
        )

    def handle(self, *args, **options):
        queue = options["queue"]
        batch_size = options["batch_size"]
        continuous = options["continuous"]
        interval = options["interval"]
        cleanup = options["cleanup"]
        retry_failed = options["retry_failed"]

        # Initialize data managers
        job_manager = JobDataManager()
        user_manager = UserDataManager()
        payment_manager = PaymentDataManager()

        # Process queues
        if continuous:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Starting continuous processing of Redis queues (interval: {interval}s)"
                )
            )
            try:
                while True:
                    self._process_queues(
                        queue, batch_size, cleanup, retry_failed, job_manager, user_manager, payment_manager
                    )
                    time.sleep(interval)
            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING("Interrupted by user"))
        else:
            self._process_queues(
                queue, batch_size, cleanup, retry_failed, job_manager, user_manager, payment_manager
            )

    def _process_queues(
        self,
        queue,
        batch_size,
        cleanup,
        retry_failed,
        job_manager,
        user_manager,
        payment_manager,
    ):
        """Process the specified queues."""
        start_time = time.time()
        total_processed = 0
        total_failed = 0

        # Clean up stale processing data if requested
        if cleanup:
            if queue in ["job", "all"]:
                cleanup_count = job_manager.cleanup_stale_processing()
                self.stdout.write(
                    f"Cleaned up {cleanup_count} stale job data items"
                )

            if queue in ["user", "all"]:
                cleanup_count = user_manager.cleanup_stale_processing()
                self.stdout.write(
                    f"Cleaned up {cleanup_count} stale user data items"
                )

            if queue in ["payment", "all"]:
                cleanup_count = payment_manager.cleanup_stale_processing()
                self.stdout.write(
                    f"Cleaned up {cleanup_count} stale payment data items"
                )

        # Retry failed data if requested
        if retry_failed:
            if queue in ["job", "all"]:
                success, failed = job_manager.retry_failed_data(
                    lambda data: {
                        "job_id": data.get("_id"),
                        "status": "created",
                        "created_at": datetime.now().isoformat(),
                    },
                    batch_size,
                )
                self.stdout.write(
                    f"Retried {success + failed} failed job data items: {success} succeeded, {failed} failed"
                )
                total_processed += success
                total_failed += failed

            if queue in ["user", "all"]:
                success, failed = user_manager.retry_failed_data(
                    lambda data: {
                        "user_id": data.get("_id"),
                        "status": "created",
                        "created_at": datetime.now().isoformat(),
                    },
                    batch_size,
                )
                self.stdout.write(
                    f"Retried {success + failed} failed user data items: {success} succeeded, {failed} failed"
                )
                total_processed += success
                total_failed += failed

            if queue in ["payment", "all"]:
                success, failed = payment_manager.retry_failed_data(
                    lambda data: {
                        "payment_id": data.get("_id"),
                        "status": "processed",
                        "processed_at": datetime.now().isoformat(),
                    },
                    batch_size,
                )
                self.stdout.write(
                    f"Retried {success + failed} failed payment data items: {success} succeeded, {failed} failed"
                )
                total_processed += success
                total_failed += failed

        # Process pending data
        if queue in ["job", "all"]:
            success, failed = job_manager.process_jobs(batch_size)
            self.stdout.write(
                f"Processed {success + failed} pending job data items: {success} succeeded, {failed} failed"
            )
            total_processed += success
            total_failed += failed

        if queue in ["user", "all"]:
            success, failed = user_manager.process_users(batch_size)
            self.stdout.write(
                f"Processed {success + failed} pending user data items: {success} succeeded, {failed} failed"
            )
            total_processed += success
            total_failed += failed

        if queue in ["payment", "all"]:
            success, failed = payment_manager.process_payments(batch_size)
            self.stdout.write(
                f"Processed {success + failed} pending payment data items: {success} succeeded, {failed} failed"
            )
            total_processed += success
            total_failed += failed

        # Print summary
        elapsed = time.time() - start_time
        self.stdout.write(
            self.style.SUCCESS(
                f"Processed {total_processed + total_failed} total items in {elapsed:.2f}s: "
                f"{total_processed} succeeded, {total_failed} failed"
            )
        )

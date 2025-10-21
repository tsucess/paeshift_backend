"""
Management command to run a Redis queue worker.

This command processes jobs in Redis queues, executing background tasks
that have been enqueued.
"""

import importlib
import logging
import time
from datetime import datetime

from django.core.management.base import BaseCommand

from core.redis_queue import RedisQueue

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run a Redis queue worker"

    def add_arguments(self, parser):
        parser.add_argument(
            "--queue",
            type=str,
            required=True,
            help="Queue to process",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=10,
            help="Number of jobs to process in a batch",
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
            "--retry-failed",
            action="store_true",
            help="Retry failed jobs",
        )

    def handle(self, *args, **options):
        queue_name = options["queue"]
        batch_size = options["batch_size"]
        continuous = options["continuous"]
        interval = options["interval"]
        retry_failed = options["retry_failed"]

        # Initialize queue
        queue = RedisQueue(queue_name)

        # Define job processor
        def process_job(job_data):
            """Process a job by importing and calling the function."""
            func_name = job_data.get("func")
            module_name = job_data.get("module")
            args = job_data.get("args", [])
            kwargs = job_data.get("kwargs", {})

            if not func_name or not module_name:
                raise ValueError("Job data missing function or module name")

            try:
                # Import module
                module = importlib.import_module(module_name)

                # Get function
                func = getattr(module, func_name)

                # Call function
                self.stdout.write(f"Executing {module_name}.{func_name}")
                result = func(*args, **kwargs)

                return {"result": str(result)}
            except Exception as e:
                logger.exception(f"Error executing job: {str(e)}")
                raise

        # Process queues
        if continuous:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Starting continuous processing of queue {queue_name} (interval: {interval}s)"
                )
            )
            try:
                while True:
                    # Retry failed jobs if requested
                    if retry_failed:
                        success, failed = queue.retry_failed_jobs(process_job, batch_size)
                        self.stdout.write(
                            f"Retried {success + failed} failed jobs: {success} succeeded, {failed} failed"
                        )

                    # Process pending jobs
                    success, failed = queue.process_jobs(process_job, batch_size)
                    self.stdout.write(
                        f"Processed {success + failed} jobs: {success} succeeded, {failed} failed"
                    )

                    # Sleep if no jobs were processed
                    if success + failed == 0:
                        time.sleep(interval)
            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING("Interrupted by user"))
        else:
            # Retry failed jobs if requested
            if retry_failed:
                success, failed = queue.retry_failed_jobs(process_job, batch_size)
                self.stdout.write(
                    f"Retried {success + failed} failed jobs: {success} succeeded, {failed} failed"
                )

            # Process pending jobs
            success, failed = queue.process_jobs(process_job, batch_size)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Processed {success + failed} jobs: {success} succeeded, {failed} failed"
                )
            )

"""
Management command to monitor payment verification performance.

This command checks the performance of payment verification tasks
and reports statistics.
"""

import logging
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django_q.models import Success, Failure
from django_q.tasks import async_task

from payment.models import Payment

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Monitor payment verification performance"

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=int,
            default=24,
            help="Number of hours to look back for tasks",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Show detailed information",
        )

    def handle(self, *args, **options):
        hours = options.get("hours", 24)
        verbose = options.get("verbose", False)
        
        # Calculate time threshold
        time_threshold = timezone.now() - timedelta(hours=hours)
        
        self.stdout.write(f"Analyzing payment verification tasks from the last {hours} hours")
        
        # Get successful tasks
        successful_tasks = Success.objects.filter(
            started__gte=time_threshold,
            func="payment.tasks.verify_payment_status",
        )
        
        # Get failed tasks
        failed_tasks = Failure.objects.filter(
            started__gte=time_threshold,
            func="payment.tasks.verify_payment_status",
        )
        
        # Get scheduled tasks
        scheduled_tasks = Success.objects.filter(
            started__gte=time_threshold,
            func="payment.tasks.check_pending_payments",
        )
        
        # Calculate statistics
        total_verifications = successful_tasks.count()
        total_failures = failed_tasks.count()
        total_scheduled = scheduled_tasks.count()
        
        # Count by result
        success_count = 0
        skipped_count = 0
        pending_count = 0
        error_count = 0
        
        for task in successful_tasks:
            result = task.result
            if isinstance(result, dict):
                status = result.get("status", "unknown")
                if status == "success":
                    success_count += 1
                elif status == "skipped":
                    skipped_count += 1
                elif status == "pending":
                    pending_count += 1
                elif status == "error":
                    error_count += 1
        
        # Count by payment provider
        paystack_count = 0
        flutterwave_count = 0
        
        for task in successful_tasks:
            kwargs = task.kwargs
            if isinstance(kwargs, dict):
                payment_method = kwargs.get("payment_method", "").lower()
                if payment_method == "paystack":
                    paystack_count += 1
                elif payment_method == "flutterwave":
                    flutterwave_count += 1
        
        # Print summary
        self.stdout.write("\n=== Payment Verification Summary ===")
        self.stdout.write(f"Period: Last {hours} hours")
        self.stdout.write(f"Total verification tasks: {total_verifications}")
        self.stdout.write(f"Total failures: {total_failures}")
        self.stdout.write(f"Total scheduled runs: {total_scheduled}")
        
        self.stdout.write("\n=== Results Breakdown ===")
        self.stdout.write(f"Successful verifications: {success_count}")
        self.stdout.write(f"Skipped (already processed): {skipped_count}")
        self.stdout.write(f"Still pending: {pending_count}")
        self.stdout.write(f"Errors: {error_count}")
        
        self.stdout.write("\n=== Provider Breakdown ===")
        self.stdout.write(f"Paystack: {paystack_count}")
        self.stdout.write(f"Flutterwave: {flutterwave_count}")
        
        # Check current pending payments
        pending_payments = Payment.objects.filter(status="Pending")
        pending_count = pending_payments.count()
        
        self.stdout.write("\n=== Current Status ===")
        self.stdout.write(f"Current pending payments: {pending_count}")
        
        # Show detailed information if requested
        if verbose and pending_count > 0:
            self.stdout.write("\n=== Pending Payments ===")
            for payment in pending_payments[:10]:  # Show first 10
                created_ago = timezone.now() - payment.created_at
                hours_ago = created_ago.total_seconds() / 3600
                self.stdout.write(
                    f"Payment {payment.pay_code} ({payment.payment_method}): "
                    f"₦{payment.original_amount} - Created {hours_ago:.1f} hours ago"
                )
            
            if pending_count > 10:
                self.stdout.write(f"... and {pending_count - 10} more")
        
        # Suggest actions if needed
        if pending_count > 0:
            self.stdout.write("\n=== Suggested Actions ===")
            self.stdout.write("Run manual verification for pending payments:")
            self.stdout.write("  python manage.py verify_pending_payments")
            
        self.stdout.write("\n=== Monitoring Complete ===")
        
        # Return statistics
        return {
            "total_verifications": total_verifications,
            "total_failures": total_failures,
            "success_count": success_count,
            "pending_count": pending_count,
            "error_count": error_count,
        }

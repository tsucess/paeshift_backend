"""
Management command to manually verify pending payments.

This command manually verifies all pending payments with Paystack and Flutterwave.
"""

import logging
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django_q.tasks import async_task

from payment.models import Payment
from payment.tasks import verify_payment_status

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Manually verify pending payments"

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=int,
            default=48,
            help="Verify payments from the last N hours",
        )
        parser.add_argument(
            "--sync",
            action="store_true",
            help="Run verification synchronously (default is async)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limit the number of payments to verify",
        )

    def handle(self, *args, **options):
        hours = options.get("hours", 48)
        sync = options.get("sync", False)
        limit = options.get("limit")
        
        # Calculate time threshold
        time_threshold = timezone.now() - timedelta(hours=hours)
        
        # Get pending payments
        pending_payments = Payment.objects.filter(
            status="Pending", created_at__gte=time_threshold
        )
        
        if limit:
            pending_payments = pending_payments[:limit]
        
        count = pending_payments.count()
        
        self.stdout.write(f"Found {count} pending payments from the last {hours} hours")
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS("No pending payments to verify"))
            return
        
        self.stdout.write(f"Verifying {count} pending payments...")
        
        # Track payment providers for logging
        paystack_count = 0
        flutterwave_count = 0
        other_count = 0
        
        # Process each pending payment
        for i, payment in enumerate(pending_payments):
            # Skip payments without a payment method
            if not payment.payment_method:
                self.stdout.write(
                    self.style.WARNING(
                        f"Payment {payment.pay_code} has no payment method specified"
                    )
                )
                other_count += 1
                continue
                
            # Track payment provider
            if payment.payment_method.lower() == "paystack":
                paystack_count += 1
            elif payment.payment_method.lower() == "flutterwave":
                flutterwave_count += 1
            else:
                other_count += 1
                
            # Show progress
            if i % 10 == 0:
                self.stdout.write(f"Processing payment {i+1}/{count}...")
                
            if sync:
                # Run verification synchronously
                try:
                    result = verify_payment_status(
                        reference=payment.pay_code,
                        payment_method=payment.payment_method,
                    )
                    if result.get("status") == "success":
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Payment {payment.pay_code} verified successfully"
                            )
                        )
                    elif result.get("status") == "skipped":
                        self.stdout.write(
                            f"Payment {payment.pay_code} already processed"
                        )
                    elif result.get("status") == "pending":
                        self.stdout.write(
                            self.style.WARNING(
                                f"Payment {payment.pay_code} still pending"
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.ERROR(
                                f"Payment {payment.pay_code} verification failed: {result.get('message')}"
                            )
                        )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Error verifying payment {payment.pay_code}: {str(e)}"
                        )
                    )
            else:
                # Use Django Q for asynchronous verification
                async_task(
                    "payment.tasks.verify_payment_status",
                    reference=payment.pay_code,
                    payment_method=payment.payment_method,
                    group="manual_verification",
                    task_name=f"verify_{payment.payment_method.lower()}_{payment.pay_code}",
                )
        
        # Calculate total count
        total_count = paystack_count + flutterwave_count + other_count
        
        # Log detailed breakdown
        self.stdout.write(
            f"Verification initiated for {total_count} pending payments "
            f"(Paystack: {paystack_count}, Flutterwave: {flutterwave_count}, Other: {other_count})"
        )
        
        if not sync:
            self.stdout.write(
                self.style.SUCCESS(
                    "Verification tasks have been queued. Check results with:"
                )
            )
            self.stdout.write("  python manage.py monitor_payment_verification --hours=1")
        
        # Return detailed results
        return {
            "status": "success", 
            "total_count": total_count,
            "paystack_count": paystack_count,
            "flutterwave_count": flutterwave_count,
            "other_count": other_count,
            "sync": sync,
        }

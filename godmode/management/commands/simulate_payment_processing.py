"""
Django management command to simulate payment processing.

This command simulates payment processing for jobs, including webhook callbacks
and payment verification. It's useful for testing the payment workflow and
webhook handling.

Usage:
    python manage.py simulate_payment_processing --count=10
"""

import json
import logging
import random
import string
import uuid
from decimal import Decimal
from typing import Any, Dict, List

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from gamification.models import UserActivity
from jobs.models import Job
from payment.models import Payment

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Simulate payment processing including webhooks"

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=10,
            help="Number of payments to process (default: 10)",
        )
        parser.add_argument(
            "--payment-method",
            type=str,
            choices=["paystack", "flutterwave", "both"],
            default="both",
            help="Payment method to simulate (default: both)",
        )
        parser.add_argument(
            "--success-rate",
            type=float,
            default=0.8,
            help="Success rate for payments (0.0-1.0, default: 0.8)",
        )

    def handle(self, *args, **options):
        count = options["count"]
        payment_method = options["payment_method"]
        success_rate = options["success_rate"]

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting payment processing simulation for {count} payments with {payment_method} gateway(s)"
            )
        )

        # Check if we have jobs
        job_count = Job.objects.filter(payment_status="pending").count()
        if job_count == 0:
            self.stdout.write(
                self.style.WARNING("No pending jobs found. Please create jobs first.")
            )
            return {"error": "No pending jobs found"}

        # Create and process payments
        results = self.process_payments(count, payment_method, success_rate)

        self.stdout.write(
            self.style.SUCCESS(
                f"Processed {len(results['payments'])} payments: "
                f"{results['success_count']} successful, {results['failed_count']} failed"
            )
        )

        # Print details of processed payments
        for i, payment in enumerate(results["payments"], 1):
            status_style = (
                self.style.SUCCESS
                if payment["status"] == "Completed"
                else self.style.ERROR
            )
            self.stdout.write(
                status_style(
                    f"{i}. Payment: {payment['reference']} - Amount: {payment['amount']} - Status: {payment['status']}"
                )
            )

        return results

    def process_payments(
        self, count: int, payment_method: str, success_rate: float
    ) -> Dict[str, Any]:
        """
        Create and process test payments.

        Args:
            count: Number of payments to process
            payment_method: Payment method to use ('paystack', 'flutterwave', or 'both')
            success_rate: Success rate for payments (0.0-1.0)

        Returns:
            Dictionary with processed payments
        """
        results = {"payments": [], "errors": [], "success_count": 0, "failed_count": 0}

        # Get jobs with pending payment status
        jobs = list(Job.objects.filter(payment_status="pending")[:count])

        # If not enough jobs, use the same jobs multiple times
        if len(jobs) < count:
            jobs = jobs * (count // len(jobs) + 1)
            jobs = jobs[:count]

        # Create test client for webhook simulation
        client = Client()

        for i, job in enumerate(jobs):
            try:
                with transaction.atomic():
                    # Determine payment method for this payment
                    if payment_method == "both":
                        current_method = random.choice(["paystack", "flutterwave"])
                    else:
                        current_method = payment_method

                    # Generate unique reference
                    reference = f"SIM_{uuid.uuid4().hex[:8]}_{i+1}"

                    # Calculate payment amount
                    amount = job.rate * job.applicants_needed
                    service_fee = amount * Decimal("0.10")
                    final_amount = amount - service_fee

                    # Create payment record
                    payment = Payment.objects.create(
                        payer=job.client,
                        job=job,
                        original_amount=amount,
                        service_fee=service_fee,
                        final_amount=final_amount,
                        pay_code=reference,
                        payment_method=current_method,
                        status="Pending",
                    )

                    # Determine if this payment will succeed
                    will_succeed = random.random() < success_rate

                    # Simulate webhook callback
                    if current_method == "paystack":
                        webhook_url = "/payment/webhooks/paystack/"
                        webhook_data = {
                            "event": "charge.success"
                            if will_succeed
                            else "charge.failed",
                            "data": {
                                "reference": reference,
                                "amount": int(amount * 100),  # Convert to kobo
                                "status": "success" if will_succeed else "failed",
                                "paid_at": timezone.now().isoformat(),
                                "metadata": {
                                    "job_id": job.id,
                                    "custom_fields": [
                                        {
                                            "display_name": "Job Title",
                                            "variable_name": "job_title",
                                            "value": job.title,
                                        }
                                    ],
                                },
                            },
                        }
                        headers = {
                            "HTTP_X_PAYSTACK_SIGNATURE": "simulated_signature",
                            "content_type": "application/json",
                        }
                    else:  # flutterwave
                        webhook_url = "/payment/webhooks/flutterwave/"
                        webhook_data = {
                            "event": "charge.completed",
                            "data": {
                                "tx_ref": reference,
                                "amount": amount,
                                "currency": "NGN",
                                "status": "successful" if will_succeed else "failed",
                                "payment_type": "card",
                                "customer": {
                                    "email": job.client.email,
                                    "name": f"{job.client.first_name} {job.client.last_name}",
                                },
                                "meta": {"job_id": job.id, "job_title": job.title},
                            },
                        }
                        headers = {
                            "HTTP_VERIF_HASH": "simulated_hash",
                            "content_type": "application/json",
                        }

                    # Call webhook endpoint
                    response = client.post(
                        webhook_url, data=json.dumps(webhook_data), **headers
                    )

                    # Record payment activity
                    UserActivity.objects.create(
                        user=job.client,
                        activity_type="payment",
                        details={
                            "job_id": job.id,
                            "payment_id": payment.id,
                            "reference": reference,
                            "amount": str(amount),
                            "service_fee": str(service_fee),
                            "final_amount": str(final_amount),
                            "method": current_method,
                            "status": "success" if will_succeed else "failed",
                            "source": "simulation",
                        },
                        points_earned=10 if will_succeed else 0,
                    )

                    # Refresh payment from database
                    payment.refresh_from_db()

                    # Add to results
                    payment_result = {
                        "id": payment.id,
                        "job_id": job.id,
                        "job_title": job.title,
                        "client_id": job.client.id,
                        "client_username": job.client.username,
                        "reference": reference,
                        "amount": str(amount),
                        "service_fee": str(service_fee),
                        "final_amount": str(final_amount),
                        "method": current_method,
                        "status": payment.status,
                        "created_at": payment.created_at.isoformat(),
                        "webhook_response": {
                            "status_code": response.status_code,
                            "content": response.content.decode("utf-8")
                            if response.content
                            else "",
                        },
                    }

                    results["payments"].append(payment_result)

                    if payment.status == "Completed":
                        results["success_count"] += 1
                    else:
                        results["failed_count"] += 1

                    logger.info(
                        f"Processed payment: {reference} for job {job.title} - "
                        f"Status: {payment.status}, Method: {current_method}"
                    )

            except Exception as e:
                error_msg = f"Error processing payment for job {job.id}: {str(e)}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
                results["failed_count"] += 1

        return results

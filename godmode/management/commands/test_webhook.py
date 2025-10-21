"""
Django management command to test the payment webhook implementation.

This command simulates a payment webhook callback to test the webhook handling.

Usage:
    python manage.py test_webhook --payment-method=paystack
"""

import json
import logging
import uuid
from typing import Any, Dict

from django.core.management.base import BaseCommand
from django.test import Client
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Test payment webhook implementation"

    def add_arguments(self, parser):
        parser.add_argument(
            "--payment-method",
            type=str,
            choices=["paystack", "flutterwave"],
            default="paystack",
            help="Payment method to simulate (default: paystack)",
        )
        parser.add_argument(
            "--success",
            action="store_true",
            help="Simulate a successful payment (default: True)",
        )
        parser.add_argument(
            "--reference",
            type=str,
            help="Payment reference to use (default: auto-generated)",
        )

    def handle(self, *args, **options):
        payment_method = options["payment_method"]
        success = options.get("success", True)
        reference = options.get("reference") or f"TEST_{uuid.uuid4().hex[:8]}"

        self.stdout.write(
            self.style.SUCCESS(
                f"Testing {payment_method} webhook with reference {reference} (success: {success})"
            )
        )

        # Create test client
        client = Client()

        # Prepare webhook data
        if payment_method == "paystack":
            webhook_url = "/payment/webhooks/paystack/"
            webhook_data = {
                "event": "charge.success" if success else "charge.failed",
                "data": {
                    "reference": reference,
                    "amount": 10000,  # 100 NGN in kobo
                    "status": "success" if success else "failed",
                    "paid_at": timezone.now().isoformat(),
                    "metadata": {
                        "custom_fields": [
                            {
                                "display_name": "Test Webhook",
                                "variable_name": "test_webhook",
                                "value": "true",
                            }
                        ]
                    },
                },
            }
            headers = {
                "HTTP_X_PAYSTACK_SIGNATURE": "test_signature",
                "content_type": "application/json",
            }
        else:  # flutterwave
            webhook_url = "/payment/webhooks/flutterwave/"
            webhook_data = {
                "event": "charge.completed",
                "data": {
                    "tx_ref": reference,
                    "amount": 100,
                    "currency": "NGN",
                    "status": "successful" if success else "failed",
                    "payment_type": "card",
                    "customer": {"email": "test@example.com", "name": "Test User"},
                    "meta": {"test_webhook": "true"},
                },
            }
            headers = {
                "HTTP_VERIF_HASH": "test_hash",
                "content_type": "application/json",
            }

        # Call webhook endpoint
        response = client.post(webhook_url, data=json.dumps(webhook_data), **headers)

        # Print response
        self.stdout.write(
            self.style.SUCCESS(f"Response status code: {response.status_code}")
        )
        self.stdout.write(
            self.style.SUCCESS(f"Response content: {response.content.decode('utf-8')}")
        )

        # Store results in a variable
        results = {
            "status_code": response.status_code,
            "content": response.content.decode("utf-8") if response.content else "",
            "reference": reference,
            "payment_method": payment_method,
            "success": success,
        }

        # Return a string summary
        return f"Webhook test completed: {payment_method} webhook with reference {reference} returned status code {response.status_code}"

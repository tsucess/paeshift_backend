"""
Tests for the webhook functionality.
"""

import json
import uuid
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

from accounts.models import CustomUser as User
from godmode.models import WebhookLog
from godmode.webhook_utils import capture_webhook, reprocess_webhook, get_webhook_stats
from payment.models import Payment


class WebhookUtilsTestCase(TestCase):
    """Test case for webhook utilities."""

    def setUp(self):
        """Set up test data."""
        # Create test user
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpassword",
        )

        # Create test payment
        self.payment = Payment.objects.create(
            payer=self.user,
            original_amount=100.00,
            service_fee=10.00,
            final_amount=90.00,
            pay_code="test-payment-123",
            payment_method="paystack",
            status="Pending",
        )

        # Create test webhook logs
        self.webhook_success = WebhookLog.objects.create(
            reference="test-payment-123",
            gateway="paystack",
            status="success",
            request_data={"reference": "test-payment-123"},
            response_data={"status": "success"},
        )

        self.webhook_failed = WebhookLog.objects.create(
            reference="test-payment-456",
            gateway="paystack",
            status="failed",
            request_data={"reference": "test-payment-456"},
            response_data={"status": "failed"},
            error_message="Payment failed",
        )

        self.webhook_error = WebhookLog.objects.create(
            reference="test-payment-789",
            gateway="flutterwave",
            status="error",
            request_data={"reference": "test-payment-789"},
            response_data={},
            error_message="Gateway error",
        )

    def test_capture_webhook(self):
        """Test capturing a webhook."""
        # Test with dictionary request data
        request_data = {
            "reference": "test-payment-999",
            "amount": 100.00,
            "status": "success",
        }
        response_data = {
            "status": "success",
            "message": "Payment successful",
        }

        webhook = capture_webhook(
            reference="test-payment-999",
            gateway="paystack",
            request_data=request_data,
            response_data=response_data,
            status="success",
            ip_address="127.0.0.1",
        )

        # Verify webhook was created
        self.assertIsNotNone(webhook)
        self.assertEqual(webhook.reference, "test-payment-999")
        self.assertEqual(webhook.gateway, "paystack")
        self.assertEqual(webhook.status, "success")
        self.assertEqual(webhook.ip_address, "127.0.0.1")

        # Verify request data has webhook_id and timestamp
        self.assertIn("webhook_id", webhook.request_data)
        self.assertIn("captured_at", webhook.request_data)
        self.assertEqual(webhook.request_data["reference"], "test-payment-999")
        self.assertEqual(webhook.request_data["amount"], 100.00)
        self.assertEqual(webhook.request_data["status"], "success")

        # Verify response data
        self.assertEqual(webhook.response_data["status"], "success")
        self.assertEqual(webhook.response_data["message"], "Payment successful")

        # Test with string request data
        request_data_str = json.dumps({
            "reference": "test-payment-888",
            "amount": 200.00,
            "status": "success",
        })

        webhook = capture_webhook(
            reference="test-payment-888",
            gateway="flutterwave",
            request_data=request_data_str,
            status="pending",
        )

        # Verify webhook was created
        self.assertIsNotNone(webhook)
        self.assertEqual(webhook.reference, "test-payment-888")
        self.assertEqual(webhook.gateway, "flutterwave")
        self.assertEqual(webhook.status, "pending")

        # Verify request data was parsed
        self.assertIn("webhook_id", webhook.request_data)
        self.assertIn("captured_at", webhook.request_data)
        self.assertEqual(webhook.request_data["reference"], "test-payment-888")
        self.assertEqual(webhook.request_data["amount"], 200.00)
        self.assertEqual(webhook.request_data["status"], "success")

        # Test with invalid JSON string
        webhook = capture_webhook(
            reference="test-payment-777",
            gateway="paystack",
            request_data="invalid-json",
            status="error",
        )

        # Verify webhook was created
        self.assertIsNotNone(webhook)
        self.assertEqual(webhook.reference, "test-payment-777")
        self.assertEqual(webhook.gateway, "paystack")
        self.assertEqual(webhook.status, "error")

        # Verify request data has raw_data
        self.assertIn("webhook_id", webhook.request_data)
        self.assertIn("captured_at", webhook.request_data)
        self.assertEqual(webhook.request_data["raw_data"], "invalid-json")

    @patch("godmode.webhook_utils._verify_paystack")
    def test_reprocess_webhook_success(self, mock_verify_paystack):
        """Test reprocessing a webhook successfully."""
        # Create a failed webhook for an existing payment
        webhook = WebhookLog.objects.create(
            reference=self.payment.pay_code,
            gateway="paystack",
            status="failed",
            request_data={"reference": self.payment.pay_code},
            response_data={},
            error_message="Payment verification failed",
        )

        # Mock verification result
        mock_verify_paystack.return_value = {
            "status": "success",
            "data": {
                "reference": self.payment.pay_code,
                "amount": 10000,  # 100.00 in kobo
                "status": "success",
            },
        }

        # Reprocess the webhook
        success, message, updated_webhook = reprocess_webhook(webhook.id)

        # Verify result
        self.assertTrue(success)
        self.assertEqual(message, "Payment verified successfully")
        self.assertEqual(updated_webhook.status, "success")
        self.assertIsNone(updated_webhook.error_message)

        # Verify payment was updated
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "Completed")

    @patch("godmode.webhook_utils._verify_paystack")
    def test_reprocess_webhook_failure(self, mock_verify_paystack):
        """Test reprocessing a webhook with verification failure."""
        # Create a failed webhook for an existing payment
        webhook = WebhookLog.objects.create(
            reference=self.payment.pay_code,
            gateway="paystack",
            status="failed",
            request_data={"reference": self.payment.pay_code},
            response_data={},
            error_message="Payment verification failed",
        )

        # Mock verification result
        mock_verify_paystack.return_value = {
            "status": "failed",
            "message": "Payment verification failed",
        }

        # Reprocess the webhook
        success, message, updated_webhook = reprocess_webhook(webhook.id)

        # Verify result
        self.assertFalse(success)
        self.assertEqual(message, "Payment verification failed")
        self.assertEqual(updated_webhook.status, "failed")

        # Verify payment was not updated
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "Pending")

    @patch("godmode.webhook_utils._verify_paystack")
    def test_reprocess_webhook_exception(self, mock_verify_paystack):
        """Test reprocessing a webhook with an exception."""
        # Create a failed webhook for an existing payment
        webhook = WebhookLog.objects.create(
            reference=self.payment.pay_code,
            gateway="paystack",
            status="failed",
            request_data={"reference": self.payment.pay_code},
            response_data={},
            error_message="Payment verification failed",
        )

        # Mock verification exception
        mock_verify_paystack.side_effect = Exception("Gateway error")

        # Reprocess the webhook
        success, message, updated_webhook = reprocess_webhook(webhook.id)

        # Verify result
        self.assertFalse(success)
        self.assertEqual(message, "Error reprocessing webhook: Gateway error")
        self.assertEqual(updated_webhook.status, "error")
        self.assertEqual(updated_webhook.error_message, "Gateway error")

        # Verify payment was not updated
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "Pending")

    def test_reprocess_webhook_invalid_id(self):
        """Test reprocessing a webhook with an invalid ID."""
        # Reprocess a non-existent webhook
        success, message, updated_webhook = reprocess_webhook(999)

        # Verify result
        self.assertFalse(success)
        self.assertEqual(message, "Webhook with ID 999 not found")
        self.assertIsNone(updated_webhook)

    def test_reprocess_webhook_invalid_status(self):
        """Test reprocessing a webhook with an invalid status."""
        # Reprocess a successful webhook
        success, message, updated_webhook = reprocess_webhook(self.webhook_success.id)

        # Verify result
        self.assertFalse(success)
        self.assertEqual(message, "Cannot reprocess webhook with status: success")
        self.assertEqual(updated_webhook, self.webhook_success)

    def test_reprocess_webhook_payment_not_found(self):
        """Test reprocessing a webhook with a payment that doesn't exist."""
        # Create a failed webhook for a non-existent payment
        webhook = WebhookLog.objects.create(
            reference="non-existent-payment",
            gateway="paystack",
            status="failed",
            request_data={"reference": "non-existent-payment"},
            response_data={},
            error_message="Payment verification failed",
        )

        # Reprocess the webhook
        success, message, updated_webhook = reprocess_webhook(webhook.id)

        # Verify result
        self.assertFalse(success)
        self.assertEqual(message, "Payment with reference non-existent-payment not found")
        self.assertEqual(updated_webhook, webhook)

    def test_reprocess_webhook_unsupported_gateway(self):
        """Test reprocessing a webhook with an unsupported gateway."""
        # Create a failed webhook with an unsupported gateway
        webhook = WebhookLog.objects.create(
            reference=self.payment.pay_code,
            gateway="unsupported",
            status="failed",
            request_data={"reference": self.payment.pay_code},
            response_data={},
            error_message="Payment verification failed",
        )

        # Reprocess the webhook
        success, message, updated_webhook = reprocess_webhook(webhook.id)

        # Verify result
        self.assertFalse(success)
        self.assertEqual(message, "Unsupported gateway: unsupported")
        self.assertEqual(updated_webhook, webhook)

    def test_get_webhook_stats(self):
        """Test getting webhook statistics."""
        # Get webhook stats
        stats = get_webhook_stats()

        # Verify stats
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["success"], 1)
        self.assertEqual(stats["failed"], 1)
        self.assertEqual(stats["error"], 1)
        self.assertEqual(stats["pending"], 0)
        self.assertEqual(stats["success_rate"], 33.33333333333333)
        self.assertEqual(stats["gateways"]["paystack"], 2)
        self.assertEqual(stats["gateways"]["flutterwave"], 1)
        self.assertEqual(stats["gateways"]["other"], 0)
        self.assertEqual(len(stats["recent"]), 3)


class WebhookAPITestCase(TestCase):
    """Test case for webhook API endpoints."""

    def setUp(self):
        """Set up test data."""
        # Create test user
        self.user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="adminpassword",
        )

        # Create test payment
        self.payment = Payment.objects.create(
            payer=self.user,
            original_amount=100.00,
            service_fee=10.00,
            final_amount=90.00,
            pay_code="test-payment-123",
            payment_method="paystack",
            status="Pending",
        )

        # Create test webhook logs
        self.webhook_success = WebhookLog.objects.create(
            reference="test-payment-123",
            gateway="paystack",
            status="success",
            request_data={"reference": "test-payment-123"},
            response_data={"status": "success"},
        )

        self.webhook_failed = WebhookLog.objects.create(
            reference="test-payment-456",
            gateway="paystack",
            status="failed",
            request_data={"reference": "test-payment-456"},
            response_data={"status": "failed"},
            error_message="Payment failed",
        )

        self.webhook_error = WebhookLog.objects.create(
            reference="test-payment-789",
            gateway="flutterwave",
            status="error",
            request_data={"reference": "test-payment-789"},
            response_data={},
            error_message="Gateway error",
        )

        # Login
        self.client.login(username="admin", password="adminpassword")

    def test_list_webhooks(self):
        """Test listing webhooks."""
        from godmode.api import list_webhooks

        # Create request mock
        request = MagicMock()
        request.user = self.user

        # Test without filters
        webhooks = list_webhooks(request)
        self.assertEqual(len(webhooks), 3)

        # Test with gateway filter
        webhooks = list_webhooks(request, gateway="paystack")
        self.assertEqual(len(webhooks), 2)

        # Test with status filter
        webhooks = list_webhooks(request, status="failed")
        self.assertEqual(len(webhooks), 1)
        self.assertEqual(webhooks[0].reference, "test-payment-456")

        # Test with reference filter
        webhooks = list_webhooks(request, reference="test-payment-7")
        self.assertEqual(len(webhooks), 1)
        self.assertEqual(webhooks[0].reference, "test-payment-789")

        # Test with date filters
        today = timezone.now().date()
        webhooks = list_webhooks(request, date_from=today.strftime("%Y-%m-%d"))
        self.assertEqual(len(webhooks), 3)

        # Test with invalid date filter
        webhooks = list_webhooks(request, date_from="invalid-date")
        self.assertEqual(len(webhooks), 3)

    def test_get_webhook(self):
        """Test getting a webhook."""
        from godmode.api import get_webhook

        # Create request mock
        request = MagicMock()
        request.user = self.user

        # Test with valid webhook ID
        response = get_webhook(request, self.webhook_success.id)
        self.assertEqual(response["id"], self.webhook_success.id)
        self.assertEqual(response["reference"], "test-payment-123")
        self.assertEqual(response["gateway"], "paystack")
        self.assertEqual(response["status"], "success")
        self.assertEqual(response["payment"]["id"], self.payment.id)

        # Test with invalid webhook ID
        response = get_webhook(request, 999)
        self.assertEqual(response["status"], "error")
        self.assertIn("not found", response["message"])

    @patch("godmode.api.reprocess_webhook")
    def test_reprocess_webhook_endpoint(self, mock_reprocess_webhook):
        """Test reprocessing a webhook endpoint."""
        from godmode.api import reprocess_webhook_endpoint, WebhookReprocessSchema

        # Create request mock
        request = MagicMock()
        request.user = self.user

        # Mock reprocess_webhook
        mock_reprocess_webhook.return_value = (
            True,
            "Payment verified successfully",
            self.webhook_failed,
        )

        # Test with valid webhook ID
        payload = WebhookReprocessSchema(webhook_id=self.webhook_failed.id)
        response = reprocess_webhook_endpoint(request, payload)
        self.assertEqual(response["status"], "success")
        self.assertEqual(response["message"], "Payment verified successfully")
        self.assertEqual(response["webhook_id"], self.webhook_failed.id)

        # Mock reprocess_webhook failure
        mock_reprocess_webhook.return_value = (
            False,
            "Payment verification failed",
            self.webhook_failed,
        )

        # Test with failed reprocessing
        response = reprocess_webhook_endpoint(request, payload)
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["message"], "Payment verification failed")
        self.assertEqual(response["webhook_id"], self.webhook_failed.id)

        # Mock reprocess_webhook exception
        mock_reprocess_webhook.side_effect = Exception("Test exception")

        # Test with exception
        response = reprocess_webhook_endpoint(request, payload)
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["message"], "Test exception")

    def test_webhook_stats_endpoint(self):
        """Test webhook stats endpoint."""
        from godmode.api import webhook_stats

        # Create request mock
        request = MagicMock()
        request.user = self.user

        # Test webhook stats
        response = webhook_stats(request)
        self.assertEqual(response["total"], 3)
        self.assertEqual(response["success"], 1)
        self.assertEqual(response["failed"], 1)
        self.assertEqual(response["error"], 1)
        self.assertEqual(response["success_rate"], 33.33333333333333)
        self.assertEqual(response["gateways"]["paystack"], 2)
        self.assertEqual(response["gateways"]["flutterwave"], 1)
        self.assertEqual(len(response["recent"]), 3)

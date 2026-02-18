"""
Performance tests for the signup endpoint.

This test verifies that the signup endpoint completes in a reasonable time
without blocking delays.
"""

import json
import time
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

User = get_user_model()


class SignupPerformanceTestCase(TestCase):
    """Test case for signup endpoint performance."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.signup_url = reverse("accounts_api:accounts_router:signup_view")

    @patch('accounts.utils.send_mail_to_nonuser')
    def test_signup_completes_quickly(self, mock_send_email):
        """Test that signup endpoint completes in under 3 seconds."""
        # Mock the email sending to simulate a successful send
        mock_send_email.return_value = True

        data = {
            "email": "newuser@example.com",
            "password": "testpassword123",
            "first_name": "Test",
            "last_name": "User",
            "role": "applicant"
        }

        # Measure the time it takes to complete the signup
        start_time = time.time()
        response = self.client.post(
            self.signup_url,
            data=json.dumps(data),
            content_type="application/json"
        )
        elapsed_time = time.time() - start_time

        # Verify the response is successful
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertIn("message", response_data)
        self.assertTrue(response_data.get("requires_verification"))

        # Verify the user was created
        user = User.objects.filter(email="newuser@example.com").first()
        self.assertIsNotNone(user)

        # Verify the signup completed in under 3 seconds
        # (Previously it was taking 3+ seconds due to time.sleep(2))
        self.assertLess(
            elapsed_time,
            3.0,
            f"Signup took {elapsed_time:.2f}s, expected < 3.0s"
        )

    @patch('accounts.utils.send_mail_to_nonuser')
    def test_signup_with_email_failure(self, mock_send_email):
        """Test that signup handles email failures gracefully without blocking."""
        # Mock the email sending to simulate a failure
        mock_send_email.return_value = False

        data = {
            "email": "newuser2@example.com",
            "password": "testpassword123",
            "first_name": "Test",
            "last_name": "User",
            "role": "applicant"
        }

        # Measure the time it takes to complete the signup
        start_time = time.time()
        response = self.client.post(
            self.signup_url,
            data=json.dumps(data),
            content_type="application/json"
        )
        elapsed_time = time.time() - start_time

        # Verify the response is still successful (user is created)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertIn("message", response_data)

        # Verify the user was created even though email failed
        user = User.objects.filter(email="newuser2@example.com").first()
        self.assertIsNotNone(user)

        # Verify the signup completed quickly even with email failure
        # (Previously it would sleep for 2 seconds on failure)
        self.assertLess(
            elapsed_time,
            2.0,
            f"Signup with email failure took {elapsed_time:.2f}s, expected < 2.0s"
        )


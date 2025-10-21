"""
Tests for authentication endpoints in accounts/api.py.

This module tests the following endpoints:
- Password change
- Password reset request
- Logout
- User details (whoami)
"""

import json
import time
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model, authenticate
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

User = get_user_model()


class AuthEndpointsTestCase(TestCase):
    """Test case for authentication endpoints."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()

        # Create test users
        self.user1 = User.objects.create_user(
            username="testuser1",
            email="testuser1@example.com",
            password="testpassword123",
            first_name="Test",
            last_name="User1"
        )

        # URLs for the endpoints
        self.change_password_url = reverse("accounts_api:accounts_router:change_password")
        self.request_password_reset_url = reverse("accounts_api:accounts_router:request_password_reset")
        self.logout_url = reverse("accounts_api:accounts_router:logout_view")
        self.whoami_url = reverse("accounts_api:accounts_router:whoami", kwargs={"user_id": self.user1.id})
        self.whoami_current_url = reverse("accounts_api:accounts_router:whoami", kwargs={"user_id": 0})

    def test_change_password(self):
        """Test changing a user's password."""
        data = {
            "user_id": self.user1.id,
            "old_password": "testpassword123",
            "new_password": "newtestpassword123",
            "confirm_password": "newtestpassword123"
        }

        response = self.client.post(
            self.change_password_url,
            data=json.dumps(data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertIn("message", response_data)
        self.assertEqual(response_data["message"], "Password changed successfully. Please login again.")

        # Verify the password was changed by trying to authenticate
        user = authenticate(username=self.user1.username, password="newtestpassword123")
        self.assertIsNotNone(user)
        self.assertEqual(user.id, self.user1.id)

    def test_change_password_mismatch(self):
        """Test changing a password with mismatched new passwords."""
        data = {
            "user_id": self.user1.id,
            "old_password": "testpassword123",
            "new_password": "newtestpassword123",
            "confirm_password": "differentpassword123"
        }

        response = self.client.post(
            self.change_password_url,
            data=json.dumps(data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertIn("error", response_data)
        self.assertIn("Passwords do not match", response_data["error"])

    def test_change_password_wrong_old_password(self):
        """Test changing a password with incorrect old password."""
        data = {
            "user_id": self.user1.id,
            "old_password": "wrongpassword123",
            "new_password": "newtestpassword123",
            "confirm_password": "newtestpassword123"
        }

        response = self.client.post(
            self.change_password_url,
            data=json.dumps(data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertIn("error", response_data)
        self.assertEqual(response_data["error"], "Current password is incorrect")

    def test_change_password_nonexistent_user(self):
        """Test changing a password for a nonexistent user."""
        data = {
            "user_id": 9999,
            "old_password": "testpassword123",
            "new_password": "newtestpassword123",
            "confirm_password": "newtestpassword123"
        }

        response = self.client.post(
            self.change_password_url,
            data=json.dumps(data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 404)
        response_data = json.loads(response.content)
        self.assertIn("error", response_data)
        self.assertEqual(response_data["error"], "User not found")

    def test_request_password_reset_existing_user(self):
        """Test requesting a password reset for an existing user."""
        data = {
            "email": "testuser1@example.com"
        }

        with patch("accounts.api.send_mail") as mock_send_mail:
            response = self.client.post(
                self.request_password_reset_url,
                data=json.dumps(data),
                content_type="application/json"
            )

            self.assertEqual(response.status_code, 200)
            response_data = json.loads(response.content)
            self.assertIn("message", response_data)
            self.assertEqual(response_data["message"], "Password reset email sent if the email exists in our system")

            # Verify email was sent
            self.assertTrue(mock_send_mail.called)

    def test_request_password_reset_nonexistent_user(self):
        """Test requesting a password reset for a nonexistent user."""
        data = {
            "email": "nonexistent@example.com"
        }

        with patch("accounts.api.send_mail") as mock_send_mail:
            response = self.client.post(
                self.request_password_reset_url,
                data=json.dumps(data),
                content_type="application/json"
            )

            self.assertEqual(response.status_code, 200)
            response_data = json.loads(response.content)
            self.assertIn("message", response_data)
            self.assertEqual(response_data["message"], "Password reset email sent if the email exists in our system")

            # Verify email was not sent
            self.assertFalse(mock_send_mail.called)

    def test_logout(self):
        """Test logging out a user."""
        # First login
        self.client.force_login(self.user1)

        response = self.client.post(self.logout_url)

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertIn("message", response_data)
        self.assertEqual(response_data["message"], "Logged out successfully")

        # Verify the user is logged out
        self.assertFalse('_auth_user_id' in self.client.session)

    def test_whoami(self):
        """Test getting user details."""
        response = self.client.get(self.whoami_url)

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)

        self.assertEqual(response_data["user_id"], self.user1.id)
        self.assertEqual(response_data["username"], self.user1.username)
        self.assertEqual(response_data["email"], self.user1.email)

    def test_whoami_nonexistent_user(self):
        """Test getting details for a nonexistent user."""
        url = reverse("accounts_api:accounts_router:whoami", kwargs={"user_id": 9999})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)
        response_data = json.loads(response.content)
        self.assertIn("error", response_data)
        self.assertEqual(response_data["error"], "User not found")

    def test_whoami_current_user(self):
        """Test getting details for the current authenticated user."""
        # First login
        self.client.force_login(self.user1)

        response = self.client.get(self.whoami_current_url)

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)

        self.assertEqual(response_data["user_id"], self.user1.id)
        self.assertEqual(response_data["username"], self.user1.username)
        self.assertEqual(response_data["email"], self.user1.email)

    def test_whoami_current_user_not_authenticated(self):
        """Test getting details for the current user when not authenticated."""
        response = self.client.get(self.whoami_current_url)

        self.assertEqual(response.status_code, 401)
        response_data = json.loads(response.content)
        self.assertIn("error", response_data)
        self.assertEqual(response_data["error"], "Not authenticated")

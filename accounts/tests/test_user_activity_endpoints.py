"""
Tests for user activity endpoints in accounts/api.py.

This module tests the following endpoints:
- Get active users
- Get user last seen
"""

import json
import time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

User = get_user_model()


class UserActivityEndpointsTestCase(TestCase):
    """Test case for user activity endpoints."""

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

        self.user2 = User.objects.create_user(
            username="testuser2",
            email="testuser2@example.com",
            password="testpassword123",
            first_name="Test",
            last_name="User2"
        )

        # Set up cache for last seen timestamps
        cache.set(f"last_seen:{self.user1.id}", time.time(), 3600)
        cache.set(f"last_seen:{self.user2.id}", time.time() - 1800, 3600)  # 30 minutes ago

        # URLs for the endpoints
        self.active_users_url = reverse("accounts_api:accounts_router:get_active_users_endpoint", kwargs={"last_minutes": 15})
        self.last_seen_url = reverse("accounts_api:accounts_router:get_user_last_seen_endpoint", kwargs={"user_id": self.user1.id})
        self.last_seen_url_user2 = reverse("accounts_api:accounts_router:get_user_last_seen_endpoint", kwargs={"user_id": self.user2.id})
        self.last_seen_url_nonexistent = reverse("accounts_api:accounts_router:get_user_last_seen_endpoint", kwargs={"user_id": 9999})

    def test_get_active_users(self):
        """Test getting active users."""
        response = self.client.get(self.active_users_url)
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertIn("active_user_ids", data)
        self.assertIn("count", data)
        self.assertIn("minutes", data)
        self.assertEqual(data["minutes"], 15)

        # User1 should be in active users (just set in setUp)
        self.assertIn(self.user1.id, data["active_user_ids"])

    def test_get_active_users_custom_minutes(self):
        """Test getting active users with custom minutes parameter."""
        url = reverse("accounts_api:accounts_router:get_active_users_endpoint", kwargs={"last_minutes": 60})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["minutes"], 60)

        # Both users should be in active users (within last 60 minutes)
        self.assertIn(self.user1.id, data["active_user_ids"])
        self.assertIn(self.user2.id, data["active_user_ids"])

    def test_get_active_users_no_active_users(self):
        """Test getting active users when there are none."""
        # Clear the cache
        cache.clear()

        response = self.client.get(self.active_users_url)
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(len(data["active_user_ids"]), 0)
        self.assertEqual(data["count"], 0)

    def test_get_user_last_seen(self):
        """Test getting a user's last seen timestamp."""
        response = self.client.get(self.last_seen_url)
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["user_id"], self.user1.id)
        self.assertIsNotNone(data["last_seen_timestamp"])
        self.assertIsNotNone(data["last_seen_formatted"])
        self.assertTrue(data["is_online"])

    def test_get_user_last_seen_offline(self):
        """Test getting last seen for a user who is offline."""
        # Set last seen to 1 hour ago (outside the default online window)
        cache.set(f"last_seen:{self.user2.id}", time.time() - 3600, 3600)

        response = self.client.get(self.last_seen_url_user2)
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["user_id"], self.user2.id)
        self.assertIsNotNone(data["last_seen_timestamp"])
        self.assertIsNotNone(data["last_seen_formatted"])
        self.assertFalse(data["is_online"])

    def test_get_user_last_seen_nonexistent_user(self):
        """Test getting last seen for a nonexistent user."""
        response = self.client.get(self.last_seen_url_nonexistent)
        self.assertEqual(response.status_code, 404)

        data = json.loads(response.content)
        self.assertIn("error", data)
        self.assertEqual(data["error"], "User not found")

    def test_get_user_last_seen_never_active(self):
        """Test getting last seen for a user who has never been active."""
        # Create a new user without setting last_seen in cache
        user3 = User.objects.create_user(
            username="testuser3",
            email="testuser3@example.com",
            password="testpassword123"
        )

        url = reverse("accounts_api:accounts_router:get_user_last_seen_endpoint", kwargs={"user_id": user3.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["user_id"], user3.id)
        self.assertIsNone(data["last_seen_timestamp"])
        self.assertIsNone(data["last_seen_formatted"])
        self.assertFalse(data["is_online"])

    @patch("accounts.user_activity.get_user_last_seen")
    def test_get_user_last_seen_with_mock(self, mock_get_user_last_seen):
        """Test getting last seen with mocked user_activity function."""
        # Mock the get_user_last_seen function to return a specific timestamp
        mock_timestamp = time.time() - 600  # 10 minutes ago
        mock_get_user_last_seen.return_value = mock_timestamp

        response = self.client.get(self.last_seen_url)
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["user_id"], self.user1.id)
        self.assertEqual(data["last_seen_timestamp"], mock_timestamp)
        self.assertTrue(data["is_online"])  # Should be online (within 15 minutes)

        # Verify the mock was called with the correct user
        mock_get_user_last_seen.assert_called_once()

    def test_get_active_users_with_custom_online_threshold(self):
        """Test getting active users with a custom online threshold."""
        # Set a very short online threshold (1 minute)
        with patch("accounts.api.ONLINE_THRESHOLD_MINUTES", 1):
            # Set user2's last seen to 5 minutes ago
            cache.set(f"last_seen:{self.user2.id}", time.time() - 300, 3600)

            # Get active users in the last 10 minutes
            url = reverse("accounts_api:accounts_router:get_active_users_endpoint", kwargs={"last_minutes": 10})
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

            data = json.loads(response.content)

            # Both users should be in active_user_ids (within last 10 minutes)
            self.assertIn(self.user1.id, data["active_user_ids"])
            self.assertIn(self.user2.id, data["active_user_ids"])

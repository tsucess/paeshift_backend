"""
Tests for user activity endpoints.
"""
import json
import time
from datetime import datetime
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

    def test_get_user_last_seen(self):
        """Test getting user last seen."""
        response = self.client.get(self.last_seen_url)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertIn("user_id", data)
        self.assertIn("last_seen_timestamp", data)
        self.assertIn("last_seen_formatted", data)
        self.assertIn("is_online", data)
        
        self.assertEqual(data["user_id"], self.user1.id)
        self.assertIsNotNone(data["last_seen_timestamp"])
        self.assertIsNotNone(data["last_seen_formatted"])
        self.assertTrue(data["is_online"])  # User1 should be online (just set in setUp)

    def test_get_user_last_seen_offline(self):
        """Test getting last seen for a user who is not online."""
        response = self.client.get(self.last_seen_url_user2)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data["user_id"], self.user2.id)
        self.assertIsNotNone(data["last_seen_timestamp"])
        self.assertIsNotNone(data["last_seen_formatted"])
        self.assertFalse(data["is_online"])  # User2 should be offline (set 30 minutes ago)

    def test_get_user_last_seen_nonexistent(self):
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

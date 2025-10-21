"""
Comprehensive tests for all endpoints in accounts/api.py.
"""
import json
import os
import tempfile
import time
from datetime import datetime
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.conf import settings

from accounts.models import Profile

User = get_user_model()


class AccountsAPITestCase(TestCase):
    """Test case for all accounts API endpoints."""

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

        # Create profiles
        self.profile1 = Profile.objects.create(
            user=self.user1,
            bio="Test bio for user 1",
            location="Test location 1"
        )

        self.profile2 = Profile.objects.create(
            user=self.user2,
            bio="Test bio for user 2",
            location="Test location 2"
        )

        # Set up cache for last seen timestamps
        cache.set(f"last_seen:{self.user1.id}", time.time(), 3600)
        cache.set(f"last_seen:{self.user2.id}", time.time() - 1800, 3600)  # 30 minutes ago

        # URLs for the endpoints
        self.change_password_url = reverse("accounts_api:accounts_router:change_password")
        self.profile_url = reverse("accounts_api:accounts_router:get_profile")
        self.profile_update_url = reverse("accounts_api:accounts_router:update_profile")
        self.profile_upload_picture_url = reverse("accounts_api:accounts_router:upload_profile_picture")
        self.request_password_reset_url = reverse("accounts_api:accounts_router:request_password_reset")
        self.logout_url = reverse("accounts_api:accounts_router:logout_view")
        self.whoami_url = reverse("accounts_api:accounts_router:whoami", kwargs={"user_id": self.user1.id})
        self.active_users_url = reverse("accounts_api:accounts_router:get_active_users_endpoint", kwargs={"last_minutes": 15})
        self.last_seen_url = reverse("accounts_api:accounts_router:get_user_last_seen_endpoint", kwargs={"user_id": self.user1.id})

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

        # Verify the password was changed
        self.user1.refresh_from_db()
        self.assertTrue(self.user1.check_password("newtestpassword123"))

    def test_change_password_incorrect_old_password(self):
        """Test changing a password with incorrect old password."""
        data = {
            "user_id": self.user1.id,
            "old_password": "wrongpassword",
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
        self.assertEqual(response_data["error"], "Old password is incorrect")

    def test_change_password_passwords_dont_match(self):
        """Test changing a password with mismatched new passwords."""
        data = {
            "user_id": self.user1.id,
            "old_password": "testpassword123",
            "new_password": "newtestpassword123",
            "confirm_password": "differentpassword"
        }

        response = self.client.post(
            self.change_password_url,
            data=json.dumps(data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertIn("error", response_data)
        self.assertEqual(response_data["error"], "New password and confirm password do not match")

    def test_get_profile(self):
        """Test getting a user's profile."""
        response = self.client.get(f"{self.profile_url}?user_id={self.user1.id}")

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)

        self.assertEqual(response_data["user_id"], self.user1.id)
        self.assertEqual(response_data["username"], self.user1.username)
        self.assertEqual(response_data["first_name"], self.user1.first_name)
        self.assertEqual(response_data["last_name"], self.user1.last_name)
        self.assertEqual(response_data["email"], self.user1.email)
        self.assertEqual(response_data["bio"], self.profile1.bio)
        self.assertEqual(response_data["location"], self.profile1.location)

    def test_get_profile_nonexistent_user(self):
        """Test getting a profile for a nonexistent user."""
        response = self.client.get(f"{self.profile_url}?user_id=9999")

        self.assertEqual(response.status_code, 404)
        response_data = json.loads(response.content)
        self.assertIn("error", response_data)
        self.assertEqual(response_data["error"], "User not found")

    def test_update_profile(self):
        """Test updating a user's profile."""
        data = {
            "user_id": self.user1.id,
            "first_name": "Updated",
            "last_name": "Name",
            "bio": "Updated bio",
            "location": "Updated location"
        }

        response = self.client.post(
            self.profile_update_url,
            data=json.dumps(data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)

        # Verify the profile was updated
        self.user1.refresh_from_db()
        self.profile1.refresh_from_db()

        self.assertEqual(self.user1.first_name, "Updated")
        self.assertEqual(self.user1.last_name, "Name")
        self.assertEqual(self.profile1.bio, "Updated bio")
        self.assertEqual(self.profile1.location, "Updated location")

        # Verify the response contains the updated data
        self.assertEqual(response_data["first_name"], "Updated")
        self.assertEqual(response_data["last_name"], "Name")
        self.assertEqual(response_data["bio"], "Updated bio")
        self.assertEqual(response_data["location"], "Updated location")

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_upload_profile_picture(self):
        """Test uploading a profile picture."""
        # Create a test image
        image_content = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
        image = SimpleUploadedFile("test_image.gif", image_content, content_type="image/gif")

        response = self.client.post(
            f"{self.profile_upload_picture_url}?user_id={self.user1.id}",
            {"file": image},
            format="multipart"
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)

        # Verify the profile picture was updated
        self.profile1.refresh_from_db()
        self.assertIsNotNone(self.profile1.profile_pic)

        # Clean up
        if self.profile1.profile_pic:
            if os.path.isfile(self.profile1.profile_pic.path):
                os.remove(self.profile1.profile_pic.path)

    @patch('accounts.api.send_mail')
    def test_request_password_reset(self, mock_send_mail):
        """Test requesting a password reset."""
        data = {
            "email": self.user1.email
        }

        response = self.client.post(
            self.request_password_reset_url,
            data=json.dumps(data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertIn("message", response_data)
        self.assertEqual(response_data["message"], "If an account exists with this email, a reset link has been sent")

        # Verify send_mail was called
        mock_send_mail.assert_called_once()

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

    def test_get_active_users(self):
        """Test getting active users."""
        response = self.client.get(self.active_users_url)

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)

        self.assertIn("active_user_ids", response_data)
        self.assertIn("count", response_data)
        self.assertIn("minutes", response_data)
        self.assertEqual(response_data["minutes"], 15)

        # User1 should be in active users (just set in setUp)
        self.assertIn(self.user1.id, response_data["active_user_ids"])

    def test_get_user_last_seen(self):
        """Test getting user last seen."""
        response = self.client.get(self.last_seen_url)

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)

        self.assertIn("user_id", response_data)
        self.assertIn("last_seen_timestamp", response_data)
        self.assertIn("last_seen_formatted", response_data)
        self.assertIn("is_online", response_data)

        self.assertEqual(response_data["user_id"], self.user1.id)
        self.assertIsNotNone(response_data["last_seen_timestamp"])
        self.assertIsNotNone(response_data["last_seen_formatted"])
        self.assertTrue(response_data["is_online"])  # User1 should be online (just set in setUp)

    def test_get_user_last_seen_offline(self):
        """Test getting last seen for a user who is not online."""
        last_seen_url_user2 = reverse("accounts_api:accounts_router:get_user_last_seen_endpoint", kwargs={"user_id": self.user2.id})
        response = self.client.get(last_seen_url_user2)

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)

        self.assertEqual(response_data["user_id"], self.user2.id)
        self.assertIsNotNone(response_data["last_seen_timestamp"])
        self.assertIsNotNone(response_data["last_seen_formatted"])
        self.assertFalse(response_data["is_online"])  # User2 should be offline (set 30 minutes ago)

    def test_get_user_last_seen_nonexistent(self):
        """Test getting last seen for a nonexistent user."""
        last_seen_url_nonexistent = reverse("accounts_api:accounts_router:get_user_last_seen_endpoint", kwargs={"user_id": 9999})
        response = self.client.get(last_seen_url_nonexistent)

        self.assertEqual(response.status_code, 404)
        response_data = json.loads(response.content)
        self.assertIn("error", response_data)
        self.assertEqual(response_data["error"], "User not found")

    def test_get_active_users_custom_minutes(self):
        """Test getting active users with custom minutes parameter."""
        url = reverse("accounts_api:accounts_router:get_active_users_endpoint", kwargs={"last_minutes": 60})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)

        self.assertEqual(response_data["minutes"], 60)

        # Both users should be in active users (within last 60 minutes)
        self.assertIn(self.user1.id, response_data["active_user_ids"])
        self.assertIn(self.user2.id, response_data["active_user_ids"])

    def test_whoami_nonexistent_user(self):
        """Test getting details for a nonexistent user."""
        whoami_url_nonexistent = reverse("accounts_api:accounts_router:whoami", kwargs={"user_id": 9999})
        response = self.client.get(whoami_url_nonexistent)

        self.assertEqual(response.status_code, 404)
        response_data = json.loads(response.content)
        self.assertIn("error", response_data)
        self.assertEqual(response_data["error"], "User not found")

    def test_whoami_current_user(self):
        """Test getting details for the current authenticated user."""
        # First login
        self.client.force_login(self.user1)

        whoami_url_current = reverse("accounts_api:accounts_router:whoami", kwargs={"user_id": 0})
        response = self.client.get(whoami_url_current)

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)

        self.assertEqual(response_data["user_id"], self.user1.id)
        self.assertEqual(response_data["username"], self.user1.username)
        self.assertEqual(response_data["email"], self.user1.email)

    def test_whoami_unauthenticated(self):
        """Test getting details for the current user when not authenticated."""
        whoami_url_current = reverse("accounts_api:accounts_router:whoami", kwargs={"user_id": 0})
        response = self.client.get(whoami_url_current)

        self.assertEqual(response.status_code, 401)
        response_data = json.loads(response.content)
        self.assertIn("error", response_data)
        self.assertEqual(response_data["error"], "Not authenticated")

    def test_update_profile_nonexistent_user(self):
        """Test updating a profile for a nonexistent user."""
        data = {
            "user_id": 9999,
            "first_name": "Updated",
            "last_name": "Name"
        }

        response = self.client.post(
            self.profile_update_url,
            data=json.dumps(data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 404)
        response_data = json.loads(response.content)
        self.assertIn("error", response_data)
        self.assertEqual(response_data["error"], "User not found")

    def test_upload_profile_picture_nonexistent_user(self):
        """Test uploading a profile picture for a nonexistent user."""
        # Create a test image
        image_content = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
        image = SimpleUploadedFile("test_image.gif", image_content, content_type="image/gif")

        url = reverse("accounts_api:accounts_router:upload_profile_picture") + "?user_id=9999"
        response = self.client.post(
            url,
            {"file": image},
            format="multipart"
        )

        self.assertEqual(response.status_code, 404)
        response_data = json.loads(response.content)
        self.assertIn("error", response_data)
        self.assertEqual(response_data["error"], "User not found")

    def test_upload_profile_picture_invalid_file_type(self):
        """Test uploading a profile picture with invalid file type."""
        # Create a test file with invalid type
        file_content = b'This is not an image file'
        file = SimpleUploadedFile("test_file.txt", file_content, content_type="text/plain")

        url = reverse("accounts_api:accounts_router:upload_profile_picture") + f"?user_id={self.user1.id}"
        response = self.client.post(
            url,
            {"file": file},
            format="multipart"
        )

        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertIn("error", response_data)
        self.assertEqual(response_data["error"], "Invalid file type. Only JPEG, PNG, and GIF are allowed.")

    def test_request_password_reset_nonexistent_email(self):
        """Test requesting a password reset for a nonexistent email."""
        data = {
            "email": "nonexistent@example.com"
        }

        response = self.client.post(
            self.request_password_reset_url,
            data=json.dumps(data),
            content_type="application/json"
        )

        # Should still return 200 to prevent email enumeration
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertIn("message", response_data)
        self.assertEqual(response_data["message"], "If an account exists with this email, a reset link has been sent")

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

    def test_get_profile_missing_user_id(self):
        """Test getting a profile without providing a user ID."""
        response = self.client.get(self.profile_url)

        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertIn("error", response_data)
        self.assertEqual(response_data["error"], "User ID is required")

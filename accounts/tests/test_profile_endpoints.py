"""
Tests for profile endpoints in accounts/api.py.

This module tests the following endpoints:
- Get profile
- Update profile
- Upload profile picture
"""

import json
import os
import tempfile
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.models import Profile

User = get_user_model()


class ProfileEndpointsTestCase(TestCase):
    """Test case for profile endpoints."""

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

        # Create profiles
        self.profile1 = Profile.objects.create(
            user=self.user1,
            bio="Test bio for user 1",
            location="Test location 1"
        )

        # URLs for the endpoints
        self.profile_url = reverse("accounts_api:accounts_router:get_profile")
        self.profile_update_url = reverse("accounts_api:accounts_router:update_profile")
        self.profile_upload_picture_url = reverse("accounts_api:accounts_router:upload_profile_picture")

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

    def test_get_profile_missing_user_id(self):
        """Test getting a profile without providing a user ID."""
        response = self.client.get(self.profile_url)

        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertIn("error", response_data)
        self.assertEqual(response_data["error"], "User ID is required")

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

        self.assertEqual(response_data["user_id"], self.user1.id)
        self.assertEqual(response_data["first_name"], "Updated")
        self.assertEqual(response_data["last_name"], "Name")
        self.assertEqual(response_data["bio"], "Updated bio")
        self.assertEqual(response_data["location"], "Updated location")

        # Verify the changes were saved to the database
        self.user1.refresh_from_db()
        self.profile1.refresh_from_db()
        self.assertEqual(self.user1.first_name, "Updated")
        self.assertEqual(self.user1.last_name, "Name")
        self.assertEqual(self.profile1.bio, "Updated bio")
        self.assertEqual(self.profile1.location, "Updated location")

    def test_update_profile_nonexistent_user(self):
        """Test updating a profile for a nonexistent user."""
        data = {
            "user_id": 9999,
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

        self.assertEqual(response.status_code, 404)
        response_data = json.loads(response.content)
        self.assertIn("error", response_data)
        self.assertEqual(response_data["error"], "User not found")

    def test_update_profile_partial(self):
        """Test updating only some fields of a user's profile."""
        data = {
            "user_id": self.user1.id,
            "bio": "Only bio updated"
        }

        response = self.client.post(
            self.profile_update_url,
            data=json.dumps(data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)

        self.assertEqual(response_data["user_id"], self.user1.id)
        self.assertEqual(response_data["first_name"], self.user1.first_name)  # Unchanged
        self.assertEqual(response_data["last_name"], self.user1.last_name)  # Unchanged
        self.assertEqual(response_data["bio"], "Only bio updated")  # Changed
        self.assertEqual(response_data["location"], self.profile1.location)  # Unchanged

        # Verify the changes were saved to the database
        self.profile1.refresh_from_db()
        self.assertEqual(self.profile1.bio, "Only bio updated")

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

        self.assertEqual(response_data["user_id"], self.user1.id)
        self.assertIsNotNone(response_data["profile_pic_url"])

        # Verify the profile picture was saved
        self.profile1.refresh_from_db()
        self.assertIsNotNone(self.profile1.profile_pic)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
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

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
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

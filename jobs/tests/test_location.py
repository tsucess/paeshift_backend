"""
Tests for job location-related endpoints.
"""
from decimal import Decimal
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from ninja.testing import TestClient

from jobs.api import core_router as api
from jobs.models import Job, User, Profile
from jobchat.models import LocationHistory


class JobLocationTests(TestCase):
    def setUp(self):
        self.client = TestClient(api)
        
        # Create client user
        self.client_user = User.objects.create_user(
            email="client@example.com",
            password="testpass123",
            first_name="Client",
            last_name="User",
        )
        self.client_profile = Profile.objects.create(user=self.client_user, role="client")
        
        # Create applicant user
        self.applicant_user = User.objects.create_user(
            email="applicant@example.com",
            password="testpass123",
            first_name="Applicant",
            last_name="User",
        )
        self.applicant_profile = Profile.objects.create(user=self.applicant_user, role="applicant")
        
        # Create test job
        self.test_job = Job.objects.create(
            title="Test Job",
            client=self.client_user,
            job_type="full_time",
            shift_type="day",
            date=timezone.now().date() + timedelta(days=7),
            start_time="09:00",
            end_time="17:00",
            rate=Decimal("50.00"),
            location="123 Test Street, Test City",
            latitude=40.7128,
            longitude=-74.0060,
        )
        
        # Create some location history entries
        LocationHistory.objects.create(
            job=self.test_job,
            user=self.client_user,
            latitude=40.7128,
            longitude=-74.0060,
            timestamp=timezone.now() - timedelta(days=2)
        )
        
        LocationHistory.objects.create(
            job=self.test_job,
            user=self.client_user,
            latitude=40.7130,
            longitude=-74.0065,
            timestamp=timezone.now() - timedelta(days=1)
        )

    def test_get_job_location(self):
        """Test retrieving job location details"""
        response = self.client.get(f"/jobs/{self.test_job.id}/location")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["job_id"], self.test_job.id)
        self.assertEqual(data["title"], "Test Job")
        self.assertEqual(data["location"]["address"], "123 Test Street, Test City")
        self.assertEqual(data["location"]["latitude"], 40.7128)
        self.assertEqual(data["location"]["longitude"], -74.0060)
        
        # By default, permissions should be false for unauthenticated users
        self.assertFalse(data["permissions"]["can_update_location"])
        self.assertFalse(data["permissions"]["is_client"])
        self.assertFalse(data["permissions"]["is_job_owner"])

    def test_get_job_location_history(self):
        """Test retrieving job location history"""
        response = self.client.get(f"/jobs/{self.test_job.id}/location-history")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["job_id"], self.test_job.id)
        self.assertEqual(len(data["location_history"]), 2)
        
        # Check that the history is ordered by timestamp (most recent first)
        self.assertEqual(data["location_history"][0]["latitude"], 40.7130)
        self.assertEqual(data["location_history"][0]["longitude"], -74.0065)
        self.assertEqual(data["location_history"][1]["latitude"], 40.7128)
        self.assertEqual(data["location_history"][1]["longitude"], -74.0060)

    def test_check_user_role_client(self):
        """Test checking user role for a client"""
        # Login as client
        self.client.cookies["sessionid"] = "test_session_client"
        self.client.force_authenticate(self.client_user)
        
        response = self.client.get("/check-user-role/")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertTrue(data["is_client"])
        self.assertFalse(data["is_applicant"])
        self.assertTrue(data["can_update_location"])

    def test_check_user_role_applicant(self):
        """Test checking user role for an applicant"""
        # Login as applicant
        self.client.cookies["sessionid"] = "test_session_applicant"
        self.client.force_authenticate(self.applicant_user)
        
        response = self.client.get("/check-user-role/")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertFalse(data["is_client"])
        self.assertTrue(data["is_applicant"])
        self.assertFalse(data["can_update_location"])

    def test_update_job_location_as_client(self):
        """Test updating job location as a client"""
        # Login as client
        self.client.cookies["sessionid"] = "test_session_client"
        self.client.force_authenticate(self.client_user)
        
        new_location = {
            "latitude": 40.7500,
            "longitude": -74.0100,
            "location": "456 New Street, Test City"
        }
        
        response = self.client.post(
            f"/jobs/{self.test_job.id}/update-location",
            json=new_location
        )
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["message"], "Location updated successfully")
        self.assertEqual(data["new_coordinates"]["latitude"], 40.7500)
        self.assertEqual(data["new_coordinates"]["longitude"], -74.0100)
        self.assertEqual(data["new_coordinates"]["location"], "456 New Street, Test City")
        
        # Verify the job was updated in the database
        updated_job = Job.objects.get(id=self.test_job.id)
        self.assertEqual(float(updated_job.latitude), 40.7500)
        self.assertEqual(float(updated_job.longitude), -74.0100)
        self.assertEqual(updated_job.location, "456 New Street, Test City")

    def test_update_job_location_as_applicant(self):
        """Test updating job location as an applicant (should fail)"""
        # Login as applicant
        self.client.cookies["sessionid"] = "test_session_applicant"
        self.client.force_authenticate(self.applicant_user)
        
        new_location = {
            "latitude": 40.7500,
            "longitude": -74.0100,
            "location": "456 New Street, Test City"
        }
        
        response = self.client.post(
            f"/jobs/{self.test_job.id}/update-location",
            json=new_location
        )
        self.assertEqual(response.status_code, 403)
        
        data = response.json()
        self.assertEqual(data["error"], "Permission denied")
        
        # Verify the job was NOT updated in the database
        unchanged_job = Job.objects.get(id=self.test_job.id)
        self.assertEqual(float(unchanged_job.latitude), 40.7128)
        self.assertEqual(float(unchanged_job.longitude), -74.0060)
        self.assertEqual(unchanged_job.location, "123 Test Street, Test City")

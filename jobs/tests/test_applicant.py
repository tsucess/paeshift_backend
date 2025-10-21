# jobs/tests/test_applicant.py
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from ninja.errors import HttpError
from ninja.testing import TestClient

from jobs.models import Application, Job, Review, UserLocation
from jobs.schemas import ApplyJobSchema

User = get_user_model()


class ApplicantAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create test users with proper credentials
        cls.client_user = User.objects.create_user(
            email="client@example.com",
            password="testpass123",
            first_name="Client",
            last_name="User",
        )

        cls.applicant_user = User.objects.create_user(
            email="applicant@example.com",
            password="testpass123",
            first_name="Applicant",
            last_name="User",
        )

        # Create test job
        cls.test_job = Job.objects.create(
            title="Test Job",
            client=cls.client_user,
            latitude=40.7128,
            longitude=-74.0060,
            location="New York",
            rate=100.00,
            is_active=True,
            status="upcoming",
            start_time=datetime.now() + timedelta(days=1),
            end_time=datetime.now() + timedelta(days=1, hours=4),
        )

        # Initialize test client
        cls.api_client = TestClient()

    def _login_applicant(self):
        """Helper method to login as applicant"""
        response = self.api_client.post(
            "/jobs/login",
            json={"email": self.applicant_user.email, "password": "testpass123"},
        )
        return response.json()["access_token"]

    def test_apply_for_job_success(self):
        token = self._login_applicant()
        response = self.api_client.post(
            "/applicants/applications/apply-job/",
            json={"user_id": self.applicant_user.id, "job_id": self.test_job.id},
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("application_id", response.json())
        self.assertTrue(
            Application.objects.filter(
                applicant=self.applicant_user, job=self.test_job
            ).exists()
        )

    def test_apply_for_job_duplicate(self):
        # Create initial application
        Application.objects.create(
            job=self.test_job, applicant=self.applicant_user, employer=self.client_user
        )

        token = self._login_applicant()
        response = self.api_client.post(
            "/applicants/applications/apply-job/",
            json={"user_id": self.applicant_user.id, "job_id": self.test_job.id},
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("already applied", response.json()["detail"].lower())

    def test_get_nearby_jobs(self):
        # Setup user location
        UserLocation.objects.create(
            user=self.applicant_user,
            last_location="POINT(-74.0060 40.7128)",
            is_online=True,
        )

        token = self._login_applicant()
        response = self.api_client.get(
            f"/applicants/applications/getnearbyjobs/{self.applicant_user.id}",
            params={"lat": 40.7128, "lng": -74.0060, "radius_km": 5},
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        jobs = response.json()["jobs"]
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["id"], self.test_job.id)

    def test_applied_jobs_history(self):
        # Create multiple applications
        for i in range(3):
            job = Job.objects.create(
                title=f"Job {i}",
                client=self.client_user,
                latitude=40.7128,
                longitude=-74.0060,
                is_active=True,
            )
            Application.objects.create(
                job=job, applicant=self.applicant_user, employer=self.client_user
            )

        token = self._login_applicant()
        response = self.api_client.get(
            f"/applicants/applicantjobs/{self.applicant_user.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["jobs_applied"]), 3)
        self.assertEqual(data["total_jobs"], 3)

    def test_job_statistics(self):
        # Create applications with different statuses
        Application.objects.create(
            job=self.test_job, applicant=self.applicant_user, status="accepted"
        )
        Application.objects.create(
            job=self.test_job, applicant=self.applicant_user, status="completed"
        )

        token = self._login_applicant()
        response = self.api_client.get(
            f"/applicants/applicant/jobs/count/{self.applicant_user.id}/",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        stats = response.json()["statistics"]
        self.assertEqual(stats["application_counts"]["total"], 2)
        self.assertEqual(stats["application_counts"]["accepted"], 1)

    def test_client_engagement_history(self):
        # Create completed jobs
        for i in range(2):
            job = Job.objects.create(
                title=f"Completed Job {i}", client=self.client_user, status="completed"
            )
            Application.objects.create(
                job=job, applicant=self.applicant_user, status="completed"
            )

        token = self._login_applicant()
        response = self.api_client.get(
            f"/applicants/applicant/clients/list/{self.applicant_user.id}/",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        summary = response.json()["summary"]
        self.assertEqual(summary["total_clients"], 1)
        self.assertEqual(summary["total_jobs_completed"], 2)

    def test_application_details(self):
        # Create application with review
        application = Application.objects.create(
            job=self.test_job, applicant=self.applicant_user, status="completed"
        )
        Review.objects.create(application=application, rating=5, comment="Great work!")

        token = self._login_applicant()
        response = self.api_client.get(
            f"/applicants/applicant/jobs/details/{self.applicant_user.id}/",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        jobs = response.json()["jobs"]
        self.assertEqual(jobs[0]["metrics"]["client_rating"], 5.0)

    def test_invalid_job_application(self):
        token = self._login_applicant()
        response = self.api_client.post(
            "/applicants/applications/apply-job/",
            json={"user_id": self.applicant_user.id, "job_id": 999},
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["detail"].lower())

    def test_unauthorized_access(self):
        # Test without authentication token
        response = self.api_client.post(
            "/applicants/applications/apply-job/",
            json={"user_id": self.applicant_user.id, "job_id": self.test_job.id},
        )

        self.assertEqual(response.status_code, 401)

    def test_pagination(self):
        # Create 15 applications
        for i in range(15):
            job = Job.objects.create(
                title=f"Job {i}", client=self.client_user, is_active=True
            )
            Application.objects.create(
                job=job, applicant=self.applicant_user, employer=self.client_user
            )

        token = self._login_applicant()
        response = self.api_client.get(
            f"/applicants/applicantjobs/{self.applicant_user.id}",
            params={"page": 2, "page_size": 5},
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["jobs_applied"]), 5)
        self.assertEqual(data["page"], 2)
        self.assertEqual(data["total_pages"], 3)


# jobs/tests/test_applicant.py
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from ninja.errors import HttpError
from ninja.testing import TestClient

from jobs.models import Application, Job, Review, UserLocation
from jobs.schemas import ApplyJobSchema

User = get_user_model()


class ApplicantAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create test users with proper credentials
        cls.client_user = User.objects.create_user(
            email="client@example.com",
            password="testpass123",
            first_name="Client",
            last_name="User",
        )

        cls.applicant_user = User.objects.create_user(
            email="applicant@example.com",
            password="testpass123",
            first_name="Applicant",
            last_name="User",
        )

        # Create test job
        cls.test_job = Job.objects.create(
            title="Test Job",
            client=cls.client_user,
            latitude=40.7128,
            longitude=-74.0060,
            location="New York",
            rate=100.00,
            is_active=True,
            status="upcoming",
            start_time=datetime.now() + timedelta(days=1),
            end_time=datetime.now() + timedelta(days=1, hours=4),
        )

        # Initialize test client
        cls.api_client = TestClient()

    def _login_applicant(self):
        """Helper method to login as applicant"""
        response = self.api_client.post(
            "/jobs/login",
            json={"email": self.applicant_user.email, "password": "testpass123"},
        )
        return response.json()["access_token"]

    def test_apply_for_job_success(self):
        token = self._login_applicant()
        response = self.api_client.post(
            "/applicants/applications/apply-job/",
            json={"user_id": self.applicant_user.id, "job_id": self.test_job.id},
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("application_id", response.json())
        self.assertTrue(
            Application.objects.filter(
                applicant=self.applicant_user, job=self.test_job
            ).exists()
        )

    def test_apply_for_job_duplicate(self):
        # Create initial application
        Application.objects.create(
            job=self.test_job, applicant=self.applicant_user, employer=self.client_user
        )

        token = self._login_applicant()
        response = self.api_client.post(
            "/applicants/applications/apply-job/",
            json={"user_id": self.applicant_user.id, "job_id": self.test_job.id},
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("already applied", response.json()["detail"].lower())

    def test_get_nearby_jobs(self):
        # Setup user location
        UserLocation.objects.create(
            user=self.applicant_user,
            last_location="POINT(-74.0060 40.7128)",
            is_online=True,
        )

        token = self._login_applicant()
        response = self.api_client.get(
            f"/applicants/applications/getnearbyjobs/{self.applicant_user.id}",
            params={"lat": 40.7128, "lng": -74.0060, "radius_km": 5},
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        jobs = response.json()["jobs"]
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["id"], self.test_job.id)

    def test_applied_jobs_history(self):
        # Create multiple applications
        for i in range(3):
            job = Job.objects.create(
                title=f"Job {i}",
                client=self.client_user,
                latitude=40.7128,
                longitude=-74.0060,
                is_active=True,
            )
            Application.objects.create(
                job=job, applicant=self.applicant_user, employer=self.client_user
            )

        token = self._login_applicant()
        response = self.api_client.get(
            f"/applicants/applicantjobs/{self.applicant_user.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["jobs_applied"]), 3)
        self.assertEqual(data["total_jobs"], 3)

    def test_job_statistics(self):
        # Create applications with different statuses
        Application.objects.create(
            job=self.test_job, applicant=self.applicant_user, status="accepted"
        )
        Application.objects.create(
            job=self.test_job, applicant=self.applicant_user, status="completed"
        )

        token = self._login_applicant()
        response = self.api_client.get(
            f"/applicants/applicant/jobs/count/{self.applicant_user.id}/",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        stats = response.json()["statistics"]
        self.assertEqual(stats["application_counts"]["total"], 2)
        self.assertEqual(stats["application_counts"]["accepted"], 1)

    def test_client_engagement_history(self):
        # Create completed jobs
        for i in range(2):
            job = Job.objects.create(
                title=f"Completed Job {i}", client=self.client_user, status="completed"
            )
            Application.objects.create(
                job=job, applicant=self.applicant_user, status="completed"
            )

        token = self._login_applicant()
        response = self.api_client.get(
            f"/applicants/applicant/clients/list/{self.applicant_user.id}/",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        summary = response.json()["summary"]
        self.assertEqual(summary["total_clients"], 1)
        self.assertEqual(summary["total_jobs_completed"], 2)

    def test_application_details(self):
        # Create application with review
        application = Application.objects.create(
            job=self.test_job, applicant=self.applicant_user, status="completed"
        )
        Review.objects.create(application=application, rating=5, comment="Great work!")

        token = self._login_applicant()
        response = self.api_client.get(
            f"/applicants/applicant/jobs/details/{self.applicant_user.id}/",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        jobs = response.json()["jobs"]
        self.assertEqual(jobs[0]["metrics"]["client_rating"], 5.0)

    def test_invalid_job_application(self):
        token = self._login_applicant()
        response = self.api_client.post(
            "/applicants/applications/apply-job/",
            json={"user_id": self.applicant_user.id, "job_id": 999},
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["detail"].lower())

    def test_unauthorized_access(self):
        # Test without authentication token
        response = self.api_client.post(
            "/applicants/applications/apply-job/",
            json={"user_id": self.applicant_user.id, "job_id": self.test_job.id},
        )

        self.assertEqual(response.status_code, 401)

    def test_pagination(self):
        # Create 15 applications
        for i in range(15):
            job = Job.objects.create(
                title=f"Job {i}", client=self.client_user, is_active=True
            )
            Application.objects.create(
                job=job, applicant=self.applicant_user, employer=self.client_user
            )

        token = self._login_applicant()
        response = self.api_client.get(
            f"/applicants/applicantjobs/{self.applicant_user.id}",
            params={"page": 2, "page_size": 5},
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["jobs_applied"]), 5)
        self.assertEqual(data["page"], 2)
        self.assertEqual(data["total_pages"], 3)

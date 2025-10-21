from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import Client, RequestFactory, TestCase
from django.utils import timezone
from ninja.testing import TestClient

from jobs.api import core_router as api
from jobs.models import (Job, JobIndustry, JobSubCategory, Profile, SavedJob,
                         User)

from .tests.base import PayshiftTestCase


class AuthAPITests(PayshiftTestCase):
    def setUp(self):
        super().setUp()
        self.client = TestClient(api)
        self.django_client = Client()

    def test_signup_success(self):
        """Test successful user registration"""
        response = self.client.post(
            "/jobs/signup",
            json={
                "email": "newuser@example.com",
                "password": "newpass123",
                "first_name": "New",
                "last_name": "User",
                "role": "applicant",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "success")
        self.assertTrue(User.objects.filter(email="newuser@example.com").exists())

    def test_signup_duplicate_email(self):
        """Test registration with existing email"""
        response = self.client.post(
            "/jobs/signup",
            json={
                "email": "existing@example.com",
                "password": "newpass123",
                "first_name": "New",
                "last_name": "User",
                "role": "applicant",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Email already exists")

    def test_whoami_authenticated(self):
        # Login first
        login_response = self.client.post(
            "/login", json={"email": "applicant@example.com", "password": "testpass123"}
        )
        self.assertEqual(login_response.status_code, 200)

        response = self.client.get(f"/whoami/{self.applicant.id}")
        self.assertEqual(response.status_code, 200)

    def test_whoami_unauthenticated(self):
        response = self.client.get("/whoami/99999")
        self.assertEqual(response.status_code, 404)


class JobsAPITests(TestCase):
    def setUp(self):
        self.client = TestClient(api)
        self.user = User.objects.create_user(
            email="employer@example.com",
            password="testpass123",
            first_name="Employer",
            last_name="User",
        )
        self.profile = Profile.objects.create(user=self.user, role="client")

        # Create test job data
        self.industry = JobIndustry.objects.create(name="Technology")
        self.subcategory = JobSubCategory.objects.create(
            name="Web Development", industry=self.industry
        )

        # Create test job
        self.test_job = Job.objects.create(
            title="Test Job",
            client=self.user,
            industry=self.industry,
            subcategory=self.subcategory,
            job_type="full_time",
            shift_type="day",
            date=timezone.now().date() + timedelta(days=7),
            start_time="09:00",
            end_time="17:00",
            rate=Decimal("50.00"),
            location="Test Location",
        )

    def test_create_job_authenticated(self):
        """Test job creation with authentication"""
        # Login first
        login_response = self.client.post(
            "/jobs/login",
            json={"email": "employer@example.com", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        response = self.client.post(
            "/jobs/create-job",
            json={
                "title": "New API Job",
                "industry": self.industry.id,
                "subcategory": self.subcategory.id,
                "applicants_needed": 1,
                "job_type": "full_time",
                "shift_type": "day",
                "date": str(timezone.now().date() + timedelta(days=7)),
                "start_time": "09:00",
                "end_time": "17:00",
                "rate": "50.00",
                "location": "Test Location",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Job.objects.count(), 2)

    def test_create_job_unauthenticated(self):
        """Test job creation without authentication"""
        response = self.client.post(
            "/jobs/create-job",
            json={"title": "Unauthenticated Job", "description": "Should fail"},
        )
        self.assertEqual(response.status_code, 403)

    def test_get_job_detail(self):
        """Test retrieving job details"""
        response = self.client.get(f"/jobs/{self.test_job.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Test Job")
        self.assertEqual(response.json()["rate"], "50.00")

    def test_get_all_jobs(self):
        """Test listing all jobs"""
        response = self.client.get("/jobs/alljobs")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["jobs"]), 1)
        self.assertEqual(response.json()["jobs"][0]["title"], "Test Job")

    def test_get_job_industries(self):
        """Test retrieving job industries"""
        response = self.client.get("/jobs/job-industries/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["name"], "Technology")

    def test_save_job(self):
        """Test saving a job"""
        # Create test user to save job
        test_user = User.objects.create_user(
            email="testuser@example.com", password="testpass123"
        )

        # Login as test user
        login_response = self.client.post(
            "/jobs/login",
            json={"email": "testuser@example.com", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        # Save job
        response = self.client.post(
            "/jobs/save-job/add/",
            json={"user_id": test_user.id, "job_id": self.test_job.id},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["saved"], True)
        self.assertTrue(
            SavedJob.objects.filter(user=test_user, job=self.test_job).exists()
        )


from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory


def add_session_to_request(request):
    middleware = SessionMiddleware()
    middleware.process_request(request)
    request.session.save()


def test_login_success(self):
    request = RequestFactory().post(
        "/login", {"email": "testuser@example.com", "password": "securepassword"}
    )
    add_session_to_request(request)
    # response = login_view(request)
    # self.assertEqual(response.status_code, 200)


from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import Client, RequestFactory, TestCase
from django.utils import timezone
from ninja.testing import TestClient

from jobs.api import core_router as api
from jobs.models import (Job, JobIndustry, JobSubCategory, Profile, SavedJob,
                         User)

from .tests.base import PayshiftTestCase


class AuthAPITests(PayshiftTestCase):
    def setUp(self):
        super().setUp()
        self.client = TestClient(api)
        self.django_client = Client()

    def test_signup_success(self):
        """Test successful user registration"""
        response = self.client.post(
            "/jobs/signup",
            json={
                "email": "newuser@example.com",
                "password": "newpass123",
                "first_name": "New",
                "last_name": "User",
                "role": "applicant",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "success")
        self.assertTrue(User.objects.filter(email="newuser@example.com").exists())

    def test_signup_duplicate_email(self):
        """Test registration with existing email"""
        response = self.client.post(
            "/jobs/signup",
            json={
                "email": "existing@example.com",
                "password": "newpass123",
                "first_name": "New",
                "last_name": "User",
                "role": "applicant",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Email already exists")

    def test_whoami_authenticated(self):
        # Login first
        login_response = self.client.post(
            "/login", json={"email": "applicant@example.com", "password": "testpass123"}
        )
        self.assertEqual(login_response.status_code, 200)

        response = self.client.get(f"/whoami/{self.applicant.id}")
        self.assertEqual(response.status_code, 200)

    def test_whoami_unauthenticated(self):
        response = self.client.get("/whoami/99999")
        self.assertEqual(response.status_code, 404)


class JobsAPITests(TestCase):
    def setUp(self):
        self.client = TestClient(api)
        self.user = User.objects.create_user(
            email="employer@example.com",
            password="testpass123",
            first_name="Employer",
            last_name="User",
        )
        self.profile = Profile.objects.create(user=self.user, role="client")

        # Create test job data
        self.industry = JobIndustry.objects.create(name="Technology")
        self.subcategory = JobSubCategory.objects.create(
            name="Web Development", industry=self.industry
        )

        # Create test job
        self.test_job = Job.objects.create(
            title="Test Job",
            client=self.user,
            industry=self.industry,
            subcategory=self.subcategory,
            job_type="full_time",
            shift_type="day",
            date=timezone.now().date() + timedelta(days=7),
            start_time="09:00",
            end_time="17:00",
            rate=Decimal("50.00"),
            location="Test Location",
        )

    def test_create_job_authenticated(self):
        """Test job creation with authentication"""
        # Login first
        login_response = self.client.post(
            "/jobs/login",
            json={"email": "employer@example.com", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        response = self.client.post(
            "/jobs/create-job",
            json={
                "title": "New API Job",
                "industry": self.industry.id,
                "subcategory": self.subcategory.id,
                "applicants_needed": 1,
                "job_type": "full_time",
                "shift_type": "day",
                "date": str(timezone.now().date() + timedelta(days=7)),
                "start_time": "09:00",
                "end_time": "17:00",
                "rate": "50.00",
                "location": "Test Location",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Job.objects.count(), 2)

    def test_create_job_unauthenticated(self):
        """Test job creation without authentication"""
        response = self.client.post(
            "/jobs/create-job",
            json={"title": "Unauthenticated Job", "description": "Should fail"},
        )
        self.assertEqual(response.status_code, 403)

    def test_get_job_detail(self):
        """Test retrieving job details"""
        response = self.client.get(f"/jobs/{self.test_job.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Test Job")
        self.assertEqual(response.json()["rate"], "50.00")

    def test_get_all_jobs(self):
        """Test listing all jobs"""
        response = self.client.get("/jobs/alljobs")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["jobs"]), 1)
        self.assertEqual(response.json()["jobs"][0]["title"], "Test Job")

    def test_get_job_industries(self):
        """Test retrieving job industries"""
        response = self.client.get("/jobs/job-industries/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["name"], "Technology")

    def test_save_job(self):
        """Test saving a job"""
        # Create test user to save job
        test_user = User.objects.create_user(
            email="testuser@example.com", password="testpass123"
        )

        # Login as test user
        login_response = self.client.post(
            "/jobs/login",
            json={"email": "testuser@example.com", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        # Save job
        response = self.client.post(
            "/jobs/save-job/add/",
            json={"user_id": test_user.id, "job_id": self.test_job.id},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["saved"], True)
        self.assertTrue(
            SavedJob.objects.filter(user=test_user, job=self.test_job).exists()
        )


from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory


def add_session_to_request(request):
    middleware = SessionMiddleware()
    middleware.process_request(request)
    request.session.save()


def test_login_success(self):
    request = RequestFactory().post(
        "/login", {"email": "testuser@example.com", "password": "securepassword"}
    )
    add_session_to_request(request)
    # response = login_view(request)
    # self.assertEqual(response.status_code, 200)

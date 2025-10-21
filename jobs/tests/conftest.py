# conftest.py
import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from ninja.testing import TestClient

User = get_user_model()
from accounts.models import Profile
from jobs.models import Application, Job, JobIndustry, JobSubCategory, SavedJob

# @pytest.fixture
# def api_client():
#     return TestClient(jobs_api)


@pytest.fixture
def test_user(db):
    user = User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
        first_name="Test",
        last_name="User",
    )
    Profile.objects.create(user=user, role="applicant")
    return user


@pytest.fixture
def test_client(db):
    user = User.objects.create_user(
        username="testclient",
        email="client@example.com",
        password="clientpass123",
        first_name="Client",
        last_name="User",
    )
    Profile.objects.create(user=user, role="client")
    return user


@pytest.fixture
def test_industry(db):
    return JobIndustry.objects.create(name="Technology")


@pytest.fixture
def test_subcategory(db, test_industry):
    return JobSubCategory.objects.create(name="Web Development", industry=test_industry)


@pytest.fixture
def test_job(db, test_client, test_industry, test_subcategory):
    return Job.objects.create(
        client=test_client,
        title="Test Job",
        industry=test_industry,
        subcategory=test_subcategory,
        applicants_needed=2,
        job_type="full_time",
        shift_type="day",
        date="2023-12-31",
        start_time="09:00:00",
        end_time="17:00:00",
        rate=25.00,
        location="Test Location",
        latitude=40.7128,
        longitude=-74.0060,
    )


@pytest.fixture
def test_application(db, test_job, test_user):
    return Application.objects.create(
        job=test_job, applicant=test_user, employer=test_job.client, status="applied"
    )


@pytest.fixture
def saved_job(db, test_user, test_job):
    return SavedJob.objects.create(user=test_user, job=test_job)

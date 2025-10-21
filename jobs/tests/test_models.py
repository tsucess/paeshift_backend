import time
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts.models import *
from jobs.models import *
from rating.models import Review
from userlocation.models import *

User = get_user_model()
import json
import logging

from ..models import Job

logger = logging.getLogger(__name__)

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from jobs.models import (Application, Job, JobIndustry, JobSubCategory,
                         UserPoints)

User = get_user_model()


class JobModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testemployer", email="employer@test.com", password="testpass123"
        )
        self.industry = JobIndustry.objects.create(name="Technology")
        self.subcategory = JobSubCategory.objects.create(
            industry=self.industry, name="Web Development"
        )

    def test_job_creation(self):
        job = Job.objects.create(
            title="Test Job",
            description="Test Description",
            client=self.user,
            industry=self.industry,
            subcategory=self.subcategory,
            job_type=Job.JobType.SINGLE_DAY,
            shift_type=Job.ShiftType.MORNING,
            date=timezone.now().date(),
            start_time=timezone.now().time(),
            end_time=(timezone.now() + timezone.timedelta(hours=8)).time(),
            rate=Decimal("100.00"),
            location="Test Location",
        )
        self.assertEqual(job.title, "Test Job")
        self.assertEqual(job.status, Job.Status.PENDING)
        self.assertEqual(job.service_fee, Decimal("5.00"))  # 5% of rate
        self.assertEqual(job.total_amount, Decimal("105.00"))

    def test_job_duration_calculation(self):
        job = Job.objects.create(
            title="Duration Test Job",
            description="Test Description",
            client=self.user,
            job_type=Job.JobType.SINGLE_DAY,
            shift_type=Job.ShiftType.MORNING,
            date=timezone.now().date(),
            start_time=timezone.now().time(),
            end_time=(timezone.now() + timezone.timedelta(hours=4)).time(),
            rate=Decimal("50.00"),
            location="Test Location",
        )
        self.assertIsNotNone(job.duration_hours)
        self.assertTrue(0 < job.duration_hours <= 4)


class ApplicationModelTests(TestCase):
    def setUp(self):
        self.employer = User.objects.create_user(
            username="testemployer", email="employer@test.com", password="testpass123"
        )
        self.applicant = User.objects.create_user(
            username="testapplicant", email="applicant@test.com", password="testpass123"
        )
        self.job = Job.objects.create(
            title="Test Job",
            description="Test Description",
            client=self.employer,
            job_type=Job.JobType.SINGLE_DAY,
            shift_type=Job.ShiftType.MORNING,
            date=timezone.now().date(),
            start_time=timezone.now().time(),
            end_time=(timezone.now() + timezone.timedelta(hours=8)).time(),
            rate=Decimal("100.00"),
            location="Test Location",
        )

    def test_application_creation(self):
        application = Application.objects.create(
            job=self.job, applicant=self.applicant, employer=self.employer
        )
        self.assertEqual(application.status, Application.Status.APPLIED)
        self.assertFalse(application.is_shown_up)

    def test_application_status_changes(self):
        application = Application.objects.create(
            job=self.job, applicant=self.applicant, employer=self.employer
        )

        # Test shortlisting
        application.shortlist()
        self.assertEqual(application.status, Application.Status.SHORTLISTED)

        # Test accepting
        application.accept()
        self.assertEqual(application.status, Application.Status.ACCEPTED)
        self.assertEqual(self.job.selected_applicant, self.applicant)

        # Test rejecting
        application.reject()
        self.assertEqual(application.status, Application.Status.REJECTED)


class UserPointsModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@test.com", password="testpass123"
        )
        self.user_points = UserPoints.objects.create(user=self.user)

    def test_points_addition(self):
        initial_points = self.user_points.total_points
        initial_level = self.user_points.current_level

        # Add points that should trigger level up
        leveled_up = self.user_points.add_points(150)

        self.assertTrue(leveled_up)
        self.assertEqual(self.user_points.total_points, initial_points + 150)
        self.assertTrue(self.user_points.current_level > initial_level)

    def test_level_up_mechanics(self):
        initial_points_to_next = self.user_points.points_to_next_level

        self.user_points.level_up()

        self.assertEqual(self.user_points.current_level, 2)
        self.assertEqual(
            self.user_points.points_to_next_level, int(initial_points_to_next * 1.5)
        )


from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from jobs.models import (Application, Job, JobIndustry, JobSubCategory,
                         UserPoints)

User = get_user_model()


class JobModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testemployer", email="employer@test.com", password="testpass123"
        )
        self.industry = JobIndustry.objects.create(name="Technology")
        self.subcategory = JobSubCategory.objects.create(
            industry=self.industry, name="Web Development"
        )

    def test_job_creation(self):
        job = Job.objects.create(
            title="Test Job",
            description="Test Description",
            client=self.user,
            industry=self.industry,
            subcategory=self.subcategory,
            job_type=Job.JobType.SINGLE_DAY,
            shift_type=Job.ShiftType.MORNING,
            date=timezone.now().date(),
            start_time=timezone.now().time(),
            end_time=(timezone.now() + timezone.timedelta(hours=8)).time(),
            rate=Decimal("100.00"),
            location="Test Location",
        )
        self.assertEqual(job.title, "Test Job")
        self.assertEqual(job.status, Job.Status.PENDING)
        self.assertEqual(job.service_fee, Decimal("5.00"))  # 5% of rate
        self.assertEqual(job.total_amount, Decimal("105.00"))

    def test_job_duration_calculation(self):
        job = Job.objects.create(
            title="Duration Test Job",
            description="Test Description",
            client=self.user,
            job_type=Job.JobType.SINGLE_DAY,
            shift_type=Job.ShiftType.MORNING,
            date=timezone.now().date(),
            start_time=timezone.now().time(),
            end_time=(timezone.now() + timezone.timedelta(hours=4)).time(),
            rate=Decimal("50.00"),
            location="Test Location",
        )
        self.assertIsNotNone(job.duration_hours)
        self.assertTrue(0 < job.duration_hours <= 4)


class ApplicationModelTests(TestCase):
    def setUp(self):
        self.employer = User.objects.create_user(
            username="testemployer", email="employer@test.com", password="testpass123"
        )
        self.applicant = User.objects.create_user(
            username="testapplicant", email="applicant@test.com", password="testpass123"
        )
        self.job = Job.objects.create(
            title="Test Job",
            description="Test Description",
            client=self.employer,
            job_type=Job.JobType.SINGLE_DAY,
            shift_type=Job.ShiftType.MORNING,
            date=timezone.now().date(),
            start_time=timezone.now().time(),
            end_time=(timezone.now() + timezone.timedelta(hours=8)).time(),
            rate=Decimal("100.00"),
            location="Test Location",
        )

    def test_application_creation(self):
        application = Application.objects.create(
            job=self.job, applicant=self.applicant, employer=self.employer
        )
        self.assertEqual(application.status, Application.Status.APPLIED)
        self.assertFalse(application.is_shown_up)

    def test_application_status_changes(self):
        application = Application.objects.create(
            job=self.job, applicant=self.applicant, employer=self.employer
        )

        # Test shortlisting
        application.shortlist()
        self.assertEqual(application.status, Application.Status.SHORTLISTED)

        # Test accepting
        application.accept()
        self.assertEqual(application.status, Application.Status.ACCEPTED)
        self.assertEqual(self.job.selected_applicant, self.applicant)

        # Test rejecting
        application.reject()
        self.assertEqual(application.status, Application.Status.REJECTED)


class UserPointsModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@test.com", password="testpass123"
        )
        self.user_points = UserPoints.objects.create(user=self.user)

    def test_points_addition(self):
        initial_points = self.user_points.total_points
        initial_level = self.user_points.current_level

        # Add points that should trigger level up
        leveled_up = self.user_points.add_points(150)

        self.assertTrue(leveled_up)
        self.assertEqual(self.user_points.total_points, initial_points + 150)
        self.assertTrue(self.user_points.current_level > initial_level)

    def test_level_up_mechanics(self):
        initial_points_to_next = self.user_points.points_to_next_level

        self.user_points.level_up()

        self.assertEqual(self.user_points.current_level, 2)
        self.assertEqual(
            self.user_points.points_to_next_level, int(initial_points_to_next * 1.5)
        )


def process_job_location(job):
    try:
        # Simulate geocoding logic
        if not hasattr(job, "id"):
            logger.error(
                f"Error geocoding job location: 'str' object has no attribute 'id'"
            )
            return None
        # JSON parsing simulation
        import json

        # Use a valid JSON string instead of empty string
        response = "{}"  # Empty JSON object for simulation
        data = json.loads(response)
    except json.JSONDecodeError as e:
        logger.error(f"Error processing job location: {str(e)}")
        return None
    return data


def geocode_location(location):
    if not location:
        logger.error("Error processing job location: Empty or invalid API response")
        return None
    try:
        # Mocked in tests, but real API call in production
        from .utils import get_address_coordinates_helper

        coords = get_address_coordinates_helper(location)
        return {"lat": coords["latitude"], "lon": coords["longitude"]}
    except json.JSONDecodeError as e:
        logger.error(f"Error processing job location: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error geocoding location: {str(e)}")
        return None


# Example usage in tests
def run_tests():
    # Test with valid job
    job1 = MockJob(id="job1", location="San Francisco")
    result1 = process_job_location(job1)
    print(f"Processed job1: {result1}")

    # Test with invalid input (string instead of MockJob object)
    job2 = "invalid_job"
    result2 = process_job_location(job2)
    print(f"Processed job2: {result2}")

    # Test with invalid location
    job3 = MockJob(id="job3", location="")
    result3 = process_job_location(job3)
    print(f"Processed job3: {result3}")


if __name__ == "__main__":
    run_tests()


class GeocodePatcherMixin:
    def setUp(self):
        super().setUp()
        self.geocode_patcher = patch("jobs.utils.get_address_coordinates_helper")
        self.mock_geocode = self.geocode_patcher.start()
        self.mock_geocode.return_value = {
            "success": True,
            "latitude": Decimal("40.7128"),
            "longitude": Decimal("-74.0060"),
        }
        self.async_task_patcher = patch("django_q.tasks.async_task")
        self.mock_async_task = self.async_task_patcher.start()
        self.mock_async_task.return_value = None

    def tearDown(self):
        self.geocode_patcher.stop()
        self.async_task_patcher.stop()
        super().tearDown()


class BaseJobTestCase(GeocodePatcherMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123"
        )
        self.industry = JobIndustry.objects.create(name="Technology")
        self.subcategory = JobSubCategory.objects.create(
            industry=self.industry, name="Web Development"
        )
        self.job = Job.objects.create(
            title="Test Job",
            description="Test Description",
            rate=Decimal("100.00"),
            created_by=self.user,
            client=self.user,
            industry=self.industry,
            subcategory=self.subcategory,
            job_type=Job.JobType.SINGLE_DAY,
            shift_type=Job.ShiftType.MORNING,
            date=timezone.now().date() + timedelta(days=7),
            start_time=datetime.strptime("09:00", "%H:%M").time(),
            end_time=datetime.strptime("17:00", "%H:%M").time(),
            applicants_needed=1,
            location="Test Location",
            latitude=Decimal("40.7128"),
            longitude=Decimal("-74.0060"),
        )


class JobModelTests(BaseJobTestCase):
    def test_job_creation(self):
        self.assertEqual(self.job.created_by, self.user)
        self.assertEqual(self.job.status, Job.Status.PENDING)
        self.assertEqual(float(self.job.latitude), 40.7128)
        self.assertEqual(float(self.job.longitude), -74.0060)

    def test_duration_hours(self):
        """Test duration_hours calculation"""
        # Test normal 8-hour shift
        self.assertEqual(self.job.duration_hours, 8.0)

        # Test overnight shift crossing midnight
        self.job.start_time = datetime.strptime("22:00", "%H:%M").time()
        self.job.end_time = datetime.strptime("06:00", "%H:%M").time()
        self.job.save()

        # Calculate expected duration (8 hours)
        start_dt = datetime.combine(self.job.date, self.job.start_time)
        end_dt = datetime.combine(self.job.date, self.job.end_time)
        if end_dt < start_dt:
            end_dt += timedelta(days=1)
        expected_duration = (end_dt - start_dt).total_seconds() / 3600

        self.assertEqual(self.job.duration_hours, expected_duration)


# = Fixtures =
@pytest.fixture
def test_user(db):
    return User.objects.create_user(
        username="testuser", email="test@example.com", password="testpass123"
    )


@pytest.fixture
def test_client(db):
    return User.objects.create_user(
        username="clientuser", email="client@example.com", password="testpass123"
    )


@pytest.fixture
def test_industry(db):
    return JobIndustry.objects.create(name="Technology")


@pytest.fixture
def test_subcategory(db, test_industry):
    return JobSubCategory.objects.create(industry=test_industry, name="Web Development")


@pytest.fixture
def test_job(db, test_client, test_industry, test_subcategory):
    return Job.objects.create(
        title="Test Job",
        description="Test Description",
        client=test_client,
        created_by=test_client,
        industry=test_industry,
        subcategory=test_subcategory,
        job_type=Job.JobType.SINGLE_DAY,
        shift_type=Job.ShiftType.MORNING,
        date=timezone.now().date() + timedelta(days=7),
        start_time=datetime.strptime("09:00", "%H:%M").time(),
        end_time=datetime.strptime("17:00", "%H:%M").time(),
        applicants_needed=1,
        rate=Decimal("50.00"),
        location="Test Location",
        latitude=Decimal("40.7128"),
        longitude=Decimal("-74.0060"),
    )


@pytest.fixture
def test_application(db, test_user, test_job):
    application = Application(job=test_job, applicant=test_user)
    application.save()  # employer will be set automatically via signals or model save
    return application


class JobIndustryModelTests(TestCase):
    def setUp(self):
        self.industry = JobIndustry.objects.create(name="Healthcare")
        self.industry2 = JobIndustry.objects.create(name="Technology")

    def test_industry_creation(self):
        self.assertEqual(self.industry.name, "Healthcare")
        self.assertEqual(self.industry.subcategories.count(), 0)

    def test_industry_name_uniqueness(self):
        with self.assertRaises(ValidationError):
            JobIndustry(name="Healthcare").full_clean()

    def test_industry_ordering(self):
        industries = list(JobIndustry.objects.all())
        self.assertEqual(industries[0].name, "Healthcare")
        self.assertEqual(industries[1].name, "Technology")


class JobSubCategoryModelTests(TestCase):
    def setUp(self):
        self.industry = JobIndustry.objects.create(name="Technology")
        self.subcategory = JobSubCategory.objects.create(
            industry=self.industry, name="Web Development"
        )

    def test_subcategory_creation(self):
        self.assertEqual(self.subcategory.name, "Web Development")
        self.assertEqual(self.subcategory.industry, self.industry)
        self.assertEqual(
            str(self.subcategory), f"Web Development (under {self.industry.name})"
        )

    def test_subcategory_name_uniqueness(self):
        with self.assertRaises(ValidationError):
            JobSubCategory(industry=self.industry, name="Web Development").full_clean()

    def test_subcategory_ordering(self):
        JobSubCategory.objects.create(industry=self.industry, name="Mobile Development")
        subcategories = list(JobSubCategory.objects.order_by("name"))
        self.assertEqual(subcategories[0].name, "Mobile Development")
        self.assertEqual(subcategories[1].name, "Web Development")


class JobApplicationModelTests(GeocodePatcherMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client_user = User.objects.create_user(
            username="test_client", email="client@example.com", password="testpass123"
        )
        self.applicant = User.objects.create_user(
            username="test_applicant",
            email="applicant@example.com",
            password="testpass123",
        )
        self.industry = JobIndustry.objects.create(name="Technology")
        self.subcategory = JobSubCategory.objects.create(
            industry=self.industry, name="Web Development"
        )
        self.job = Job.objects.create(
            title="Test Job",
            description="Test Description",
            client=self.client_user,
            created_by=self.client_user,
            industry=self.industry,
            subcategory=self.subcategory,
            job_type=Job.JobType.SINGLE_DAY,
            shift_type=Job.ShiftType.MORNING,
            date=timezone.now().date() + timedelta(days=7),
            start_time=datetime.strptime("09:00", "%H:%M").time(),
            end_time=datetime.strptime("17:00", "%H:%M").time(),
            applicants_needed=1,
            rate=Decimal("50.00"),
            location="Test Location",
            latitude=Decimal("40.7128"),
            longitude=Decimal("-74.0060"),
        )
        self.application = Application(job=self.job, applicant=self.applicant)
        self.application.save()

    def test_application_creation(self):
        self.assertEqual(self.application.applicant, self.applicant)
        self.assertEqual(self.application.job, self.job)
        self.assertEqual(self.application.status, Application.Status.PENDING)
        self.assertEqual(self.application.employer, self.job.client)

    def test_application_uniqueness(self):
        job = Job.objects.create(
            title="Uniqueness Test Job",
            description="Uniqueness Test Description",
            client=self.client_user,
            created_by=self.client_user,
            industry=self.industry,
            subcategory=self.subcategory,
            job_type=Job.JobType.SINGLE_DAY,
            shift_type=Job.ShiftType.MORNING,
            date=timezone.now().date() + timedelta(days=7),
            start_time=datetime.strptime("09:00", "%H:%M").time(),
            end_time=datetime.strptime("17:00", "%H:%M").time(),
            applicants_needed=1,
            rate=Decimal("50.00"),
            location="Test Location",
            latitude=Decimal("40.7128"),
            longitude=Decimal("-74.0060"),
        )
        Application.objects.create(job=job, applicant=self.applicant)
        with self.assertRaises(ValidationError):
            Application.objects.create(job=job, applicant=self.applicant)

    def test_valid_ratings(self):
        test_ratings = [1.0, 2.5, 3.0, 4.5, 5.0]
        for rating in test_ratings:
            with self.subTest(rating=rating):
                job = Job.objects.create(
                    title=f"Test Job {rating}",
                    description=f"Test Description {rating}",
                    client=self.client_user,
                    created_by=self.client_user,
                    industry=self.industry,
                    subcategory=self.subcategory,
                    job_type=Job.JobType.SINGLE_DAY,
                    shift_type=Job.ShiftType.MORNING,
                    date=timezone.now().date() + timedelta(days=7),
                    start_time=datetime.strptime("09:00", "%H:%M").time(),
                    end_time=datetime.strptime("17:00", "%H:%M").time(),
                    applicants_needed=1,
                    rate=Decimal("50.00"),
                    location="Test Location",
                    latitude=Decimal("40.7128"),
                    longitude=Decimal("-74.0060"),
                )
                application = Application(
                    job=job,
                    applicant=self.applicant,
                )
                application.manual_rating = rating
                try:
                    application.full_clean()
                    application.save()
                except ValidationError as e:
                    self.fail(f"Valid rating {rating} raised ValidationError: {e}")


class SavedJobModelTests(GeocodePatcherMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.industry = JobIndustry.objects.create(name="Technology")
        self.subcategory = JobSubCategory.objects.create(
            name="Web Development", industry=self.industry
        )
        self.job = Job.objects.create(
            title="Test Job",
            client=self.user,
            created_by=self.user,
            industry=self.industry,
            subcategory=self.subcategory,
            job_type=Job.JobType.SINGLE_DAY,
            shift_type=Job.ShiftType.MORNING,
            date=timezone.now().date() + timedelta(days=7),
            start_time=datetime.strptime("09:00", "%H:%M").time(),
            end_time=datetime.strptime("17:00", "%H:%M").time(),
            applicants_needed=1,
            rate=Decimal("50.00"),
            location="Test Location",
            latitude=Decimal("40.7128"),
            longitude=Decimal("-74.0060"),
        )

    def test_save_job(self):
        saved_job = SavedJob.objects.create(user=self.user, job=self.job)
        self.assertIsNotNone(saved_job.saved_at)
        self.assertEqual(saved_job.user.email, "test@example.com")
        self.assertEqual(self.user.saved_jobs.count(), 1)
        self.assertEqual(self.job.saved_by_users.count(), 1)

    def test_saved_job_uniqueness(self):
        SavedJob.objects.create(user=self.user, job=self.job)
        with self.assertRaises(ValidationError):
            SavedJob(user=self.user, job=self.job).full_clean()


class ProfileModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.profile, _ = Profile.objects.get_or_create(user=self.user)
        self.profile.manual_rating = Decimal("3.5")
        self.profile.save()
        self.other_user = User.objects.create_user(
            username="otheruser", email="other@example.com", password="testpass123"
        )

    def test_balance_operations(self):
        from payment.models import Wallet

        # Get or create wallet
        wallet, created = Wallet.objects.get_or_create(
            user=self.user,
            defaults={"balance": Decimal("0.00")}
        )

        # Test adding to balance
        self.profile.add_to_balance(Decimal("100.00"))
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, Decimal("100.00"))

        # Test successful deduction
        success = self.profile.deduct_from_balance(Decimal("50.00"))
        self.assertTrue(success)
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, Decimal("50.00"))

        # Test failed deduction (insufficient funds)
        success = self.profile.deduct_from_balance(Decimal("100.00"))
        self.assertFalse(success)
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, Decimal("50.00"))

    def test_rating_calculation(self):
        Review.objects.filter(reviewed=self.user).delete()
        reviewer1 = User.objects.create_user(
            username="reviewer1", email="reviewer1@example.com", password="testpass123"
        )
        Review.objects.create(
            reviewer=reviewer1, reviewed=self.user, rating=4.0, feedback="Great work!"
        )
        self.assertEqual(float(self.profile.rating), 4.0)
        reviewer2 = User.objects.create_user(
            username="reviewer2", email="reviewer2@example.com", password="testpass123"
        )
        Review.objects.create(
            reviewer=reviewer2, reviewed=self.user, rating=5.0, feedback="Excellent!"
        )
        self.assertEqual(float(self.profile.rating), 4.5)


from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from jobs.models import (Application, ApplicationStatusLog, Job, JobIndustry,
                         JobSubCategory, SavedJob)

User = get_user_model()
pytestmark = pytest.mark.django_db


# Helper Functions
def create_test_user(email="test@example.com", password="testpass123"):
    return User.objects.create_user(email=email, password=password)


def create_job_industry(name="IT"):
    return JobIndustry.objects.create(name=name)


def create_job_subcategory(industry, name="Web Development"):
    return JobSubCategory.objects.create(industry=industry, name=name)


# ------------------------------------------------------
# 1️⃣ JobIndustry Model Tests
# ------------------------------------------------------
class TestJobIndustry:
    def test_create_job_industry(self):
        industry = create_job_industry()
        assert industry.name == "IT"
        assert isinstance(industry.timestamp, datetime)

    def test_str_representation(self):
        industry = create_job_industry()
        assert str(industry) == f"IT (Created on {industry.timestamp.date()})"

    def test_name_min_length_validation(self):
        with pytest.raises(ValidationError) as e:
            JobIndustry(name="A").full_clean()
        assert "Industry name must be at least 2 characters" in str(e.value)

    def test_name_uniqueness(self):
        create_job_industry()
        with pytest.raises(ValidationError):
            JobIndustry(name="IT").full_clean()

    def test_ordering(self):
        names = ["Finance", "Agriculture", "Technology"]
        for name in names:
            JobIndustry.objects.create(name=name)
        industries = JobIndustry.objects.all()
        assert industries[0].name == "Agriculture"
        assert industries[1].name == "Finance"
        assert industries[2].name == "Technology"


# ------------------------------------------------------
# 2️⃣ JobSubCategory Model Tests
# ------------------------------------------------------
class TestJobSubCategory:
    def test_create_subcategory(self):
        industry = create_job_industry()
        subcategory = create_job_subcategory(industry)
        assert subcategory.name == "Web Development"
        assert subcategory.industry == industry

    def test_str_representation(self):
        industry = create_job_industry()
        subcategory = create_job_subcategory(industry)
        assert str(subcategory) == "Web Development (under IT)"

    def test_full_info_property(self):
        industry = create_job_industry()
        subcategory = create_job_subcategory(industry)
        assert "Web Development | Industry created" in subcategory.full_info

    def test_unique_together_constraint(self):
        industry = create_job_industry()
        create_job_subcategory(industry)
        with pytest.raises(ValidationError):
            JobSubCategory(industry=industry, name="Web Development").full_clean()

    def test_ordering(self):
        industry = create_job_industry()
        names = ["Frontend", "Backend", "DevOps"]
        for name in names:
            JobSubCategory.objects.create(industry=industry, name=name)
        subcategories = JobSubCategory.objects.all()
        assert subcategories[0].name == "Backend"
        assert subcategories[1].name == "DevOps"
        assert subcategories[2].name == "Frontend"


# ------------------------------------------------------
# 3️⃣ Job Model Tests
# ------------------------------------------------------
class TestJob:
    @pytest.fixture
    def job_data(self):
        user = create_test_user()
        industry = create_job_industry()
        subcategory = create_job_subcategory(industry)
        return {
            "title": "Senior Django Developer",
            "description": "Develop awesome web apps",
            "client": user,
            "created_by": user,
            "industry": industry,
            "subcategory": subcategory,
            "job_type": Job.JobType.FULL_TIME,
            "shift_type": Job.ShiftType.DAY,
            "date": timezone.now().date() + timedelta(days=7),
            "start_time": datetime.strptime("09:00", "%H:%M").time(),
            "end_time": datetime.strptime("17:00", "%H:%M").time(),
            "rate": Decimal("50.00"),
            "location": "New York, NY",
        }

    def test_create_job(self, job_data):
        job = Job.objects.create(**job_data)
        assert job.title == "Senior Django Developer"
        assert job.status == Job.Status.PENDING
        assert job.payment_status == Job.PaymentStatus.PENDING
        assert job.is_active is True

    def test_job_str_representation(self, job_data):
        job = Job.objects.create(**job_data)
        assert job.title in str(job)
        assert job.get_status_display() in str(job)

    def test_duration_hours_calculation(self, job_data):
        job = Job.objects.create(**job_data)
        assert job.duration_hours == Decimal("8.00")

    def test_overnight_shift_duration(self, job_data):
        job_data["end_time"] = datetime.strptime("04:00", "%H:%M").time()
        job = Job.objects.create(**job_data)
        assert job.duration_hours == Decimal("19.00")  # 9pm to 4am next day

    def test_is_shift_ongoing(self, job_data):
        job = Job.objects.create(**job_data)
        assert job.is_shift_ongoing is False

        job.actual_shift_start = timezone.now()
        assert job.is_shift_ongoing is True

        job.actual_shift_end = timezone.now()
        assert job.is_shift_ongoing is False

    def test_start_shift_validation(self, job_data):
        job = Job.objects.create(**job_data)
        job.start_shift()
        assert job.status == Job.Status.ONGOING

        with pytest.raises(ValidationError):
            job.start_shift()  # Already ongoing

    def test_end_shift_validation(self, job_data):
        job = Job.objects.create(**job_data)
        job.start_shift()
        job.end_shift()
        assert job.status == Job.Status.COMPLETED

        with pytest.raises(ValidationError):
            job.end_shift()  # Already completed

    def test_deactivate_job(self, job_data):
        job = Job.objects.create(**job_data)
        job.deactivate()
        assert job.status == Job.Status.CANCELED
        assert job.is_active is False

        with pytest.raises(ValidationError):
            job.deactivate()  # Already canceled

    def test_payment_status_transitions(self, job_data):
        job = Job.objects.create(**job_data)

        # Valid transition
        job.payment_status = Job.PaymentStatus.HELD
        job.full_clean()

        # Invalid transition
        job.payment_status = Job.PaymentStatus.COMPLETED
        with pytest.raises(ValidationError):
            job.full_clean()


# ------------------------------------------------------
# 4️⃣ Application Model Tests
# ------------------------------------------------------
class TestApplication:
    @pytest.fixture
    def application_data(self, job_data):
        job = Job.objects.create(**job_data)
        applicant = create_test_user(email="applicant@example.com")
        return {
            "job": job,
            "applicant": applicant,
            "status": Application.Status.PENDING,
        }

    def test_create_application(self, application_data):
        app = Application.objects.create(**application_data)
        assert app.status == Application.Status.PENDING
        assert app.applicant.email == "applicant@example.com"

    def test_application_str_representation(self, application_data):
        app = Application.objects.create(**application_data)
        assert app.applicant.email in str(app)
        assert app.job.title in str(app)
        assert "Pending" in str(app)

    def test_update_status(self, application_data):
        app = Application.objects.create(**application_data)
        assert app.update_status(Application.Status.APPLIED) is True
        assert app.status == Application.Status.APPLIED
        assert app.status_changed_at is not None

        # Should return False when status doesn't change
        assert app.update_status(Application.Status.APPLIED) is False

    def test_accept_application(self, application_data):
        app = Application.objects.create(**application_data)
        assert app.accept() is True
        assert app.status == Application.Status.ACCEPTED
        assert app.job.selected_applicant == app.applicant
        assert app.job.status == Job.Status.ONGOING

    def test_accept_duplicate_application(self, application_data):
        app1 = Application.objects.create(**application_data)
        app2 = Application.objects.create(**application_data)
        app1.accept()
        with pytest.raises(ValidationError):
            app2.accept()

    def test_withdraw_application(self, application_data):
        app = Application.objects.create(**application_data)
        assert app.withdraw() is True
        assert app.status == Application.Status.WITHDRAWN

        # Can't withdraw accepted/rejected apps
        app.status = Application.Status.ACCEPTED
        with pytest.raises(ValidationError):
            app.withdraw()

    def test_rating_property(self, application_data):
        app = Application.objects.create(**application_data)
        app.manual_rating = 4.5
        assert app.rating == 4.5

    def test_duplicate_application_validation(self, application_data):
        Application.objects.create(**application_data)
        with pytest.raises(ValidationError):
            Application(**application_data).full_clean()


# ------------------------------------------------------
# 5️⃣ ApplicationStatusLog Model Tests
# ------------------------------------------------------
class TestApplicationStatusLog:
    def test_create_status_log(self, application_data):
        app = Application.objects.create(**application_data)
        log = ApplicationStatusLog.objects.create(
            application=app,
            old_status=Application.Status.PENDING,
            new_status=Application.Status.APPLIED,
        )
        assert str(log) == f"Application {app.id}: PENDING → APPLIED"

    def test_status_change_validation(self, application_data):
        app = Application.objects.create(**application_data)
        with pytest.raises(ValidationError):
            ApplicationStatusLog(
                application=app,
                old_status=Application.Status.PENDING,
                new_status=Application.Status.PENDING,
            ).full_clean()


# ------------------------------------------------------
# 6️⃣ SavedJob Model Tests
# ------------------------------------------------------
class TestSavedJob:
    def test_create_saved_job(self, job_data):
        user = create_test_user()
        job = Job.objects.create(**job_data)
        saved_job = SavedJob.objects.create(user=user, job=job)
        assert (
            str(saved_job)
            == f"{user.email} saved {job.title} on {saved_job.saved_at.date()}"
        )

    def test_unique_together_constraint(self, job_data):
        user = create_test_user()
        job = Job.objects.create(**job_data)
        SavedJob.objects.create(user=user, job=job)
        with pytest.raises(Exception):  # IntegrityError
            SavedJob.objects.create(user=user, job=job)

    def test_job_details_property(self, job_data):
        user = create_test_user()
        job = Job.objects.create(**job_data)
        saved_job = SavedJob.objects.create(user=user, job=job)
        details = saved_job.job_details
        assert details["title"] == job.title
        assert details["status"] == job.status

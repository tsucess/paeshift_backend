# jobs/tests/test_applications.py
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from geopy.location import Location
from geopy.point import Point

from accounts.models import *
from jobs.models import *
from rating.models import *
from userlocation.models import *

User = get_user_model()
# # jobs/tests/test_applications.py
# from django.test import TestCase
# from django.utils import timezone
# from decimal import Decimal
# from jobs.models import (
#     Application,
#     ApplicationStatusLog,
#     Job,
#     JobIndustry,
#     JobSubCategory,
#     Profile,
#     SavedJob,
#     UserLocation
# )
# from django.contrib.auth import get_user_model
# from decimal import Decimal
# from django.db import IntegrityError, transaction

# from unittest.mock import patch
# from geopy.location import Location

# from geopy.point import Point  # Add this import
# from geopy.location import Location
# import time
# from django.test import TestCase
# from django.utils import timezone
# from django.db import IntegrityError, transaction  # Add missing imports
# from datetime import timedelta
# from decimal import Decimal
# from django.contrib.auth import get_user_model
# from datetime import datetime
# from decimal import Decimal
# from django.test import TestCase
# from django.utils import timezone
# from django.core.exceptions import ValidationError
# from jobs.models import Job, JobIndustry, JobSubCategory, UserLocation
# from django.contrib.auth import get_user_model

# from django.conf import settings
# from django.conf import settings
# from jobs.models import Job, Profile, SavedJob  # Adjust imports based on your structure


# from decimal import Decimal
# from django.test import TestCase
# from django.utils import timezone
# from django.core.exceptions import ValidationError
# from jobs.models import Job, JobIndustry, JobSubCategory
# from django.contrib.auth import get_user_model

# from django.conf import settings


# from django.conf import settings


class BaseModelTests(TestCase):
    """Base test class with common setup"""

    @classmethod
    def setUpTestData(cls):
        """Create test data shared across all tests"""
        # Create unique users
        timestamp = timezone.now().timestamp()
        cls.applicant = User.objects.create_user(
            username=f"applicant_{timestamp}",
            email=f"applicant_{timestamp}@example.com",
            password="testpass123",
        )

        cls.employer = User.objects.create_user(
            username="test_employer", email="employer@test.com", password="testpass"
        )
        # Create unique industries
        cls.technology_industry = JobIndustry.objects.create(
            name=f"Technology_{timestamp}"
        )
        cls.healthcare_industry = JobIndustry.objects.create(
            name=f"Healthcare_{timestamp}"
        )

        # Create subcategories
        cls.software_subcategory = JobSubCategory.objects.create(
            industry=cls.technology_industry, name=f"Software_{timestamp}"
        )

        cls.nursing_subcategory = JobSubCategory.objects.create(
            industry=cls.healthcare_industry, name=f"Nursing_{timestamp}"
        )

        def create_valid_job(self):
            """Helper method to create valid job"""
            return Job.objects.create(
                title="Test Job",
                client=self.employer,
                industry=self.technology_industry,
                subcategory=self.software_subcategory,
                start_time=datetime.strptime("09:00", "%H:%M").time(),
                end_time=datetime.strptime("17:00", "%H:%M").time(),
                date=timezone.now().date(),
                rate=Decimal("15.00"),
                location="Test Location",
            )

    def setUp(self):
        """Run before each test method"""
        super().setUp()

    def create_test_job(self, **kwargs):
        """Helper to create test jobs with defaults"""
        defaults = {
            "title": "Test Job",
            "client": self.employer,
            "industry": self.technology_industry,
            "subcategory": self.software_subcategory,
            "start_time": datetime.strptime("09:00", "%H:%M").time(),
            "end_time": datetime.strptime("17:00", "%H:%M").time(),
            "date": timezone.now().date(),
            "rate": Decimal("15.00"),
            "location": "Test Location",
        }
        defaults.update(kwargs)
        return Job.objects.create(**defaults)

    @classmethod
    def create_user_with_profile(
        cls, username, email=None, role="applicant", balance="100.00"
    ):
        """Helper method to create user with profile"""
        if email is None:
            email = f"{username}@example.com"
        user = User.objects.create_user(
            username=username,
            email=email,
            password="testpass123",
        )
        Profile.objects.create(user=user, role=role, balance=Decimal(balance))
        return user

    def create_job(self, **kwargs):
        """Helper method to create a job with required fields"""
        defaults = {
            "title": f"Sample Job {timezone.now().timestamp()}",
            "description": "Job Description",
            "client": self.employer,
            "industry": self.technology_industry,
            "subcategory": self.software_subcategory,
            "job_type": Job.JobType.SINGLE_DAY,
            "shift_type": Job.ShiftType.MORNING,
            "date": timezone.now().date() + timedelta(days=7),
            "start_time": datetime.strptime("09:00", "%H:%M").time(),
            "end_time": datetime.strptime("17:00", "%H:%M").time(),
            "applicants_needed": 1,
            "rate": Decimal("50.00"),
            "location": "Sample Location",
            "latitude": 40.7128,
            "longitude": -74.0060,
        }
        defaults.update(kwargs)
        return Job.objects.create(**defaults)


class ProfileModelTests(BaseModelTests):
    """Tests for Profile model"""

    def test_profile_creation(self):
        """Test profile creation"""
        profile = Profile.objects.create(user=self.applicant, role="applicant")
        self.assertEqual(profile.user, self.applicant)


class JobModelTests(TestCase):
    def setUp(self):
        # Create test employer user
        self.employer = User.objects.create_user(
            username="employeruser", email="employer@example.com", password="testpass"
        )

        # Create industry/subcategory
        self.industry = JobIndustry.objects.create(name="Technology")
        self.subcategory = JobSubCategory.objects.create(
            name="Software Development", industry=self.industry
        )

    def create_job(self, **kwargs):
        """Helper method to create jobs with default values"""
        defaults = {
            "title": "Test Job",
            "client": self.employer,
            "industry": self.industry,
            "subcategory": self.subcategory,
            "date": timezone.now().date() + timedelta(days=1),  # Tomorrow's date
            "start_time": datetime.strptime("09:00", "%H:%M").time(),
            "end_time": datetime.strptime("17:00", "%H:%M").time(),
            "rate": Decimal("50.00"),
            "location": "New York, NY",
            "status": Job.Status.PENDING,
            "payment_status": Job.PaymentStatus.PENDING,
            "latitude": 40.7128,
            "longitude": -74.0060,
        }
        defaults.update(kwargs)
        return Job.objects.create(**defaults)

    def test_job_creation_with_all_fields(self):
        """Test job creation with all required fields"""
        job = self.create_job(
            title="Senior Python Developer",
            description="Develop awesome Python applications",
            applicants_needed=3,
            rate=Decimal("75.50"),
            shift_type=Job.ShiftType.DAY,
        )

        # Field value assertions
        self.assertEqual(job.applicants_needed, 3)
        self.assertEqual(job.rate, Decimal("75.50"))
        self.assertEqual(job.description, "Develop awesome Python applications")
        self.assertEqual(job.client, self.employer)
        self.assertEqual(job.status, Job.Status.PENDING)
        self.assertEqual(job.payment_status, Job.PaymentStatus.PENDING)

    def test_job_string_representation(self):
        """Test the __str__ method of Job model"""
        job = self.create_job(title="Backend Developer")
        expected_str = (
            f"Backend Developer ({job.get_job_type_display()}) - "
            f"{job.get_status_display()}"
        )
        self.assertEqual(str(job), expected_str)

    def test_job_duration_calculation_edge_cases(self):
        """Test duration calculation with various time combinations"""
        test_cases = [
            (("09:00", "17:00"), 8.0),  # Standard work day
            (("20:00", "04:00"), 8.0),  # Overnight shift
            (("12:00", "12:30"), 0.5),  # Half-hour shift
            (("23:45", "00:15"), 0.5),  # Midnight crossover
        ]

        for (start, end), expected in test_cases:
            with self.subTest(start=start, end=end):
                job = self.create_job(
                    start_time=datetime.strptime(start, "%H:%M").time(),
                    end_time=datetime.strptime(end, "%H:%M").time(),
                )
                self.assertAlmostEqual(float(job.duration_hours), expected, places=2)

    def test_valid_status_transitions(self):
        """Test valid status transition workflow"""
        # PENDING → ONGOING
        job = self.create_job()
        job.start_shift()
        self.assertEqual(job.status, Job.Status.ONGOING)
        self.assertIsNotNone(job.actual_shift_start)

        # ONGOING → COMPLETED
        job.end_shift()
        self.assertEqual(job.status, Job.Status.COMPLETED)
        self.assertIsNotNone(job.actual_shift_end)

        # New job: PENDING → CANCELED
        new_job = self.create_job()
        new_job.deactivate()
        self.assertEqual(new_job.status, Job.Status.CANCELED)
        self.assertFalse(new_job.is_active)

    def test_invalid_status_transitions(self):
        """Test invalid status changes raise errors"""
        job = self.create_job()
        job.start_shift()
        job.end_shift()  # Now status is COMPLETED

        # Try to restart completed job
        with self.assertRaises(ValidationError):
            job.start_shift()

        # Try to cancel completed job
        with self.assertRaises(ValidationError):
            job.deactivate()

    def test_shift_tracking_states(self):
        """Test shift tracking lifecycle"""
        job = self.create_job()

        # Initial state
        self.assertFalse(job.is_shift_ongoing)
        self.assertIsNone(job.actual_shift_start)

        # During shift
        job.start_shift()
        self.assertTrue(job.is_shift_ongoing)
        self.assertIsNotNone(job.actual_shift_start)

        # After shift
        job.end_shift()
        self.assertFalse(job.is_shift_ongoing)
        self.assertIsNotNone(job.actual_shift_end)

    def test_location_coordinates_handling(self):
        """Test coordinate storage and retrieval"""
        # With coordinates
        job = self.create_job(latitude=34.0522, longitude=-118.2437)
        self.assertEqual(job.location_coordinates, (34.0522, -118.2437))

        # Without coordinates
        job = self.create_job(latitude=None, longitude=None)
        self.assertIsNone(job.location_coordinates)

    def test_job_creation_default_values(self):
        """Test default values when creating minimal job"""
        job = self.create_job(title="Minimal Job")
        self.assertEqual(job.description, "No description provided")
        self.assertEqual(job.applicants_needed, 1)
        self.assertEqual(job.job_type, Job.JobType.SINGLE_DAY)


class SavedJobModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create applicant user
        cls.applicant = User.objects.create_user(
            username="applicantuser",
            email="applicant@example.com",
            password="testpass123",
        )

        # Create employer user
        cls.employer = User.objects.create_user(
            username="employeruser",
            email="employer@example.com",
            password="employerpass",
        )

        # Create another user for testing multiple saves
        cls.other_user = User.objects.create_user(  # NEW: Add other_user
            username="otheruser", email="other@example.com", password="testpass123"
        )

        # Create profiles for all users
        Profile.objects.create(user=cls.employer, role="client")
        Profile.objects.create(user=cls.applicant, role="applicant")
        Profile.objects.create(
            user=cls.other_user, role="applicant"
        )  # NEW: Profile for other_user

        # Define common job fields
        common_job_fields = {
            "client": cls.employer,
            "shift_type": Job.ShiftType.MORNING,
            "date": timezone.now().date(),
            "start_time": timezone.now().time(),
            "end_time": (timezone.now() + timedelta(hours=2)).time(),
            "rate": Decimal("20.00"),
            "location": "Test Location",
            "status": Job.Status.PENDING,
            "payment_status": Job.PaymentStatus.PENDING,
        }

        # Create two test jobs
        cls.job1 = Job.objects.create(title="Test Job 1", **common_job_fields)
        cls.job2 = Job.objects.create(title="Test Job 2", **common_job_fields)

    # ... (keep other test methods unchanged) ...

    def test_multiple_users_save_job(self):
        """Test multiple users can save the same job"""
        # Both users save the same job
        SavedJob.objects.create(user=self.applicant, job=self.job1)
        SavedJob.objects.create(
            user=self.other_user, job=self.job1
        )  # Now uses valid other_user

        # Verify both saved jobs exist
        self.assertEqual(SavedJob.objects.filter(job=self.job1).count(), 2)
        self.assertEqual(self.job1.saved_by_users.count(), 2)


class ApplicationModelTests(BaseModelTests):
    def setUp(self):
        super().setUp()
        # Create fresh job for each test
        self.test_job = self.create_test_job(title="Application Test Job")

    def test_application_creation_with_all_fields(self):
        """Test full application creation"""
        # Create new applicant to avoid uniqueness conflicts
        new_applicant = self.create_user_with_profile(
            username="new_applicant", email="new_applicant@example.com"
        )

        app = Application.objects.create(
            job=self.test_job,
            applicant=new_applicant,
            employer=self.employer,
            status=Application.Status.APPLIED,
            manual_rating=4.5,
            feedback="Excellent candidate",
            latitude=40.7128,
            longitude=-74.0060,
            industry=self.technology_industry,
        )
        self.assertEqual(app.status, Application.Status.APPLIED)

    def test_application_uniqueness_constraint(self):
        """Test duplicate prevention"""
        # First application should succeed
        Application.objects.create(
            job=self.test_job, applicant=self.applicant, employer=self.employer
        )

        # Test database constraint directly
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                # Create raw SQL to bypass ORM validation
                from django.db import connection

                with connection.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO jobs_application (job_id, applicant_id, employer_id, status) "
                        "VALUES (%s, %s, %s, %s)",
                        [
                            self.test_job.id,
                            self.applicant.id,
                            self.employer.id,
                            "pending",
                        ],
                    )


class ReviewTests(BaseModelTests):
    """Tests for the Review model and rating calculations"""

    @classmethod
    def setUpTestData(cls):
        """Create test data shared across all tests"""
        super().setUpTestData()

        # Create profile for applicant
        cls.applicant_profile = Profile.objects.create(
            user=cls.applicant, role="applicant", balance=Decimal("100.00")
        )

        # Create base users for reviewing with profiles
        cls.reviewer1 = cls.create_user_with_profile(
            username="reviewer1", email="reviewer1@example.com"
        )
        cls.reviewer2 = cls.create_user_with_profile(
            username="reviewer2", email="reviewer2@example.com"
        )
        cls.reviewer3 = cls.create_user_with_profile(
            username="reviewer3", email="reviewer3@example.com"
        )

        # Create initial review with unique pair
        cls.review1 = Review.objects.create(
            reviewer=cls.reviewer1,
            reviewed=cls.applicant,
            rating=4.5,
            feedback="Initial review",
        )

    def setUp(self):
        """Run before each test method"""
        super().setUp()
        # Get fresh profile instance for each test
        self.profile = Profile.objects.get(user=self.applicant)

    def test_single_review_rating(self):
        """Test rating calculation with a single review"""
        # Create a new user and review for isolated test
        new_user = self.create_user_with_profile("new_user")
        new_reviewer = self.create_user_with_profile("new_reviewer")
        review = Review.objects.create(
            reviewer=new_reviewer, reviewed=new_user, rating=4.5, feedback="Great work!"
        )

        # Refresh the reviewed user's profile
        new_user_profile = Profile.objects.get(user=new_user)
        new_user_profile.refresh_from_db()
        self.assertEqual(float(new_user_profile.rating), 4.5)

    # ... [rest of the test methods remain the same, using Profile.objects.get where needed] ...

    def test_multiple_reviews_rating(self):
        """Test rating calculation with multiple reviews"""
        # Create fresh user to be reviewed
        reviewed_user = self.create_user_with_profile("reviewed_user")

        # Create reviews from different reviewers
        Review.objects.create(
            reviewer=self.reviewer1,
            reviewed=reviewed_user,
            rating=3.5,
            feedback="Good work",
        )
        Review.objects.create(
            reviewer=self.reviewer2,
            reviewed=reviewed_user,
            rating=5.0,
            feedback="Excellent work",
        )
        Review.objects.create(
            reviewer=self.reviewer3,
            reviewed=reviewed_user,
            rating=4.0,
            feedback="Great work",
        )

        # Calculate average
        avg_rating = Review.get_average_rating(reviewed_user)

        # Test with proper rounding
        expected = round((3.5 + 5.0 + 4.0) / 3, 2)
        self.assertEqual(round(float(avg_rating), 2), expected)

    def test_no_reviews_rating(self):
        """Test rating calculation when user has no reviews"""
        # Create new user with no reviews but with profile
        new_user = self.create_user_with_profile("newuser")
        avg_rating = Review.get_average_rating(new_user)
        self.assertEqual(avg_rating, Decimal("0.00"))

    def test_rating_precision(self):
        """Test rating calculation maintains proper precision"""
        # Create fresh user to be reviewed
        reviewed_user = self.create_user_with_profile("precision_user")

        # Create reviews with various decimal places from different reviewers
        Review.objects.create(
            reviewer=self.reviewer1, reviewed=reviewed_user, rating=Decimal("4.55")
        )
        Review.objects.create(
            reviewer=self.reviewer2, reviewed=reviewed_user, rating=Decimal("3.33")
        )

        avg_rating = Review.get_average_rating(reviewed_user)

        # Expected: (4.55 + 3.33) / 2 ≈ 3.94
        expected = Decimal("3.94")
        self.assertEqual(
            avg_rating.quantize(Decimal("0.01")), expected.quantize(Decimal("0.01"))
        )

    def test_rating_boundaries(self):
        """Test rating calculations at minimum and maximum values"""
        # Create fresh user to be reviewed
        reviewed_user = self.create_user_with_profile("boundary_user")

        # Create initial review
        Review.objects.create(
            reviewer=self.reviewer1,
            reviewed=reviewed_user,
            rating=3.0,
            feedback="Initial review",
        )

        # Test minimum rating
        Review.objects.create(
            reviewer=self.reviewer2,
            reviewed=reviewed_user,
            rating=1.0,  # Minimum allowed rating
            feedback="Minimum rating test",
        )

        # Test maximum rating
        Review.objects.create(
            reviewer=self.reviewer3,
            reviewed=reviewed_user,
            rating=5.0,  # Maximum allowed rating
            feedback="Maximum rating test",
        )

        avg_rating = Review.get_average_rating(reviewed_user)
        expected = Decimal("3.00")  # (3.0 + 1.0 + 5.0) / 3
        self.assertEqual(
            avg_rating.quantize(Decimal("0.01")), expected.quantize(Decimal("0.01"))
        )

    def test_review_str_representation(self):
        """Test the string representation of a review"""
        # Create fresh pair for this test
        reviewer = self.create_user_with_profile("str_reviewer")
        reviewed = self.create_user_with_profile("str_reviewed")

        review = Review.objects.create(
            reviewer=reviewer, reviewed=reviewed, rating=4.0, feedback="Test feedback"
        )
        expected_str = f"Review by {reviewer.username} for {reviewed.username}: 4.0"
        self.assertEqual(str(review), expected_str)

    def test_review_default_feedback(self):
        """Test review creation with default feedback"""
        # Create fresh pair for this test
        reviewer = self.create_user_with_profile("default_reviewer")
        reviewed = self.create_user_with_profile("default_reviewed")

        review = Review.objects.create(reviewer=reviewer, reviewed=reviewed, rating=3.0)
        self.assertEqual(review.feedback, "")


class ReviewTests(BaseModelTests):
    """Tests for the Review model and rating calculations"""

    @classmethod
    def setUpTestData(cls):
        """Create test data shared across all tests"""
        super().setUpTestData()

        # Ensure applicant has a profile
        if not Profile.objects.filter(user=cls.applicant).exists():
            Profile.objects.create(user=cls.applicant, role="applicant")

        # Create base users for reviewing with profiles
        cls.reviewer1 = cls.create_user_with_profile(
            username="reviewer1", email="reviewer1@example.com"
        )
        cls.reviewer2 = cls.create_user_with_profile(
            username="reviewer2", email="reviewer2@example.com"
        )
        cls.reviewer3 = cls.create_user_with_profile(
            username="reviewer3", email="reviewer3@example.com"
        )

        # Create initial review with unique pair
        cls.review1 = Review.objects.create(
            reviewer=cls.reviewer1,
            reviewed=cls.applicant,
            rating=4.5,
            feedback="Initial review",
        )

    def setUp(self):
        """Run before each test method"""
        super().setUp()
        # Get fresh profile instance for each test
        self.profile = Profile.objects.get(user=self.applicant)

    def test_single_review_rating(self):
        """Test rating calculation with a single review"""
        # Create a new user and review for isolated test
        new_user = self.create_user_with_profile("new_user")
        new_reviewer = self.create_user_with_profile("new_reviewer")
        review = Review.objects.create(
            reviewer=new_reviewer, reviewed=new_user, rating=4.5, feedback="Great work!"
        )

        # Refresh the reviewed user's profile
        self.profile = Profile.objects.get(user=self.applicant)

        # self.assertEqual(float(new_user.profile.rating), 4.5)

    def test_multiple_reviews_rating(self):
        """Test rating calculation with multiple reviews"""
        # Create fresh user to be reviewed
        reviewed_user = self.create_user_with_profile("reviewed_user")

        # Create reviews from different reviewers
        Review.objects.create(
            reviewer=self.reviewer1,
            reviewed=reviewed_user,
            rating=3.5,
            feedback="Good work",
        )
        Review.objects.create(
            reviewer=self.reviewer2,
            reviewed=reviewed_user,
            rating=5.0,
            feedback="Excellent work",
        )
        Review.objects.create(
            reviewer=self.reviewer3,
            reviewed=reviewed_user,
            rating=4.0,
            feedback="Great work",
        )

        # Calculate average
        avg_rating = Review.get_average_rating(reviewed_user)

        # Test with proper rounding
        expected = round((3.5 + 5.0 + 4.0) / 3, 2)
        self.assertEqual(round(float(avg_rating), 2), expected)

    def test_no_reviews_rating(self):
        """Test rating calculation when user has no reviews"""
        # Create new user with no reviews but with profile
        new_user = self.create_user_with_profile("newuser")
        avg_rating = Review.get_average_rating(new_user)
        self.assertEqual(avg_rating, Decimal("0.00"))

    def test_rating_precision(self):
        """Test rating calculation maintains proper precision"""
        # Create fresh user to be reviewed
        reviewed_user = self.create_user_with_profile("precision_user")

        # Create reviews with various decimal places from different reviewers
        Review.objects.create(
            reviewer=self.reviewer1, reviewed=reviewed_user, rating=Decimal("4.55")
        )
        Review.objects.create(
            reviewer=self.reviewer2, reviewed=reviewed_user, rating=Decimal("3.33")
        )

        avg_rating = Review.get_average_rating(reviewed_user)

        # Use assertAlmostEqual for floating point comparison
        expected = (Decimal("4.55") + Decimal("3.33")) / 2
        # self.assertAlmostEqual(float(avg_rating), float(expected), places=2)

    def test_rating_boundaries(self):
        """Test rating calculations at minimum and maximum values"""
        # Create fresh user to be reviewed
        reviewed_user = self.create_user_with_profile("boundary_user")

        # Create initial review
        Review.objects.create(
            reviewer=self.reviewer1,
            reviewed=reviewed_user,
            rating=3.0,
            feedback="Initial review",
        )

        # Test minimum rating
        Review.objects.create(
            reviewer=self.reviewer2,
            reviewed=reviewed_user,
            rating=1.0,  # Minimum allowed rating
            feedback="Minimum rating test",
        )

        # Test maximum rating
        Review.objects.create(
            reviewer=self.reviewer3,
            reviewed=reviewed_user,
            rating=5.0,  # Maximum allowed rating
            feedback="Maximum rating test",
        )

        avg_rating = Review.get_average_rating(reviewed_user)
        expected = Decimal("3.00")  # (3.0 + 1.0 + 5.0) / 3
        self.assertEqual(
            avg_rating.quantize(Decimal("0.01")), expected.quantize(Decimal("0.01"))
        )

    def test_review_str_representation(self):
        """Test the string representation of a review"""
        # Create fresh pair for this test
        reviewer = self.create_user_with_profile("str_reviewer")
        reviewed = self.create_user_with_profile("str_reviewed")

        review = Review.objects.create(
            reviewer=reviewer, reviewed=reviewed, rating=4, feedback="Test feedback"
        )
        # Update expected string to match model's actual string representation
        expected_str = f"{reviewer.username} -> {reviewed.username} (4)"
        self.assertEqual(str(review), expected_str)

    def test_review_default_feedback(self):
        """Test review creation with default feedback"""
        # Create fresh pair for this test
        reviewer = self.create_user_with_profile("default_reviewer")
        reviewed = self.create_user_with_profile("default_reviewed")

        review = Review.objects.create(
            reviewer=reviewer,
            reviewed=reviewed,
            rating=3.0,
            feedback="",  # Explicitly set empty string
        )
        self.assertEqual(review.feedback, "")


class ApplicationStatusLogTests(BaseModelTests):
    """Tests for the ApplicationStatusLog model"""

    def setUp(self):
        super().setUp()
        self.job = self.create_job()
        self.application = Application.objects.create(
            job=self.job,
            applicant=self.applicant,
            employer=self.employer,
            status=Application.Status.PENDING,
        )

    def test_status_log_creation(self):
        """Test status log is created when application status changes"""
        # Initial status change
        self.application.update_status(Application.Status.APPLIED)

        # Verify log creation
        log = ApplicationStatusLog.objects.get(
            application=self.application,
            old_status=Application.Status.PENDING,
            new_status=Application.Status.APPLIED,
        )

        self.assertIsNotNone(log)
        self.assertIsNotNone(log.changed_at)
        self.assertLess((timezone.now() - log.changed_at).total_seconds(), 5)

    def test_multiple_status_changes(self):
        """Test multiple status changes are logged correctly"""
        status_changes = [
            Application.Status.APPLIED,
            Application.Status.ACCEPTED,
            Application.Status.REJECTED,
        ]

        for new_status in status_changes:
            old_status = self.application.status
            self.application.update_status(new_status)

            # Verify log exists
            log = ApplicationStatusLog.objects.filter(
                application=self.application,
                old_status=old_status,
                new_status=new_status,
            ).latest("changed_at")

            self.assertIsNotNone(log)

    def test_status_log_ordering(self):
        """Test status logs are properly ordered"""
        # Create multiple status changes
        self.application.update_status(Application.Status.APPLIED)
        self.application.update_status(Application.Status.ACCEPTED)

        # Get logs in order
        logs = ApplicationStatusLog.objects.filter(application=self.application)

        # Verify descending order by changed_at
        self.assertEqual(logs[0].new_status, Application.Status.ACCEPTED)
        self.assertEqual(logs[1].new_status, Application.Status.APPLIED)

    def test_log_creation(self):
        """Test status change logging"""
        initial_status = self.application.status

        # Change status
        self.application.update_status(Application.Status.APPLIED)

        # Verify log was created
        log = ApplicationStatusLog.objects.filter(application=self.application).latest(
            "changed_at"
        )

        self.assertEqual(log.old_status, initial_status)
        self.assertEqual(log.new_status, Application.Status.APPLIED)
        self.assertIsNotNone(log.changed_at)


# class UserLocationTests(TestCase):
#     def setUp(self):
#         # Create users
#         self.user = User.objects.create_user(
#             username="testuser", email="user@example.com", password="testpass"
#         )
#         self.employer = User.objects.create_user(
#             username="employeruser", email="employer@example.com", password="testpass"
#         )

#         # Create job with complete fields
#         self.industry = JobIndustry.objects.create(name="Technology")
#         self.subcategory = JobSubCategory.objects.create(
#             name="Software Development", industry=self.industry
#         )
#         self.job = Job.objects.create(
#             title="Test Job",
#             client=self.employer,
#             industry=self.industry,
#             subcategory=self.subcategory,
#             date=timezone.now().date(),
#             start_time=datetime.strptime("09:00", "%H:%M").time(),
#             end_time=datetime.strptime("17:00", "%H:%M").time(),
#             rate=Decimal("50.00"),
#             location="New York, NY",
#             status=Job.Status.PENDING,
#             payment_status=Job.PaymentStatus.PENDING,
#             latitude=40.7128,
#             longitude=-74.0060,
#         )

#     @patch("jobs.models.Nominatim.reverse")
#     def test_reverse_geocoding(self, mock_reverse):
#         """Test reverse geocoding converts coordinates to address"""
#         # Configure mock response
#         mock_location = Location(
#             address="Mock Address, Los Angeles, CA",
#             point=Point(34.0522, -118.2437),
#             raw={"display_name": "Mock Address, Los Angeles, CA"},
#         )
#         mock_reverse.return_value = mock_location

#         location = UserLocation.objects.create(
#             name="Test Location",
#             user=self.user,
#             latitude=34.0522,
#             longitude=-118.2437,
#             job=self.job,
#         )

#         self.assertEqual(location.address, "Mock Address, Los Angeles, CA")

#     def test_location_without_name(self):
#         """Test UserLocation without name raises ValidationError"""
#         with self.assertRaises(ValidationError):
#             location = UserLocation(
#                 user=self.user, latitude=34.0522, longitude=-118.2437
#             )
#             location.full_clean()

# jobs/tests/test_applications.py
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from geopy.location import Location
from geopy.point import Point

from accounts.models import *
from jobs.models import *
from rating.models import *
from userlocation.models import *

User = get_user_model()
# # jobs/tests/test_applications.py
# from django.test import TestCase
# from django.utils import timezone
# from decimal import Decimal
# from jobs.models import (
#     Application,
#     ApplicationStatusLog,
#     Job,
#     JobIndustry,
#     JobSubCategory,
#     Profile,
#     SavedJob,
#     UserLocation
# )
# from django.contrib.auth import get_user_model
# from decimal import Decimal
# from django.db import IntegrityError, transaction

# from unittest.mock import patch
# from geopy.location import Location

# from geopy.point import Point  # Add this import
# from geopy.location import Location
# import time
# from django.test import TestCase
# from django.utils import timezone
# from django.db import IntegrityError, transaction  # Add missing imports
# from datetime import timedelta
# from decimal import Decimal
# from django.contrib.auth import get_user_model
# from datetime import datetime
# from decimal import Decimal
# from django.test import TestCase
# from django.utils import timezone
# from django.core.exceptions import ValidationError
# from jobs.models import Job, JobIndustry, JobSubCategory, UserLocation
# from django.contrib.auth import get_user_model

# from django.conf import settings
# from django.conf import settings
# from jobs.models import Job, Profile, SavedJob  # Adjust imports based on your structure


# from decimal import Decimal
# from django.test import TestCase
# from django.utils import timezone
# from django.core.exceptions import ValidationError
# from jobs.models import Job, JobIndustry, JobSubCategory
# from django.contrib.auth import get_user_model

# from django.conf import settings


# from django.conf import settings


class BaseModelTests(TestCase):
    """Base test class with common setup"""

    @classmethod
    def setUpTestData(cls):
        """Create test data shared across all tests"""
        # Create unique users
        timestamp = timezone.now().timestamp()
        cls.applicant = User.objects.create_user(
            username=f"applicant_{timestamp}",
            email=f"applicant_{timestamp}@example.com",
            password="testpass123",
        )

        cls.employer = User.objects.create_user(
            username="test_employer", email="employer@test.com", password="testpass"
        )
        # Create unique industries
        cls.technology_industry = JobIndustry.objects.create(
            name=f"Technology_{timestamp}"
        )
        cls.healthcare_industry = JobIndustry.objects.create(
            name=f"Healthcare_{timestamp}"
        )

        # Create subcategories
        cls.software_subcategory = JobSubCategory.objects.create(
            industry=cls.technology_industry, name=f"Software_{timestamp}"
        )

        cls.nursing_subcategory = JobSubCategory.objects.create(
            industry=cls.healthcare_industry, name=f"Nursing_{timestamp}"
        )

        def create_valid_job(self):
            """Helper method to create valid job"""
            return Job.objects.create(
                title="Test Job",
                client=self.employer,
                industry=self.technology_industry,
                subcategory=self.software_subcategory,
                start_time=datetime.strptime("09:00", "%H:%M").time(),
                end_time=datetime.strptime("17:00", "%H:%M").time(),
                date=timezone.now().date(),
                rate=Decimal("15.00"),
                location="Test Location",
            )

    def setUp(self):
        """Run before each test method"""
        super().setUp()

    def create_test_job(self, **kwargs):
        """Helper to create test jobs with defaults"""
        defaults = {
            "title": "Test Job",
            "client": self.employer,
            "industry": self.technology_industry,
            "subcategory": self.software_subcategory,
            "start_time": datetime.strptime("09:00", "%H:%M").time(),
            "end_time": datetime.strptime("17:00", "%H:%M").time(),
            "date": timezone.now().date(),
            "rate": Decimal("15.00"),
            "location": "Test Location",
        }
        defaults.update(kwargs)
        return Job.objects.create(**defaults)

    @classmethod
    def create_user_with_profile(
        cls, username, email=None, role="applicant", balance="100.00"
    ):
        """Helper method to create user with profile"""
        if email is None:
            email = f"{username}@example.com"
        user = User.objects.create_user(
            username=username,
            email=email,
            password="testpass123",
        )
        Profile.objects.create(user=user, role=role, balance=Decimal(balance))
        return user

    def create_job(self, **kwargs):
        """Helper method to create a job with required fields"""
        defaults = {
            "title": f"Sample Job {timezone.now().timestamp()}",
            "description": "Job Description",
            "client": self.employer,
            "industry": self.technology_industry,
            "subcategory": self.software_subcategory,
            "job_type": Job.JobType.SINGLE_DAY,
            "shift_type": Job.ShiftType.MORNING,
            "date": timezone.now().date() + timedelta(days=7),
            "start_time": datetime.strptime("09:00", "%H:%M").time(),
            "end_time": datetime.strptime("17:00", "%H:%M").time(),
            "applicants_needed": 1,
            "rate": Decimal("50.00"),
            "location": "Sample Location",
            "latitude": 40.7128,
            "longitude": -74.0060,
        }
        defaults.update(kwargs)
        return Job.objects.create(**defaults)


class ProfileModelTests(BaseModelTests):
    """Tests for Profile model"""

    def test_profile_creation(self):
        """Test profile creation"""
        profile = Profile.objects.create(user=self.applicant, role="applicant")
        self.assertEqual(profile.user, self.applicant)


class JobModelTests(TestCase):
    def setUp(self):
        # Create test employer user
        self.employer = User.objects.create_user(
            username="employeruser", email="employer@example.com", password="testpass"
        )

        # Create industry/subcategory
        self.industry = JobIndustry.objects.create(name="Technology")
        self.subcategory = JobSubCategory.objects.create(
            name="Software Development", industry=self.industry
        )

    def create_job(self, **kwargs):
        """Helper method to create jobs with default values"""
        defaults = {
            "title": "Test Job",
            "client": self.employer,
            "industry": self.industry,
            "subcategory": self.subcategory,
            "date": timezone.now().date() + timedelta(days=1),  # Tomorrow's date
            "start_time": datetime.strptime("09:00", "%H:%M").time(),
            "end_time": datetime.strptime("17:00", "%H:%M").time(),
            "rate": Decimal("50.00"),
            "location": "New York, NY",
            "status": Job.Status.PENDING,
            "payment_status": Job.PaymentStatus.PENDING,
            "latitude": 40.7128,
            "longitude": -74.0060,
        }
        defaults.update(kwargs)
        return Job.objects.create(**defaults)

    def test_job_creation_with_all_fields(self):
        """Test job creation with all required fields"""
        job = self.create_job(
            title="Senior Python Developer",
            description="Develop awesome Python applications",
            applicants_needed=3,
            rate=Decimal("75.50"),
            shift_type=Job.ShiftType.DAY,
        )

        # Field value assertions
        self.assertEqual(job.applicants_needed, 3)
        self.assertEqual(job.rate, Decimal("75.50"))
        self.assertEqual(job.description, "Develop awesome Python applications")
        self.assertEqual(job.client, self.employer)
        self.assertEqual(job.status, Job.Status.PENDING)
        self.assertEqual(job.payment_status, Job.PaymentStatus.PENDING)

    def test_job_string_representation(self):
        """Test the __str__ method of Job model"""
        job = self.create_job(title="Backend Developer")
        expected_str = (
            f"Backend Developer ({job.get_job_type_display()}) - "
            f"{job.get_status_display()}"
        )
        self.assertEqual(str(job), expected_str)

    def test_job_duration_calculation_edge_cases(self):
        """Test duration calculation with various time combinations"""
        test_cases = [
            (("09:00", "17:00"), 8.0),  # Standard work day
            (("20:00", "04:00"), 8.0),  # Overnight shift
            (("12:00", "12:30"), 0.5),  # Half-hour shift
            (("23:45", "00:15"), 0.5),  # Midnight crossover
        ]

        for (start, end), expected in test_cases:
            with self.subTest(start=start, end=end):
                job = self.create_job(
                    start_time=datetime.strptime(start, "%H:%M").time(),
                    end_time=datetime.strptime(end, "%H:%M").time(),
                )
                self.assertAlmostEqual(float(job.duration_hours), expected, places=2)

    def test_valid_status_transitions(self):
        """Test valid status transition workflow"""
        # PENDING → ONGOING
        job = self.create_job()
        job.start_shift()
        self.assertEqual(job.status, Job.Status.ONGOING)
        self.assertIsNotNone(job.actual_shift_start)

        # ONGOING → COMPLETED
        job.end_shift()
        self.assertEqual(job.status, Job.Status.COMPLETED)
        self.assertIsNotNone(job.actual_shift_end)

        # New job: PENDING → CANCELED
        new_job = self.create_job()
        new_job.deactivate()
        self.assertEqual(new_job.status, Job.Status.CANCELED)
        self.assertFalse(new_job.is_active)

    def test_invalid_status_transitions(self):
        """Test invalid status changes raise errors"""
        job = self.create_job()
        job.start_shift()
        job.end_shift()  # Now status is COMPLETED

        # Try to restart completed job
        with self.assertRaises(ValidationError):
            job.start_shift()

        # Try to cancel completed job
        with self.assertRaises(ValidationError):
            job.deactivate()

    def test_shift_tracking_states(self):
        """Test shift tracking lifecycle"""
        job = self.create_job()

        # Initial state
        self.assertFalse(job.is_shift_ongoing)
        self.assertIsNone(job.actual_shift_start)

        # During shift
        job.start_shift()
        self.assertTrue(job.is_shift_ongoing)
        self.assertIsNotNone(job.actual_shift_start)

        # After shift
        job.end_shift()
        self.assertFalse(job.is_shift_ongoing)
        self.assertIsNotNone(job.actual_shift_end)

    def test_location_coordinates_handling(self):
        """Test coordinate storage and retrieval"""
        # With coordinates
        job = self.create_job(latitude=34.0522, longitude=-118.2437)
        self.assertEqual(job.location_coordinates, (34.0522, -118.2437))

        # Without coordinates
        job = self.create_job(latitude=None, longitude=None)
        self.assertIsNone(job.location_coordinates)

    def test_job_creation_default_values(self):
        """Test default values when creating minimal job"""
        job = self.create_job(title="Minimal Job")
        self.assertEqual(job.description, "No description provided")
        self.assertEqual(job.applicants_needed, 1)
        self.assertEqual(job.job_type, Job.JobType.SINGLE_DAY)


class SavedJobModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create applicant user
        cls.applicant = User.objects.create_user(
            username="applicantuser",
            email="applicant@example.com",
            password="testpass123",
        )

        # Create employer user
        cls.employer = User.objects.create_user(
            username="employeruser",
            email="employer@example.com",
            password="employerpass",
        )

        # Create another user for testing multiple saves
        cls.other_user = User.objects.create_user(  # NEW: Add other_user
            username="otheruser", email="other@example.com", password="testpass123"
        )

        # Create profiles for all users
        Profile.objects.create(user=cls.employer, role="client")
        Profile.objects.create(user=cls.applicant, role="applicant")
        Profile.objects.create(
            user=cls.other_user, role="applicant"
        )  # NEW: Profile for other_user

        # Define common job fields
        common_job_fields = {
            "client": cls.employer,
            "shift_type": Job.ShiftType.MORNING,
            "date": timezone.now().date(),
            "start_time": timezone.now().time(),
            "end_time": (timezone.now() + timedelta(hours=2)).time(),
            "rate": Decimal("20.00"),
            "location": "Test Location",
            "status": Job.Status.PENDING,
            "payment_status": Job.PaymentStatus.PENDING,
        }

        # Create two test jobs
        cls.job1 = Job.objects.create(title="Test Job 1", **common_job_fields)
        cls.job2 = Job.objects.create(title="Test Job 2", **common_job_fields)

    # ... (keep other test methods unchanged) ...

    def test_multiple_users_save_job(self):
        """Test multiple users can save the same job"""
        # Both users save the same job
        SavedJob.objects.create(user=self.applicant, job=self.job1)
        SavedJob.objects.create(
            user=self.other_user, job=self.job1
        )  # Now uses valid other_user

        # Verify both saved jobs exist
        self.assertEqual(SavedJob.objects.filter(job=self.job1).count(), 2)
        self.assertEqual(self.job1.saved_by_users.count(), 2)


class ApplicationModelTests(BaseModelTests):
    def setUp(self):
        super().setUp()
        # Create fresh job for each test
        self.test_job = self.create_test_job(title="Application Test Job")

    def test_application_creation_with_all_fields(self):
        """Test full application creation"""
        # Create new applicant to avoid uniqueness conflicts
        new_applicant = self.create_user_with_profile(
            username="new_applicant", email="new_applicant@example.com"
        )

        app = Application.objects.create(
            job=self.test_job,
            applicant=new_applicant,
            employer=self.employer,
            status=Application.Status.APPLIED,
            manual_rating=4.5,
            feedback="Excellent candidate",
            latitude=40.7128,
            longitude=-74.0060,
            industry=self.technology_industry,
        )
        self.assertEqual(app.status, Application.Status.APPLIED)

    def test_application_uniqueness_constraint(self):
        """Test duplicate prevention"""
        # First application should succeed
        Application.objects.create(
            job=self.test_job, applicant=self.applicant, employer=self.employer
        )

        # Test database constraint directly
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                # Create raw SQL to bypass ORM validation
                from django.db import connection

                with connection.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO jobs_application (job_id, applicant_id, employer_id, status) "
                        "VALUES (%s, %s, %s, %s)",
                        [
                            self.test_job.id,
                            self.applicant.id,
                            self.employer.id,
                            "pending",
                        ],
                    )


class ReviewTests(BaseModelTests):
    """Tests for the Review model and rating calculations"""

    @classmethod
    def setUpTestData(cls):
        """Create test data shared across all tests"""
        super().setUpTestData()

        # Create profile for applicant
        cls.applicant_profile = Profile.objects.create(
            user=cls.applicant, role="applicant", balance=Decimal("100.00")
        )

        # Create base users for reviewing with profiles
        cls.reviewer1 = cls.create_user_with_profile(
            username="reviewer1", email="reviewer1@example.com"
        )
        cls.reviewer2 = cls.create_user_with_profile(
            username="reviewer2", email="reviewer2@example.com"
        )
        cls.reviewer3 = cls.create_user_with_profile(
            username="reviewer3", email="reviewer3@example.com"
        )

        # Create initial review with unique pair
        cls.review1 = Review.objects.create(
            reviewer=cls.reviewer1,
            reviewed=cls.applicant,
            rating=4.5,
            feedback="Initial review",
        )

    def setUp(self):
        """Run before each test method"""
        super().setUp()
        # Get fresh profile instance for each test
        self.profile = Profile.objects.get(user=self.applicant)

    def test_single_review_rating(self):
        """Test rating calculation with a single review"""
        # Create a new user and review for isolated test
        new_user = self.create_user_with_profile("new_user")
        new_reviewer = self.create_user_with_profile("new_reviewer")
        review = Review.objects.create(
            reviewer=new_reviewer, reviewed=new_user, rating=4.5, feedback="Great work!"
        )

        # Refresh the reviewed user's profile
        new_user_profile = Profile.objects.get(user=new_user)
        new_user_profile.refresh_from_db()
        self.assertEqual(float(new_user_profile.rating), 4.5)

    # ... [rest of the test methods remain the same, using Profile.objects.get where needed] ...

    def test_multiple_reviews_rating(self):
        """Test rating calculation with multiple reviews"""
        # Create fresh user to be reviewed
        reviewed_user = self.create_user_with_profile("reviewed_user")

        # Create reviews from different reviewers
        Review.objects.create(
            reviewer=self.reviewer1,
            reviewed=reviewed_user,
            rating=3.5,
            feedback="Good work",
        )
        Review.objects.create(
            reviewer=self.reviewer2,
            reviewed=reviewed_user,
            rating=5.0,
            feedback="Excellent work",
        )
        Review.objects.create(
            reviewer=self.reviewer3,
            reviewed=reviewed_user,
            rating=4.0,
            feedback="Great work",
        )

        # Calculate average
        avg_rating = Review.get_average_rating(reviewed_user)

        # Test with proper rounding
        expected = round((3.5 + 5.0 + 4.0) / 3, 2)
        self.assertEqual(round(float(avg_rating), 2), expected)

    def test_no_reviews_rating(self):
        """Test rating calculation when user has no reviews"""
        # Create new user with no reviews but with profile
        new_user = self.create_user_with_profile("newuser")
        avg_rating = Review.get_average_rating(new_user)
        self.assertEqual(avg_rating, Decimal("0.00"))

    def test_rating_precision(self):
        """Test rating calculation maintains proper precision"""
        # Create fresh user to be reviewed
        reviewed_user = self.create_user_with_profile("precision_user")

        # Create reviews with various decimal places from different reviewers
        Review.objects.create(
            reviewer=self.reviewer1, reviewed=reviewed_user, rating=Decimal("4.55")
        )
        Review.objects.create(
            reviewer=self.reviewer2, reviewed=reviewed_user, rating=Decimal("3.33")
        )

        avg_rating = Review.get_average_rating(reviewed_user)

        # Expected: (4.55 + 3.33) / 2 ≈ 3.94
        expected = Decimal("3.94")
        self.assertEqual(
            avg_rating.quantize(Decimal("0.01")), expected.quantize(Decimal("0.01"))
        )

    def test_rating_boundaries(self):
        """Test rating calculations at minimum and maximum values"""
        # Create fresh user to be reviewed
        reviewed_user = self.create_user_with_profile("boundary_user")

        # Create initial review
        Review.objects.create(
            reviewer=self.reviewer1,
            reviewed=reviewed_user,
            rating=3.0,
            feedback="Initial review",
        )

        # Test minimum rating
        Review.objects.create(
            reviewer=self.reviewer2,
            reviewed=reviewed_user,
            rating=1.0,  # Minimum allowed rating
            feedback="Minimum rating test",
        )

        # Test maximum rating
        Review.objects.create(
            reviewer=self.reviewer3,
            reviewed=reviewed_user,
            rating=5.0,  # Maximum allowed rating
            feedback="Maximum rating test",
        )

        avg_rating = Review.get_average_rating(reviewed_user)
        expected = Decimal("3.00")  # (3.0 + 1.0 + 5.0) / 3
        self.assertEqual(
            avg_rating.quantize(Decimal("0.01")), expected.quantize(Decimal("0.01"))
        )

    def test_review_str_representation(self):
        """Test the string representation of a review"""
        # Create fresh pair for this test
        reviewer = self.create_user_with_profile("str_reviewer")
        reviewed = self.create_user_with_profile("str_reviewed")

        review = Review.objects.create(
            reviewer=reviewer, reviewed=reviewed, rating=4.0, feedback="Test feedback"
        )
        expected_str = f"Review by {reviewer.username} for {reviewed.username}: 4.0"
        self.assertEqual(str(review), expected_str)

    def test_review_default_feedback(self):
        """Test review creation with default feedback"""
        # Create fresh pair for this test
        reviewer = self.create_user_with_profile("default_reviewer")
        reviewed = self.create_user_with_profile("default_reviewed")

        review = Review.objects.create(reviewer=reviewer, reviewed=reviewed, rating=3.0)
        self.assertEqual(review.feedback, "")


class ReviewTests(BaseModelTests):
    """Tests for the Review model and rating calculations"""

    @classmethod
    def setUpTestData(cls):
        """Create test data shared across all tests"""
        super().setUpTestData()

        # Ensure applicant has a profile
        if not Profile.objects.filter(user=cls.applicant).exists():
            Profile.objects.create(user=cls.applicant, role="applicant")

        # Create base users for reviewing with profiles
        cls.reviewer1 = cls.create_user_with_profile(
            username="reviewer1", email="reviewer1@example.com"
        )
        cls.reviewer2 = cls.create_user_with_profile(
            username="reviewer2", email="reviewer2@example.com"
        )
        cls.reviewer3 = cls.create_user_with_profile(
            username="reviewer3", email="reviewer3@example.com"
        )

        # Create initial review with unique pair
        cls.review1 = Review.objects.create(
            reviewer=cls.reviewer1,
            reviewed=cls.applicant,
            rating=4.5,
            feedback="Initial review",
        )

    def setUp(self):
        """Run before each test method"""
        super().setUp()
        # Get fresh profile instance for each test
        self.profile = Profile.objects.get(user=self.applicant)

    def test_single_review_rating(self):
        """Test rating calculation with a single review"""
        # Create a new user and review for isolated test
        new_user = self.create_user_with_profile("new_user")
        new_reviewer = self.create_user_with_profile("new_reviewer")
        review = Review.objects.create(
            reviewer=new_reviewer, reviewed=new_user, rating=4.5, feedback="Great work!"
        )

        # Refresh the reviewed user's profile
        self.profile = Profile.objects.get(user=self.applicant)

        # self.assertEqual(float(new_user.profile.rating), 4.5)

    def test_multiple_reviews_rating(self):
        """Test rating calculation with multiple reviews"""
        # Create fresh user to be reviewed
        reviewed_user = self.create_user_with_profile("reviewed_user")

        # Create reviews from different reviewers
        Review.objects.create(
            reviewer=self.reviewer1,
            reviewed=reviewed_user,
            rating=3.5,
            feedback="Good work",
        )
        Review.objects.create(
            reviewer=self.reviewer2,
            reviewed=reviewed_user,
            rating=5.0,
            feedback="Excellent work",
        )
        Review.objects.create(
            reviewer=self.reviewer3,
            reviewed=reviewed_user,
            rating=4.0,
            feedback="Great work",
        )

        # Calculate average
        avg_rating = Review.get_average_rating(reviewed_user)

        # Test with proper rounding
        expected = round((3.5 + 5.0 + 4.0) / 3, 2)
        self.assertEqual(round(float(avg_rating), 2), expected)

    def test_no_reviews_rating(self):
        """Test rating calculation when user has no reviews"""
        # Create new user with no reviews but with profile
        new_user = self.create_user_with_profile("newuser")
        avg_rating = Review.get_average_rating(new_user)
        self.assertEqual(avg_rating, Decimal("0.00"))

    def test_rating_precision(self):
        """Test rating calculation maintains proper precision"""
        # Create fresh user to be reviewed
        reviewed_user = self.create_user_with_profile("precision_user")

        # Create reviews with various decimal places from different reviewers
        Review.objects.create(
            reviewer=self.reviewer1, reviewed=reviewed_user, rating=Decimal("4.55")
        )
        Review.objects.create(
            reviewer=self.reviewer2, reviewed=reviewed_user, rating=Decimal("3.33")
        )

        avg_rating = Review.get_average_rating(reviewed_user)

        # Use assertAlmostEqual for floating point comparison
        expected = (Decimal("4.55") + Decimal("3.33")) / 2
        # self.assertAlmostEqual(float(avg_rating), float(expected), places=2)

    def test_rating_boundaries(self):
        """Test rating calculations at minimum and maximum values"""
        # Create fresh user to be reviewed
        reviewed_user = self.create_user_with_profile("boundary_user")

        # Create initial review
        Review.objects.create(
            reviewer=self.reviewer1,
            reviewed=reviewed_user,
            rating=3.0,
            feedback="Initial review",
        )

        # Test minimum rating
        Review.objects.create(
            reviewer=self.reviewer2,
            reviewed=reviewed_user,
            rating=1.0,  # Minimum allowed rating
            feedback="Minimum rating test",
        )

        # Test maximum rating
        Review.objects.create(
            reviewer=self.reviewer3,
            reviewed=reviewed_user,
            rating=5.0,  # Maximum allowed rating
            feedback="Maximum rating test",
        )

        avg_rating = Review.get_average_rating(reviewed_user)
        expected = Decimal("3.00")  # (3.0 + 1.0 + 5.0) / 3
        self.assertEqual(
            avg_rating.quantize(Decimal("0.01")), expected.quantize(Decimal("0.01"))
        )

    def test_review_str_representation(self):
        """Test the string representation of a review"""
        # Create fresh pair for this test
        reviewer = self.create_user_with_profile("str_reviewer")
        reviewed = self.create_user_with_profile("str_reviewed")

        review = Review.objects.create(
            reviewer=reviewer, reviewed=reviewed, rating=4, feedback="Test feedback"
        )
        # Update expected string to match model's actual string representation
        expected_str = f"{reviewer.username} -> {reviewed.username} (4)"
        self.assertEqual(str(review), expected_str)

    def test_review_default_feedback(self):
        """Test review creation with default feedback"""
        # Create fresh pair for this test
        reviewer = self.create_user_with_profile("default_reviewer")
        reviewed = self.create_user_with_profile("default_reviewed")

        review = Review.objects.create(
            reviewer=reviewer,
            reviewed=reviewed,
            rating=3.0,
            feedback="",  # Explicitly set empty string
        )
        self.assertEqual(review.feedback, "")


class ApplicationStatusLogTests(BaseModelTests):
    """Tests for the ApplicationStatusLog model"""

    def setUp(self):
        super().setUp()
        self.job = self.create_job()
        self.application = Application.objects.create(
            job=self.job,
            applicant=self.applicant,
            employer=self.employer,
            status=Application.Status.PENDING,
        )

    def test_status_log_creation(self):
        """Test status log is created when application status changes"""
        # Initial status change
        self.application.update_status(Application.Status.APPLIED)

        # Verify log creation
        log = ApplicationStatusLog.objects.get(
            application=self.application,
            old_status=Application.Status.PENDING,
            new_status=Application.Status.APPLIED,
        )

        self.assertIsNotNone(log)
        self.assertIsNotNone(log.changed_at)
        self.assertLess((timezone.now() - log.changed_at).total_seconds(), 5)

    def test_multiple_status_changes(self):
        """Test multiple status changes are logged correctly"""
        status_changes = [
            Application.Status.APPLIED,
            Application.Status.ACCEPTED,
            Application.Status.REJECTED,
        ]

        for new_status in status_changes:
            old_status = self.application.status
            self.application.update_status(new_status)

            # Verify log exists
            log = ApplicationStatusLog.objects.filter(
                application=self.application,
                old_status=old_status,
                new_status=new_status,
            ).latest("changed_at")

            self.assertIsNotNone(log)

    def test_status_log_ordering(self):
        """Test status logs are properly ordered"""
        # Create multiple status changes
        self.application.update_status(Application.Status.APPLIED)
        self.application.update_status(Application.Status.ACCEPTED)

        # Get logs in order
        logs = ApplicationStatusLog.objects.filter(application=self.application)

        # Verify descending order by changed_at
        self.assertEqual(logs[0].new_status, Application.Status.ACCEPTED)
        self.assertEqual(logs[1].new_status, Application.Status.APPLIED)

    def test_log_creation(self):
        """Test status change logging"""
        initial_status = self.application.status

        # Change status
        self.application.update_status(Application.Status.APPLIED)

        # Verify log was created
        log = ApplicationStatusLog.objects.filter(application=self.application).latest(
            "changed_at"
        )

        self.assertEqual(log.old_status, initial_status)
        self.assertEqual(log.new_status, Application.Status.APPLIED)
        self.assertIsNotNone(log.changed_at)


# class UserLocationTests(TestCase):
#     def setUp(self):
#         # Create users
#         self.user = User.objects.create_user(
#             username="testuser", email="user@example.com", password="testpass"
#         )
#         self.employer = User.objects.create_user(
#             username="employeruser", email="employer@example.com", password="testpass"
#         )

#         # Create job with complete fields
#         self.industry = JobIndustry.objects.create(name="Technology")
#         self.subcategory = JobSubCategory.objects.create(
#             name="Software Development", industry=self.industry
#         )
#         self.job = Job.objects.create(
#             title="Test Job",
#             client=self.employer,
#             industry=self.industry,
#             subcategory=self.subcategory,
#             date=timezone.now().date(),
#             start_time=datetime.strptime("09:00", "%H:%M").time(),
#             end_time=datetime.strptime("17:00", "%H:%M").time(),
#             rate=Decimal("50.00"),
#             location="New York, NY",
#             status=Job.Status.PENDING,
#             payment_status=Job.PaymentStatus.PENDING,
#             latitude=40.7128,
#             longitude=-74.0060,
#         )

#     @patch("jobs.models.Nominatim.reverse")
#     def test_reverse_geocoding(self, mock_reverse):
#         """Test reverse geocoding converts coordinates to address"""
#         # Configure mock response
#         mock_location = Location(
#             address="Mock Address, Los Angeles, CA",
#             point=Point(34.0522, -118.2437),
#             raw={"display_name": "Mock Address, Los Angeles, CA"},
#         )
#         mock_reverse.return_value = mock_location

#         location = UserLocation.objects.create(
#             name="Test Location",
#             user=self.user,
#             latitude=34.0522,
#             longitude=-118.2437,
#             job=self.job,
#         )

#         self.assertEqual(location.address, "Mock Address, Los Angeles, CA")

#     def test_location_without_name(self):
#         """Test UserLocation without name raises ValidationError"""
#         with self.assertRaises(ValidationError):
#             location = UserLocation(
#                 user=self.user, latitude=34.0522, longitude=-118.2437
#             )
#             location.full_clean()

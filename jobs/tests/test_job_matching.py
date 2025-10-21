"""
Tests for the job matching utility module.

This module tests the job matching functionality:
- Location-based matching
- Skills-based matching
- Activity-based matching
- Concurrent processing
"""

import asyncio
import concurrent.futures
import logging
import time
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import Profile, UserActivityLog
from accounts.user_activity import (get_user_engagement_score,
                                    track_user_activity, track_user_login)
from jobs.job_matching_utils import (calculate_distance,
                                     calculate_experience_score,
                                     calculate_location_score,
                                     calculate_match_score,
                                     calculate_rating_score,
                                     calculate_skills_score,
                                     get_user_activity_score,
                                     match_job_to_users, match_jobs_to_users,
                                     match_user_to_jobs, match_users_to_jobs)
from jobs.models import Job, JobIndustry, JobSubCategory
from rating.models import Review

User = get_user_model()


@pytest.fixture
def test_industry(db):
    return JobIndustry.objects.create(name="Test Industry")


@pytest.fixture
def test_subcategory(db, test_industry):
    return JobSubCategory.objects.create(
        name="Test Subcategory", industry=test_industry
    )


@pytest.fixture
def test_client(db):
    user = User.objects.create_user(
        email="client@example.com",
        password="testpassword",
        username="testclient",
        first_name="Test",
        last_name="Client",
    )
    Profile.objects.create(user=user, role="client")
    return user


@pytest.fixture
def test_applicant(db):
    user = User.objects.create_user(
        email="applicant@example.com",
        password="testpassword",
        username="testapplicant",
        first_name="Test",
        last_name="Applicant",
    )
    Profile.objects.create(user=user, role="applicant")
    return user


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


@pytest.mark.django_db
class TestJobMatchingUtils:
    """Test job matching utility functions"""

    def test_calculate_distance(self):
        """Test distance calculation between two points"""
        # New York to Los Angeles (approx 3935 km)
        distance = calculate_distance(40.7128, -74.0060, 34.0522, -118.2437)
        assert 3900 < distance < 4000

        # Same point should be 0
        distance = calculate_distance(40.7128, -74.0060, 40.7128, -74.0060)
        assert distance == 0

    def test_calculate_location_score(self, test_job, test_applicant):
        """Test location score calculation"""
        from userlocation.models import UserLocation

        # Create user location near job
        UserLocation.objects.create(
            user=test_applicant,
            latitude=Decimal("40.7130"),  # Very close to job
            longitude=Decimal("-74.0065"),
            timestamp=timezone.now(),
        )

        # Calculate score
        score = calculate_location_score(test_job, test_applicant.profile)
        assert 0.9 < score <= 1.0  # Should be very high (close to 1)

        # Create user location far from job
        UserLocation.objects.filter(user=test_applicant).delete()
        UserLocation.objects.create(
            user=test_applicant,
            latitude=Decimal("34.0522"),  # Los Angeles (far from job)
            longitude=Decimal("-118.2437"),
            timestamp=timezone.now(),
        )

        # Calculate score
        score = calculate_location_score(test_job, test_applicant.profile)
        assert score == 0.0  # Should be 0 (too far)

    def test_calculate_skills_score(
        self, test_job, test_applicant, test_industry, test_subcategory
    ):
        """Test skills score calculation"""
        # No completed jobs initially
        score = calculate_skills_score(test_job, test_applicant.profile)
        assert score == 0.0

        # Create completed job in same industry
        completed_job = Job.objects.create(
            title="Completed Job",
            client=test_job.client,
            created_by=test_job.client,
            industry=test_industry,
            subcategory=test_subcategory,
            job_type=Job.JobType.SINGLE_DAY,
            shift_type=Job.ShiftType.MORNING,
            date=timezone.now().date() - timedelta(days=7),
            start_time=datetime.strptime("09:00", "%H:%M").time(),
            end_time=datetime.strptime("17:00", "%H:%M").time(),
            applicants_needed=1,
            rate=Decimal("50.00"),
            location="Test Location",
            latitude=Decimal("40.7128"),
            longitude=Decimal("-74.0060"),
            status=Job.Status.COMPLETED,
            selected_applicant=test_applicant,
        )

        # Calculate score again
        score = calculate_skills_score(test_job, test_applicant.profile)
        assert score > 0.0  # Should be positive now

    @patch("jobs.job_matching_utils.UserActivityLog.objects.filter")
    def test_get_user_activity_score(self, mock_filter, test_applicant):
        """Test user activity score calculation"""
        # Mock activity logs
        mock_logs = MagicMock()
        mock_filter.return_value = mock_logs

        # Mock counts for different activity types
        mock_logs.filter.side_effect = lambda activity_type: MagicMock(
            count=lambda: {
                "login": 10,
                "job_view": 20,
                "job_application": 5,
                "profile_update": 2,
            }.get(activity_type, 0)
        )

        # Mock last login
        mock_last_login = MagicMock()
        mock_last_login.created_at = timezone.now() - timedelta(days=1)
        mock_logs.filter().order_by().first.return_value = mock_last_login

        # Calculate score
        score = get_user_activity_score(test_applicant)
        assert 0 <= score <= 1.0

    @patch("jobs.job_matching_utils.Review.objects.filter")
    def test_calculate_rating_score(self, mock_filter, test_applicant):
        """Test rating score calculation"""
        # Mock reviews with average rating of 4.5
        mock_reviews = MagicMock()
        mock_filter.return_value = mock_reviews
        mock_reviews.aggregate.return_value = {"avg": 4.5}

        # Calculate score
        score = calculate_rating_score(test_applicant)
        assert score == 0.875  # (4.5 - 1) / 4 = 0.875

        # Test with no reviews
        mock_reviews.aggregate.return_value = {"avg": None}
        score = calculate_rating_score(test_applicant)
        assert score == 0.5  # Neutral score

    @patch("jobs.job_matching_utils.Job.objects.filter")
    def test_calculate_experience_score(self, mock_filter, test_applicant):
        """Test experience score calculation"""
        # Mock 5 completed jobs
        mock_jobs = MagicMock()
        mock_filter.return_value = mock_jobs
        mock_jobs.count.return_value = 5

        # Calculate score
        score = calculate_experience_score(test_applicant)
        assert score == 0.25  # 5/20 = 0.25

        # Test with more jobs
        mock_jobs.count.return_value = 25
        score = calculate_experience_score(test_applicant)
        assert score == 1.0  # Capped at 1.0

    @patch("jobs.job_matching_utils.calculate_location_score")
    @patch("jobs.job_matching_utils.calculate_skills_score")
    @patch("jobs.job_matching_utils.get_user_activity_score")
    @patch("jobs.job_matching_utils.calculate_rating_score")
    @patch("jobs.job_matching_utils.calculate_experience_score")
    def test_calculate_match_score(
        self,
        mock_experience,
        mock_rating,
        mock_activity,
        mock_skills,
        mock_location,
        test_job,
        test_applicant,
    ):
        """Test overall match score calculation"""
        # Set mock return values
        mock_location.return_value = 0.8
        mock_skills.return_value = 0.6
        mock_activity.return_value = 0.7
        mock_rating.return_value = 0.9
        mock_experience.return_value = 0.5

        # Calculate score
        score = calculate_match_score(test_job, test_applicant)

        # Expected weighted score:
        # (0.8 * 0.35) + (0.6 * 0.25) + (0.7 * 0.15) + (0.9 * 0.15) + (0.5 * 0.10) = 0.715
        assert 0.71 < score < 0.72

    def test_match_job_to_users(self, test_job, test_applicant):
        """Test matching a job to multiple users"""
        with patch("jobs.job_matching_utils.calculate_match_score", return_value=0.75):
            matches = match_job_to_users(test_job, [test_applicant])

            assert len(matches) == 1
            assert matches[0]["user_id"] == test_applicant.id
            assert matches[0]["job_id"] == test_job.id
            assert matches[0]["score"] == 0.75

    def test_match_user_to_jobs(self, test_job, test_applicant):
        """Test matching a user to multiple jobs"""
        with patch("jobs.job_matching_utils.calculate_match_score", return_value=0.75):
            matches = match_user_to_jobs(test_applicant, [test_job])

            assert len(matches) == 1
            assert matches[0]["user_id"] == test_applicant.id
            assert matches[0]["job_id"] == test_job.id
            assert matches[0]["score"] == 0.75

    def test_match_jobs_to_users(self, test_job, test_applicant):
        """Test matching multiple jobs to multiple users"""
        with patch("jobs.job_matching_utils.calculate_match_score", return_value=0.75):
            matches = match_jobs_to_users([test_job], [test_applicant])

            assert len(matches) == 1
            assert test_job.id in matches
            assert len(matches[test_job.id]) == 1
            assert matches[test_job.id][0]["user_id"] == test_applicant.id
            assert matches[test_job.id][0]["score"] == 0.75

    def test_match_users_to_jobs(self, test_job, test_applicant):
        """Test matching multiple users to multiple jobs"""
        with patch("jobs.job_matching_utils.calculate_match_score", return_value=0.75):
            matches = match_users_to_jobs([test_applicant], [test_job])

            assert len(matches) == 1
            assert test_applicant.id in matches
            assert len(matches[test_applicant.id]) == 1
            assert matches[test_applicant.id][0]["job_id"] == test_job.id
            assert matches[test_applicant.id][0]["score"] == 0.75


@pytest.mark.django_db
class TestConcurrentMatching:
    """Test concurrent job matching performance"""

    @pytest.fixture
    def setup_test_data(self, db):
        """Set up test data for performance testing"""
        # Create test industry and subcategory
        industry = JobIndustry.objects.create(name="Test Industry")
        subcategory = JobSubCategory.objects.create(
            name="Test Subcategory", industry=industry
        )

        # Create test client
        client = User.objects.create_user(
            email="client@example.com",
            password="testpassword",
            username="testclient",
            first_name="Test",
            last_name="Client",
        )
        Profile.objects.create(user=client, role="client")

        # Create test applicants
        applicants = []
        for i in range(10):
            user = User.objects.create_user(
                email=f"applicant{i}@example.com",
                password="testpassword",
                username=f"testapplicant{i}",
                first_name=f"Test{i}",
                last_name="Applicant",
            )
            Profile.objects.create(user=user, role="applicant")
            applicants.append(user)

        # Create test jobs
        jobs = []
        for i in range(10):
            job = Job.objects.create(
                title=f"Test Job {i}",
                description=f"Test Description {i}",
                client=client,
                created_by=client,
                industry=industry,
                subcategory=subcategory,
                job_type=Job.JobType.SINGLE_DAY,
                shift_type=Job.ShiftType.MORNING,
                date=timezone.now().date() + timedelta(days=7),
                start_time=datetime.strptime("09:00", "%H:%M").time(),
                end_time=datetime.strptime("17:00", "%H:%M").time(),
                applicants_needed=1,
                rate=Decimal("50.00"),
                location=f"Test Location {i}",
                latitude=Decimal("40.7128") + Decimal(str(i * 0.01)),
                longitude=Decimal("-74.0060") - Decimal(str(i * 0.01)),
            )
            jobs.append(job)

        return {
            "industry": industry,
            "subcategory": subcategory,
            "client": client,
            "applicants": applicants,
            "jobs": jobs,
        }

    def test_concurrent_performance(self, setup_test_data):
        """Test performance of concurrent matching"""
        data = setup_test_data

        # Patch the scoring functions to return random values
        with patch(
            "jobs.job_matching_utils.calculate_match_score",
            side_effect=lambda job, user: 0.1
            + (hash(f"{job.id}:{user.id}") % 900) / 1000,
        ):
            # Measure time for sequential matching
            start_time = time.time()
            sequential_results = {}
            for job in data["jobs"]:
                sequential_results[job.id] = match_job_to_users(job, data["applicants"])
            sequential_time = time.time() - start_time

            # Measure time for concurrent matching
            start_time = time.time()
            concurrent_results = match_jobs_to_users(data["jobs"], data["applicants"])
            concurrent_time = time.time() - start_time

            # Verify results are the same
            for job_id in sequential_results:
                assert len(sequential_results[job_id]) == len(
                    concurrent_results[job_id]
                )

            # Concurrent should be faster (or at least not much slower)
            # Allow some overhead for small datasets
            assert (
                concurrent_time <= sequential_time * 1.5
            ), f"Concurrent ({concurrent_time:.4f}s) should be faster than sequential ({sequential_time:.4f}s)"

            # Log performance
            print(f"\nSequential time: {sequential_time:.4f}s")
            print(f"Concurrent time: {concurrent_time:.4f}s")
            print(f"Speedup: {sequential_time / concurrent_time:.2f}x")


@pytest.mark.django_db
class TestUserActivityIntegration:
    """Test integration between user activity and job matching"""

    def test_activity_affects_matching(self, test_job, test_applicant):
        """Test that user activity affects match scores"""
        # Initial match score
        with patch(
            "jobs.job_matching_utils.calculate_location_score", return_value=0.5
        ), patch(
            "jobs.job_matching_utils.calculate_skills_score", return_value=0.5
        ), patch(
            "jobs.job_matching_utils.calculate_rating_score", return_value=0.5
        ), patch(
            "jobs.job_matching_utils.calculate_experience_score", return_value=0.5
        ):
            # Get initial score with no activity
            with patch(
                "jobs.job_matching_utils.get_user_activity_score", return_value=0.0
            ):
                initial_score = calculate_match_score(test_job, test_applicant)

            # Get score with high activity
            with patch(
                "jobs.job_matching_utils.get_user_activity_score", return_value=1.0
            ):
                high_activity_score = calculate_match_score(test_job, test_applicant)

            # High activity should increase the score
            assert high_activity_score > initial_score

            # The difference should be exactly the weight of activity
            assert high_activity_score - initial_score == 0.15  # WEIGHT_ACTIVITY

"""
Tests for the dispute management system.

This module tests:
- Dispute creation
- Admin assignment to disputes
- Dispute resolution
- API endpoints for dispute management
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from adminaccess.models import AdminProfile, AdminRole
from disputes.models import Dispute
from disputes.tasks import assign_dispute_to_admin, check_unassigned_disputes
from jobs.models import Job, JobIndustry, JobSubCategory

User = get_user_model()


@pytest.fixture
def admin_user(db):
    """Create an admin user with AdminProfile"""
    user = User.objects.create_user(
        username="admin1",
        email="admin1@example.com",
        password="password123",
        is_staff=True,
    )

    # Create admin role
    AdminRole.objects.create(user=user, role="support")

    # Create admin profile
    admin_profile = AdminProfile.objects.create(
        user=user, current_dispute_count=0, is_available=True
    )

    return user


@pytest.fixture
def client_user(db):
    """Create a client user"""
    user = User.objects.create_user(
        username="client1", email="client1@example.com", password="password123"
    )
    return user


@pytest.fixture
def applicant_user(db):
    """Create an applicant user"""
    user = User.objects.create_user(
        username="applicant1", email="applicant1@example.com", password="password123"
    )
    return user


@pytest.fixture
def test_job(db, client_user):
    """Create a test job"""
    industry = JobIndustry.objects.create(name="Test Industry")
    subcategory = JobSubCategory.objects.create(
        name="Test Subcategory", industry=industry
    )

    job = Job.objects.create(
        title="Test Job",
        description="Test job description",
        client=client_user,
        created_by=client_user,
        industry=industry,
        subcategory=subcategory,
        location="Test Location",
        latitude=40.7128,
        longitude=-74.0060,
    )

    return job


@pytest.fixture
def test_dispute(db, test_job, applicant_user):
    """Create a test dispute"""
    dispute = Dispute.objects.create(
        job=test_job,
        raised_by=applicant_user,
        title="Test Dispute",
        description="This is a test dispute",
        status=Dispute.Status.OPEN,
    )

    return dispute


@pytest.mark.django_db
class TestDisputeModel:
    """Test the Dispute model"""

    def test_dispute_creation(self, test_job, applicant_user):
        """Test creating a dispute"""
        dispute = Dispute.objects.create(
            job=test_job,
            raised_by=applicant_user,
            title="Test Dispute",
            description="This is a test dispute",
            status=Dispute.Status.OPEN,
        )

        assert dispute.id is not None
        assert dispute.job == test_job
        assert dispute.raised_by == applicant_user
        assert dispute.title == "Test Dispute"
        assert dispute.description == "This is a test dispute"
        assert dispute.status == Dispute.Status.OPEN
        assert dispute.assigned_admin is None

    def test_dispute_status_choices(self, test_dispute):
        """Test dispute status choices"""
        # Test changing status
        test_dispute.status = Dispute.Status.ASSIGNED
        test_dispute.save()

        # Refresh from database
        test_dispute.refresh_from_db()
        assert test_dispute.status == Dispute.Status.ASSIGNED

        # Test all status choices
        assert Dispute.Status.OPEN == "open"
        assert Dispute.Status.ASSIGNED == "assigned"
        assert Dispute.Status.IN_REVIEW == "in_review"
        assert Dispute.Status.RESOLVED == "resolved"
        assert Dispute.Status.CLOSED == "closed"
        assert Dispute.Status.ESCALATED == "escalated"


@pytest.mark.django_db
class TestAdminProfile:
    """Test the AdminProfile model"""

    def test_admin_profile_creation(self, admin_user):
        """Test creating an admin profile"""
        profile = AdminProfile.objects.get(user=admin_user)

        assert profile.user == admin_user
        assert profile.current_dispute_count == 0
        assert profile.total_disputes_handled == 0
        assert profile.disputes_resolved == 0
        assert profile.is_available is True

    def test_increment_dispute_count(self, admin_user):
        """Test incrementing dispute count"""
        profile = AdminProfile.objects.get(user=admin_user)

        profile.increment_dispute_count()
        assert profile.current_dispute_count == 1
        assert profile.total_disputes_handled == 1

        profile.increment_dispute_count()
        assert profile.current_dispute_count == 2
        assert profile.total_disputes_handled == 2

    def test_decrement_dispute_count(self, admin_user):
        """Test decrementing dispute count"""
        profile = AdminProfile.objects.get(user=admin_user)

        # Set initial counts
        profile.current_dispute_count = 2
        profile.save()

        profile.decrement_dispute_count()
        assert profile.current_dispute_count == 1
        assert profile.disputes_resolved == 1

        profile.decrement_dispute_count()
        assert profile.current_dispute_count == 0
        assert profile.disputes_resolved == 2

        # Should not go below zero
        profile.decrement_dispute_count()
        assert profile.current_dispute_count == 0
        assert profile.disputes_resolved == 3

    def test_update_resolution_time(self, admin_user):
        """Test updating resolution time"""
        profile = AdminProfile.objects.get(user=admin_user)

        # First resolution
        profile.update_resolution_time(5.0)
        assert profile.average_resolution_time == 5.0

        # Set disputes resolved
        profile.disputes_resolved = 1
        profile.save()

        # Second resolution
        profile.update_resolution_time(7.0)
        assert profile.average_resolution_time == 6.0  # (5.0 + 7.0) / 2


@pytest.mark.django_db
class TestDisputeAssignment:
    """Test dispute assignment to admins"""

    def test_assign_dispute_to_admin_task(self, test_dispute, admin_user):
        """Test the assign_dispute_to_admin task"""
        # Run the task
        result = assign_dispute_to_admin(test_dispute.id)

        # Check result
        assert result["status"] == "success"
        assert admin_user.username in result["message"]

        # Refresh dispute from database
        test_dispute.refresh_from_db()
        assert test_dispute.status == Dispute.Status.ASSIGNED
        assert test_dispute.assigned_admin == admin_user

        # Check admin profile
        admin_profile = AdminProfile.objects.get(user=admin_user)
        assert admin_profile.current_dispute_count == 1
        assert admin_profile.total_disputes_handled == 1

    def test_assign_dispute_idempotency(self, test_dispute, admin_user):
        """Test that assigning a dispute is idempotent"""
        # First assignment
        result1 = assign_dispute_to_admin(test_dispute.id)
        assert result1["status"] == "success"

        # Get current counts
        admin_profile = AdminProfile.objects.get(user=admin_user)
        initial_count = admin_profile.current_dispute_count
        initial_total = admin_profile.total_disputes_handled

        # Second assignment should be skipped
        result2 = assign_dispute_to_admin(test_dispute.id)
        assert result2["status"] == "skipped"

        # Counts should not change
        admin_profile.refresh_from_db()
        assert admin_profile.current_dispute_count == initial_count
        assert admin_profile.total_disputes_handled == initial_total

    def test_check_unassigned_disputes(self, test_dispute):
        """Test the check_unassigned_disputes task"""
        with patch("disputes.tasks.assign_dispute_to_admin.delay") as mock_task:
            result = check_unassigned_disputes()

            assert result["status"] == "success"
            assert "Triggered assignment for 1 unassigned disputes" in result["message"]
            mock_task.assert_called_once_with(test_dispute.id)

    def test_admin_selection_by_workload(self, db, test_dispute):
        """Test that admin with lowest workload is selected"""
        # Create multiple admins with different workloads
        admin1 = User.objects.create_user(
            username="admin1",
            email="admin1@example.com",
            password="password123",
            is_staff=True,
        )
        AdminRole.objects.create(user=admin1, role="support")
        AdminProfile.objects.create(
            user=admin1, current_dispute_count=5, is_available=True
        )

        admin2 = User.objects.create_user(
            username="admin2",
            email="admin2@example.com",
            password="password123",
            is_staff=True,
        )
        AdminRole.objects.create(user=admin2, role="support")
        AdminProfile.objects.create(
            user=admin2, current_dispute_count=2, is_available=True
        )

        admin3 = User.objects.create_user(
            username="admin3",
            email="admin3@example.com",
            password="password123",
            is_staff=True,
        )
        AdminRole.objects.create(user=admin3, role="support")
        AdminProfile.objects.create(
            user=admin3, current_dispute_count=0, is_available=True
        )

        # Run assignment task
        result = assign_dispute_to_admin(test_dispute.id)

        # Dispute should be assigned to admin3 (lowest workload)
        test_dispute.refresh_from_db()
        assert test_dispute.assigned_admin == admin3

        # Admin3's workload should increase
        admin3_profile = AdminProfile.objects.get(user=admin3)
        assert admin3_profile.current_dispute_count == 1


@pytest.mark.django_db
class TestDisputeAPI:
    """Test the dispute API endpoints"""

    def test_raise_dispute_endpoint(self, client, test_job, applicant_user):
        """Test the raise-dispute endpoint"""
        # Log in
        client.force_login(applicant_user)

        # Make request
        url = f"/api/jobs/{test_job.id}/raise-dispute"
        data = {
            "title": "API Test Dispute",
            "description": "This dispute was created via API",
        }
        response = client.post(
            url, data=json.dumps(data), content_type="application/json"
        )

        # Check response
        assert response.status_code == 201
        response_data = response.json()
        assert response_data["success"] is True
        assert "dispute_id" in response_data

        # Check dispute was created
        dispute_id = response_data["dispute_id"]
        dispute = Dispute.objects.get(id=dispute_id)
        assert dispute.job == test_job
        assert dispute.raised_by == applicant_user
        assert dispute.title == "API Test Dispute"
        assert dispute.status == Dispute.Status.OPEN

    def test_raise_dispute_unauthenticated(self, client, test_job):
        """Test raising a dispute without authentication"""
        url = f"/api/jobs/{test_job.id}/raise-dispute"
        data = {"title": "Unauthenticated Dispute", "description": "This should fail"}
        response = client.post(
            url, data=json.dumps(data), content_type="application/json"
        )

        # Should return 401
        assert response.status_code == 401

        # No dispute should be created
        assert not Dispute.objects.filter(title="Unauthenticated Dispute").exists()

    def test_raise_dispute_duplicate(self, client, test_job, applicant_user):
        """Test raising a duplicate dispute"""
        # Create existing dispute
        Dispute.objects.create(
            job=test_job,
            raised_by=applicant_user,
            title="Existing Dispute",
            description="Already exists",
            status=Dispute.Status.OPEN,
        )

        # Log in
        client.force_login(applicant_user)

        # Try to create another dispute
        url = f"/api/jobs/{test_job.id}/raise-dispute"
        data = {"title": "Duplicate Dispute", "description": "This should fail"}
        response = client.post(
            url, data=json.dumps(data), content_type="application/json"
        )

        # Should return 400
        assert response.status_code == 400

        # No new dispute should be created
        assert not Dispute.objects.filter(title="Duplicate Dispute").exists()


@pytest.mark.django_db
class TestJobMatchingWithDisputes:
    """Test job matching integration with dispute management"""

    @patch("jobs.job_matching_utils.match_jobs_to_users")
    def test_job_creation_triggers_matching(self, mock_match, client_user):
        """Test that creating a job triggers the matching function"""
        # Create job
        industry = JobIndustry.objects.create(name="Test Industry")
        subcategory = JobSubCategory.objects.create(
            name="Test Subcategory", industry=industry
        )

        with patch("jobs.signals.django_q.async_task") as mock_async:
            job = Job.objects.create(
                title="Matching Test Job",
                description="Test job description",
                client=client_user,
                created_by=client_user,
                industry=industry,
                subcategory=subcategory,
                location="Test Location",
                latitude=40.7128,
                longitude=-74.0060,
            )

            # Check that async task was called
            mock_async.assert_called_once()

            # The first argument should be the function name
            assert (
                mock_async.call_args[0][0]
                == "jobs.job_matching_utils.match_jobs_to_users"
            )

            # The second argument should include the job ID
            assert job.id in mock_async.call_args[0][1:]

    @patch("jobs.job_matching_utils.match_jobs_to_users")
    @patch("jobs.job_matching_utils.cache.set")
    def test_matching_results_are_cached(
        self, mock_cache, mock_match, test_job, applicant_user
    ):
        """Test that matching results are cached"""
        # Mock the matching function to return test data
        mock_match.return_value = {
            test_job.id: [
                {
                    "user_id": applicant_user.id,
                    "username": applicant_user.username,
                    "score": 0.85,
                    "job_id": test_job.id,
                    "job_title": test_job.title,
                }
            ]
        }

        # Call the matching function through the signal
        with patch("jobs.signals.match_jobs_to_users") as mock_signal_match:
            mock_signal_match.return_value = mock_match.return_value

            # Simulate signal by calling the function directly
            from jobs.signals import match_job_to_users_on_create

            match_job_to_users_on_create(sender=Job, instance=test_job, created=True)

            # Check that cache.set was called with the right key pattern
            mock_cache.assert_called()

            # The cache key should include the job ID
            cache_key = f"job_matches:{test_job.id}"
            assert any(call[0][0] == cache_key for call in mock_cache.call_args_list)

    @patch("jobs.signals.send_job_match_notification")
    def test_notifications_sent_for_matches(
        self, mock_notify, test_job, applicant_user
    ):
        """Test that notifications are sent for job matches"""
        # Create a high-scoring match
        match_data = {
            "user_id": applicant_user.id,
            "username": applicant_user.username,
            "score": 0.85,  # High score
            "job_id": test_job.id,
            "job_title": test_job.title,
        }

        # Simulate the notification sending
        from jobs.signals import send_notifications_for_matches

        send_notifications_for_matches(test_job, [match_data])

        # Check that notification was sent
        mock_notify.assert_called_once()
        assert mock_notify.call_args[0][0] == applicant_user
        assert mock_notify.call_args[0][1] == test_job

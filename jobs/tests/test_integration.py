import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from jobs.models import (Achievement, Application, Badge, Job, JobIndustry,
                         Profile, Review, UserAchievement, UserBadge,
                         UserPoints)

# from tracker.models import JobTracker

User = get_user_model()


class JobCompletionIntegrationTestCase(TestCase):
    """
    Integration tests for job completion flow and gamification system.

    This test case tests the complete flow from job creation to completion,
    including achievement and badge awarding.
    """

    def setUp(self):
        # Create test users
        self.client = Client()

        # Create worker user
        self.worker = User.objects.create_user(
            username="testworker", email="worker@example.com", password="testpassword"
        )
        self.worker_profile = Profile.objects.create(user=self.worker, role="applicant")

        # Create client user
        self.employer = User.objects.create_user(
            username="testemployer",
            email="employer@example.com",
            password="testpassword",
        )
        self.employer_profile = Profile.objects.create(
            user=self.employer, role="client"
        )

        # Create industry
        self.industry = JobIndustry.objects.create(name="Test Industry")

        # Create job
        self.job = Job.objects.create(
            title="Test Job",
            description="Test Description",
            client=self.employer,
            industry=self.industry,
            job_type=Job.JobType.SINGLE_DAY,
            shift_type=Job.ShiftType.MORNING,
            date=timezone.now().date(),
            start_time=timezone.now().time(),
            end_time=(timezone.now() + timezone.timedelta(hours=8)).time(),
            rate=Decimal("100.00"),
            applicants_needed=1,
            location="Test Location",
            status=Job.Status.UPCOMING,
        )

        # Create job tracker
        self.tracker = JobTracker.objects.create(job=self.job, status="pending")

        # Create application
        self.application = Application.objects.create(
            job=self.job,
            applicant=self.worker,
            employer=self.employer,
            status=Application.Status.APPLIED,
        )

        # Create user points
        self.worker_points = UserPoints.objects.create(
            user=self.worker, total_points=0, current_level=1, points_to_next_level=100
        )

        # Create achievement for job completion
        self.job_achievement = Achievement.objects.create(
            name="First Job",
            description="Complete your first job",
            achievement_type="job_count",
            points=100,
            criteria={"required_count": 1},
        )

        # Create badge for job completion
        self.job_badge = Badge.objects.create(
            name="Reliable Worker",
            description="Complete your first job successfully",
            badge_type="job_completion",
            points=50,
            criteria={"required_jobs": 1, "required_success_rate": 100},
        )

    def test_complete_job_flow(self):
        """Test complete job flow with gamification"""
        self.client.force_login(self.employer)

        # First, accept the application
        self.application.accept()
        self.application.save()

        # Start the job
        self.job.start_shift()
        self.job.save()

        # Check that the job is now ongoing
        self.assertEqual(self.job.status, Job.Status.ONGOING)
        self.assertIsNotNone(self.job.actual_shift_start)

        # Complete the job
        url = reverse("complete_job", args=[self.job.id])
        response = self.client.post(url)

        # Check response
        self.assertEqual(response.status_code, 200)

        # Refresh objects from database
        self.job.refresh_from_db()
        self.application.refresh_from_db()
        self.tracker.refresh_from_db()

        # Check that job status is updated
        self.assertEqual(self.job.status, Job.Status.COMPLETED)
        self.assertEqual(self.tracker.status, "completed")

        # Verify application is marked as shown up
        self.assertTrue(self.application.is_shown_up)

        # Now check gamification progress
        self.client.logout()
        self.client.force_login(self.worker)

        url = reverse("get_gamification_progress", args=[self.worker.id])
        response = self.client.get(url)

        # Check that the worker got achievements and badges
        data = json.loads(response.content)

        # Get updated worker points
        worker_points = UserPoints.objects.get(user=self.worker)

        # Verify points were awarded and achievement was unlocked
        self.assertTrue(worker_points.total_points > 0)
        self.assertTrue(
            UserAchievement.objects.filter(
                user=self.worker, achievement=self.job_achievement
            ).exists()
        )

        # Check mobile dashboard
        url = reverse("mobile_gamification_dashboard", args=[self.worker.id])
        response = self.client.get(url)

        # Verify dashboard data
        data = json.loads(response.content)
        self.assertEqual(data["user_id"], self.worker.id)
        self.assertTrue(data["total_points"] > 0)

        # Check leaderboards
        url = reverse("get_leaderboards")
        response = self.client.get(url)

        # Verify leaderboard includes the worker
        data = json.loads(response.content)
        top_points_user_ids = [user["user_id"] for user in data["top_points"]]
        self.assertIn(self.worker.id, top_points_user_ids)


class RatingGamificationIntegrationTestCase(TestCase):
    """
    Integration tests for rating system and related gamification.

    This test case tests the flow where a user receives a high rating
    and gets awarded rating-based achievements and badges.
    """

    def setUp(self):
        # Create test users
        self.client = Client()

        # Create worker user
        self.worker = User.objects.create_user(
            username="testworker", email="worker@example.com", password="testpassword"
        )
        self.worker_profile = Profile.objects.create(user=self.worker, role="applicant")

        # Create client user
        self.employer = User.objects.create_user(
            username="testemployer",
            email="employer@example.com",
            password="testpassword",
        )
        self.employer_profile = Profile.objects.create(
            user=self.employer, role="client"
        )

        # Create user points
        self.worker_points = UserPoints.objects.create(
            user=self.worker, total_points=0, current_level=1, points_to_next_level=100
        )

        # Create rating achievement
        self.rating_achievement = Achievement.objects.create(
            name="Top Rated",
            description="Receive a high rating",
            achievement_type="rating",
            points=200,
            criteria={"required_rating": 4.5},
        )

        # Create rating badge
        self.rating_badge = Badge.objects.create(
            name="Quality Worker",
            description="Maintain high ratings",
            badge_type="rating",
            points=100,
            criteria={"required_rating": 4.5, "required_reviews": 1},
        )

    def test_rating_gamification(self):
        """Test rating flow with gamification"""
        self.client.force_login(self.employer)

        # Create review with high rating
        review = Review.objects.create(
            reviewer=self.employer,
            reviewed=self.worker,
            rating=Decimal("5.0"),
            feedback="Excellent worker",
        )

        # Check achievements
        url = reverse("check_achievements")
        payload = {"user_id": self.worker.id}
        response = self.client.post(url, payload, content_type="application/json")

        # Check badges
        url = reverse("check_badges")
        response = self.client.post(url, payload, content_type="application/json")

        # Verify achievements and badges were awarded
        self.assertTrue(
            UserAchievement.objects.filter(
                user=self.worker, achievement=self.rating_achievement
            ).exists()
        )

        self.worker_profile.refresh_from_db()
        self.assertIn(self.rating_badge.id, self.worker_profile.badges)

        # Verify points were added
        worker_points = UserPoints.objects.get(user=self.worker)
        self.assertEqual(
            worker_points.total_points,
            self.rating_achievement.points + self.rating_badge.points,
        )


import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from jobs.models import (Achievement, Application, Badge, Job, JobIndustry,
                         Profile, Review, UserAchievement, UserBadge,
                         UserPoints)

# from tracker.models import JobTracker

User = get_user_model()


class JobCompletionIntegrationTestCase(TestCase):
    """
    Integration tests for job completion flow and gamification system.

    This test case tests the complete flow from job creation to completion,
    including achievement and badge awarding.
    """

    def setUp(self):
        # Create test users
        self.client = Client()

        # Create worker user
        self.worker = User.objects.create_user(
            username="testworker", email="worker@example.com", password="testpassword"
        )
        self.worker_profile = Profile.objects.create(user=self.worker, role="applicant")

        # Create client user
        self.employer = User.objects.create_user(
            username="testemployer",
            email="employer@example.com",
            password="testpassword",
        )
        self.employer_profile = Profile.objects.create(
            user=self.employer, role="client"
        )

        # Create industry
        self.industry = JobIndustry.objects.create(name="Test Industry")

        # Create job
        self.job = Job.objects.create(
            title="Test Job",
            description="Test Description",
            client=self.employer,
            industry=self.industry,
            job_type=Job.JobType.SINGLE_DAY,
            shift_type=Job.ShiftType.MORNING,
            date=timezone.now().date(),
            start_time=timezone.now().time(),
            end_time=(timezone.now() + timezone.timedelta(hours=8)).time(),
            rate=Decimal("100.00"),
            applicants_needed=1,
            location="Test Location",
            status=Job.Status.UPCOMING,
        )

        # Create job tracker
        self.tracker = JobTracker.objects.create(job=self.job, status="pending")

        # Create application
        self.application = Application.objects.create(
            job=self.job,
            applicant=self.worker,
            employer=self.employer,
            status=Application.Status.APPLIED,
        )

        # Create user points
        self.worker_points = UserPoints.objects.create(
            user=self.worker, total_points=0, current_level=1, points_to_next_level=100
        )

        # Create achievement for job completion
        self.job_achievement = Achievement.objects.create(
            name="First Job",
            description="Complete your first job",
            achievement_type="job_count",
            points=100,
            criteria={"required_count": 1},
        )

        # Create badge for job completion
        self.job_badge = Badge.objects.create(
            name="Reliable Worker",
            description="Complete your first job successfully",
            badge_type="job_completion",
            points=50,
            criteria={"required_jobs": 1, "required_success_rate": 100},
        )

    def test_complete_job_flow(self):
        """Test complete job flow with gamification"""
        self.client.force_login(self.employer)

        # First, accept the application
        self.application.accept()
        self.application.save()

        # Start the job
        self.job.start_shift()
        self.job.save()

        # Check that the job is now ongoing
        self.assertEqual(self.job.status, Job.Status.ONGOING)
        self.assertIsNotNone(self.job.actual_shift_start)

        # Complete the job
        url = reverse("complete_job", args=[self.job.id])
        response = self.client.post(url)

        # Check response
        self.assertEqual(response.status_code, 200)

        # Refresh objects from database
        self.job.refresh_from_db()
        self.application.refresh_from_db()
        self.tracker.refresh_from_db()

        # Check that job status is updated
        self.assertEqual(self.job.status, Job.Status.COMPLETED)
        self.assertEqual(self.tracker.status, "completed")

        # Verify application is marked as shown up
        self.assertTrue(self.application.is_shown_up)

        # Now check gamification progress
        self.client.logout()
        self.client.force_login(self.worker)

        url = reverse("get_gamification_progress", args=[self.worker.id])
        response = self.client.get(url)

        # Check that the worker got achievements and badges
        data = json.loads(response.content)

        # Get updated worker points
        worker_points = UserPoints.objects.get(user=self.worker)

        # Verify points were awarded and achievement was unlocked
        self.assertTrue(worker_points.total_points > 0)
        self.assertTrue(
            UserAchievement.objects.filter(
                user=self.worker, achievement=self.job_achievement
            ).exists()
        )

        # Check mobile dashboard
        url = reverse("mobile_gamification_dashboard", args=[self.worker.id])
        response = self.client.get(url)

        # Verify dashboard data
        data = json.loads(response.content)
        self.assertEqual(data["user_id"], self.worker.id)
        self.assertTrue(data["total_points"] > 0)

        # Check leaderboards
        url = reverse("get_leaderboards")
        response = self.client.get(url)

        # Verify leaderboard includes the worker
        data = json.loads(response.content)
        top_points_user_ids = [user["user_id"] for user in data["top_points"]]
        self.assertIn(self.worker.id, top_points_user_ids)


class RatingGamificationIntegrationTestCase(TestCase):
    """
    Integration tests for rating system and related gamification.

    This test case tests the flow where a user receives a high rating
    and gets awarded rating-based achievements and badges.
    """

    def setUp(self):
        # Create test users
        self.client = Client()

        # Create worker user
        self.worker = User.objects.create_user(
            username="testworker", email="worker@example.com", password="testpassword"
        )
        self.worker_profile = Profile.objects.create(user=self.worker, role="applicant")

        # Create client user
        self.employer = User.objects.create_user(
            username="testemployer",
            email="employer@example.com",
            password="testpassword",
        )
        self.employer_profile = Profile.objects.create(
            user=self.employer, role="client"
        )

        # Create user points
        self.worker_points = UserPoints.objects.create(
            user=self.worker, total_points=0, current_level=1, points_to_next_level=100
        )

        # Create rating achievement
        self.rating_achievement = Achievement.objects.create(
            name="Top Rated",
            description="Receive a high rating",
            achievement_type="rating",
            points=200,
            criteria={"required_rating": 4.5},
        )

        # Create rating badge
        self.rating_badge = Badge.objects.create(
            name="Quality Worker",
            description="Maintain high ratings",
            badge_type="rating",
            points=100,
            criteria={"required_rating": 4.5, "required_reviews": 1},
        )

    def test_rating_gamification(self):
        """Test rating flow with gamification"""
        self.client.force_login(self.employer)

        # Create review with high rating
        review = Review.objects.create(
            reviewer=self.employer,
            reviewed=self.worker,
            rating=Decimal("5.0"),
            feedback="Excellent worker",
        )

        # Check achievements
        url = reverse("check_achievements")
        payload = {"user_id": self.worker.id}
        response = self.client.post(url, payload, content_type="application/json")

        # Check badges
        url = reverse("check_badges")
        response = self.client.post(url, payload, content_type="application/json")

        # Verify achievements and badges were awarded
        self.assertTrue(
            UserAchievement.objects.filter(
                user=self.worker, achievement=self.rating_achievement
            ).exists()
        )

        self.worker_profile.refresh_from_db()
        self.assertIn(self.rating_badge.id, self.worker_profile.badges)

        # Verify points were added
        worker_points = UserPoints.objects.get(user=self.worker)
        self.assertEqual(
            worker_points.total_points,
            self.rating_achievement.points + self.rating_badge.points,
        )

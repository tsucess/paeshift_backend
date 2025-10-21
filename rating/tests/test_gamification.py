import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from gamification.models import (Achievement, Badge, UserAchievement,
                                 UserBadge, UserPoints)
from jobs.models import Application, Job, JobIndustry
from rating.models import Review

User = get_user_model()


class GamificationTestCase(TestCase):
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

        # Create admin user
        self.admin = User.objects.create_user(
            username="testadmin",
            email="admin@example.com",
            password="testpassword",
            is_staff=True,
            is_superuser=True,
        )

        # Create industry
        self.industry = JobIndustry.objects.create(name="Test Industry")

        # Create achievements
        self.achievement = Achievement.objects.create(
            name="Test Achievement",
            description="Test Description",
            achievement_type="job_count",
            points=100,
            criteria={"required_count": 1},
        )

        # Create badges
        self.badge = Badge.objects.create(
            name="Test Badge",
            description="Test Description",
            badge_type="job_completion",
            points=200,
            criteria={"required_jobs": 1, "required_success_rate": 100},
        )

        self.client_badge = Badge.objects.create(
            name="Test Client Badge",
            description="Test Client Badge Description",
            badge_type="client_jobs",
            points=300,
            criteria={"required_jobs": 1, "required_completion_rate": 100},
        )

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

        self.employer_points = UserPoints.objects.create(
            user=self.employer,
            total_points=0,
            current_level=1,
            points_to_next_level=100,
        )

    def test_get_gamification_progress(self):
        """Test retrieving gamification progress"""
        self.client.force_login(self.worker)

        # Create user achievement
        user_achievement = UserAchievement.objects.create(
            user=self.worker, achievement=self.achievement, unlocked_at=timezone.now()
        )

        # Add badge to profile
        self.worker_profile.badges = [self.badge.id]
        self.worker_profile.save()

        # Create user badge
        user_badge = UserBadge.objects.create(
            user=self.worker, badge=self.badge, earned_at=timezone.now()
        )

        # Make request
        url = reverse("get_gamification_progress", args=[self.worker.id])
        response = self.client.get(url)

        # Check response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Verify data
        self.assertIn("badges", data)
        self.assertIn("achievements", data)
        self.assertIn("points", data)

        # Check points
        self.assertEqual(data["points"]["total_points"], 0)
        self.assertEqual(data["points"]["current_level"], 1)

        # Test unauthorized access
        self.client.logout()
        self.client.force_login(self.employer)

        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_check_achievements(self):
        """Test checking and awarding achievements"""
        self.client.force_login(self.worker)

        # Complete a job
        self.application.status = Application.Status.ACCEPTED
        self.application.is_shown_up = True
        self.application.save()

        self.job.status = Job.Status.COMPLETED
        self.job.save()

        # Make request
        url = reverse("check_achievements")
        payload = {"user_id": self.worker.id}
        response = self.client.post(url, payload, content_type="application/json")

        # Check response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Verify achievement was awarded
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["user_id"], self.worker.id)
        self.assertEqual(data[0]["achievement_id"], self.achievement.id)
        self.assertTrue(data[0]["is_completed"])

        # Verify points were added
        user_points = UserPoints.objects.get(user=self.worker)
        self.assertEqual(user_points.total_points, self.achievement.points)

        # Test unauthorized access
        self.client.logout()
        self.client.force_login(self.employer)

        response = self.client.post(
            url, {"user_id": self.worker.id}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 403)

    def test_check_badges(self):
        """Test checking and awarding badges"""
        self.client.force_login(self.worker)

        # Complete a job
        self.application.status = Application.Status.ACCEPTED
        self.application.is_shown_up = True
        self.application.save()

        self.job.status = Job.Status.COMPLETED
        self.job.save()

        # Make request
        url = reverse("check_badges")
        payload = {"user_id": self.worker.id}
        response = self.client.post(url, payload, content_type="application/json")

        # Check response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Verify badge was awarded
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["user_id"], self.worker.id)
        self.assertEqual(data[0]["badge_id"], self.badge.id)
        self.assertTrue(data[0]["is_completed"])

        # Verify points were added
        user_points = UserPoints.objects.get(user=self.worker)
        self.assertEqual(user_points.total_points, self.badge.points)

        # Verify badge ID was added to profile
        profile = Profile.objects.get(user=self.worker)
        self.assertIn(self.badge.id, profile.badges)

    def test_mobile_dashboard(self):
        """Test mobile gamification dashboard"""
        self.client.force_login(self.worker)

        # Create user achievement
        user_achievement = UserAchievement.objects.create(
            user=self.worker, achievement=self.achievement, unlocked_at=timezone.now()
        )

        # Add badge to profile
        self.worker_profile.badges = [self.badge.id]
        self.worker_profile.save()

        # Create user badge
        user_badge = UserBadge.objects.create(
            user=self.worker, badge=self.badge, earned_at=timezone.now()
        )

        # Make request
        url = reverse("mobile_gamification_dashboard", args=[self.worker.id])
        response = self.client.get(url)

        # Check response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Verify data
        self.assertEqual(data["user_id"], self.worker.id)
        self.assertEqual(data["username"], self.worker.username)
        self.assertEqual(data["level"], 1)
        self.assertEqual(len(data["badges"]), 1)
        self.assertEqual(len(data["recent_achievements"]), 1)

    def test_leaderboards(self):
        """Test leaderboard endpoint"""
        self.client.force_login(self.worker)

        # Add some points to users
        self.worker_points.total_points = 500
        self.worker_points.current_level = 5
        self.worker_points.save()

        self.employer_points.total_points = 300
        self.employer_points.current_level = 3
        self.employer_points.save()

        # Add achievements
        UserAchievement.objects.create(
            user=self.worker, achievement=self.achievement, unlocked_at=timezone.now()
        )

        # Add badges
        self.worker_profile.badges = [self.badge.id]
        self.worker_profile.save()

        UserBadge.objects.create(
            user=self.worker, badge=self.badge, earned_at=timezone.now()
        )

        # Add ratings
        Review.objects.create(
            reviewer=self.employer,
            reviewed=self.worker,
            rating=Decimal("4.5"),
            feedback="Great worker",
        )

        # Make request
        url = reverse("get_leaderboards")
        response = self.client.get(url)

        # Check response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Verify data structure
        self.assertIn("top_points", data)
        self.assertIn("top_achievements", data)
        self.assertIn("top_completed_jobs", data)
        self.assertIn("top_rated", data)
        self.assertIn("weekly_rising_stars", data)

        # Verify top points
        self.assertEqual(len(data["top_points"]), 2)
        self.assertEqual(data["top_points"][0]["user_id"], self.worker.id)
        self.assertEqual(data["top_points"][0]["total_points"], 500)

        # Test filtering by industry
        url = f"{reverse('get_leaderboards')}?industry_id={self.industry.id}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class BadgeCheckerTestCase(TestCase):
    def setUp(self):
        # Create test users
        self.worker = User.objects.create_user(
            username="testworker", email="worker@example.com", password="testpassword"
        )
        self.worker_profile = Profile.objects.create(user=self.worker, role="applicant")

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

        # Create badges
        self.job_badge = Badge.objects.create(
            name="Job Completion Badge",
            description="Complete a job",
            badge_type="job_completion",
            points=100,
            criteria={"required_jobs": 1, "required_success_rate": 100},
        )

        self.rating_badge = Badge.objects.create(
            name="Rating Badge",
            description="Get a high rating",
            badge_type="rating",
            points=200,
            criteria={"required_rating": 4.5, "required_reviews": 1},
        )

        self.client_badge = Badge.objects.create(
            name="Client Badge",
            description="Post jobs",
            badge_type="client_jobs",
            points=300,
            criteria={"required_jobs": 1, "required_completion_rate": 100},
        )

    def test_job_completion_badge(self):
        """Test job completion badge checker"""
        from gamification.badge_checker import BadgeChecker

        # Create job
        job = Job.objects.create(
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

        # Create application
        application = Application.objects.create(
            job=job,
            applicant=self.worker,
            employer=self.employer,
            status=Application.Status.ACCEPTED,
            is_shown_up=True,
        )

        # Check badge criteria
        result = BadgeChecker.check_job_completion(self.worker, self.job_badge.criteria)
        self.assertTrue(result)

    def test_rating_badge(self):
        """Test rating badge checker"""
        from gamification.models import Badge

        # Create review
        Review.objects.create(
            reviewer=self.employer,
            reviewed=self.worker,
            rating=Decimal("5.0"),
            feedback="Excellent worker",
        )

        # Check badge criteria
        result = BadgeChecker.check_rating_badge(
            self.worker, self.rating_badge.criteria
        )
        self.assertTrue(result)

    def test_client_jobs_badge(self):
        """Test client jobs badge checker"""
        from jobs.gamification import BadgeChecker

        # Create job
        job = Job.objects.create(
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
            status=Job.Status.COMPLETED,
        )

        # Check badge criteria
        result = BadgeChecker.check_client_jobs(
            self.employer, self.client_badge.criteria
        )
        self.assertTrue(result)


class AchievementCheckerTestCase(TestCase):
    def setUp(self):
        # Create test users
        self.worker = User.objects.create_user(
            username="testworker", email="worker@example.com", password="testpassword"
        )
        self.worker_profile = Profile.objects.create(user=self.worker, role="applicant")

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

        # Create achievements
        self.job_achievement = Achievement.objects.create(
            name="Job Count Achievement",
            description="Complete jobs",
            achievement_type="job_count",
            points=100,
            criteria={"required_count": 1},
        )

        self.rating_achievement = Achievement.objects.create(
            name="Rating Achievement",
            description="Get a high rating",
            achievement_type="rating",
            points=200,
            criteria={"required_rating": 4.5},
        )

    def test_job_count_achievement(self):
        """Test job count achievement checker"""
        from jobs.gamification import AchievementChecker

        # Create job
        job = Job.objects.create(
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

        # Create application
        application = Application.objects.create(
            job=job,
            applicant=self.worker,
            employer=self.employer,
            status=Application.Status.ACCEPTED,
            is_shown_up=True,
        )

        # Check achievement criteria
        result = AchievementChecker.check_job_count(
            self.worker, self.job_achievement.criteria
        )
        self.assertTrue(result)

    def test_rating_achievement(self):
        """Test rating achievement checker"""
        from jobs.gamification import AchievementChecker

        # Create review
        Review.objects.create(
            reviewer=self.employer,
            reviewed=self.worker,
            rating=Decimal("5.0"),
            feedback="Excellent worker",
        )

        # Check achievement criteria
        result = AchievementChecker.check_rating(
            self.worker, self.rating_achievement.criteria
        )
        self.assertTrue(result)


class UserPointsTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpassword"
        )

        self.user_points = UserPoints.objects.create(
            user=self.user, total_points=0, current_level=1, points_to_next_level=100
        )

    def test_add_points(self):
        """Test adding points"""
        # Add points below level threshold
        self.user_points.add_points(50)
        self.assertEqual(self.user_points.total_points, 50)
        self.assertEqual(self.user_points.current_level, 1)

        # Add points to trigger level up
        self.user_points.add_points(60)
        self.assertEqual(self.user_points.total_points, 110)
        self.assertEqual(self.user_points.current_level, 2)

        # Verify points_to_next_level increased
        self.assertTrue(self.user_points.points_to_next_level > 100)

    def test_level_up(self):
        """Test level up logic"""
        initial_points_to_next_level = self.user_points.points_to_next_level

        self.user_points.level_up()

        self.assertEqual(self.user_points.current_level, 2)
        self.assertTrue(
            self.user_points.points_to_next_level > initial_points_to_next_level
        )
        self.assertIsNotNone(self.user_points.last_level_up)

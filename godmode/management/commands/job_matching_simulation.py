"""
Django management command to run concurrent job matching simulations.

This command allows running job matching simulations with user activity tracking:
1. Creates test users with varying activity levels
2. Creates test jobs with different attributes
3. Runs concurrent job matching using the job_matching_utils module
4. Tracks performance metrics and match quality
5. Generates reports on match effectiveness

Usage:
    python manage.py job_matching_simulation --users=50 --jobs=100 --iterations=5
"""

import asyncio
import concurrent.futures
import json
import logging
import random
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Profile, UserActivityLog
from accounts.user_activity import (get_user_activity_summary,
                                    get_user_engagement_score, track_job_view,
                                    track_user_activity, track_user_login)
from gamification.models import UserActivity, UserPoints
from jobs.job_matching_utils import match_jobs_to_users, match_users_to_jobs
from jobs.management.commands3.simulation import (SAMPLE_JOB_TITLES,
                                                  SAMPLE_LOCATIONS,
                                                  create_test_job,
                                                  create_test_user)
from jobs.models import Application, Job, JobIndustry, JobSubCategory

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run concurrent job matching simulations with user activity tracking"

    def add_arguments(self, parser):
        parser.add_argument(
            "--users",
            type=int,
            default=50,
            help="Number of users to create for simulation",
        )
        parser.add_argument(
            "--jobs",
            type=int,
            default=100,
            help="Number of jobs to create for simulation",
        )
        parser.add_argument(
            "--iterations",
            type=int,
            default=3,
            help="Number of matching iterations to run",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=20,
            help="Batch size for concurrent processing",
        )
        parser.add_argument(
            "--save-results",
            action="store_true",
            help="Save detailed results to JSON file",
        )
        parser.add_argument(
            "--clear-existing",
            action="store_true",
            help="Clear existing test data before running",
        )

    def handle(self, *args, **options):
        num_users = options["users"]
        num_jobs = options["jobs"]
        iterations = options["iterations"]
        batch_size = options["batch_size"]
        save_results = options["save_results"]
        clear_existing = options["clear_existing"]

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting job matching simulation with {num_users} users and {num_jobs} jobs"
            )
        )

        # Clear existing test data if requested
        if clear_existing:
            self._clear_test_data()

        # Create test data
        users = self._create_test_users(num_users)
        jobs = self._create_test_jobs(num_jobs)

        # Simulate user activity
        self._simulate_user_activity(users)

        # Run matching iterations
        results = []
        for i in range(iterations):
            self.stdout.write(
                self.style.NOTICE(f"Running matching iteration {i+1}/{iterations}")
            )
            iteration_result = self._run_matching_iteration(users, jobs, batch_size)
            results.append(iteration_result)

            # Print summary of this iteration
            self._print_iteration_summary(iteration_result, i + 1)

        # Print overall summary
        self._print_overall_summary(results)

        # Save detailed results if requested
        if save_results:
            self._save_results(results)

        self.stdout.write(
            self.style.SUCCESS("Job matching simulation completed successfully!")
        )

    def _clear_test_data(self):
        """Clear existing test data"""
        self.stdout.write("Clearing existing test data...")

        # Delete test users and their related data
        test_users = User.objects.filter(email__contains="@example.com")
        count = test_users.count()
        test_users.delete()

        self.stdout.write(f"Deleted {count} test users and their related data")

    def _create_test_users(self, num_users: int) -> List[User]:
        """Create test users with profiles"""
        self.stdout.write("Creating test users...")

        users = []
        for i in range(num_users):
            # Determine role (70% applicants, 30% clients)
            role = "applicant" if random.random() < 0.7 else "client"

            # Create user
            user = create_test_user(role=role)
            users.append(user)

            # Create UserPoints record
            UserPoints.objects.get_or_create(user=user)

            self.stdout.write(f"  Created user {user.username} ({role})")

        self.stdout.write(self.style.SUCCESS(f"Created {len(users)} test users"))
        return users

    def _create_test_jobs(self, num_jobs: int) -> List[Job]:
        """Create test jobs"""
        self.stdout.write("Creating test jobs...")

        # Get client users
        client_users = User.objects.filter(
            profile__role="client", email__contains="@example.com"
        )

        if client_users.count() == 0:
            self.stdout.write(
                self.style.ERROR("No client users found. Cannot create jobs.")
            )
            return []

        jobs = []
        for i in range(num_jobs):
            # Select random client
            client = random.choice(client_users)

            # Create job
            job = create_test_job(client)
            jobs.append(job)

            self.stdout.write(f"  Created job {job.title} (ID: {job.id})")

        self.stdout.write(self.style.SUCCESS(f"Created {len(jobs)} test jobs"))
        return jobs

    def _simulate_user_activity(self, users: List[User]) -> None:
        """Simulate user activity for test users"""
        self.stdout.write("Simulating user activity...")

        # Activity types to simulate
        activity_types = [
            "login",
            "job_view",
            "job_apply",
            "profile_update",
            "search",
            "message",
            "logout",
        ]

        # Get available jobs
        jobs = Job.objects.all()
        if jobs.count() == 0:
            self.stdout.write(
                self.style.WARNING("No jobs available for activity simulation")
            )
            return

        # Simulate different activity levels for users
        for user in users:
            # Determine activity level (high, medium, low)
            activity_level = random.choices(
                ["high", "medium", "low"], weights=[0.2, 0.5, 0.3], k=1
            )[0]

            # Determine number of activities based on level
            if activity_level == "high":
                num_activities = random.randint(20, 50)
            elif activity_level == "medium":
                num_activities = random.randint(5, 19)
            else:  # low
                num_activities = random.randint(1, 4)

            # Create activity logs
            for _ in range(num_activities):
                # Select random activity type
                activity_type = random.choice(activity_types)

                # Create activity with appropriate details
                if activity_type == "login":
                    track_user_login(user, ip_address="127.0.0.1")
                elif activity_type == "job_view":
                    job = random.choice(jobs)
                    track_job_view(user, job.id)
                else:
                    details = {}
                    if activity_type == "job_apply":
                        job = random.choice(jobs)
                        details = {"job_id": job.id}
                        points = 20
                    elif activity_type == "profile_update":
                        details = {"fields_updated": ["bio", "skills"]}
                        points = 15
                    elif activity_type == "search":
                        details = {
                            "query": random.choice(
                                ["plumber", "electrician", "carpenter"]
                            )
                        }
                        points = 5
                    elif activity_type == "message":
                        details = {"recipient_id": random.choice(users).id}
                        points = 10
                    else:  # logout
                        points = 0

                    track_user_activity(user, activity_type, details, points=points)

            # Update timestamp to simulate activity over time
            activity_logs = UserActivityLog.objects.filter(user=user)
            for log in activity_logs:
                # Random time in the last 30 days
                days_ago = random.randint(0, 30)
                hours_ago = random.randint(0, 23)
                minutes_ago = random.randint(0, 59)

                new_timestamp = timezone.now() - timedelta(
                    days=days_ago, hours=hours_ago, minutes=minutes_ago
                )

                log.created_at = new_timestamp
                log.save(update_fields=["created_at"])

            self.stdout.write(
                f"  Simulated {num_activities} activities for {user.username} ({activity_level} level)"
            )

        self.stdout.write(
            self.style.SUCCESS(f"Simulated activity for {len(users)} users")
        )

    def _run_matching_iteration(
        self, users: List[User], jobs: List[Job], batch_size: int
    ) -> Dict[str, Any]:
        """Run a single matching iteration"""
        start_time = time.time()

        # Get applicant users
        applicant_users = [
            u for u in users if hasattr(u, "profile") and u.profile.role == "applicant"
        ]

        # Split into batches for concurrent processing
        user_batches = [
            applicant_users[i : i + batch_size]
            for i in range(0, len(applicant_users), batch_size)
        ]
        job_batches = [
            jobs[i : i + batch_size] for i in range(0, len(jobs), batch_size)
        ]

        # Run job-to-users matching
        job_matches_start = time.time()
        job_matches = match_jobs_to_users(jobs, applicant_users)
        job_matches_time = time.time() - job_matches_start

        # Run users-to-jobs matching
        user_matches_start = time.time()
        user_matches = match_users_to_jobs(applicant_users, jobs)
        user_matches_time = time.time() - user_matches_start

        # Calculate match statistics
        job_match_counts = {
            job_id: len(matches) for job_id, matches in job_matches.items()
        }
        user_match_counts = {
            user_id: len(matches) for user_id, matches in user_matches.items()
        }

        avg_matches_per_job = (
            sum(job_match_counts.values()) / len(job_match_counts)
            if job_match_counts
            else 0
        )
        avg_matches_per_user = (
            sum(user_match_counts.values()) / len(user_match_counts)
            if user_match_counts
            else 0
        )

        # Calculate score statistics
        all_job_scores = []
        for matches in job_matches.values():
            all_job_scores.extend([match["score"] for match in matches])

        all_user_scores = []
        for matches in user_matches.values():
            all_user_scores.extend([match["score"] for match in matches])

        avg_job_match_score = (
            sum(all_job_scores) / len(all_job_scores) if all_job_scores else 0
        )
        avg_user_match_score = (
            sum(all_user_scores) / len(all_user_scores) if all_user_scores else 0
        )

        # Collect user engagement scores
        engagement_scores = {}
        for user in applicant_users:
            engagement_scores[user.id] = get_user_engagement_score(user)

        # Find correlation between engagement and match quality
        engagement_match_correlation = self._calculate_correlation(
            [engagement_scores.get(user_id, 0) for user_id in user_match_counts.keys()],
            [count for count in user_match_counts.values()],
        )

        total_time = time.time() - start_time

        # Return results
        return {
            "timestamp": timezone.now().isoformat(),
            "num_users": len(applicant_users),
            "num_jobs": len(jobs),
            "job_matches_time": job_matches_time,
            "user_matches_time": user_matches_time,
            "total_time": total_time,
            "avg_matches_per_job": avg_matches_per_job,
            "avg_matches_per_user": avg_matches_per_user,
            "avg_job_match_score": avg_job_match_score,
            "avg_user_match_score": avg_user_match_score,
            "engagement_match_correlation": engagement_match_correlation,
            "job_match_counts": job_match_counts,
            "user_match_counts": user_match_counts,
            "engagement_scores": engagement_scores,
            # Include top matches for analysis
            "top_job_matches": {
                job_id: matches[:5] for job_id, matches in job_matches.items()
            },
            "top_user_matches": {
                user_id: matches[:5] for user_id, matches in user_matches.items()
            },
        }

    def _calculate_correlation(self, x: List[float], y: List[float]) -> float:
        """Calculate Pearson correlation coefficient between two lists"""
        if len(x) != len(y) or len(x) < 2:
            return 0.0

        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(x_i * y_i for x_i, y_i in zip(x, y))
        sum_x_sq = sum(x_i**2 for x_i in x)
        sum_y_sq = sum(y_i**2 for y_i in y)

        numerator = n * sum_xy - sum_x * sum_y
        denominator = ((n * sum_x_sq - sum_x**2) * (n * sum_y_sq - sum_y**2)) ** 0.5

        if denominator == 0:
            return 0.0

        return numerator / denominator

    def _print_iteration_summary(self, result: Dict[str, Any], iteration: int) -> None:
        """Print summary of a matching iteration"""
        self.stdout.write(
            self.style.SUCCESS(
                f'Iteration {iteration} completed in {result["total_time"]:.2f} seconds'
            )
        )
        self.stdout.write(
            f'  Job matching time: {result["job_matches_time"]:.2f} seconds'
        )
        self.stdout.write(
            f'  User matching time: {result["user_matches_time"]:.2f} seconds'
        )
        self.stdout.write(
            f'  Average matches per job: {result["avg_matches_per_job"]:.2f}'
        )
        self.stdout.write(
            f'  Average matches per user: {result["avg_matches_per_user"]:.2f}'
        )
        self.stdout.write(
            f'  Average job match score: {result["avg_job_match_score"]:.4f}'
        )
        self.stdout.write(
            f'  Average user match score: {result["avg_user_match_score"]:.4f}'
        )
        self.stdout.write(
            f'  Engagement-match correlation: {result["engagement_match_correlation"]:.4f}'
        )

    def _print_overall_summary(self, results: List[Dict[str, Any]]) -> None:
        """Print overall summary of all iterations"""
        avg_total_time = sum(r["total_time"] for r in results) / len(results)
        avg_job_matches_time = sum(r["job_matches_time"] for r in results) / len(
            results
        )
        avg_user_matches_time = sum(r["user_matches_time"] for r in results) / len(
            results
        )
        avg_matches_per_job = sum(r["avg_matches_per_job"] for r in results) / len(
            results
        )
        avg_matches_per_user = sum(r["avg_matches_per_user"] for r in results) / len(
            results
        )
        avg_job_match_score = sum(r["avg_job_match_score"] for r in results) / len(
            results
        )
        avg_user_match_score = sum(r["avg_user_match_score"] for r in results) / len(
            results
        )
        avg_correlation = sum(r["engagement_match_correlation"] for r in results) / len(
            results
        )

        self.stdout.write(self.style.SUCCESS("\nOverall Summary:"))
        self.stdout.write(f"  Number of iterations: {len(results)}")
        self.stdout.write(f"  Average total time: {avg_total_time:.2f} seconds")
        self.stdout.write(
            f"  Average job matching time: {avg_job_matches_time:.2f} seconds"
        )
        self.stdout.write(
            f"  Average user matching time: {avg_user_matches_time:.2f} seconds"
        )
        self.stdout.write(f"  Average matches per job: {avg_matches_per_job:.2f}")
        self.stdout.write(f"  Average matches per user: {avg_matches_per_user:.2f}")
        self.stdout.write(f"  Average job match score: {avg_job_match_score:.4f}")
        self.stdout.write(f"  Average user match score: {avg_user_match_score:.4f}")
        self.stdout.write(
            f"  Average engagement-match correlation: {avg_correlation:.4f}"
        )

        # Print performance analysis
        self.stdout.write(self.style.NOTICE("\nPerformance Analysis:"))
        self.stdout.write(
            f'  Jobs/second: {len(results[0]["job_match_counts"]) / avg_job_matches_time:.2f}'
        )
        self.stdout.write(
            f'  Users/second: {len(results[0]["user_match_counts"]) / avg_user_matches_time:.2f}'
        )
        self.stdout.write(
            f'  Matches/second: {avg_matches_per_job * len(results[0]["job_match_counts"]) / avg_total_time:.2f}'
        )

    def _save_results(self, results: List[Dict[str, Any]]) -> None:
        """Save detailed results to JSON file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"job_matching_simulation_{timestamp}.json"

        # Convert to serializable format
        serializable_results = []
        for result in results:
            serializable_result = {k: v for k, v in result.items()}
            # Convert non-serializable types
            if "timestamp" in serializable_result:
                serializable_result["timestamp"] = str(serializable_result["timestamp"])

            serializable_results.append(serializable_result)

        with open(filename, "w") as f:
            json.dump(serializable_results, f, indent=2)

        self.stdout.write(self.style.SUCCESS(f"Saved detailed results to {filename}"))

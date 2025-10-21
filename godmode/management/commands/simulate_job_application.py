"""
Django management command to simulate job applications.

This command creates test job applications from applicants to existing jobs.
It's useful for testing the job application workflow and matching algorithms.

Usage:
    python manage.py simulate_job_application --applicant-count=10 --applications-per-applicant=3
"""

import logging
import random
from typing import Any, Dict, List

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from gamification.models import UserActivity
from jobs.models import Application, Job

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Simulate job applications from applicants to jobs"

    def add_arguments(self, parser):
        parser.add_argument(
            "--applicant-count",
            type=int,
            default=10,
            help="Number of applicant users to create or use (default: 10)",
        )
        parser.add_argument(
            "--applications-per-applicant",
            type=int,
            default=3,
            help="Number of applications per applicant (default: 3)",
        )
        parser.add_argument(
            "--use-existing-applicants",
            action="store_true",
            help="Use existing applicant users instead of creating new ones",
        )

    def handle(self, *args, **options):
        applicant_count = options["applicant_count"]
        applications_per_applicant = options["applications_per_applicant"]
        use_existing_applicants = options["use_existing_applicants"]

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting job application simulation for {applicant_count} applicants, {applications_per_applicant} applications each"
            )
        )

        # Check if we have jobs
        job_count = Job.objects.filter(status="pending").count()
        if job_count == 0:
            self.stdout.write(
                self.style.WARNING("No pending jobs found. Please create jobs first.")
            )
            return {"error": "No pending jobs found"}

        # Get or create applicant users
        if use_existing_applicants:
            applicants = list(User.objects.filter(role="applicant")[:applicant_count])
            if len(applicants) < applicant_count:
                self.stdout.write(
                    self.style.WARNING(
                        f"Only {len(applicants)} existing applicants found, creating {applicant_count - len(applicants)} more"
                    )
                )
                # Import the applicant registration command
                from jobs.management.commands3.simulate_applicant_registration import \
                    Command as ApplicantCommand

                applicant_cmd = ApplicantCommand()
                applicant_results = applicant_cmd.create_applicant_users(
                    applicant_count - len(applicants),
                    "applicantpass123",
                    True,  # Create with location history
                )

                # Get the newly created applicants
                new_applicant_ids = [a["id"] for a in applicant_results["applicants"]]
                new_applicants = list(User.objects.filter(id__in=new_applicant_ids))

                # Combine with existing applicants
                applicants.extend(new_applicants)
        else:
            # Import the applicant registration command
            from jobs.management.commands3.simulate_applicant_registration import \
                Command as ApplicantCommand

            applicant_cmd = ApplicantCommand()
            applicant_results = applicant_cmd.create_applicant_users(
                applicant_count,
                "applicantpass123",
                True,  # Create with location history
            )

            # Get the newly created applicants
            applicant_ids = [a["id"] for a in applicant_results["applicants"]]
            applicants = list(User.objects.filter(id__in=applicant_ids))

        # Get available jobs
        jobs = list(Job.objects.filter(status="pending"))

        # Create applications
        results = self.create_applications(applicants, jobs, applications_per_applicant)

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {len(results['applications'])} job applications"
            )
        )

        # Print details of created applications
        for i, application in enumerate(results["applications"], 1):
            self.stdout.write(
                self.style.SUCCESS(
                    f"{i}. Application: {application['applicant_username']} applied to {application['job_title']}"
                )
            )

        # Return a string summary
        return f"Job application simulation completed: {len(results['applications'])} applications created for {len(set(app['applicant_id'] for app in results['applications']))} applicants"

    def create_applications(
        self, applicants: List[User], jobs: List[Job], applications_per_applicant: int
    ) -> Dict[str, Any]:
        """
        Create test job applications for the given applicants.

        Args:
            applicants: List of applicant users
            jobs: List of available jobs
            applications_per_applicant: Number of applications per applicant

        Returns:
            Dictionary with created applications
        """
        results = {"applications": [], "errors": []}

        for applicant in applicants:
            # Shuffle jobs to get random ones for each applicant
            available_jobs = random.sample(
                jobs, min(len(jobs), applications_per_applicant)
            )

            for job in available_jobs:
                try:
                    with transaction.atomic():
                        # Check if applicant already applied to this job
                        if Application.objects.filter(
                            applicant=applicant, job=job
                        ).exists():
                            continue

                        # Create application
                        application = Application.objects.create(
                            job=job, applicant=applicant, status="Pending"
                        )

                        # Record application activity
                        UserActivity.objects.create(
                            user=applicant,
                            activity_type="job_application",
                            details={
                                "job_id": job.id,
                                "application_id": application.id,
                                "source": "simulation",
                            },
                            points_earned=5,
                        )

                        # Add to results
                        results["applications"].append(
                            {
                                "id": application.id,
                                "job_id": job.id,
                                "job_title": job.title,
                                "applicant_id": applicant.id,
                                "applicant_username": applicant.username,
                                "status": "Pending",
                                "created_at": application.created_at.isoformat(),
                            }
                        )

                        logger.info(
                            f"Created application: {applicant.username} applied to job {job.title}"
                        )

                except Exception as e:
                    error_msg = f"Error creating application for {applicant.username} to job {job.id}: {str(e)}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)

        return results

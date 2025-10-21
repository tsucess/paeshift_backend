"""
Django management command to simulate job creation.

This command creates test jobs with different attributes and triggers
the geocoding process. It's useful for testing the job creation workflow
and geocoding functionality.

Usage:
    python manage.py simulate_job_creation --client-count=5 --jobs-per-client=3
"""

import logging
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from gamification.models import UserActivity
from jobs.models import Job, JobIndustry, JobSubCategory

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Simulate job creation with geocoding"

    def add_arguments(self, parser):
        parser.add_argument(
            "--client-count",
            type=int,
            default=5,
            help="Number of client users to create or use (default: 5)",
        )
        parser.add_argument(
            "--jobs-per-client",
            type=int,
            default=3,
            help="Number of jobs per client (default: 3)",
        )
        parser.add_argument(
            "--use-existing-clients",
            action="store_true",
            help="Use existing client users instead of creating new ones",
        )

    def handle(self, *args, **options):
        client_count = options["client_count"]
        jobs_per_client = options["jobs_per_client"]
        use_existing_clients = options["use_existing_clients"]

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting job creation simulation for {client_count} clients, {jobs_per_client} jobs each"
            )
        )

        # Check if we have industries and subcategories
        if JobIndustry.objects.count() == 0:
            self.stdout.write(
                self.style.WARNING(
                    "No job industries found. Creating sample industries..."
                )
            )
            self.create_sample_industries()

        # Get or create client users
        if use_existing_clients:
            clients = list(User.objects.filter(role="client")[:client_count])
            if len(clients) < client_count:
                self.stdout.write(
                    self.style.WARNING(
                        f"Only {len(clients)} existing clients found, creating {client_count - len(clients)} more"
                    )
                )
                # Import the client registration command
                from jobs.management.commands3.simulate_client_registration import \
                    Command as ClientCommand

                client_cmd = ClientCommand()
                client_results = client_cmd.create_client_users(
                    client_count - len(clients), "clientpass123"
                )

                # Get the newly created clients
                new_client_ids = [c["id"] for c in client_results["clients"]]
                new_clients = list(User.objects.filter(id__in=new_client_ids))

                # Combine with existing clients
                clients.extend(new_clients)
        else:
            # Import the client registration command
            from jobs.management.commands3.simulate_client_registration import \
                Command as ClientCommand

            client_cmd = ClientCommand()
            client_results = client_cmd.create_client_users(
                client_count, "clientpass123"
            )

            # Get the newly created clients
            client_ids = [c["id"] for c in client_results["clients"]]
            clients = list(User.objects.filter(id__in=client_ids))

        # Create jobs
        results = self.create_jobs(clients, jobs_per_client)

        self.stdout.write(self.style.SUCCESS(f"Created {len(results['jobs'])} jobs"))

        # Print details of created jobs
        for i, job in enumerate(results["jobs"], 1):
            self.stdout.write(
                self.style.SUCCESS(
                    f"{i}. Job: {job['title']} - Client: {job['client_username']} - Location: {job['location']}"
                )
            )

        # Return a string summary
        return f"Job creation simulation completed: {len(results['jobs'])} jobs created for {len(set(job['client_id'] for job in results['jobs']))} clients"

    def create_jobs(self, clients: List[User], jobs_per_client: int) -> Dict[str, Any]:
        """
        Create test jobs for the given clients.

        Args:
            clients: List of client users
            jobs_per_client: Number of jobs per client

        Returns:
            Dictionary with created jobs
        """
        results = {"jobs": [], "errors": []}

        # Sample data for realistic jobs
        job_titles = [
            "Web Developer Needed",
            "Graphic Designer for Logo",
            "Content Writer for Blog",
            "Data Entry Specialist",
            "Customer Service Representative",
            "Sales Associate",
            "Marketing Coordinator",
            "Accountant for Small Business",
            "English Teacher",
            "Translator for Documents",
            "Social Media Manager",
            "Administrative Assistant",
            "Event Planner",
            "Personal Assistant",
            "Software Engineer",
            "Mobile App Developer",
            "UI/UX Designer",
            "Video Editor",
            "Photographer for Event",
            "Delivery Driver",
        ]

        job_types = [
            "single_day",
            "multiple_days",
            "temporary",
            "part_time",
            "full_time",
        ]
        shift_types = ["morning", "afternoon", "evening", "night", "day", "flexible"]

        locations = [
            "Lagos, Nigeria",
            "Abuja, Nigeria",
            "Port Harcourt, Nigeria",
            "Ibadan, Nigeria",
            "Kano, Nigeria",
            "Kaduna, Nigeria",
            "Benin City, Nigeria",
            "Maiduguri, Nigeria",
            "Warri, Nigeria",
            "Enugu, Nigeria",
            "Owerri, Nigeria",
            "Uyo, Nigeria",
            "Calabar, Nigeria",
            "Jos, Nigeria",
            "Sokoto, Nigeria",
            "Ilorin, Nigeria",
        ]

        # Get all industries and subcategories
        industries = list(JobIndustry.objects.all())

        for client in clients:
            for j in range(jobs_per_client):
                try:
                    with transaction.atomic():
                        # Select random industry
                        industry = random.choice(industries)

                        # Get subcategories for this industry
                        subcategories = list(
                            JobSubCategory.objects.filter(industry=industry)
                        )
                        if not subcategories:
                            # Create a subcategory if none exists
                            subcategory = JobSubCategory.objects.create(
                                name=f"{industry.name} General", industry=industry
                            )
                            subcategories = [subcategory]

                        # Select random subcategory
                        subcategory = random.choice(subcategories)

                        # Generate random job details
                        title = random.choice(job_titles)
                        job_type = random.choice(job_types)
                        shift_type = random.choice(shift_types)
                        location = random.choice(locations)

                        # Generate random date in the future (1-30 days)
                        job_date = timezone.now().date() + timedelta(
                            days=random.randint(1, 30)
                        )

                        # Generate random start and end times
                        start_hour = random.randint(8, 16)
                        duration_hours = random.randint(2, 8)
                        start_time = datetime.strptime(
                            f"{start_hour}:00", "%H:%M"
                        ).time()
                        end_time = datetime.strptime(
                            f"{start_hour + duration_hours}:00", "%H:%M"
                        ).time()

                        # Generate random rate and applicants needed
                        rate = random.randint(1000, 10000)
                        applicants_needed = random.randint(1, 5)

                        # Create job
                        job = Job.objects.create(
                            client=client,
                            created_by=client,
                            title=title,
                            description=f"This is a test job for {title}. Created by simulation.",
                            industry=industry,
                            subcategory=subcategory,
                            job_type=job_type,
                            shift_type=shift_type,
                            date=job_date,
                            start_time=start_time,
                            end_time=end_time,
                            rate=rate,
                            applicants_needed=applicants_needed,
                            location=location,
                            payment_status="pending",
                            status="pending",
                        )

                        # Record job creation activity
                        UserActivity.objects.create(
                            user=client,
                            activity_type="job_creation",
                            details={
                                "job_id": job.id,
                                "title": job.title,
                                "source": "simulation",
                            },
                            points_earned=20,
                        )

                        # Add to results
                        results["jobs"].append(
                            {
                                "id": job.id,
                                "title": job.title,
                                "client_id": client.id,
                                "client_username": client.username,
                                "industry": industry.name,
                                "subcategory": subcategory.name,
                                "job_type": job_type,
                                "shift_type": shift_type,
                                "date": job_date.isoformat(),
                                "start_time": start_time.strftime("%H:%M"),
                                "end_time": end_time.strftime("%H:%M"),
                                "rate": rate,
                                "applicants_needed": applicants_needed,
                                "location": location,
                                "status": "pending",
                            }
                        )

                        logger.info(
                            f"Created job: {job.title} for client {client.username}"
                        )

                except Exception as e:
                    error_msg = (
                        f"Error creating job for client {client.username}: {str(e)}"
                    )
                    logger.error(error_msg)
                    results["errors"].append(error_msg)

        return results

    def create_sample_industries(self):
        """Create sample industries and subcategories if none exist"""
        industries_data = [
            {
                "name": "Technology",
                "subcategories": [
                    "Web Development",
                    "Mobile Development",
                    "Software Engineering",
                    "Data Science",
                    "IT Support",
                ],
            },
            {
                "name": "Design",
                "subcategories": [
                    "Graphic Design",
                    "UI/UX Design",
                    "Logo Design",
                    "Illustration",
                    "Animation",
                ],
            },
            {
                "name": "Writing",
                "subcategories": [
                    "Content Writing",
                    "Copywriting",
                    "Technical Writing",
                    "Creative Writing",
                    "Editing",
                ],
            },
            {
                "name": "Customer Service",
                "subcategories": [
                    "Call Center",
                    "Customer Support",
                    "Virtual Assistant",
                    "Technical Support",
                    "Chat Support",
                ],
            },
            {
                "name": "Sales & Marketing",
                "subcategories": [
                    "Digital Marketing",
                    "Social Media Marketing",
                    "SEO",
                    "Sales",
                    "Market Research",
                ],
            },
        ]

        for industry_data in industries_data:
            try:
                with transaction.atomic():
                    industry = JobIndustry.objects.create(name=industry_data["name"])

                    for subcategory_name in industry_data["subcategories"]:
                        JobSubCategory.objects.create(
                            name=subcategory_name, industry=industry
                        )

                    logger.info(
                        f"Created industry: {industry.name} with {len(industry_data['subcategories'])} subcategories"
                    )

            except Exception as e:
                logger.error(
                    f"Error creating industry {industry_data['name']}: {str(e)}"
                )

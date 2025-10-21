"""
Django management command to simulate applicant registration.

This command creates test applicant users with profiles and sample data.
It's useful for testing the applicant functionality and job application process.

Usage:
    python manage.py simulate_applicant_registration --count=20
"""

import logging
import random
import string
from typing import Any, Dict, List

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import Profile
from gamification.models import UserActivity, UserPoints
from jobchat.models import LocationHistory
from jobs.models import Job

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Simulate applicant registration with profiles"

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=20,
            help="Number of applicant users to create (default: 20)",
        )
        parser.add_argument(
            "--password",
            type=str,
            default="applicantpass123",
            help="Password for applicant users (default: applicantpass123)",
        )
        parser.add_argument(
            "--with-location",
            action="store_true",
            help="Create location history for applicants",
        )

    def handle(self, *args, **options):
        count = options["count"]
        password = options["password"]
        with_location = options["with_location"]

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting applicant registration simulation for {count} users"
            )
        )

        results = self.create_applicant_users(count, password, with_location)

        self.stdout.write(
            self.style.SUCCESS(f"Created {len(results['applicants'])} applicant users")
        )

        # Print details of created applicants
        for i, applicant in enumerate(results["applicants"], 1):
            self.stdout.write(
                self.style.SUCCESS(
                    f"{i}. Applicant: {applicant['username']} ({applicant['email']}) - {applicant['first_name']} {applicant['last_name']}"
                )
            )

        # Return a string summary instead of a dictionary
        return f"Applicant registration simulation completed: {len(results['applicants'])} applicant users created"

    def create_applicant_users(
        self, count: int, password: str, with_location: bool = False
    ) -> Dict[str, Any]:
        """
        Create test applicant users with profiles.

        Args:
            count: Number of applicant users to create
            password: Password for applicant users
            with_location: Whether to create location history

        Returns:
            Dictionary with created applicant users
        """
        results = {"applicants": [], "errors": []}

        # Sample data for realistic applicant profiles
        first_names = [
            "David",
            "Susan",
            "Joseph",
            "Margaret",
            "Charles",
            "Jessica",
            "Thomas",
            "Sarah",
            "Daniel",
            "Nancy",
        ]
        last_names = [
            "Wilson",
            "Moore",
            "Taylor",
            "Anderson",
            "Thomas",
            "Jackson",
            "White",
            "Harris",
            "Martin",
            "Thompson",
        ]
        skills = [
            "Web Development",
            "Graphic Design",
            "Content Writing",
            "Data Entry",
            "Customer Service",
            "Sales",
            "Marketing",
            "Accounting",
            "Teaching",
            "Translation",
        ]
        education_levels = [
            "High School",
            "Associate's Degree",
            "Bachelor's Degree",
            "Master's Degree",
            "PhD",
        ]
        locations = [
            {"name": "Lagos, Nigeria", "lat": 6.5244, "lng": 3.3792},
            {"name": "Abuja, Nigeria", "lat": 9.0765, "lng": 7.3986},
            {"name": "Port Harcourt, Nigeria", "lat": 4.8156, "lng": 7.0498},
            {"name": "Ibadan, Nigeria", "lat": 7.3775, "lng": 3.9470},
            {"name": "Kano, Nigeria", "lat": 12.0022, "lng": 8.5920},
            {"name": "Kaduna, Nigeria", "lat": 10.5222, "lng": 7.4383},
            {"name": "Benin City, Nigeria", "lat": 6.3350, "lng": 5.6037},
            {"name": "Maiduguri, Nigeria", "lat": 11.8311, "lng": 13.1510},
            {"name": "Warri, Nigeria", "lat": 5.5156, "lng": 5.7478},
            {"name": "Enugu, Nigeria", "lat": 6.4584, "lng": 7.5464},
        ]

        for i in range(count):
            try:
                with transaction.atomic():
                    # Generate unique username and email
                    username = f"applicant_{i+1}_{random.randint(1000, 9999)}"
                    email = f"{username}@example.com"
                    first_name = random.choice(first_names)
                    last_name = random.choice(last_names)

                    # Create user
                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        password=password,
                        first_name=first_name,
                        last_name=last_name,
                        role="applicant",
                    )

                    # Select random location
                    location = random.choice(locations)

                    # Create profile
                    profile = Profile.objects.create(
                        user=user,
                        role="applicant",
                        skills=", ".join(random.sample(skills, k=random.randint(1, 5))),
                        education=random.choice(education_levels),
                        location=location["name"],
                        bio=f"Applicant profile for {first_name} {last_name}",
                    )

                    # Create user points for gamification
                    user_points = UserPoints.objects.create(
                        user=user,
                        total_points=random.randint(0, 200),
                        level=random.randint(1, 10),
                    )

                    # Record registration activity
                    UserActivity.objects.create(
                        user=user,
                        activity_type="registration",
                        details={"role": "applicant", "source": "simulation"},
                        points_earned=10,
                    )

                    # Create location history if requested
                    if with_location:
                        # Get a random job to associate with the location history
                        jobs = list(Job.objects.all()[:5])
                        if jobs:
                            job = random.choice(jobs)
                            # Create a few location history entries with slight variations
                            for j in range(3):
                                # Add small random variation to coordinates
                                lat_variation = random.uniform(-0.05, 0.05)
                                lng_variation = random.uniform(-0.05, 0.05)

                                LocationHistory.objects.create(
                                    user=user,
                                    job=job,
                                    latitude=location["lat"] + lat_variation,
                                    longitude=location["lng"] + lng_variation,
                                )

                    # Add to results
                    results["applicants"].append(
                        {
                            "id": user.id,
                            "username": username,
                            "email": email,
                            "first_name": first_name,
                            "last_name": last_name,
                            "profile_id": profile.id,
                            "skills": profile.skills,
                            "education": profile.education,
                            "location": profile.location,
                        }
                    )

                    logger.info(
                        f"Created applicant user: {username} ({first_name} {last_name})"
                    )

            except Exception as e:
                error_msg = f"Error creating applicant user: {str(e)}"
                logger.error(error_msg)
                results["errors"].append(error_msg)

        return results

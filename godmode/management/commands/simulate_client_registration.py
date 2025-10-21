"""
Django management command to simulate client registration.

This command creates test client users with profiles and sample data.
It's useful for testing the client functionality and job creation process.

Usage:
    python manage.py simulate_client_registration --count=10
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

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Simulate client registration with profiles"

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=10,
            help="Number of client users to create (default: 10)",
        )
        parser.add_argument(
            "--password",
            type=str,
            default="clientpass123",
            help="Password for client users (default: clientpass123)",
        )

    def handle(self, *args, **options):
        count = options["count"]
        password = options["password"]

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting client registration simulation for {count} users"
            )
        )

        results = self.create_client_users(count, password)

        self.stdout.write(
            self.style.SUCCESS(f"Created {len(results['clients'])} client users")
        )

        # Print details of created clients
        for i, client in enumerate(results["clients"], 1):
            self.stdout.write(
                self.style.SUCCESS(
                    f"{i}. Client: {client['username']} ({client['email']}) - {client['first_name']} {client['last_name']}"
                )
            )

        # Return a string summary instead of a dictionary
        return f"Client registration simulation completed: {len(results['clients'])} client users created"

    def create_client_users(self, count: int, password: str) -> Dict[str, Any]:
        """
        Create test client users with profiles.

        Args:
            count: Number of client users to create
            password: Password for client users

        Returns:
            Dictionary with created client users
        """
        results = {"clients": [], "errors": []}

        # Sample data for realistic client profiles
        first_names = [
            "James",
            "Mary",
            "John",
            "Patricia",
            "Robert",
            "Jennifer",
            "Michael",
            "Linda",
            "William",
            "Elizabeth",
        ]
        last_names = [
            "Smith",
            "Johnson",
            "Williams",
            "Brown",
            "Jones",
            "Garcia",
            "Miller",
            "Davis",
            "Rodriguez",
            "Martinez",
        ]
        company_names = [
            "Acme Corp",
            "Globex",
            "Initech",
            "Umbrella Corp",
            "Stark Industries",
            "Wayne Enterprises",
            "Cyberdyne Systems",
            "Soylent Corp",
            "Massive Dynamic",
            "Oscorp",
        ]
        industries = [
            "Technology",
            "Healthcare",
            "Finance",
            "Retail",
            "Manufacturing",
            "Construction",
            "Education",
            "Hospitality",
            "Transportation",
            "Energy",
        ]
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
        ]

        for i in range(count):
            try:
                with transaction.atomic():
                    # Generate unique username and email
                    username = f"client_{i+1}_{random.randint(1000, 9999)}"
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
                        role="client",
                    )

                    # Create profile
                    profile = Profile.objects.create(
                        user=user,
                        role="client",
                        location=random.choice(locations),
                        bio=f"Client profile for {first_name} {last_name} at {random.choice(company_names)} in the {random.choice(industries)} industry.",
                    )

                    # Create user points for gamification
                    user_points = UserPoints.objects.create(
                        user=user,
                        total_points=random.randint(0, 100),
                        level=random.randint(1, 5),
                    )

                    # Record registration activity
                    UserActivity.objects.create(
                        user=user,
                        activity_type="registration",
                        details={"role": "client", "source": "simulation"},
                        points_earned=10,
                    )

                    # Add to results
                    results["clients"].append(
                        {
                            "id": user.id,
                            "username": username,
                            "email": email,
                            "first_name": first_name,
                            "last_name": last_name,
                            "profile_id": profile.id,
                            "location": profile.location,
                        }
                    )

                    logger.info(
                        f"Created client user: {username} ({first_name} {last_name})"
                    )

            except Exception as e:
                error_msg = f"Error creating client user: {str(e)}"
                logger.error(error_msg)
                results["errors"].append(error_msg)

        return results

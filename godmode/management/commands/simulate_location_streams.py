"""
Simulate location streams for the Payshift platform.

This command simulates the creation and updating of location data for users, including:
- Home address (static location in user profile)
- Job locations (locations associated with jobs)
- Live location history (dynamic location updates as users move)

Usage:
    python manage.py simulate_location_streams --user-count=10 --updates-per-user=5
"""

import json
import logging
import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Profile
from jobchat.models import LocationHistory
from jobs.models import Job

User = get_user_model()
logger = logging.getLogger(__name__)

# Sample locations in Nigeria
NIGERIA_LOCATIONS = [
    {
        "name": "Lagos, Nigeria",
        "lat": 6.5244,
        "lng": 3.3792,
        "areas": [
            {"name": "Ikeja", "lat": 6.6018, "lng": 3.3515},
            {"name": "Victoria Island", "lat": 6.4281, "lng": 3.4219},
            {"name": "Lekki", "lat": 6.4698, "lng": 3.5852},
            {"name": "Surulere", "lat": 6.5059, "lng": 3.3509},
            {"name": "Yaba", "lat": 6.5165, "lng": 3.3838},
        ],
    },
    {
        "name": "Abuja, Nigeria",
        "lat": 9.0765,
        "lng": 7.3986,
        "areas": [
            {"name": "Wuse", "lat": 9.0765, "lng": 7.4756},
            {"name": "Garki", "lat": 9.0297, "lng": 7.4951},
            {"name": "Maitama", "lat": 9.0876, "lng": 7.4863},
            {"name": "Asokoro", "lat": 9.0437, "lng": 7.5320},
            {"name": "Gwarinpa", "lat": 9.1192, "lng": 7.3756},
        ],
    },
    {
        "name": "Port Harcourt, Nigeria",
        "lat": 4.8156,
        "lng": 7.0498,
        "areas": [
            {"name": "GRA", "lat": 4.8320, "lng": 7.0080},
            {"name": "Rumuola", "lat": 4.8372, "lng": 7.0126},
            {"name": "Rumuokoro", "lat": 4.8708, "lng": 6.9997},
            {"name": "Elekahia", "lat": 4.8156, "lng": 7.0498},
            {"name": "Diobu", "lat": 4.7833, "lng": 7.0167},
        ],
    },
    {
        "name": "Kano, Nigeria",
        "lat": 12.0022,
        "lng": 8.5920,
        "areas": [
            {"name": "Nassarawa", "lat": 12.0022, "lng": 8.5920},
            {"name": "Fagge", "lat": 12.0000, "lng": 8.5167},
            {"name": "Dala", "lat": 12.0500, "lng": 8.5167},
            {"name": "Gwale", "lat": 12.0500, "lng": 8.5500},
            {"name": "Tarauni", "lat": 11.9833, "lng": 8.5500},
        ],
    },
    {
        "name": "Ibadan, Nigeria",
        "lat": 7.3775,
        "lng": 3.9470,
        "areas": [
            {"name": "Bodija", "lat": 7.4167, "lng": 3.9167},
            {"name": "Dugbe", "lat": 7.3833, "lng": 3.8833},
            {"name": "Mokola", "lat": 7.4000, "lng": 3.9000},
            {"name": "Iwo Road", "lat": 7.4000, "lng": 4.0000},
            {"name": "Challenge", "lat": 7.3500, "lng": 3.8833},
        ],
    },
]


class Command(BaseCommand):
    help = "Simulate location streams for the Payshift platform"

    def add_arguments(self, parser):
        parser.add_argument(
            "--user-count",
            type=int,
            default=10,
            help="Number of users to update locations for",
        )
        parser.add_argument(
            "--updates-per-user",
            type=int,
            default=5,
            help="Number of location updates per user",
        )
        parser.add_argument(
            "--update-home-address",
            action="store_true",
            help="Update home addresses in user profiles",
        )
        parser.add_argument(
            "--create-location-history",
            action="store_true",
            help="Create location history entries",
        )
        parser.add_argument(
            "--update-job-locations",
            action="store_true",
            help="Update job locations",
        )

    def handle(self, *args, **options):
        user_count = options["user_count"]
        updates_per_user = options["updates_per_user"]
        update_home_address = options["update_home_address"]
        create_location_history = options["create_location_history"]
        update_job_locations = options["update_job_locations"]

        # If no specific options are selected, do all updates
        if not any(
            [update_home_address, create_location_history, update_job_locations]
        ):
            update_home_address = True
            create_location_history = True
            update_job_locations = True

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting location streams simulation for {user_count} users "
                f"with {updates_per_user} updates per user"
            )
        )

        # Get users
        users = self.get_users(user_count)

        if not users:
            self.stdout.write(
                self.style.WARNING("No users available for location updates")
            )
            return "No users available for location updates"

        # Initialize results
        results = {
            "home_address_updates": [],
            "location_history_entries": [],
            "job_location_updates": [],
        }

        # Update home addresses
        if update_home_address:
            self.stdout.write("Updating home addresses...")
            home_results = self.update_home_addresses(users)
            results["home_address_updates"] = home_results
            self.stdout.write(
                self.style.SUCCESS(f"Updated {len(home_results)} home addresses")
            )

        # Create location history
        if create_location_history:
            self.stdout.write("Creating location history entries...")
            history_results = self.create_location_histories(users, updates_per_user)
            results["location_history_entries"] = history_results
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created {len(history_results)} location history entries"
                )
            )

        # Update job locations
        if update_job_locations:
            self.stdout.write("Updating job locations...")
            job_results = self.update_job_locations()
            results["job_location_updates"] = job_results
            self.stdout.write(
                self.style.SUCCESS(f"Updated {len(job_results)} job locations")
            )

        # Return a string summary
        summary = f"Location streams simulation completed: "
        if update_home_address:
            summary += (
                f"{len(results['home_address_updates'])} home addresses updated, "
            )
        if create_location_history:
            summary += f"{len(results['location_history_entries'])} location history entries created, "
        if update_job_locations:
            summary += f"{len(results['job_location_updates'])} job locations updated"

        return summary.rstrip(", ")

    def get_users(self, count: int) -> List[User]:
        """
        Get users for location updates.

        Args:
            count: Number of users to get

        Returns:
            List of users
        """
        # Get users with profiles
        users = list(User.objects.filter(profile__isnull=False)[:count])

        # If we don't have enough users, get any users
        if len(users) < count:
            more_users = list(
                User.objects.exclude(id__in=[user.id for user in users])[
                    : count - len(users)
                ]
            )

            users.extend(more_users)

        return users[:count]

    def update_home_addresses(self, users: List[User]) -> List[Dict]:
        """
        Update home addresses in user profiles.

        Args:
            users: List of users to update

        Returns:
            List of update results
        """
        results = []

        for user in users:
            # Get or create profile
            profile, created = Profile.objects.get_or_create(user=user)

            # Select a random location
            location = random.choice(NIGERIA_LOCATIONS)
            area = random.choice(location["areas"])

            # Add some randomness to coordinates
            lat_variation = random.uniform(-0.01, 0.01)
            lng_variation = random.uniform(-0.01, 0.01)

            # Update profile
            profile.location = f"{area['name']}, {location['name']}"
            profile.save()

            # Add to results
            results.append(
                {
                    "user_id": user.id,
                    "username": user.username,
                    "profile_id": profile.id,
                    "location": profile.location,
                    "latitude": area["lat"] + lat_variation,
                    "longitude": area["lng"] + lng_variation,
                    "timestamp": timezone.now().isoformat(),
                }
            )

        return results

    def create_location_histories(
        self, users: List[User], updates_per_user: int
    ) -> List[Dict]:
        """
        Create location history entries for users.

        Args:
            users: List of users to create history for
            updates_per_user: Number of updates per user

        Returns:
            List of created history entries
        """
        results = []

        # Get jobs for location history
        jobs = list(Job.objects.all()[:50])

        if not jobs:
            self.stdout.write(
                self.style.WARNING("No jobs available for location history")
            )
            return results

        for user in users:
            # Select a base location
            location = random.choice(NIGERIA_LOCATIONS)

            # Create multiple history entries
            for i in range(updates_per_user):
                # Select a random job
                job = random.choice(jobs)

                # Add some randomness to coordinates to simulate movement
                lat_variation = random.uniform(-0.05, 0.05)
                lng_variation = random.uniform(-0.05, 0.05)

                # Create timestamp with some time difference
                timestamp = timezone.now() - timedelta(
                    minutes=random.randint(0, 60 * 24)
                )

                # Create location history entry
                history = LocationHistory.objects.create(
                    user=user,
                    job=job,
                    latitude=location["lat"] + lat_variation,
                    longitude=location["lng"] + lng_variation,
                )

                # Add to results
                results.append(
                    {
                        "id": history.id,
                        "user_id": user.id,
                        "username": user.username,
                        "job_id": job.id,
                        "job_title": job.title,
                        "latitude": history.latitude,
                        "longitude": history.longitude,
                        "created_at": history.created_at.isoformat(),
                    }
                )

        return results

    def update_job_locations(self) -> List[Dict]:
        """
        Update job locations.

        Returns:
            List of update results
        """
        results = []

        # Get jobs without coordinates
        jobs = list(
            Job.objects.filter(latitude__isnull=True, longitude__isnull=True)[:50]
        )

        # If we don't have enough jobs without coordinates, get any jobs
        if len(jobs) < 50:
            more_jobs = list(
                Job.objects.exclude(id__in=[job.id for job in jobs])[: 50 - len(jobs)]
            )

            jobs.extend(more_jobs)

        for job in jobs:
            # Select a random location
            location = random.choice(NIGERIA_LOCATIONS)
            area = random.choice(location["areas"])

            # Add some randomness to coordinates
            lat_variation = random.uniform(-0.01, 0.01)
            lng_variation = random.uniform(-0.01, 0.01)

            # Update job
            job.location = f"{area['name']}, {location['name']}"
            job.latitude = area["lat"] + lat_variation
            job.longitude = area["lng"] + lng_variation
            job.save()

            # Add to results
            results.append(
                {
                    "job_id": job.id,
                    "job_title": job.title,
                    "location": job.location,
                    "latitude": job.latitude,
                    "longitude": job.longitude,
                    "client_id": job.client_id,
                    "updated_at": timezone.now().isoformat(),
                }
            )

        return results

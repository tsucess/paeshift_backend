"""
Django management command to simulate admin registration.

This command creates test admin users with different roles and permissions.
It's useful for testing the admin functionality and permissions system.

Usage:
    python manage.py simulate_admin_registration --count=5
"""

import logging
import random
import string
from typing import Any, Dict, List

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from adminaccess.models import AdminProfile, AdminRole

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Simulate admin registration with different roles"

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=3,
            help="Number of admin users to create (default: 3)",
        )
        parser.add_argument(
            "--password",
            type=str,
            default="adminpass123",
            help="Password for admin users (default: adminpass123)",
        )

    def handle(self, *args, **options):
        count = options["count"]
        password = options["password"]

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting admin registration simulation for {count} users"
            )
        )

        results = self.create_admin_users(count, password)

        self.stdout.write(
            self.style.SUCCESS(f"Created {len(results['admins'])} admin users")
        )

        # Print details of created admins
        for i, admin in enumerate(results["admins"], 1):
            self.stdout.write(
                self.style.SUCCESS(
                    f"{i}. Admin: {admin['username']} ({admin['email']}) - Role: {admin['role']}"
                )
            )

        # Return a string summary instead of a dictionary
        return f"Admin registration simulation completed: {len(results['admins'])} admin users created"

    def create_admin_users(self, count: int, password: str) -> Dict[str, Any]:
        """
        Create test admin users with different roles.

        Args:
            count: Number of admin users to create
            password: Password for admin users

        Returns:
            Dictionary with created admin users
        """
        results = {"admins": [], "errors": []}

        # Define possible admin roles
        roles = ["super_admin", "content_admin", "support_admin", "finance_admin"]

        for i in range(count):
            try:
                with transaction.atomic():
                    # Generate unique username and email
                    username = f"admin_{i+1}_{random.randint(1000, 9999)}"
                    email = f"{username}@example.com"
                    first_name = random.choice(
                        ["John", "Jane", "Alex", "Sarah", "Michael", "Emma"]
                    )
                    last_name = random.choice(
                        ["Smith", "Johnson", "Williams", "Brown", "Jones", "Miller"]
                    )

                    # Create superuser
                    user = User.objects.create_superuser(
                        username=username,
                        email=email,
                        password=password,
                        first_name=first_name,
                        last_name=last_name,
                        role="admin",
                    )

                    # Assign random role
                    role = random.choice(roles)

                    # Create admin profile
                    admin_profile = AdminProfile.objects.create(
                        user=user, current_dispute_count=0
                    )

                    # Create admin role
                    admin_role = AdminRole.objects.create(user=user, role=role)

                    # Add to results
                    results["admins"].append(
                        {
                            "id": user.id,
                            "username": username,
                            "email": email,
                            "first_name": first_name,
                            "last_name": last_name,
                            "role": role,
                            "profile_id": admin_profile.id,
                            "role_id": admin_role.id,
                        }
                    )

                    logger.info(f"Created admin user: {username} with role {role}")

            except Exception as e:
                error_msg = f"Error creating admin user: {str(e)}"
                logger.error(error_msg)
                results["errors"].append(error_msg)

        return results

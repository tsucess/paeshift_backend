"""
Management command to create default roles in the system.
"""
import logging

from django.core.management.base import BaseCommand

from accounts.models import Role

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Create default roles in the system."""

    help = "Create default roles in the system"

    def handle(self, *args, **options):
        """Create default roles."""
        self.stdout.write("Creating default roles...")

        # Define default roles
        default_roles = [
            {"name": Role.APPLICANT, "description": "Job applicant role"},
            {"name": Role.CLIENT, "description": "Client role"},
            {"name": Role.ADMIN, "description": "Administrator role"},
        ]

        # Create roles
        for role_data in default_roles:
            role, created = Role.objects.get_or_create(
                name=role_data["name"],
                defaults={"description": role_data["description"]}
            )

            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"Created role: {role.name}")
                )
                logger.info(f"Created role: {role.name}")
            else:
                self.stdout.write(
                    self.style.WARNING(f"Role already exists: {role.name}")
                )
                logger.debug(f"Role already exists: {role.name}")

        self.stdout.write(self.style.SUCCESS("Default roles created successfully"))

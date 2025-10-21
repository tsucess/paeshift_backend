"""
Management command to ensure default roles exist in the system.
"""
import logging

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Role

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Ensure default roles exist in the system."""

    help = "Ensure default roles exist in the system"

    def handle(self, *args, **options):
        """Create default roles if they don't exist."""
        self.stdout.write("Ensuring default roles exist...")

        # Define default roles
        default_roles = [
            {"name": Role.APPLICANT, "description": "Job applicant role"},
            {"name": Role.CLIENT, "description": "Client role"},
            {"name": Role.ADMIN, "description": "Administrator role"},
        ]

        # Create roles if they don't exist
        with transaction.atomic():
            for role_data in default_roles:
                role, created = Role.objects.get_or_create(
                    name=role_data["name"],
                    defaults={"description": role_data["description"]}
                )

                if created:
                    self.stdout.write(
                        self.style.SUCCESS(f"Created role: {role.name} (ID: {role.id})")
                    )
                    logger.info(f"Created role: {role.name} (ID: {role.id})")
                else:
                    self.stdout.write(
                        self.style.WARNING(f"Role already exists: {role.name} (ID: {role.id})")
                    )
                    logger.debug(f"Role already exists: {role.name} (ID: {role.id})")

        # List all roles
        self.stdout.write("\nAll roles in the database:")
        for role in Role.objects.all():
            self.stdout.write(f"- {role.name} (ID: {role.id}): {role.description}")

        self.stdout.write(self.style.SUCCESS("Default roles check completed successfully"))

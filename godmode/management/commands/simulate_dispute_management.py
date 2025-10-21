"""
Simulate dispute management for the Payshift platform.

This command simulates the creation and resolution of disputes between clients and applicants.
It creates dispute records, assigns them to admins, and simulates the resolution process.

Usage:
    python manage.py simulate_dispute_management --count=5 --resolution-rate=0.7
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

from adminaccess.models import AdminProfile
from disputes.models import Dispute, DisputeMessage
from jobs.models import Application, Job

User = get_user_model()
logger = logging.getLogger(__name__)

# Dispute types and reasons
DISPUTE_TYPES = ["payment", "behavior", "quality", "attendance", "communication"]
DISPUTE_REASONS = {
    "payment": [
        "Payment amount incorrect",
        "Payment delayed",
        "Payment not received",
        "Unauthorized deductions",
    ],
    "behavior": [
        "Unprofessional conduct",
        "Harassment",
        "Discrimination",
        "Safety concerns",
    ],
    "quality": [
        "Work not completed as agreed",
        "Poor quality of work",
        "Incomplete work",
        "Not following instructions",
    ],
    "attendance": [
        "Late arrival",
        "Early departure",
        "No-show",
        "Excessive breaks",
    ],
    "communication": [
        "Lack of communication",
        "Misleading information",
        "Language barrier",
        "Unresponsive to messages",
    ],
}

# Resolution messages
RESOLUTION_MESSAGES = [
    "After reviewing the evidence, we have determined that the dispute is valid.",
    "Based on our investigation, we have resolved this dispute in favor of the {party}.",
    "We have carefully considered both sides and reached a fair resolution.",
    "The dispute has been resolved according to our platform policies.",
    "We have mediated this dispute and reached a mutually acceptable solution.",
]


class Command(BaseCommand):
    help = "Simulate dispute management for the Payshift platform"

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=5,
            help="Number of disputes to create",
        )
        parser.add_argument(
            "--resolution-rate",
            type=float,
            default=0.7,
            help="Rate at which disputes are resolved (0.0-1.0)",
        )
        parser.add_argument(
            "--client-favor-rate",
            type=float,
            default=0.5,
            help="Rate at which resolutions favor the client (0.0-1.0)",
        )

    def handle(self, *args, **options):
        count = options["count"]
        resolution_rate = options["resolution_rate"]
        client_favor_rate = options["client_favor_rate"]

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting dispute management simulation for {count} disputes "
                f"with {resolution_rate:.0%} resolution rate"
            )
        )

        # Get applications for disputes
        applications = self.get_applications_for_disputes(count)

        if not applications:
            self.stdout.write(
                self.style.WARNING("No applications available for dispute creation")
            )
            return "No applications available for dispute creation"

        # Get admin users for dispute assignment
        admins = self.get_admin_users()

        if not admins:
            self.stdout.write(
                self.style.WARNING("No admin users available for dispute assignment")
            )
            return "No admin users available for dispute assignment"

        # Create disputes
        results = self.create_disputes(
            applications, admins, resolution_rate, client_favor_rate
        )

        # Print summary
        self.stdout.write(
            self.style.SUCCESS(f"Created {len(results['disputes'])} disputes")
        )
        self.stdout.write(f"Resolved disputes: {results['resolved_count']}")
        self.stdout.write(f"Pending disputes: {results['pending_count']}")

        # Return a string summary
        return f"Dispute management simulation completed: {len(results['disputes'])} disputes created with {results['resolved_count']} resolved and {results['pending_count']} pending"

    def get_applications_for_disputes(self, count: int) -> List[Application]:
        """
        Get applications that can have disputes.

        Args:
            count: Number of applications to get

        Returns:
            List of applications
        """
        # Get applications with status 'Accepted' or 'Completed'
        applications = list(
            Application.objects.filter(
                status__in=["Accepted", "Completed"]
            ).select_related("job", "applicant", "job__client")[: count * 2]
        )

        # If we don't have enough applications, get any applications
        if len(applications) < count:
            more_applications = list(
                Application.objects.exclude(
                    id__in=[app.id for app in applications]
                ).select_related("job", "applicant", "job__client")[
                    : count - len(applications)
                ]
            )

            applications.extend(more_applications)

        # Shuffle and return the requested number
        random.shuffle(applications)
        return applications[:count]

    def get_admin_users(self) -> List[User]:
        """
        Get admin users for dispute assignment.

        Returns:
            List of admin users
        """
        # Get users with admin profiles
        admin_profiles = AdminProfile.objects.select_related("user").all()

        if not admin_profiles:
            # If no admin profiles exist, get users with role 'admin'
            return list(User.objects.filter(role="admin"))

        return [profile.user for profile in admin_profiles]

    def create_disputes(
        self,
        applications: List[Application],
        admins: List[User],
        resolution_rate: float,
        client_favor_rate: float,
    ) -> Dict:
        """
        Create disputes for applications.

        Args:
            applications: List of applications to create disputes for
            admins: List of admin users for assignment
            resolution_rate: Rate at which disputes are resolved
            client_favor_rate: Rate at which resolutions favor the client

        Returns:
            Dictionary with results
        """
        results = {
            "disputes": [],
            "resolved_count": 0,
            "pending_count": 0,
        }

        for application in applications:
            # Determine if client or applicant is filing the dispute
            is_client_filing = random.random() < 0.5

            # Get the parties involved
            client = application.job.client
            applicant = application.applicant

            # Select dispute type and reason
            dispute_type = random.choice(DISPUTE_TYPES)
            dispute_reason = random.choice(DISPUTE_REASONS[dispute_type])

            # Select admin with lowest current dispute count
            admin = self.select_admin_with_lowest_workload(admins)

            # Create dispute
            with transaction.atomic():
                dispute = Dispute.objects.create(
                    job=application.job,
                    application=application,
                    filed_by=client if is_client_filing else applicant,
                    filed_against=applicant if is_client_filing else client,
                    assigned_admin=admin,
                    dispute_type=dispute_type,
                    reason=dispute_reason,
                    description=f"Dispute regarding {dispute_type}: {dispute_reason}",
                    status="Pending",
                    created_at=timezone.now(),
                )

                # Create initial message
                DisputeMessage.objects.create(
                    dispute=dispute,
                    sender=client if is_client_filing else applicant,
                    message=f"I am filing a dispute regarding {dispute_reason.lower()}. This issue needs to be resolved.",
                    created_at=timezone.now(),
                )

                # Create response from the other party
                DisputeMessage.objects.create(
                    dispute=dispute,
                    sender=applicant if is_client_filing else client,
                    message=f"I acknowledge this dispute and would like to provide my perspective on the matter.",
                    created_at=timezone.now() + timedelta(hours=random.randint(1, 24)),
                )

                # Determine if this dispute will be resolved
                will_resolve = random.random() < resolution_rate

                if will_resolve:
                    # Determine which party the resolution favors
                    favors_client = random.random() < client_favor_rate
                    favored_party = "client" if favors_client else "applicant"

                    # Create admin message
                    DisputeMessage.objects.create(
                        dispute=dispute,
                        sender=admin,
                        message=f"I have reviewed this dispute and will now provide a resolution.",
                        created_at=timezone.now()
                        + timedelta(hours=random.randint(24, 72)),
                    )

                    # Create resolution message
                    resolution_message = random.choice(RESOLUTION_MESSAGES).format(
                        party=favored_party
                    )
                    DisputeMessage.objects.create(
                        dispute=dispute,
                        sender=admin,
                        message=resolution_message,
                        created_at=timezone.now()
                        + timedelta(hours=random.randint(73, 96)),
                    )

                    # Update dispute status
                    dispute.status = "Resolved"
                    dispute.resolution = resolution_message
                    dispute.resolved_at = timezone.now() + timedelta(
                        hours=random.randint(73, 96)
                    )
                    dispute.resolution_favors = favored_party
                    dispute.save()

                    results["resolved_count"] += 1
                else:
                    # Create admin acknowledgment message
                    DisputeMessage.objects.create(
                        dispute=dispute,
                        sender=admin,
                        message=f"I have been assigned to this dispute and will be reviewing the details.",
                        created_at=timezone.now()
                        + timedelta(hours=random.randint(1, 48)),
                    )

                    results["pending_count"] += 1

                # Update admin's dispute count
                admin_profile, created = AdminProfile.objects.get_or_create(user=admin)
                admin_profile.current_dispute_count = Dispute.objects.filter(
                    assigned_admin=admin, status="Pending"
                ).count()
                admin_profile.save()

                # Add to results
                results["disputes"].append(
                    {
                        "id": dispute.id,
                        "job_id": application.job.id,
                        "job_title": application.job.title,
                        "application_id": application.id,
                        "client_id": client.id,
                        "client_name": f"{client.first_name} {client.last_name}",
                        "applicant_id": applicant.id,
                        "applicant_name": f"{applicant.first_name} {applicant.last_name}",
                        "admin_id": admin.id,
                        "admin_name": f"{admin.first_name} {admin.last_name}",
                        "dispute_type": dispute_type,
                        "reason": dispute_reason,
                        "status": dispute.status,
                        "filed_by": "client" if is_client_filing else "applicant",
                        "created_at": dispute.created_at.isoformat(),
                        "resolved_at": dispute.resolved_at.isoformat()
                        if dispute.resolved_at
                        else None,
                    }
                )

        return results

    def select_admin_with_lowest_workload(self, admins: List[User]) -> User:
        """
        Select the admin with the lowest current dispute workload.

        Args:
            admins: List of admin users

        Returns:
            Admin user with lowest workload
        """
        if not admins:
            raise ValueError("No admin users available")

        # Get dispute counts for each admin
        admin_workloads = []
        for admin in admins:
            # Get or create admin profile
            admin_profile, created = AdminProfile.objects.get_or_create(user=admin)

            # If profile was just created, count disputes
            if created:
                admin_profile.current_dispute_count = Dispute.objects.filter(
                    assigned_admin=admin, status="Pending"
                ).count()
                admin_profile.save()

            admin_workloads.append((admin, admin_profile.current_dispute_count))

        # Sort by dispute count (ascending)
        admin_workloads.sort(key=lambda x: x[1])

        # Return admin with lowest count
        return admin_workloads[0][0]

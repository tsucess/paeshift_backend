"""
Django management command to run a full end-to-end simulation.

This command runs all the individual simulations in sequence to create a complete
test environment with admins, clients, applicants, jobs, applications, and payments.
It also analyzes the results and reports any issues or potential problems.

Usage:
    python manage.py run_full_simulation --admin-count=3 --client-count=10 --applicant-count=20
"""

import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from jobs.models import Job

User = get_user_model()

# Import simulation commands
from jobs.management.commands3.simulate_admin_registration import \
    Command as AdminCommand
from jobs.management.commands3.simulate_applicant_registration import \
    Command as ApplicantCommand
from jobs.management.commands3.simulate_client_registration import \
    Command as ClientCommand
from jobs.management.commands3.simulate_job_application import \
    Command as ApplicationCommand
from jobs.management.commands3.simulate_job_creation import \
    Command as JobCommand
from jobs.management.commands3.simulate_payment_processing import \
    Command as PaymentCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run a full end-to-end simulation of the entire application workflow"

    def add_arguments(self, parser):
        parser.add_argument(
            "--admin-count",
            type=int,
            default=3,
            help="Number of admin users to create (default: 3)",
        )
        parser.add_argument(
            "--client-count",
            type=int,
            default=10,
            help="Number of client users to create (default: 10)",
        )
        parser.add_argument(
            "--applicant-count",
            type=int,
            default=20,
            help="Number of applicant users to create (default: 20)",
        )
        parser.add_argument(
            "--jobs-per-client",
            type=int,
            default=3,
            help="Number of jobs per client (default: 3)",
        )
        parser.add_argument(
            "--applications-per-applicant",
            type=int,
            default=3,
            help="Number of applications per applicant (default: 3)",
        )
        parser.add_argument(
            "--payment-success-rate",
            type=float,
            default=0.8,
            help="Success rate for payments (0.0-1.0, default: 0.8)",
        )
        parser.add_argument(
            "--output-file",
            type=str,
            help="Output file for simulation results (default: simulation_results_TIMESTAMP.json)",
        )

    def handle(self, *args, **options):
        admin_count = options["admin_count"]
        client_count = options["client_count"]
        applicant_count = options["applicant_count"]
        jobs_per_client = options["jobs_per_client"]
        applications_per_applicant = options["applications_per_applicant"]
        payment_success_rate = options["payment_success_rate"]
        output_file = options["output_file"]

        # Generate timestamp for this simulation run
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if not output_file:
            output_file = f"simulation_results_{timestamp}.json"

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting full end-to-end simulation with:"
                f"\n - {admin_count} admins"
                f"\n - {client_count} clients"
                f"\n - {applicant_count} applicants"
                f"\n - {jobs_per_client} jobs per client"
                f"\n - {applications_per_applicant} applications per applicant"
                f"\n - {payment_success_rate:.0%} payment success rate"
            )
        )

        # Initialize results dictionary
        results = {
            "timestamp": timestamp,
            "parameters": {
                "admin_count": admin_count,
                "client_count": client_count,
                "applicant_count": applicant_count,
                "jobs_per_client": jobs_per_client,
                "applications_per_applicant": applications_per_applicant,
                "payment_success_rate": payment_success_rate,
            },
            "steps": {},
            "issues": [],
            "summary": {},
        }

        # Step 1: Admin Registration
        self.stdout.write(self.style.NOTICE("\n=== Step 1: Admin Registration ==="))
        start_time = time.time()
        admin_cmd = AdminCommand()
        admin_results = admin_cmd.create_admin_users(admin_count, "adminpass123")
        results["steps"]["admin_registration"] = {
            "duration": time.time() - start_time,
            "results": admin_results,
        }
        self.stdout.write(
            self.style.SUCCESS(f"Created {len(admin_results['admins'])} admin users")
        )

        # Step 2: Client Registration
        self.stdout.write(self.style.NOTICE("\n=== Step 2: Client Registration ==="))
        start_time = time.time()
        client_cmd = ClientCommand()
        client_results = client_cmd.create_client_users(client_count, "clientpass123")
        results["steps"]["client_registration"] = {
            "duration": time.time() - start_time,
            "results": client_results,
        }
        self.stdout.write(
            self.style.SUCCESS(f"Created {len(client_results['clients'])} client users")
        )

        # Step 3: Applicant Registration
        self.stdout.write(self.style.NOTICE("\n=== Step 3: Applicant Registration ==="))
        start_time = time.time()
        applicant_cmd = ApplicantCommand()
        applicant_results = applicant_cmd.create_applicant_users(
            applicant_count, "applicantpass123", True  # Create with location history
        )
        results["steps"]["applicant_registration"] = {
            "duration": time.time() - start_time,
            "results": applicant_results,
        }
        self.stdout.write(
            self.style.SUCCESS(
                f"Created {len(applicant_results['applicants'])} applicant users"
            )
        )

        # Step 4: Job Creation
        self.stdout.write(self.style.NOTICE("\n=== Step 4: Job Creation ==="))
        start_time = time.time()
        job_cmd = JobCommand()

        # Get client IDs from previous step
        client_ids = [c["id"] for c in client_results["clients"]]

        job_results = job_cmd.create_jobs(
            clients=list(User.objects.filter(role="client")[:client_count]),
            jobs_per_client=jobs_per_client,
        )
        results["steps"]["job_creation"] = {
            "duration": time.time() - start_time,
            "results": job_results,
        }
        self.stdout.write(
            self.style.SUCCESS(f"Created {len(job_results['jobs'])} jobs")
        )

        # Step 5: Job Application
        self.stdout.write(self.style.NOTICE("\n=== Step 5: Job Application ==="))
        start_time = time.time()
        application_cmd = ApplicationCommand()

        # Get applicant IDs from previous step
        applicant_ids = [a["id"] for a in applicant_results["applicants"]]

        # Get available jobs
        jobs = list(Job.objects.filter(status="pending"))

        # Get applicants
        applicants = list(User.objects.filter(role="applicant")[:applicant_count])

        # Create applications
        application_results = application_cmd.create_applications(
            applicants=applicants,
            jobs=jobs,
            applications_per_applicant=applications_per_applicant,
        )
        results["steps"]["job_application"] = {
            "duration": time.time() - start_time,
            "results": application_results,
        }
        self.stdout.write(
            self.style.SUCCESS(
                f"Created {len(application_results['applications'])} job applications"
            )
        )

        # Step 6: Payment Processing
        self.stdout.write(self.style.NOTICE("\n=== Step 6: Payment Processing ==="))
        start_time = time.time()
        payment_cmd = PaymentCommand()

        # Calculate number of payments to process
        payment_count = min(len(job_results["jobs"]), client_count * jobs_per_client)

        payment_results = payment_cmd.handle(
            count=payment_count,
            payment_method="both",
            success_rate=payment_success_rate,
        )
        results["steps"]["payment_processing"] = {
            "duration": time.time() - start_time,
            "results": payment_results,
        }
        self.stdout.write(
            self.style.SUCCESS(
                f"Processed {len(payment_results['payments'])} payments: "
                f"{payment_results['success_count']} successful, {payment_results['failed_count']} failed"
            )
        )

        # Analyze results and identify issues
        self.stdout.write(self.style.NOTICE("\n=== Analyzing Results ==="))
        issues = self.analyze_results(results)
        results["issues"] = issues

        # Generate summary
        total_duration = sum(step["duration"] for step in results["steps"].values())
        results["summary"] = {
            "total_duration": total_duration,
            "admin_count": len(admin_results["admins"]),
            "client_count": len(client_results["clients"]),
            "applicant_count": len(applicant_results["applicants"]),
            "job_count": len(job_results["jobs"]),
            "application_count": len(application_results["applications"]),
            "payment_count": len(payment_results["payments"]),
            "payment_success_count": payment_results["success_count"],
            "payment_failed_count": payment_results["failed_count"],
            "issue_count": len(issues),
        }

        # Save results to file
        self.save_results_to_file(results, output_file)
        self.stdout.write(
            self.style.SUCCESS(f"Simulation results saved to {output_file}")
        )

        # Print summary
        self.stdout.write(self.style.NOTICE("\n=== Simulation Summary ==="))
        self.stdout.write(f"Total duration: {total_duration:.2f} seconds")
        self.stdout.write(f"Admin users created: {results['summary']['admin_count']}")
        self.stdout.write(f"Client users created: {results['summary']['client_count']}")
        self.stdout.write(
            f"Applicant users created: {results['summary']['applicant_count']}"
        )
        self.stdout.write(f"Jobs created: {results['summary']['job_count']}")
        self.stdout.write(
            f"Applications created: {results['summary']['application_count']}"
        )
        self.stdout.write(f"Payments processed: {results['summary']['payment_count']}")
        self.stdout.write(
            f"Successful payments: {results['summary']['payment_success_count']}"
        )
        self.stdout.write(
            f"Failed payments: {results['summary']['payment_failed_count']}"
        )
        self.stdout.write(f"Issues identified: {results['summary']['issue_count']}")

        # Print issues
        if issues:
            self.stdout.write(self.style.NOTICE("\n=== Issues Identified ==="))
            for i, issue in enumerate(issues, 1):
                self.stdout.write(self.style.WARNING(f"{i}. {issue['description']}"))
                if issue.get("recommendation"):
                    self.stdout.write(f"   Recommendation: {issue['recommendation']}")

        # Return a string summary
        return f"Full simulation completed with {results['summary']['admin_count']} admins, {results['summary']['client_count']} clients, {results['summary']['applicant_count']} applicants, {results['summary']['job_count']} jobs, {results['summary']['application_count']} applications, and {results['summary']['payment_count']} payments processed."

    def analyze_results(self, results: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Analyze simulation results and identify issues.

        Args:
            results: Dictionary with simulation results

        Returns:
            List of identified issues
        """
        issues = []

        # Check for errors in each step
        for step_name, step_data in results["steps"].items():
            step_results = step_data.get("results", {})

            if "errors" in step_results and step_results["errors"]:
                for error in step_results["errors"]:
                    issues.append(
                        {
                            "step": step_name,
                            "type": "error",
                            "description": f"Error in {step_name}: {error}",
                            "recommendation": "Check the error message and fix the underlying issue.",
                        }
                    )

        # Check payment success rate
        payment_step = results["steps"].get("payment_processing", {})
        payment_results = payment_step.get("results", {})

        if payment_results:
            success_count = payment_results.get("success_count", 0)
            total_count = len(payment_results.get("payments", []))

            if total_count > 0:
                success_rate = success_count / total_count

                if success_rate < 0.5:
                    issues.append(
                        {
                            "step": "payment_processing",
                            "type": "warning",
                            "description": f"Low payment success rate: {success_rate:.0%}",
                            "recommendation": "Check payment gateway configuration and webhook handling.",
                        }
                    )

        # Check job creation geocoding
        job_step = results["steps"].get("job_creation", {})
        job_results = job_step.get("results", {})

        if job_results:
            jobs = job_results.get("jobs", [])

            if jobs:
                # Check if any jobs have missing geocoding
                jobs_without_geocoding = [
                    job
                    for job in jobs
                    if not job.get("latitude") and not job.get("longitude")
                ]

                if jobs_without_geocoding:
                    issues.append(
                        {
                            "step": "job_creation",
                            "type": "warning",
                            "description": f"{len(jobs_without_geocoding)} jobs have missing geocoding information",
                            "recommendation": "Check the geocoding service and ensure it's working properly.",
                        }
                    )

        # Check application distribution
        application_step = results["steps"].get("job_application", {})
        application_results = application_step.get("results", {})

        if application_results:
            applications = application_results.get("applications", [])

            if applications:
                # Count applications per job
                job_application_counts = {}

                for app in applications:
                    job_id = app.get("job_id")
                    if job_id:
                        job_application_counts[job_id] = (
                            job_application_counts.get(job_id, 0) + 1
                        )

                # Check for jobs with too many or too few applications
                jobs_with_many_apps = [
                    job_id
                    for job_id, count in job_application_counts.items()
                    if count > 10
                ]

                if jobs_with_many_apps:
                    issues.append(
                        {
                            "step": "job_application",
                            "type": "info",
                            "description": f"{len(jobs_with_many_apps)} jobs have more than 10 applications",
                            "recommendation": "Consider implementing pagination for job applications.",
                        }
                    )

        return issues

    def save_results_to_file(self, results: Dict[str, Any], filename: str):
        """
        Save simulation results to a JSON file.

        Args:
            results: Dictionary with simulation results
            filename: Output filename
        """
        # Ensure the directory exists
        os.makedirs(os.path.dirname(os.path.abspath(filename)) or ".", exist_ok=True)

        # Convert datetime objects to ISO format strings
        def json_serial(obj):
            if isinstance(obj, (datetime, timezone.datetime)):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")

        # Write to file
        with open(filename, "w") as f:
            json.dump(results, f, default=json_serial, indent=2)

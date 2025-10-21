"""
Django management command to run comprehensive job lifecycle simulations.

This command allows running the simulations from the command line, including:
1. User creation (clients and applicants)
2. Job creation with async geocoding
3. Job application process
4. Job status changes (accepted, ongoing, ended, canceled)
5. Dispute creation and resolution
6. Review submission
7. Redis caching verification

Usage:
    python manage.py run_simulation --job-users=5 --jobs-per-user=2 --applicants=10 --applications-per-user=3 --lifecycle-jobs=5
"""

import logging
import time

from django.core.management.base import BaseCommand

from jobs.management.commands3.simulation import (
    run_job_application_simulation, run_job_creation_simulation,
    run_job_lifecycle_simulation)

logger = logging.getLogger(__name__)
"""
Script to run job creation and application simulations.

This script runs the simulations and provides detailed analysis of the results,
including geocoding performance, webhook functionality, and application process.

Usage:
    python manage.py shell < jobs/run_simulation.py
"""

import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("simulation")

# Add the project directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import Django settings
import django

django.setup()

from django.contrib.auth import get_user_model

# Import models for analysis
from jobs.models import Application, Job
# Import simulation functions
from jobs.simulation import (run_job_application_simulation,
                             run_job_creation_simulation)

User = get_user_model()


def analyze_geocoding_results(results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze geocoding results from the simulation.

    Args:
        results: Results from the job creation simulation

    Returns:
        Dictionary with analysis results
    """
    analysis = {
        "total_jobs": len(results["jobs_created"]),
        "successful_geocoding": sum(
            1 for r in results["geocoding_results"] if r["geocoded"]
        ),
        "failed_geocoding": sum(
            1 for r in results["geocoding_results"] if not r["geocoded"]
        ),
        "average_geocoding_time": results["average_geocoding_time"],
        "success_rate": results["success_rate"],
        "geocoding_attempts": {},
    }

    # Analyze attempts distribution
    for result in results["geocoding_results"]:
        attempts = result["attempts"]
        if attempts in analysis["geocoding_attempts"]:
            analysis["geocoding_attempts"][attempts] += 1
        else:
            analysis["geocoding_attempts"][attempts] = 1

    return analysis


def analyze_application_results(results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze job application results from the simulation.

    Args:
        results: Results from the job application simulation

    Returns:
        Dictionary with analysis results
    """
    analysis = {
        "total_applicants": len(results["applicants_created"]),
        "total_applications": len(results["applications_created"]),
        "applications_per_applicant": results.get("applications_per_applicant", 0),
        "total_time": results["total_time"],
        "application_status_distribution": {},
    }

    # Analyze application status distribution
    for application in results["applications_created"]:
        status = application["status"]
        if status in analysis["application_status_distribution"]:
            analysis["application_status_distribution"][status] += 1
        else:
            analysis["application_status_distribution"][status] = 1

    return analysis


def check_webhook_functionality() -> Dict[str, Any]:
    """
    Check if webhooks are functioning properly.

    Returns:
        Dictionary with webhook functionality analysis
    """
    # In a real implementation, this would check webhook logs or a test endpoint
    # For simulation purposes, we'll just return a placeholder
    return {
        "webhook_functionality": "Not implemented in simulation",
        "note": "In a real environment, this would check webhook logs or a test endpoint",
    }


def save_results_to_file(results: Dict[str, Any], filename: str) -> None:
    """
    Save simulation results to a JSON file.

    Args:
        results: Simulation results
        filename: Output filename
    """
    try:
        with open(filename, "w") as f:
            json.dump(results, f, indent=2, default=str)
        logger.info(f"Results saved to {filename}")
    except Exception as e:
        logger.error(f"Error saving results to file: {str(e)}")


def main():
    """Run the simulation and analyze results."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    logger.info("=" * 80)
    logger.info("STARTING JOB CREATION SIMULATION")
    logger.info("=" * 80)

    # Run job creation simulation
    job_creation_results = run_job_creation_simulation(num_users=5, num_jobs_per_user=2)

    # Analyze geocoding results
    geocoding_analysis = analyze_geocoding_results(job_creation_results)

    # Check webhook functionality
    webhook_analysis = check_webhook_functionality()

    logger.info("=" * 80)
    logger.info("STARTING JOB APPLICATION SIMULATION")
    logger.info("=" * 80)

    # Run job application simulation
    job_application_results = run_job_application_simulation(
        num_applicants=10, num_applications_per_user=3
    )

    # Analyze application results
    application_analysis = analyze_application_results(job_application_results)

    # Combine all results
    combined_results = {
        "timestamp": timestamp,
        "job_creation": job_creation_results,
        "geocoding_analysis": geocoding_analysis,
        "webhook_analysis": webhook_analysis,
        "job_application": job_application_results,
        "application_analysis": application_analysis,
    }

    # Save results to file
    save_results_to_file(combined_results, f"simulation_results_{timestamp}.json")

    # Print summary
    logger.info("=" * 80)
    logger.info("SIMULATION SUMMARY")
    logger.info("=" * 80)
    logger.info(
        f"Created {geocoding_analysis['total_jobs']} jobs with {geocoding_analysis['successful_geocoding']} successful geocodings"
    )
    logger.info(f"Geocoding success rate: {geocoding_analysis['success_rate']:.2f}%")
    logger.info(
        f"Average geocoding time: {geocoding_analysis['average_geocoding_time']:.2f} seconds"
    )
    logger.info(
        f"Created {application_analysis['total_applications']} applications from {application_analysis['total_applicants']} applicants"
    )
    logger.info(
        f"Applications per applicant: {application_analysis['applications_per_applicant']:.2f}"
    )
    logger.info("=" * 80)


if __name__ == "__main__":
    main()


class Command(BaseCommand):
    help = "Run job creation and application simulations"

    def add_arguments(self, parser):
        parser.add_argument(
            "--job-users",
            type=int,
            default=5,
            help="Number of users to create for job creation simulation",
        )
        parser.add_argument(
            "--jobs-per-user",
            type=int,
            default=2,
            help="Number of jobs per user for job creation simulation",
        )
        parser.add_argument(
            "--applicants",
            type=int,
            default=10,
            help="Number of applicants to create for job application simulation",
        )
        parser.add_argument(
            "--applications-per-user",
            type=int,
            default=3,
            help="Number of applications per user for job application simulation",
        )
        parser.add_argument(
            "--lifecycle-jobs",
            type=int,
            default=5,
            help="Number of jobs to process through the complete lifecycle",
        )
        parser.add_argument(
            "--skip-job-creation",
            action="store_true",
            help="Skip job creation simulation",
        )
        parser.add_argument(
            "--skip-job-application",
            action="store_true",
            help="Skip job application simulation",
        )
        parser.add_argument(
            "--skip-job-lifecycle",
            action="store_true",
            help="Skip job lifecycle simulation",
        )
        parser.add_argument(
            "--only-lifecycle",
            action="store_true",
            help="Only run the job lifecycle simulation",
        )

    def handle(self, *args, **options):
        job_users = options["job_users"]
        jobs_per_user = options["jobs_per_user"]
        applicants = options["applicants"]
        applications_per_user = options["applications_per_user"]
        lifecycle_jobs = options["lifecycle_jobs"]
        skip_job_creation = options["skip_job_creation"]
        skip_job_application = options["skip_job_application"]
        skip_job_lifecycle = options["skip_job_lifecycle"]
        only_lifecycle = options["only_lifecycle"]

        # If only_lifecycle is set, skip other simulations
        if only_lifecycle:
            skip_job_creation = True
            skip_job_application = True
            skip_job_lifecycle = False

        self.stdout.write(self.style.SUCCESS("Starting simulation..."))
        start_time = time.time()

        # Run job creation simulation
        if not skip_job_creation:
            self.stdout.write(
                self.style.NOTICE(
                    f"Running job creation simulation with {job_users} users, {jobs_per_user} jobs per user..."
                )
            )
            job_creation_results = run_job_creation_simulation(
                num_users=job_users, num_jobs_per_user=jobs_per_user
            )

            # Print summary
            total_jobs = len(job_creation_results["jobs_created"])
            successful_geocoding = sum(
                1 for r in job_creation_results["geocoding_results"] if r["geocoded"]
            )

            self.stdout.write(self.style.SUCCESS(f"Job creation simulation completed:"))
            self.stdout.write(
                f"  - Created {total_jobs} jobs with {successful_geocoding} successful geocodings"
            )
            self.stdout.write(
                f'  - Geocoding success rate: {job_creation_results["success_rate"]:.2f}%'
            )
            self.stdout.write(
                f'  - Average geocoding time: {job_creation_results["average_geocoding_time"]:.2f} seconds'
            )
            self.stdout.write(
                f'  - Total time: {job_creation_results["total_time"]:.2f} seconds'
            )

        # Run job application simulation
        if not skip_job_application:
            self.stdout.write(
                self.style.NOTICE(
                    f"Running job application simulation with {applicants} applicants, {applications_per_user} applications per user..."
                )
            )
            job_application_results = run_job_application_simulation(
                num_applicants=applicants,
                num_applications_per_user=applications_per_user,
            )

            # Print summary
            total_applications = len(job_application_results["applications_created"])
            total_applicants = len(job_application_results["applicants_created"])

            self.stdout.write(
                self.style.SUCCESS(f"Job application simulation completed:")
            )
            self.stdout.write(
                f"  - Created {total_applications} applications from {total_applicants} applicants"
            )
            self.stdout.write(
                f'  - Applications per applicant: {job_application_results.get("applications_per_applicant", 0):.2f}'
            )
            self.stdout.write(
                f'  - Total time: {job_application_results["total_time"]:.2f} seconds'
            )

        # Run job lifecycle simulation
        if not skip_job_lifecycle:
            self.stdout.write(
                self.style.NOTICE(
                    f"Running job lifecycle simulation with {lifecycle_jobs} jobs..."
                )
            )
            job_lifecycle_results = run_job_lifecycle_simulation(
                num_jobs=lifecycle_jobs
            )

            # Print summary
            total_jobs_processed = job_lifecycle_results.get("total_jobs_processed", 0)

            self.stdout.write(
                self.style.SUCCESS(f"Job lifecycle simulation completed:")
            )
            self.stdout.write(
                f"  - Processed {total_jobs_processed} jobs through their lifecycle"
            )

            # Count outcomes
            completed_jobs = 0
            disputed_jobs = 0
            canceled_jobs = 0

            for job in job_lifecycle_results.get("jobs_processed", []):
                for status_change in job.get("status_changes", []):
                    if status_change.get("status") == "completed":
                        completed_jobs += 1
                    elif status_change.get("status") == "disputed":
                        disputed_jobs += 1
                    elif status_change.get("status") == "canceled":
                        canceled_jobs += 1

            self.stdout.write(
                f"  - Outcomes: {completed_jobs} completed, {disputed_jobs} disputed, {canceled_jobs} canceled"
            )
            self.stdout.write(
                f'  - Total time: {job_lifecycle_results["total_time"]:.2f} seconds'
            )

        # Print overall summary
        total_time = time.time() - start_time
        self.stdout.write(
            self.style.SUCCESS(
                f"Simulation completed successfully in {total_time:.2f} seconds!"
            )
        )

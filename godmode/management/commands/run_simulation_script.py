"""
Script to run job creation and application simulations.

This script runs the simulations and provides detailed analysis of the results,
including geocoding performance, webhook functionality, and application process.

Usage:
    python manage.py shell < jobs/management/commands/run_simulation_script.py
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

# Import simulation functions
from jobs.management.commands3.simulation import (
    run_job_application_simulation, run_job_creation_simulation)
# Import models for analysis
from jobs.models import Application, Job

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

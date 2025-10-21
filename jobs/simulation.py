"""
Simulation module for testing job creation and application processes.

This module provides functions to simulate:
1. Job creation by new users
2. Async geocoding process verification
3. Webhook functionality testing
4. Job application simulation

Usage:
    python manage.py shell
    from jobs.simulation import run_job_creation_simulation, run_job_application_simulation
    run_job_creation_simulation(num_users=5, num_jobs_per_user=2)
    run_job_application_simulation(num_applicants=10, num_applications_per_user=3)
"""

import logging
import random
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from accounts.models import Profile
from jobs.geocoding import geocode_address
from jobs.models import Application, Job, JobIndustry, JobSubCategory
from jobs.utils import resolve_industry, resolve_subcategory
from jobs.validation import validate_date, validate_time

# Configure logging
logger = logging.getLogger(__name__)
User = get_user_model()

# Sample data for simulation
SAMPLE_FIRST_NAMES = [
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
    "David",
    "Barbara",
    "Richard",
    "Susan",
    "Joseph",
    "Jessica",
]

SAMPLE_LAST_NAMES = [
    "Smith",
    "Johnson",
    "Williams",
    "Jones",
    "Brown",
    "Davis",
    "Miller",
    "Wilson",
    "Moore",
    "Taylor",
    "Anderson",
    "Thomas",
    "Jackson",
    "White",
    "Harris",
    "Martin",
]

SAMPLE_JOB_TITLES = [
    "Electrician Needed",
    "Plumber Required",
    "Carpenter for Home Renovation",
    "House Cleaning Service",
    "Gardening and Lawn Care",
    "Moving Help Needed",
    "Painter for Interior Work",
    "Handyman for Various Tasks",
    "Appliance Repair",
    "Computer Technician",
    "Tutor for Math",
    "Personal Trainer",
    "Photographer",
    "Web Developer",
    "Graphic Designer",
    "Babysitter Needed",
]

SAMPLE_LOCATIONS = [
    "123 Main St, New York, NY 10001",
    "456 Elm St, Los Angeles, CA 90001",
    "789 Oak St, Chicago, IL 60007",
    "321 Pine St, Houston, TX 77001",
    "654 Maple St, Phoenix, AZ 85001",
    "987 Cedar St, Philadelphia, PA 19019",
    "741 Birch St, San Antonio, TX 78201",
    "852 Walnut St, San Diego, CA 92101",
    "963 Spruce St, Dallas, TX 75201",
    "159 Ash St, San Jose, CA 95101",
]


def create_test_user(
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    email: Optional[str] = None,
    role: str = "client",
) -> User:
    """
    Create a test user for simulation purposes.

    Args:
        first_name: Optional first name (random if not provided)
        last_name: Optional last name (random if not provided)
        email: Optional email (generated if not provided)
        role: User role (client or applicant)

    Returns:
        Newly created User instance
    """
    if not first_name:
        first_name = random.choice(SAMPLE_FIRST_NAMES)

    if not last_name:
        last_name = random.choice(SAMPLE_LAST_NAMES)

    if not email:
        timestamp = int(time.time())
        email = f"{first_name.lower()}.{last_name.lower()}.{timestamp}@example.com"

    username = f"{first_name.lower()}_{last_name.lower()}_{timestamp}"

    try:
        with transaction.atomic():
            user = User.objects.create_user(
                username=username,
                email=email,
                password="testpassword123",
                first_name=first_name,
                last_name=last_name,
            )

            # Create or update profile
            profile, created = Profile.objects.get_or_create(user=user)
            profile.role = role
            profile.save()

            logger.info(f"Created test user: {username} ({email}) with role: {role}")
            return user
    except Exception as e:
        logger.error(f"Error creating test user: {str(e)}")
        raise


def create_test_job(user: User, job_data: Optional[Dict[str, Any]] = None) -> Job:
    """
    Create a test job for simulation purposes.

    Args:
        user: The user creating the job
        job_data: Optional job data (random if not provided)

    Returns:
        Newly created Job instance
    """
    if not job_data:
        # Generate random job data
        industry = random.choice(JobIndustry.objects.all())
        subcategory = random.choice(JobSubCategory.objects.filter(industry=industry))

        # Generate random date (between today and 30 days in future)
        job_date = timezone.now().date() + timedelta(days=random.randint(1, 30))

        # Generate random times (ensuring end_time > start_time)
        start_hour = random.randint(8, 16)  # 8 AM to 4 PM
        duration_hours = random.randint(2, 8)  # 2 to 8 hours
        end_hour = min(start_hour + duration_hours, 23)

        start_time = f"{start_hour:02d}:00"
        end_time = f"{end_hour:02d}:00"

        # Generate random rate between $15 and $50
        rate = Decimal(str(random.randint(15, 50)))

        job_data = {
            "title": random.choice(SAMPLE_JOB_TITLES),
            "industry": industry.id,
            "subcategory": subcategory.id,
            "applicants_needed": random.randint(1, 5),
            "job_type": random.choice(["single_day", "multiple_days"]),
            "shift_type": random.choice(["morning", "afternoon", "evening"]),
            "date": job_date.strftime("%Y-%m-%d"),
            "start_time": start_time,
            "end_time": end_time,
            "rate": rate,
            "location": random.choice(SAMPLE_LOCATIONS),
        }

    try:
        # Validate date and time
        is_valid_date, job_date, date_error = validate_date(job_data["date"])
        if not is_valid_date:
            raise ValueError(f"Invalid date: {date_error}")

        is_valid_start, start_time, start_error = validate_time(job_data["start_time"])
        if not is_valid_start:
            raise ValueError(f"Invalid start time: {start_error}")

        is_valid_end, end_time, end_error = validate_time(job_data["end_time"])
        if not is_valid_end:
            raise ValueError(f"Invalid end time: {end_error}")

        # Create job
        with transaction.atomic():
            job = Job.objects.create(
                client=user,
                created_by=user,
                title=job_data["title"],
                industry=resolve_industry(job_data["industry"]),
                subcategory=resolve_subcategory(job_data["subcategory"]),
                applicants_needed=job_data["applicants_needed"],
                job_type=job_data["job_type"],
                shift_type=job_data["shift_type"],
                date=job_date,
                start_time=start_time,
                end_time=end_time,
                rate=job_data["rate"],
                location=job_data["location"].strip(),
                payment_status="pending",
                status="pending",
                latitude=None,
                longitude=None,
            )

            # Calculate service fee and total amount
            job.calculate_service_fee_and_total()
            job.save(update_fields=["total_amount", "service_fee"])

            logger.info(f"Created test job: {job.id} - {job.title} by {user.username}")
            return job
    except Exception as e:
        logger.error(f"Error creating test job: {str(e)}")
        raise


def check_geocoding_status(
    job: Job, max_attempts: int = 5, delay: int = 2
) -> Dict[str, Any]:
    """
    Check the geocoding status of a job.

    Args:
        job: The job to check
        max_attempts: Maximum number of attempts to check
        delay: Delay between attempts in seconds

    Returns:
        Dictionary with geocoding status information
    """
    result = {
        "job_id": job.id,
        "initial_location": job.location,
        "geocoded": False,
        "attempts": 0,
        "latitude": None,
        "longitude": None,
        "elapsed_time": 0,
    }

    start_time = time.time()

    for attempt in range(max_attempts):
        result["attempts"] += 1

        # Refresh job from database
        job.refresh_from_db()

        if job.latitude is not None and job.longitude is not None:
            result["geocoded"] = True
            result["latitude"] = job.latitude
            result["longitude"] = job.longitude
            break

        logger.info(
            f"Geocoding not complete for job {job.id}, attempt {attempt+1}/{max_attempts}"
        )
        time.sleep(delay)

    result["elapsed_time"] = time.time() - start_time

    if not result["geocoded"]:
        logger.warning(
            f"Geocoding not completed for job {job.id} after {max_attempts} attempts"
        )
    else:
        logger.info(
            f"Geocoding completed for job {job.id} in {result['elapsed_time']:.2f} seconds"
        )

    return result


def create_test_application(applicant: User, job: Job) -> Application:
    """
    Create a test job application.

    Args:
        applicant: The user applying for the job
        job: The job being applied for

    Returns:
        Newly created Application instance
    """
    try:
        # Check if user already applied
        existing_application = Application.objects.filter(
            applicant=applicant, job=job
        ).first()
        if existing_application:
            logger.info(f"User {applicant.username} already applied to job {job.id}")
            return existing_application

        # Create application - only use fields that exist in the model
        application = Application.objects.create(
            applicant=applicant,
            job=job,
            status="Pending",  # Use the actual status value from Status choices
            feedback=f"Test application created at {timezone.now().isoformat()}",  # Use feedback instead of notes
        )

        logger.info(
            f"Created application {application.id}: {applicant.username} applied to job {job.id}"
        )
        return application
    except Exception as e:
        logger.error(f"Error creating application: {str(e)}")
        raise


def run_job_creation_simulation(
    num_users: int = 5, num_jobs_per_user: int = 2
) -> Dict[str, Any]:
    """
    Run a simulation of job creation by new users.

    Args:
        num_users: Number of users to create
        num_jobs_per_user: Number of jobs per user

    Returns:
        Dictionary with simulation results
    """
    logger.info(
        f"Starting job creation simulation with {num_users} users, {num_jobs_per_user} jobs per user"
    )

    results = {
        "users_created": [],
        "jobs_created": [],
        "geocoding_results": [],
        "success_rate": 0,
        "average_geocoding_time": 0,
        "total_time": 0,
    }

    start_time = time.time()

    try:
        # Ensure we have industries and subcategories
        if JobIndustry.objects.count() == 0:
            logger.error(
                "No job industries found in database. Please create some industries first."
            )
            return results

        # Create test users
        for i in range(num_users):
            user = create_test_user(role="client")
            results["users_created"].append(
                {"id": user.id, "username": user.username, "email": user.email}
            )

            # Create jobs for this user
            for j in range(num_jobs_per_user):
                job = create_test_job(user)

                job_result = {
                    "id": job.id,
                    "title": job.title,
                    "location": job.location,
                    "user_id": user.id,
                }

                results["jobs_created"].append(job_result)

                # Check geocoding status
                geocoding_result = check_geocoding_status(job)
                results["geocoding_results"].append(geocoding_result)

    except Exception as e:
        logger.error(f"Error in job creation simulation: {str(e)}")

    # Calculate statistics
    total_jobs = len(results["jobs_created"])
    successful_geocoding = sum(1 for r in results["geocoding_results"] if r["geocoded"])

    if total_jobs > 0:
        results["success_rate"] = (successful_geocoding / total_jobs) * 100

    if successful_geocoding > 0:
        total_geocoding_time = sum(
            r["elapsed_time"] for r in results["geocoding_results"] if r["geocoded"]
        )
        results["average_geocoding_time"] = total_geocoding_time / successful_geocoding

    results["total_time"] = time.time() - start_time

    logger.info(
        f"Job creation simulation completed in {results['total_time']:.2f} seconds"
    )
    logger.info(
        f"Created {total_jobs} jobs with {successful_geocoding} successful geocodings"
    )
    logger.info(f"Geocoding success rate: {results['success_rate']:.2f}%")
    logger.info(
        f"Average geocoding time: {results['average_geocoding_time']:.2f} seconds"
    )

    return results


def run_job_application_simulation(
    num_applicants: int = 10, num_applications_per_user: int = 3
) -> Dict[str, Any]:
    """
    Run a simulation of job applications.

    Args:
        num_applicants: Number of applicant users to create
        num_applications_per_user: Number of applications per user

    Returns:
        Dictionary with simulation results
    """
    logger.info(
        f"Starting job application simulation with {num_applicants} applicants, {num_applications_per_user} applications per user"
    )

    results = {
        "applicants_created": [],
        "applications_created": [],
        "success_rate": 0,
        "total_time": 0,
    }

    start_time = time.time()

    try:
        # Get available jobs
        available_jobs = Job.objects.filter(status="pending").order_by("?")

        if available_jobs.count() == 0:
            logger.error("No available jobs found. Please create some jobs first.")
            return results

        # Create test applicants
        for i in range(num_applicants):
            applicant = create_test_user(role="applicant")
            results["applicants_created"].append(
                {
                    "id": applicant.id,
                    "username": applicant.username,
                    "email": applicant.email,
                }
            )

            # Create applications for this user
            successful_applications = 0

            for j in range(num_applications_per_user):
                # Get a random job
                if available_jobs.count() > 0:
                    job = available_jobs[j % available_jobs.count()]

                    try:
                        application = create_test_application(applicant, job)

                        application_result = {
                            "id": application.id,
                            "job_id": job.id,
                            "job_title": job.title,
                            "applicant_id": applicant.id,
                            "status": application.status,
                            "is_accepted": application.status
                            == Application.Status.ACCEPTED,  # Add this for compatibility
                            "created_at": application.created_at.isoformat()
                            if application.created_at
                            else None,
                        }

                        results["applications_created"].append(application_result)
                        successful_applications += 1
                    except Exception as e:
                        logger.error(
                            f"Error creating application for user {applicant.id} to job {job.id}: {str(e)}"
                        )

            logger.info(
                f"Created {successful_applications} applications for user {applicant.username}"
            )

    except Exception as e:
        logger.error(f"Error in job application simulation: {str(e)}")

    # Calculate statistics
    total_applications = len(results["applications_created"])
    total_applicants = len(results["applicants_created"])

    if total_applicants > 0:
        results["applications_per_applicant"] = total_applications / total_applicants

    results["total_time"] = time.time() - start_time

    logger.info(
        f"Job application simulation completed in {results['total_time']:.2f} seconds"
    )
    logger.info(
        f"Created {total_applications} applications from {total_applicants} applicants"
    )

    return results


if __name__ == "__main__":
    # This allows running the simulation directly
    print("This script should be run from Django shell:")
    print("python manage.py shell")
    print(
        "from jobs.simulation import run_job_creation_simulation, run_job_application_simulation"
    )
    print("run_job_creation_simulation(num_users=5, num_jobs_per_user=2)")
    print(
        "run_job_application_simulation(num_applicants=10, num_applications_per_user=3)"
    )

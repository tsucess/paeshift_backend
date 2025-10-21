"""
Run selected simulations for the Payshift platform.

This command allows running one or more simulations for testing and development purposes.
Available simulations include:
- Admin registration
- Client registration
- Applicant registration
- Job creation
- Job application
- Payment processing
- Dispute management
- End-to-end workflow

Usage:
    python manage.py run_simulations --simulations=admin,client,applicant,job,application,payment,dispute,full
    python manage.py run_simulations --list  # List available simulations
"""

import argparse
import json
import logging
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from jobs.management.commands3.run_full_simulation import \
    Command as FullSimulationCommand
from jobs.management.commands3.simulate_admin_registration import \
    Command as AdminRegistrationCommand
from jobs.management.commands3.simulate_applicant_registration import \
    Command as ApplicantRegistrationCommand
from jobs.management.commands3.simulate_client_registration import \
    Command as ClientRegistrationCommand
from jobs.management.commands3.simulate_job_application import \
    Command as JobApplicationCommand
from jobs.management.commands3.simulate_job_creation import \
    Command as JobCreationCommand
from jobs.management.commands3.simulate_payment_processing import \
    Command as PaymentProcessingCommand
from jobs.management.commands3.test_webhook import \
    Command as TestWebhookCommand

logger = logging.getLogger(__name__)
"""
Comprehensive simulation module for testing the entire job lifecycle.

This module provides functions to simulate:
1. User creation (clients and applicants)
2. Job creation with async geocoding
3. Job application process
4. Job status changes (accepted, ongoing, ended, canceled)
5. Dispute creation and resolution
6. Review submission
7. Redis caching verification

Usage:
    python manage.py run_simulation --job-users=5 --jobs-per-user=2 --applicants=10 --applications-per-user=3
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
from disputes.models import Dispute
from jobs.geocoding import geocode_address
from jobs.models import Application, Job, JobIndustry, JobSubCategory
from jobs.utils import resolve_industry, resolve_subcategory
from jobs.validation import validate_date, validate_time
from rating.models import Review

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


def update_application_status(application: Application, new_status: str) -> Application:
    """
    Update the status of a job application.

    Args:
        application: The application to update
        new_status: The new status to set

    Returns:
        Updated Application instance
    """
    try:
        # Update application status
        application.status = new_status
        application.save(update_fields=["status"])

        # If accepting the application, update the job status
        if new_status == "Accepted":
            job = application.job
            job.status = "upcoming"  # Use valid status from Job.Status
            job.save(update_fields=["status"])

            # Reject other applications for this job
            other_applications = Application.objects.filter(job=job).exclude(
                id=application.id
            )

            for other_app in other_applications:
                other_app.status = "Rejected"  # Use string value
                other_app.save(update_fields=["status"])

        logger.info(f"Updated application {application.id} status to {new_status}")
        return application
    except Exception as e:
        logger.error(f"Error updating application status: {str(e)}")
        raise


def update_job_status(job: Job, new_status: str) -> Job:
    """
    Update the status of a job.

    Args:
        job: The job to update
        new_status: The new status to set

    Returns:
        Updated Job instance
    """
    try:
        # Update job status
        job.status = new_status
        job.save(update_fields=["status"])

        logger.info(f"Updated job {job.id} status to {new_status}")
        return job
    except Exception as e:
        logger.error(f"Error updating job status: {str(e)}")
        raise


def create_test_dispute(
    application: Application, created_by: User, reason: str = None
) -> Dispute:
    """
    Create a test dispute for a job application.

    Args:
        application: The application to dispute
        created_by: The user creating the dispute
        reason: Optional reason for the dispute

    Returns:
        Newly created Dispute instance
    """
    if not reason:
        reasons = [
            "Worker didn't show up",
            "Work quality was poor",
            "Job requirements changed",
            "Payment issues",
            "Communication problems",
            "Safety concerns",
            "Time tracking discrepancies",
            "Scope of work disagreement",
        ]
        reason = random.choice(reasons)

    try:
        # Create dispute
        dispute = Dispute.objects.create(
            job=application.job,  # Required field
            application=application,
            created_by=created_by,
            reason=reason,
            title=f"Dispute for job: {application.job.title}",
            status="open",
        )

        logger.info(
            f"Created dispute {dispute.id} for application {application.id}: {reason}"
        )
        return dispute
    except Exception as e:
        logger.error(f"Error creating dispute: {str(e)}")
        raise


def resolve_test_dispute(
    dispute: Dispute, resolver: User, resolution: str = None, status: str = "resolved"
) -> Dispute:
    """
    Resolve a test dispute.

    Args:
        dispute: The dispute to resolve
        resolver: The user resolving the dispute
        resolution: Optional resolution description
        status: The resolution status

    Returns:
        Updated Dispute instance
    """
    if not resolution:
        resolutions = [
            "Refund issued to client",
            "Partial payment approved",
            "Additional work scheduled",
            "Mediation completed successfully",
            "Dispute dismissed",
            "Compensation provided",
            "Agreement reached between parties",
        ]
        resolution = random.choice(resolutions)

    try:
        # Update dispute
        dispute.resolved_by = resolver
        dispute.resolution = resolution
        dispute.status = status
        dispute.resolved_at = timezone.now()
        dispute.save(
            update_fields=["resolved_by", "resolution", "status", "resolved_at"]
        )

        logger.info(f"Resolved dispute {dispute.id}: {resolution}")
        return dispute
    except Exception as e:
        logger.error(f"Error resolving dispute: {str(e)}")
        raise


def create_test_review(
    job: Job, reviewer: User, reviewee: User, rating: int = None, comment: str = None
) -> Review:
    """
    Create a test review for a job.

    Args:
        job: The job to review
        reviewer: The user creating the review
        reviewee: The user being reviewed
        rating: Optional rating (1-5)
        comment: Optional review comment

    Returns:
        Newly created Review instance
    """
    if rating is None:
        rating = random.randint(1, 5)

    if not comment:
        positive_comments = [
            "Great work! Very professional.",
            "Completed the job on time and with high quality.",
            "Excellent communication throughout the project.",
            "Would definitely hire again.",
            "Very skilled and knowledgeable.",
            "Went above and beyond expectations.",
        ]

        negative_comments = [
            "Did not complete the job as described.",
            "Communication could have been better.",
            "Arrived late without notice.",
            "Quality of work was below expectations.",
            "Would not recommend for similar jobs.",
        ]

        if rating >= 4:
            comment = random.choice(positive_comments)
        else:
            comment = random.choice(negative_comments)

    try:
        # Create review
        review = Review.objects.create(
            reviewer=reviewer,
            reviewed=reviewee,
            rating=rating,
            feedback=comment,
            is_verified=True,
        )

        logger.info(f"Created review for job {job.id}: {rating}/5 - {comment[:30]}...")
        return review
    except Exception as e:
        logger.error(f"Error creating review: {str(e)}")
        raise


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


def run_job_lifecycle_simulation(num_jobs: int = 5) -> Dict[str, Any]:
    """
    Run a simulation of the complete job lifecycle including status changes.

    Args:
        num_jobs: Number of jobs to process through the lifecycle

    Returns:
        Dictionary with simulation results
    """
    logger.info(f"Starting job lifecycle simulation with {num_jobs} jobs")

    results = {"jobs_processed": [], "status_changes": [], "total_time": 0}

    start_time = time.time()

    try:
        # Get jobs with pending applications
        jobs_with_applications = (
            Job.objects.filter(applications__isnull=False, status="pending")
            .distinct()
            .order_by("?")[:num_jobs]
        )

        if jobs_with_applications.count() == 0:
            logger.error(
                "No jobs with applications found. Please create jobs and applications first."
            )
            return results

        # Process each job through its lifecycle
        for job in jobs_with_applications:
            job_result = {
                "id": job.id,
                "title": job.title,
                "client_id": job.client.id,
                "status_changes": [],
            }

            # Get a random application for this job
            application = Application.objects.filter(job=job).order_by("?").first()

            if not application:
                logger.warning(f"No applications found for job {job.id}")
                continue

            # 1. Accept an application
            update_application_status(application, "Accepted")
            job_result["status_changes"].append(
                {
                    "status": "accepted",
                    "timestamp": timezone.now().isoformat(),
                    "application_id": application.id,
                    "applicant_id": application.applicant.id,
                }
            )

            # 2. Mark job as ongoing
            update_job_status(job, "ongoing")
            job_result["status_changes"].append(
                {"status": "ongoing", "timestamp": timezone.now().isoformat()}
            )

            # 3. Randomly decide if job completes normally or has issues
            job_outcome = random.choice(["completed", "disputed", "canceled"])

            if job_outcome == "completed":
                # Mark job as completed
                update_job_status(job, "completed")
                job_result["status_changes"].append(
                    {"status": "completed", "timestamp": timezone.now().isoformat()}
                )

                # Create reviews
                client_review = create_test_review(
                    job=job,
                    reviewer=job.client,
                    reviewee=application.applicant,
                    rating=random.randint(3, 5),
                )

                applicant_review = create_test_review(
                    job=job,
                    reviewer=application.applicant,
                    reviewee=job.client,
                    rating=random.randint(3, 5),
                )

                job_result["reviews"] = [
                    {
                        "id": client_review.id,
                        "reviewer_id": client_review.reviewer.id,
                        "reviewee_id": client_review.reviewed.id,
                        "rating": client_review.rating,
                        "comment": client_review.feedback,
                    },
                    {
                        "id": applicant_review.id,
                        "reviewer_id": applicant_review.reviewer.id,
                        "reviewee_id": applicant_review.reviewed.id,
                        "rating": applicant_review.rating,
                        "comment": applicant_review.feedback,
                    },
                ]

            elif job_outcome == "disputed":
                # Create a dispute
                dispute = create_test_dispute(
                    application=application, created_by=job.client
                )

                # Resolve the dispute
                resolved_dispute = resolve_test_dispute(
                    dispute=dispute,
                    resolver=User.objects.filter(is_staff=True).first() or job.client,
                )

                # Mark job as completed after dispute resolution
                update_job_status(job, "completed")

                job_result["status_changes"].append(
                    {
                        "status": "disputed",
                        "timestamp": timezone.now().isoformat(),
                        "dispute_id": dispute.id,
                        "dispute_reason": dispute.reason,
                    }
                )

                job_result["status_changes"].append(
                    {
                        "status": "completed",
                        "timestamp": timezone.now().isoformat(),
                        "dispute_resolution": resolved_dispute.resolution,
                    }
                )

                # Create reviews (likely lower ratings due to dispute)
                client_review = create_test_review(
                    job=job,
                    reviewer=job.client,
                    reviewee=application.applicant,
                    rating=random.randint(1, 3),
                )

                applicant_review = create_test_review(
                    job=job,
                    reviewer=application.applicant,
                    reviewee=job.client,
                    rating=random.randint(1, 3),
                )

                job_result["reviews"] = [
                    {
                        "id": client_review.id,
                        "reviewer_id": client_review.reviewer.id,
                        "reviewee_id": client_review.reviewed.id,
                        "rating": client_review.rating,
                        "comment": client_review.feedback,
                    },
                    {
                        "id": applicant_review.id,
                        "reviewer_id": applicant_review.reviewer.id,
                        "reviewee_id": applicant_review.reviewed.id,
                        "rating": applicant_review.rating,
                        "comment": applicant_review.feedback,
                    },
                ]

                job_result["dispute"] = {
                    "id": dispute.id,
                    "reason": dispute.reason,
                    "created_by_id": dispute.created_by.id,
                    "resolution": resolved_dispute.resolution,
                    "resolved_by_id": resolved_dispute.resolved_by.id,
                    "status": resolved_dispute.status,
                }

            else:  # canceled
                # Mark job as canceled
                update_job_status(job, "canceled")
                job_result["status_changes"].append(
                    {
                        "status": "canceled",
                        "timestamp": timezone.now().isoformat(),
                        "reason": "Client canceled the job",
                    }
                )

            results["jobs_processed"].append(job_result)
            logger.info(f"Processed job {job.id} through lifecycle: {job_outcome}")

    except Exception as e:
        logger.error(f"Error in job lifecycle simulation: {str(e)}")

    results["total_time"] = time.time() - start_time
    results["total_jobs_processed"] = len(results["jobs_processed"])

    logger.info(
        f"Job lifecycle simulation completed in {results['total_time']:.2f} seconds"
    )
    logger.info(
        f"Processed {results['total_jobs_processed']} jobs through their lifecycle"
    )

    return results


# Define available simulations
AVAILABLE_SIMULATIONS = {
    "admin": {
        "name": "Admin Registration",
        "description": "Simulates admin user registration",
        "command": AdminRegistrationCommand(),
        "default_args": {"count": 1, "password": "password123"},
    },
    "client": {
        "name": "Client Registration",
        "description": "Simulates client user registration",
        "command": ClientRegistrationCommand(),
        "default_args": {"count": 2, "password": "password123"},
    },
    "applicant": {
        "name": "Applicant Registration",
        "description": "Simulates applicant user registration",
        "command": ApplicantRegistrationCommand(),
        "default_args": {"count": 5, "password": "password123", "with_location": True},
    },
    "job": {
        "name": "Job Creation",
        "description": "Simulates job creation by clients",
        "command": JobCreationCommand(),
        "default_args": {
            "client_count": 2,
            "jobs_per_client": 3,
            "use_existing_clients": True,
        },
    },
    "application": {
        "name": "Job Application",
        "description": "Simulates job applications by applicants",
        "command": JobApplicationCommand(),
        "default_args": {
            "applicant_count": 5,
            "applications_per_applicant": 2,
            "use_existing_applicants": True,
        },
    },
    "payment": {
        "name": "Payment Processing",
        "description": "Simulates payment processing for jobs",
        "command": PaymentProcessingCommand(),
        "default_args": {"count": 3, "payment_method": "both", "success_rate": 0.8},
    },
    "webhook": {
        "name": "Payment Webhook",
        "description": "Tests payment webhook processing",
        "command": TestWebhookCommand(),
        "default_args": {"payment_method": "paystack", "success": True},
    },
    "full": {
        "name": "Full End-to-End Simulation",
        "description": "Runs a complete end-to-end simulation of the platform",
        "command": FullSimulationCommand(),
        "default_args": {
            "admin_count": 1,
            "client_count": 2,
            "applicant_count": 5,
            "jobs_per_client": 3,
            "applications_per_applicant": 2,
            "payment_success_rate": 0.8,
        },
    },
}


class Command(BaseCommand):
    help = "Run selected simulations for the Payshift platform"

    def add_arguments(self, parser):
        parser.add_argument(
            "--simulations",
            type=str,
            help="Comma-separated list of simulations to run (e.g., admin,client,job)",
        )
        parser.add_argument(
            "--list",
            action="store_true",
            help="List available simulations",
        )
        parser.add_argument(
            "--save-results",
            action="store_true",
            help="Save simulation results to a JSON file",
        )
        parser.add_argument(
            "--admin-count",
            type=int,
            default=1,
            help="Number of admin users to create",
        )
        parser.add_argument(
            "--client-count",
            type=int,
            default=2,
            help="Number of client users to create",
        )
        parser.add_argument(
            "--applicant-count",
            type=int,
            default=5,
            help="Number of applicant users to create",
        )
        parser.add_argument(
            "--jobs-per-client",
            type=int,
            default=3,
            help="Number of jobs to create per client",
        )
        parser.add_argument(
            "--applications-per-applicant",
            type=int,
            default=2,
            help="Number of job applications per applicant",
        )
        parser.add_argument(
            "--payment-success-rate",
            type=float,
            default=0.8,
            help="Success rate for payment processing (0.0-1.0)",
        )
        parser.add_argument(
            "--password",
            type=str,
            default="password123",
            help="Password for created users",
        )

    def handle(self, *args, **options):
        # If --list is specified, list available simulations and exit
        if options["list"]:
            self.list_simulations()
            return "Available simulations listed above"

        # Get simulations to run
        simulations_to_run = []
        if options["simulations"]:
            simulation_keys = options["simulations"].split(",")
            for key in simulation_keys:
                if key not in AVAILABLE_SIMULATIONS:
                    raise CommandError(
                        f"Unknown simulation: {key}. Use --list to see available simulations."
                    )
                simulations_to_run.append(key)
        else:
            # Default to running all simulations
            simulations_to_run = list(AVAILABLE_SIMULATIONS.keys())

        # Run selected simulations
        results = {}
        start_time = time.time()

        for sim_key in simulations_to_run:
            sim_info = AVAILABLE_SIMULATIONS[sim_key]
            self.stdout.write(
                self.style.SUCCESS(f"\n=== Running {sim_info['name']} Simulation ===")
            )

            # Prepare arguments for the simulation
            sim_args = sim_info["default_args"].copy()

            # Override with command-line arguments if applicable
            if "count" in sim_args and sim_key == "admin":
                sim_args["count"] = options["admin_count"]
            if "count" in sim_args and sim_key == "client":
                sim_args["count"] = options["client_count"]
            if "count" in sim_args and sim_key == "applicant":
                sim_args["count"] = options["applicant_count"]
            if "client_count" in sim_args:
                sim_args["client_count"] = options["client_count"]
            if "jobs_per_client" in sim_args:
                sim_args["jobs_per_client"] = options["jobs_per_client"]
            if "applicant_count" in sim_args:
                sim_args["applicant_count"] = options["applicant_count"]
            if "applications_per_applicant" in sim_args:
                sim_args["applications_per_applicant"] = options[
                    "applications_per_applicant"
                ]
            if "success_rate" in sim_args:
                sim_args["success_rate"] = options["payment_success_rate"]
            if "password" in sim_args:
                sim_args["password"] = options["password"]

            # Special case for full simulation
            if sim_key == "full":
                sim_args = {
                    "admin_count": options["admin_count"],
                    "client_count": options["client_count"],
                    "applicant_count": options["applicant_count"],
                    "jobs_per_client": options["jobs_per_client"],
                    "applications_per_applicant": options["applications_per_applicant"],
                    "payment_success_rate": options["payment_success_rate"],
                    "output_file": f"simulation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                }

            # Run the simulation
            try:
                self.stdout.write(f"Running with arguments: {sim_args}")
                result = sim_info["command"].handle(**sim_args)
                results[sim_key] = {
                    "success": True,
                    "result": result,
                    "timestamp": timezone.now().isoformat(),
                }
                self.stdout.write(
                    self.style.SUCCESS(f"✅ {sim_info['name']} completed successfully")
                )
            except Exception as e:
                results[sim_key] = {
                    "success": False,
                    "error": str(e),
                    "timestamp": timezone.now().isoformat(),
                }
                self.stdout.write(
                    self.style.ERROR(f"❌ {sim_info['name']} failed: {str(e)}")
                )
                logger.exception(f"Error running {sim_info['name']} simulation")

        # Calculate total execution time
        execution_time = time.time() - start_time

        # Add summary to results
        results["summary"] = {
            "simulations_run": len(simulations_to_run),
            "successful_simulations": sum(
                1
                for sim in results.values()
                if isinstance(sim, dict) and sim.get("success", False)
            ),
            "failed_simulations": sum(
                1
                for sim in results.values()
                if isinstance(sim, dict) and not sim.get("success", True)
            ),
            "execution_time_seconds": execution_time,
            "timestamp": timezone.now().isoformat(),
        }

        # Save results to file if requested
        if options["save_results"]:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"simulation_results_{timestamp}.json"
            with open(filename, "w") as f:
                json.dump(results, f, indent=2)
            self.stdout.write(self.style.SUCCESS(f"Results saved to {filename}"))

        # Print summary
        self.stdout.write("\n=== Simulation Summary ===")
        self.stdout.write(
            f"Total simulations run: {results['summary']['simulations_run']}"
        )
        self.stdout.write(
            f"Successful simulations: {results['summary']['successful_simulations']}"
        )
        self.stdout.write(
            f"Failed simulations: {results['summary']['failed_simulations']}"
        )
        self.stdout.write(f"Total execution time: {execution_time:.2f} seconds")

        return f"Completed {results['summary']['successful_simulations']} of {results['summary']['simulations_run']} simulations"

    def list_simulations(self):
        """List all available simulations with descriptions."""
        self.stdout.write(self.style.SUCCESS("=== Available Simulations ==="))
        for key, info in AVAILABLE_SIMULATIONS.items():
            self.stdout.write(f"{key}: {info['name']}")
            self.stdout.write(f"  {info['description']}")
            self.stdout.write(f"  Default arguments: {info['default_args']}")
            self.stdout.write("")

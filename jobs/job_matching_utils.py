"""
Job Matching Utility Module

This module provides functions for matching jobs to users based on various weighted factors:
- Location proximity (distance between job and user)
- Skills match (industry and subcategory alignment)
- User activity score (engagement metrics)
- User rating and experience

Usage:
    from jobs.job_matching_utils import match_jobs_to_users
    matches = match_jobs_to_users(jobs, users)
"""

import logging
import math
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Avg, Count, Q
from django.utils import timezone

from accounts.models import Profile, UserActivityLog
from jobs.models import Job, JobIndustry, JobSubCategory
from rating.models import Review

# Use the User model from get_user_model() to avoid import issues
User = get_user_model()
logger = logging.getLogger(__name__)

# Weight constants for different matching factors
WEIGHT_LOCATION = 0.35  # 35% weight for location proximity
WEIGHT_SKILLS = 0.25  # 25% weight for skills match
WEIGHT_ACTIVITY = 0.15  # 15% weight for user activity
WEIGHT_RATING = 0.15  # 15% weight for user rating
WEIGHT_EXPERIENCE = 0.10  # 10% weight for job experience

# Constants for activity scoring
ACTIVITY_RECENCY_DAYS = 30  # Consider activity in the last 30 days
LOGIN_POINTS = 10  # Points for each login
JOB_VIEW_POINTS = 5  # Points for each job view
APPLICATION_POINTS = 20  # Points for each job application
PROFILE_UPDATE_POINTS = 15  # Points for profile updates
SESSION_DURATION_FACTOR = 0.1  # Points per minute of session time

# Cache timeout for activity scores (1 hour)
ACTIVITY_SCORE_CACHE_TIMEOUT = 60 * 60


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the Haversine distance between two points in kilometers.

    Args:
        lat1: Latitude of first point
        lon1: Longitude of first point
        lat2: Latitude of second point
        lon2: Longitude of second point

    Returns:
        Distance in kilometers
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))
    r = 6371  # Radius of Earth in kilometers

    return c * r


def calculate_location_score(job, user_profile) -> float:
    """
    Calculate location proximity score (0-1) based on distance.

    Args:
        job: Job instance
        user_profile: User profile with location data

    Returns:
        Normalized score between 0 and 1, where 1 is closest
    """
    # Get user's last known location
    from userlocation.models import UserLocation

    try:
        user_location = (
            UserLocation.objects.filter(user=user_profile.user)
            .order_by("-last_updated")
            .first()
        )

        if not user_location or not job.latitude or not job.longitude:
            return 0.0

        # Calculate distance
        distance_km = calculate_distance(
            float(job.latitude),
            float(job.longitude),
            float(user_location.latitude),
            float(user_location.longitude),
        )

        # Normalize distance score (closer = higher score)
        # Max distance considered is 50km, beyond that score is 0
        max_distance = 50.0
        if distance_km > max_distance:
            return 0.0

        return 1.0 - (distance_km / max_distance)
    except Exception as e:
        logger.error(f"Error calculating location score: {str(e)}")
        return 0.0


def calculate_skills_score(job, user_profile) -> float:
    """
    Calculate skills match score based on industry and subcategory alignment.

    Args:
        job: Job instance
        user_profile: User profile with skills data

    Returns:
        Normalized score between 0 and 1
    """
    score = 0.0

    try:
        # Check if user has completed jobs in the same industry
        completed_jobs_same_industry = Job.objects.filter(
            selected_applicant=user_profile.user,
            status=Job.Status.COMPLETED,
            industry=job.industry,
        ).count()

        # Check if user has completed jobs in the same subcategory
        completed_jobs_same_subcategory = Job.objects.filter(
            selected_applicant=user_profile.user,
            status=Job.Status.COMPLETED,
            subcategory=job.subcategory,
        ).count()

        # Calculate industry match score (0.6 weight)
        industry_score = min(completed_jobs_same_industry / 5.0, 1.0) * 0.6

        # Calculate subcategory match score (0.4 weight)
        subcategory_score = min(completed_jobs_same_subcategory / 3.0, 1.0) * 0.4

        score = industry_score + subcategory_score
    except Exception as e:
        logger.error(f"Error calculating skills score: {str(e)}")

    return score


def get_user_activity_score(user) -> float:
    """
    Calculate user activity score based on recent platform engagement.

    Args:
        user: User instance

    Returns:
        Normalized activity score between 0 and 1
    """
    # Try to get cached score first
    cache_key = f"activity_score:{user.id}"
    cached_score = cache.get(cache_key)
    if cached_score is not None:
        return cached_score

    score = 0.0

    try:
        # Get activity logs from the last 30 days
        recent_date = timezone.now() - timezone.timedelta(days=ACTIVITY_RECENCY_DAYS)
        activity_logs = UserActivityLog.objects.filter(
            user=user, created_at__gte=recent_date
        )

        # Count different types of activities
        login_count = activity_logs.filter(activity_type="login").count()
        job_view_count = activity_logs.filter(activity_type="job_view").count()
        application_count = activity_logs.filter(
            activity_type="job_application"
        ).count()
        profile_update_count = activity_logs.filter(
            activity_type="profile_update"
        ).count()

        # Calculate raw score
        raw_score = (
            login_count * LOGIN_POINTS
            + job_view_count * JOB_VIEW_POINTS
            + application_count * APPLICATION_POINTS
            + profile_update_count * PROFILE_UPDATE_POINTS
        )

        # Get last login time and calculate recency factor
        last_login = (
            activity_logs.filter(activity_type="login").order_by("-created_at").first()
        )
        recency_factor = 1.0
        if last_login:
            days_since_login = (timezone.now() - last_login.created_at).days
            recency_factor = max(1.0 - (days_since_login / ACTIVITY_RECENCY_DAYS), 0.1)

        # Apply recency factor
        raw_score *= recency_factor

        # Normalize score (max expected raw score is around 500)
        max_expected_score = 500
        score = min(raw_score / max_expected_score, 1.0)

        # Cache the score
        cache.set(cache_key, score, ACTIVITY_SCORE_CACHE_TIMEOUT)
    except Exception as e:
        logger.error(f"Error calculating activity score: {str(e)}")

    return score


def calculate_rating_score(user) -> float:
    """
    Calculate user rating score based on reviews.

    Args:
        user: User instance

    Returns:
        Normalized rating score between 0 and 1
    """
    try:
        # Get average rating
        avg_rating = Review.objects.filter(reviewed=user).aggregate(avg=Avg("rating"))[
            "avg"
        ]

        if not avg_rating:
            return 0.5  # Neutral score for users without ratings

        # Normalize rating (1-5 scale to 0-1 scale)
        return (float(avg_rating) - 1) / 4.0
    except Exception as e:
        logger.error(f"Error calculating rating score: {str(e)}")
        return 0.5


def calculate_experience_score(user) -> float:
    """
    Calculate user experience score based on completed jobs.

    Args:
        user: User instance

    Returns:
        Normalized experience score between 0 and 1
    """
    try:
        # Count completed jobs
        completed_jobs = Job.objects.filter(
            selected_applicant=user, status=Job.Status.COMPLETED
        ).count()

        # Normalize experience (max expected is 20 jobs)
        return min(completed_jobs / 20.0, 1.0)
    except Exception as e:
        logger.error(f"Error calculating experience score: {str(e)}")
        return 0.0


def calculate_match_score(job, user) -> float:
    """
    Calculate overall match score between a job and user.

    Args:
        job: Job instance
        user: User instance

    Returns:
        Weighted match score between 0 and 1
    """
    try:
        profile = Profile.objects.get(user=user)

        # Calculate individual scores
        location_score = calculate_location_score(job, profile)
        skills_score = calculate_skills_score(job, profile)
        activity_score = get_user_activity_score(user)
        rating_score = calculate_rating_score(user)
        experience_score = calculate_experience_score(user)

        # Apply weights to get final score
        final_score = (
            location_score * WEIGHT_LOCATION
            + skills_score * WEIGHT_SKILLS
            + activity_score * WEIGHT_ACTIVITY
            + rating_score * WEIGHT_RATING
            + experience_score * WEIGHT_EXPERIENCE
        )

        return final_score
    except Exception as e:
        logger.error(f"Error calculating match score: {str(e)}")
        return 0.0


def match_job_to_users(job, users) -> List[Dict[str, Any]]:
    """
    Match a single job to multiple users.

    Args:
        job: Job instance
        users: List of User instances

    Returns:
        List of dictionaries with user IDs and match scores
    """
    matches = []

    for user in users:
        score = calculate_match_score(job, user)
        if score > 0:  # Only include non-zero matches
            matches.append(
                {
                    "user_id": user.id,
                    "username": user.username,
                    "score": score,
                    "job_id": job.id,
                    "job_title": job.title,
                }
            )

    # Sort by score (highest first)
    return sorted(matches, key=lambda x: x["score"], reverse=True)


def match_user_to_jobs(user, jobs) -> List[Dict[str, Any]]:
    """
    Match a single user to multiple jobs.

    Args:
        user: User instance
        jobs: List of Job instances

    Returns:
        List of dictionaries with job IDs and match scores
    """
    matches = []

    for job in jobs:
        score = calculate_match_score(job, user)
        if score > 0:  # Only include non-zero matches
            matches.append(
                {
                    "job_id": job.id,
                    "job_title": job.title,
                    "score": score,
                    "user_id": user.id,
                    "username": user.username,
                }
            )

    # Sort by score (highest first)
    return sorted(matches, key=lambda x: x["score"], reverse=True)


def match_jobs_to_users(jobs, users) -> Dict[int, List[Dict[str, Any]]]:
    """
    Match multiple jobs to multiple users concurrently.

    Args:
        jobs: List of Job instances
        users: List of User instances

    Returns:
        Dictionary mapping job IDs to lists of matched users with scores
    """
    start_time = time.time()
    logger.info(f"Starting job matching for {len(jobs)} jobs and {len(users)} users")

    results = {}

    # Use ThreadPoolExecutor for concurrent processing
    with ThreadPoolExecutor(max_workers=min(10, len(jobs))) as executor:
        # Submit tasks for each job
        future_to_job = {
            executor.submit(match_job_to_users, job, users): job.id for job in jobs
        }

        # Process results as they complete
        for future in future_to_job:
            job_id = future_to_job[future]
            try:
                matches = future.result()
                results[job_id] = matches
            except Exception as e:
                logger.error(f"Error matching job {job_id}: {str(e)}")
                results[job_id] = []

    elapsed_time = time.time() - start_time
    logger.info(f"Job matching completed in {elapsed_time:.2f} seconds")

    return results


def match_users_to_jobs(users, jobs) -> Dict[int, List[Dict[str, Any]]]:
    """
    Match multiple users to multiple jobs concurrently.

    Args:
        users: List of User instances
        jobs: List of Job instances

    Returns:
        Dictionary mapping user IDs to lists of matched jobs with scores
    """
    start_time = time.time()
    logger.info(f"Starting user matching for {len(users)} users and {len(jobs)} jobs")

    results = {}

    # Use ThreadPoolExecutor for concurrent processing
    with ThreadPoolExecutor(max_workers=min(10, len(users))) as executor:
        # Submit tasks for each user
        future_to_user = {
            executor.submit(match_user_to_jobs, user, jobs): user.id for user in users
        }

        # Process results as they complete
        for future in future_to_user:
            user_id = future_to_user[future]
            try:
                matches = future.result()
                results[user_id] = matches
            except Exception as e:
                logger.error(f"Error matching user {user_id}: {str(e)}")
                results[user_id] = []

    elapsed_time = time.time() - start_time
    logger.info(f"User matching completed in {elapsed_time:.2f} seconds")

    return results

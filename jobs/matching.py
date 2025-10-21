"""
Job matching module for finding the best applicants for jobs.
Provides functions for matching applicants to jobs based on location, skills, availability, and rating.
"""

import logging
from typing import Dict, List

from django.contrib.auth import get_user_model

from accounts.models import Profile
from jobs.models import Application, Job

User = get_user_model()
logger = logging.getLogger(__name__)

# Constants for job matching logic
WEIGHT_RATING = 3
WEIGHT_DISTANCE = 2
WEIGHT_COMPLETION_RATE = 2
WEIGHT_ACHIEVEMENT = 1
WEIGHT_BADGE = 1
WEIGHT_POINT = 1


def get_job_matches(job_id: int, limit: int = 10) -> List[Dict]:
    """
    Get the best matching applicants for a job.
    Returns a list of applicants with scores, sorted descending.
    """
    try:
        job = Job.objects.get(id=job_id)
        applicants = User.objects.filter(profile__role="applicant")
        matches = []
        for applicant in applicants:
            score = calculate_match_score(job, applicant)
            if score > 0:
                matches.append({
                    "applicant_id": applicant.id,
                    "username": applicant.username,
                    "first_name": applicant.first_name,
                    "last_name": applicant.last_name,
                    "score": score,
                    "profile_id": getattr(applicant.profile, "id", None),
                    "skills": getattr(applicant.profile, "skills", ""),
                    "location": getattr(applicant.profile, "location", ""),
                })
        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches[:limit]
    except Job.DoesNotExist:
        logger.error(f"Job with ID {job_id} not found")
        return []
    except Exception as e:
        logger.error(f"Error getting job matches for job_id={job_id}: {str(e)}")
        return []

def get_applicant_matches(applicant_id: int, limit: int = 10) -> List[Dict]:
    """
    Get the best matching jobs for an applicant.
    Returns a list of jobs with scores, sorted descending.
    Softened: always include jobs with score > 10 (base score), so user always sees some jobs.
    """
    try:
        applicant = User.objects.get(id=applicant_id)
        jobs = Job.objects.filter(is_active=True)
        matches = []
        for job in jobs:
            score = calculate_match_score(job, applicant)
            if score > 10:  # Lowered threshold, include partial matches
                matches.append({
                    "job_id": job.id,
                    "title": job.title,
                    "location": job.location,
                    "score": score,
                    "client_id": job.client_id,
                    "client_name": f"{job.client.first_name} {job.client.last_name}",
                    "date": job.date.isoformat(),
                    "rate": float(job.rate),
                })
        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches[:limit]
    except User.DoesNotExist:
        logger.error(f"Applicant with ID {applicant_id} not found")
        return []
    except Exception as e:
        logger.error(f"Error getting applicant matches for applicant_id={applicant_id}: {str(e)}")
        return []

def calculate_match_score(job, applicant) -> float:
    """
    Calculate a match score between a job and an applicant (0-100).
    Jobs that the user has already applied to will still get a score,
    but will be marked with application status in the job data.
    """
    score = 0.0
    try:
        profile = getattr(applicant, "profile", None)
        if not profile:
            return 0.0

        # Calculate base match score regardless of application status
        score += calculate_location_match(job, profile) * 0.3
        score += calculate_skills_match(job, profile) * 0.4
        score += calculate_availability_match(job, applicant) * 0.2
        score += calculate_rating_match(profile) * 0.1

        # If user has applied, slightly reduce score but don't eliminate the job
        if Application.objects.filter(job=job, applicant=applicant).exists():
            score = score * 0.8  # Reduce score by 20% for applied jobs

        return score
    except Exception as e:
        logger.error(f"Error calculating match score: {str(e)}")
        return 0.0

def calculate_location_match(job: Job, profile: Profile) -> float:
    """
    Calculate location match score (softened: partial/fuzzy match allowed).
    """
    if not profile.location or not job.location:
        return 10.0  # Give a small base score if location is missing
    job_loc = job.location.lower()
    profile_loc = profile.location.lower()
    if profile_loc == job_loc:
        return 100.0
    # Partial substring match
    if profile_loc in job_loc or job_loc in profile_loc:
        return 70.0
    # Overlap on any word (city, state, etc.)
    job_parts = set([p.strip() for p in job_loc.replace(",", " ").split()])
    profile_parts = set([p.strip() for p in profile_loc.replace(",", " ").split()])
    if job_parts & profile_parts:
        return 40.0
    return 10.0  # Small base score for any non-match

def calculate_skills_match(job: Job, profile: Profile) -> float:
    """
    Calculate skills match score (softened: partial/fuzzy match allowed).
    """
    if not profile.skills or not job.title:
        return 10.0  # Small base score if missing
    applicant_skills = [s.strip().lower() for s in profile.skills.split(",") if s.strip()]
    job_keywords = set(job.title.lower().split())
    if job.description:
        job_keywords |= set(job.description.lower().split())
    # Fuzzy/substring match: count skills that appear as substrings in any job keyword
    matches = 0
    for skill in applicant_skills:
        for word in job_keywords:
            if skill in word or word in skill:
                matches += 1
                break
    if not applicant_skills:
        return 10.0
    # Give a base score, plus proportional match
    return min(100.0, 10.0 + (matches / len(applicant_skills)) * 90.0)

def calculate_availability_match(job, applicant) -> float:
    """
    Calculate availability match score.
    """
    other_jobs = Application.objects.filter(
        applicant=applicant, job__date=job.date, status__in=["Accepted", "Pending"]
    ).count()
    if other_jobs == 0:
        return 100.0
    elif other_jobs == 1:
        return 50.0
    else:
        return 0.0

def calculate_rating_match(profile: Profile) -> float:
    """
    Calculate rating match score.
    """
    rating = getattr(profile, "rating", 0.0)
    if not rating:
        return 50.0
    return min(100.0, rating * 20.0)

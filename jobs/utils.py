# ==
# 📌 Python Standard Library Imports
# ==
import json
import logging
import os
import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from math import atan2, cos, radians, sin, sqrt
from typing import Dict, List, Optional, Tuple, Union

# ==
# 📌 Third-Party Imports
# ==
import requests
from asgiref.sync import async_to_sync

# Define a custom channel layer function to work with newer channels version
def get_channel_layer():
    from channels.layers import get_channel_layer as gcl
    return gcl()
# ==
# 📌 Django Core Imports
# ==
from django.conf import settings
from django.contrib.auth import (authenticate, get_backends, get_user_model,
                                 login, logout, update_session_auth_hash)
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.tokens import default_token_generator
from django.contrib.humanize.templatetags.humanize import (naturalday,
                                                           naturaltime)
from django.contrib.sessions.models import Session
from django.core.mail import send_mail
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import IntegrityError
from django.db.models import Avg, Count, F, Max, Q, Sum
from django.http import HttpRequest, JsonResponse
from django.middleware.csrf import CsrfViewMiddleware
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.timezone import localtime
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from ninja import File, Query, Router
from ninja.files import UploadedFile
from ninja.responses import Response
from ninja.security import django_auth
from pydantic import BaseModel, ConfigDict, field_validator
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Profile

logger = logging.getLogger(__name__)
# ==
# 📌 Local Application Imports
# ==
from .models import *
from .models import Application, Job
from .schemas import *

# ==
# 📌 Constants and Configuration
# ==
logger = logging.getLogger(__name__)
router = Router(tags=["Core"])
from ninja.security import HttpBearer
import logging

from celery.exceptions import CeleryError
# Temporarily commented out - django_q has pkg_resources issue
# from django_q.tasks import async_task

from rating.models import Review

WEIGHT_RATING = 3
WEIGHT_DISTANCE = 2
WEIGHT_EXPERIENCE = 1.5
WEIGHT_COMPLETION_RATE = 2
GOOGLE_MAPS_API_KEY = settings.GOOGLE_MAPS_API_KEY

logger = logging.getLogger(__name__)
# import googlemaps
# ==
# 📌 Helper Functions
# ==


def authenticated_user_or_error(request, message="You must be logged in"):
    """Check if user is authenticated, return user or error response"""

    if not request.user.is_authenticated:
        return None, JsonResponse({"error": message}, status=401)

    return request.user, None  # Always return a tuple


def fetch_all_users():
    """Fetch all users from the database including full name and profile_pic_url"""
    users = []
    for user in User.objects.all():
        profile_pic_url = None
        try:
            if hasattr(user, "profile") and user.profile:
                profile = user.profile
                # Safely access pictures relationship
                if hasattr(profile, "pictures"):
                    active_pic = profile.pictures.filter(is_active=True).first()
                    if active_pic:
                        profile_pic_url = active_pic.url
        except Exception as e:
            # Log the error but continue processing other users
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Error fetching profile picture for user {user.id}: {str(e)}")
            profile_pic_url = None

        try:
            users.append({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "date_joined": user.date_joined,
                "role": user.role,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "full_name": user.get_full_name(),
                "profile_pic_url": profile_pic_url,
            })
        except Exception as e:
            # Log the error but continue processing other users
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error processing user {user.id}: {str(e)}")
            continue

    return users


def get_related_object(model, field, value):
    """
    Helper function to retrieve an object by a specific field.
    Returns a tuple: (object, None) if found, or (None, JsonResponse error) if not.
    """
    try:
        obj = model.objects.get(**{field: value})
        return obj, None
    except model.DoesNotExist:
        return None, JsonResponse(
            {"error": f"{model.__name__} with {field} '{value}' does not exist."},
            status=400,
        )

def serialize_job(job, include_extra: bool = True, user_id: int = None) -> dict:
    from jobs.models import Application
    now = date.today()
    job_start_date = job.start_date

    date_flags = {
        "is_today": job_start_date == now if job_start_date else False,
        "is_yesterday": job_start_date == (now - timedelta(days=1)) if job_start_date else False,
        "is_this_week": (
            job_start_date.isocalendar()[1] == now.isocalendar()[1] if job_start_date else False
        ),
        "is_this_month": (
            job_start_date.month == now.month and job_start_date.year == now.year
            if job_start_date
            else False
        ),
    }

    applicants_count = 0
    applicants_user_ids = []
    accepted_applicants_count = 0
    has_applied = False
    application_status = None

    try:
        if hasattr(job, "applications"):
            applicants_count = job.applications.count()
            applicants_user_ids = list(job.applications.values_list("applicant_id", flat=True))
            accepted_applicants_count = job.applications.filter(status=Application.Status.ACCEPTED).count()
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Error fetching applications for job {job.id}: {str(e)}")

    # Determine if the user has applied and get application status
    try:
        if user_id is not None:
            application = Application.objects.filter(job=job, applicant_id=user_id).exclude(status=Application.Status.WITHDRAWN).first()
            if application:
                has_applied = True
                application_status = application.status
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Error checking application status for user {user_id} on job {job.id}: {str(e)}")

    # Get client rating safely
    client_rating = None
    if job.client and hasattr(job.client, "profile"):
        try:
            client_rating = job.client.profile.rating
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Error fetching rating for user {job.client.id}: {str(e)}")

    data = {
        "id": job.id,
        "title": job.title,
        "description": job.description,
        "industry_id": job.industry.id if job.industry else None,
        "industry_name": job.industry.name if job.industry else None,
        "subcategory": job.subcategory.name if job.subcategory else None,
        "client_username": job.client.username if job.client else None,
        "client_rating": client_rating,
        "client_first_name": job.client.first_name if job.client else None,
        "client_last_name": job.client.last_name if job.client else None,
        "client_profile_pic_url": None,
        "start_date": job.start_date.isoformat() if job.start_date else None,
        "end_date": job.end_date.isoformat() if job.end_date else None,
        "date": job.start_date.isoformat() if job.start_date else None,  # Add this line
        "date_posted_human": (
            naturalday(localtime(job.created_at)) if job.created_at else None
        ),
        "date_human": naturalday(job.start_date) if job.start_date else None,
        "start_time_human": (
            job.start_time.strftime("%I:%M %p") if job.start_time else None
        ),
        "end_time_human": job.end_time.strftime("%I:%M %p") if job.end_time else None,
        "updated_at_human": (
            naturaltime(localtime(job.updated_at)) if job.updated_at else None
        ),
        "location": job.location,
        "latitude": job.latitude,
        "longitude": job.longitude,
        "rate": str(job.rate),
        "applicants_needed": job.applicants_needed,
        "applicants_count": applicants_count,
        "accepted_applicants_count": accepted_applicants_count,
        "applicants_user_ids": applicants_user_ids,
        "status": job.status,
        "payment_status": job.payment_status,
        "total_amount": str(job.total_amount),
        "service_fee": str(job.service_fee),
        "is_shift_ongoing": job.is_shift_ongoing,
        "total_duration_hours": (
            f"{round(job.duration_hours, 2)}" if job.duration_hours else None
        ),
        **date_flags,
        "has_applied": has_applied,
        "application_status": application_status,
    }

    if job.client and hasattr(job.client, "profile"):
        try:
            profile = job.client.profile
            active_pic = profile.pictures.filter(is_active=True).first()
            data["client_profile_pic_url"] = active_pic.url if active_pic else None
        except Exception as e:
            # Log the error but don't fail the entire request
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Error fetching profile picture for user {job.client.id}: {str(e)}")
            data["client_profile_pic_url"] = None

    if include_extra:
        data.update(
            {
                "duration": (
                    str(job.duration_hours) if job.duration_hours is not None else None
                ),
                "client_id": job.client.id if job.client else None,
                "employer_name": (
                    f"{job.client.first_name} {job.client.last_name}"
                    if job.client
                    else None
                ),
                "job_type": job.job_type,
                "shift_type": job.shift_type,
                "start_time_str": (
                    job.start_time.isoformat() if job.start_time else None
                ),
                "end_time_str": job.end_time.isoformat() if job.end_time else None,
                "actual_shift_start": (
                    job.actual_shift_start.isoformat() if job.actual_shift_start else None
                ),
                "actual_shift_end": (
                    job.actual_shift_end.isoformat() if job.actual_shift_end else None
                ),
            }
        )

    return data

# ==
# 📌 Helper Functions
# ==
def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees)
    """
    # Convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    r = 6371  # Radius of earth in kilometers
    return c * r


def calculate_distance_score(
    job_lat: float,
    job_lon: float,
    user_lat: float,
    user_lon: float,
    max_distance_km: float = 50,
) -> float:
    """
    Calculate a normalized distance score (0-1) based on Haversine distance
    Returns 0 if any coordinate is None or distance exceeds max_distance_km
    """
    if None in (job_lat, job_lon, user_lat, user_lon):
        return 0

    distance = haversine(job_lat, job_lon, user_lat, user_lon)

    if distance > max_distance_km:
        return 0

    # Normalize to 0-1 range (closer is better)
    return 1 - (distance / max_distance_km)


def resolve_industry(industry_id):
    try:
        return JobIndustry.objects.get(id=industry_id)
    except JobIndustry.DoesNotExist:
        raise ValueError(f"JobIndustry with id {industry_id} does not exist.")


def resolve_subcategory(subcategory):
    if not subcategory:
        return None
    try:
        return JobSubCategory.objects.get(id=int(subcategory))
    except (ValueError, JobSubCategory.DoesNotExist):
        return JobSubCategory.objects.filter(name__iexact=subcategory.strip()).first()


@router.get("/authenticate", tags=["Auth"])
def get_logged_in_user(request: HttpRequest) -> JsonResponse:
    """Returns the currently logged-in user."""
    if request.user.is_authenticated:
        return JsonResponse(
            {"username": request.user.username, "email": request.user.email}, status=200
        )
    return JsonResponse({"error": "Not authenticated"}, status=401)


# Import the enhanced geocoding module
from .geocoding import geocode_address


def get_address_coordinates_helper(address: str) -> dict:
    """
    Enhanced geocoding with multiple providers and Redis caching

    This function is a wrapper around the geocode_address function in the geocoding module.
    It maintains backward compatibility with existing code while providing enhanced functionality.

    Args:
        address: The address string to geocode

    Returns:
        Dictionary with geocoding results including success status, coordinates, and error info
    """
    # Use the enhanced geocoding module
    return geocode_address(address)


def fallback_geocode_and_save(job_id):
    """Synchronous fallback geocoding"""
    try:
        # Get the job by ID
        from .models import Job

        try:
            job = Job.objects.get(id=job_id)
        except Job.DoesNotExist:
            logger.warning(f"Job {job_id} not found for geocoding")
            return None

        if not job.location:
            logger.warning(f"No location for job {job.id}")
            return job

        from .geocoding import geocode_address

        coords = geocode_address(job.location)

        if coords["success"]:
            job.latitude = coords["latitude"]
            job.longitude = coords["longitude"]
            job.save(update_fields=["latitude", "longitude"])
            logger.info(f"Geocoded job {job.id} successfully")
        else:
            logger.warning(f"Geocoding failed for job {job.id}: {coords.get('error')}")

    except Exception as e:
        logger.error(f"Fallback geocoding error for job {job_id}: {str(e)}")
        return None

    return job

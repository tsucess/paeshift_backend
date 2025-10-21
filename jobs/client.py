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
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, F, Max, Q, Sum
from django.http import HttpRequest, JsonResponse
from django.middleware.csrf import CsrfViewMiddleware
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.timezone import localtime
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from geopy.exc import GeocoderServiceError, GeocoderTimedOut
from geopy.geocoders import Nominatim
from haversine import Unit, haversine as haversine_lib
from ninja import File, Query, Router
from ninja.files import UploadedFile
from ninja.responses import Response
from ninja.security import HttpBearer, django_auth
from pydantic import BaseModel, ConfigDict, field_validator
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken

from jobs.utils import serialize_job

# ==
# 📌 Local Application Imports
# ==
from .models import *
from .schemas import *
from core.cache import cache_api_response
from core.redis_decorators import time_view, track_user_activity

from userlocation.models import UserLocation
from accounts.models import Profile
# ==
# 📌 Constants and Configuration
# ==
logger = logging.getLogger(__name__)
# Initialize channel_layer lazily to avoid import errors
channel_layer = None

WEIGHT_RATING = 3
WEIGHT_DISTANCE = 2
WEIGHT_EXPERIENCE = 1.5
WEIGHT_COMPLETION_RATE = 2
GOOGLE_MAPS_API_KEY = settings.GOOGLE_MAPS_API_KEY

client_router = Router()
User = get_user_model()


def haversine(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees)
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    distance = 6371 * c  # Radius of earth in kilometers

    return distance


def calculate_distance_score(job_lat, job_lon, user_lat, user_lon, max_distance_km=50):
    """
    Calculate a distance score between 0 and 1.
    Closer distances get higher scores.
    """
    distance = haversine(job_lat, job_lon, user_lat, user_lon)

    # If distance is greater than max_distance_km, return 0
    if distance > max_distance_km:
        return 0

    # Otherwise, calculate a score between 0 and 1
    # where 0 is max_distance_km away and 1 is at the same location
    return 1 - (distance / max_distance_km)


# ==
# 📌 Authentication Classes
# ==
class JWTAuth(HttpBearer):
    def authenticate(self, request, token):
        print(f"🔐 Client JWT Auth: Received token: {token[:20] if token else 'None'}...")

        try:
            # Validate the token
            from rest_framework_simplejwt.tokens import UntypedToken, AccessToken
            from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
            from django.contrib.auth import get_user_model

            UntypedToken(token)
            print(f"✅ Client JWT Auth: Token validation successful")

            # Decode the token to get user info
            access_token = AccessToken(token)
            user_id = access_token['user_id']
            print(f"✅ Client JWT Auth: Extracted user_id: {user_id}")

            # Get the user
            User = get_user_model()
            user = User.objects.get(id=user_id)
            print(f"✅ Client JWT Auth: Found user: {user.username} (ID: {user.id})")
            return user
        except (InvalidToken, TokenError) as e:
            print(f"❌ Client JWT Auth: Authentication failed: {e}")
            return None
        except Exception as e:
            print(f"❌ Client JWT Auth: Unexpected error: {e}")
            return None

class ClientAuth(HttpBearer):
    def authenticate(self, request, token):
        if token == "supersecret":
            user = request.user
            if user.is_authenticated and user.role == "client":
                return user
        return None


# ======
# Client Endpoints
# ======


def get_nearby_applicants(instance):
    """Find applicants near the job location"""

    try:
        job_location = (
            json.loads(instance.location)
            if isinstance(instance.location, str)
            else instance.location
        )
    except json.JSONDecodeError:
        job_location = {}  # Handle invalid JSON

    if (
        not isinstance(job_location, dict)
        or "latitude" not in job_location
        or "longitude" not in job_location
    ):
        return []  # No valid location data

    latitude = float(job_location["latitude"])
    longitude = float(job_location["longitude"])

    # 🔹 Query Applicants within Range
    nearby_applicants = Application.objects.filter(
        latitude__range=(latitude - 0.1, latitude + 0.1),
        longitude__range=(longitude - 0.1, longitude + 0.1),
    ).values("applicant_id")

    return list(nearby_applicants)



@client_router.get('/jobs/{job_id}', response=JobDetailSchema)
def get_job_detail(request, job_id: int):
    # Optimize query with select_related for related objects
    job = get_object_or_404(
        Job.objects.select_related(
            'client__profile',
            'industry',
            'subcategory',
            'created_by__profile'
        ).prefetch_related('applications'),
        id=job_id
    )
    data = serialize_job(job)
    return data

@client_router.get("/clientjobs/{user_id}", tags=["Client Endpoints"])
@time_view("client_jobs_by_id")
@track_user_activity("view_client_jobs")
def get_client_jobs_by_id(
    request, user_id: int, page: int = Query(1, gt=0), page_size: int = Query(50, gt=0)
):
    """
    Get all jobs for a specific client.
    Returns paginated list of jobs with basic client information.
    """
    client = get_object_or_404(User.objects.select_related('profile'), id=user_id)
    # Optimize query with select_related for related objects
    qs = Job.objects.select_related(
        'client__profile',
        'industry',
        'subcategory',
        'created_by__profile'
    ).prefetch_related('applications').filter(client=client).order_by("-date")

    paginator = Paginator(qs, page_size)

    try:
        jobs_page = paginator.page(page)
    except PageNotAnInteger:
        jobs_page = paginator.page(1)
    except EmptyPage:
        jobs_page = []

    jobs_data = [serialize_job(job, include_extra=True) for job in jobs_page]

    return JsonResponse({
        "client_id": client.id,
        "client_username": client.username,
        "client_first_name": client.first_name,
        "client_last_name": client.last_name,
        "client_rating": client.profile.rating if hasattr(client, 'profile') else None,
        "jobs": jobs_data,
        "pagination": {
            "current_page": page,
            "total_pages": paginator.num_pages,
            "total_items": paginator.count,
            "items_per_page": page_size,
            "has_next": jobs_page.has_next() if jobs_page else False,
            "has_previous": jobs_page.has_previous() if jobs_page else False
        }
    }, status=200)




@client_router.get("/jobs/{job_id}/best-applicants/", tags=["Client Endpoints"])
def get_best_applicants(request, job_id: int):
    """Fetch and notify the best applicants for a job using Haversine."""
    # Optimize query with select_related for related objects
    job = get_object_or_404(
        Job.objects.select_related(
            'client__profile',
            'industry',
            'subcategory'
        ),
        id=job_id
    )
    candidates = find_best_applicants(job)

    top_applicants = []
    for candidate in candidates:
        # Get user location
        user_location = UserLocation.objects.filter(user=candidate.user).first()
        if not user_location or not user_location.last_location:
            continue

        # Calculate distance
        distance = haversine(
            job.latitude,
            job.longitude,
            user_location.last_location.y,
            user_location.last_location.x,
        )

        top_applicants.append(
            {
                "id": candidate.user.id,
                "name": candidate.user.username,
                "rating": candidate.avg_rating or 0,
                "distance_km": round(distance, 2),
            }
        )

    # Notify candidates via WebSocket
    channel_layer = get_channel_layer()
    for applicant in candidates:
        async_to_sync(channel_layer.group_send)(
            f"user_matching_{applicant.user.id}",
            {
                "type": "job_match_found",
                "message": f"New job match found: {job.title}!",
                "job_id": job.id,
            },
        )

    return {"top_applicants": top_applicants}




def _handle_application_action(request, application_id: int, payload: ClientActionSchema, action: str):
    application = get_object_or_404(Application, id=application_id)

    if application.job.client_id != payload.user_id:
        return 403, {"error": f"You are not authorized to {action} this application"}

    if action == "accept":
        if application.status != Application.Status.APPLIED:
            return 400, {
                "error": "Application cannot be accepted",
                "details": f"Application is already in {application.get_status_display()} status"
            }
        try:
            with transaction.atomic():
                application.accept()
            return 200, {
                "status": "success",
                "message": "Application accepted successfully",
                "data": {
                    "application_id": application.id,
                    "job_id": application.job.id,
                    "job_title": application.job.title,
                    "applicant_id": application.applicant.id,
                    "applicant_name": f"{application.applicant.first_name} {application.applicant.last_name}",
                    "status": application.status,
                    "accepted_at": timezone.now().isoformat(),
                }
            }
        except Exception as e:
            return 500, {"error": f"An error occurred: {str(e)}"}

    elif action == "decline":
        if application.status not in [Application.Status.APPLIED, Application.Status.ACCEPTED]:
            return 400, {
                "error": "Application cannot be declined",
                "details": f"Application is already in {application.get_status_display()} status"
            }
        try:
            with transaction.atomic():
                application.reject()
            return 200, {
                "status": "success",
                "message": "Application declined successfully",
                "data": {
                    "application_id": application.id,
                    "job_id": application.job.id,
                    "job_title": application.job.title,
                    "applicant_id": application.applicant.id,
                    "applicant_name": f"{application.applicant.first_name} {application.applicant.last_name}",
                    "status": application.status,
                    "declined_at": timezone.now().isoformat(),
                }
            }
        except Exception as e:
            return 500, {"error": f"An error occurred: {str(e)}"}
    else:
        return 400, {"error": "Invalid action"}

@client_router.put(
    "/applications/{application_id}/accept/",
    response={200: dict, 400: dict, 403: dict, 404: dict, 500: dict},
    auth=JWTAuth(),
)
def accept_application(request, application_id: int, payload: ClientActionSchema):
    return _handle_application_action(request, application_id, payload, "accept")

@client_router.put(
    "/applications/{application_id}/decline/",
    response={200: dict, 400: dict, 403: dict, 404: dict, 500: dict},
    auth=JWTAuth(),
)
def decline_application(request, application_id: int, payload: ClientActionSchema):
    return _handle_application_action(request, application_id, payload, "decline")















def get_industry_or_subcategory(model, value):
    """Helper to get industry/subcategory by ID or name"""
    try:
        return (
            model.objects.get(id=int(value))
            if value.isdigit()
            else model.objects.get(name=value.strip())
        )
    except (ValueError, model.DoesNotExist):
        return f"{model.__name__} not found"


def find_best_applicants(job, max_distance_km=50):
    """Find and rank the best applicants for a given job using Haversine"""
    if not job.latitude or not job.longitude:
        return []

    # Get all potential candidates in the same industry/subcategory
    candidates = (
        Profile.objects.filter(
            industry=job.industry, subcategory=job.subcategory, is_active=True
        )
        .select_related("user")
        .prefetch_related("user__ratings_received")
    )

    ranked_candidates = []
    for candidate in candidates:
        if not candidate.last_location:
            continue

        # Extract coordinates
        user_lat = candidate.last_location.y
        user_lon = candidate.last_location.x
        job_lat = job.latitude
        job_lon = job.longitude

        # Calculate distance score
        distance_score = calculate_distance_score(
            job_lat, job_lon, user_lat, user_lon, max_distance_km
        )

        # Calculate other metrics
        avg_rating = (
            candidate.user.ratings_received.aggregate(Avg("rating"))["rating__avg"] or 0
        )
        jobs_completed = candidate.user.accepted_jobs.count()

        # Calculate composite score
        composite_score = (
            (avg_rating * WEIGHT_RATING)
            + (distance_score * WEIGHT_DISTANCE)
            + (jobs_completed * WEIGHT_EXPERIENCE)
        )

        ranked_candidates.append(
            {
                "profile": candidate,
                "composite_score": composite_score,
                "distance_km": haversine(job_lat, job_lon, user_lat, user_lon),
                "avg_rating": avg_rating,
                "jobs_completed": jobs_completed,
            }
        )

    # Sort by composite score (descending)
    ranked_candidates.sort(key=lambda x: x["composite_score"], reverse=True)

    return [candidate["profile"] for candidate in ranked_candidates[:10]]

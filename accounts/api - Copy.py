# This is a fall back back up page to pick from when i am having issues with api.py


# ==============================
# 📌 Python Standard Library Imports
# ==============================
import json
import logging
import os
from datetime import datetime
from typing import List, Optional

# ==============================
# 📌 Third-Party Imports
# ==============================
import requests
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.contrib.auth import (authenticate, get_backends, get_user_model,
                                 login, logout)
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import IntegrityError, transaction
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from geopy.exc import GeocoderServiceError, GeocoderTimedOut
from ninja import File, Router
from ninja.files import UploadedFile
from ninja.responses import Response
from pydantic import BaseModel, field_validator
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

from jobs.utils import get_user_response

# ==============================
# 📌 Local Application Imports
# ==============================
from .models import *
from .schemas import (LoginSchema, PasswordResetRequestSchema,
                      PasswordResetSchema, SignupSchema,
                      UserProfileUpdateSchema)

User = get_user_model()
channel_layer = get_channel_layer()
logger = logging.getLogger(__name__)
accounts_router = Router(tags=["Core"])
# ==============================
# 📌 Python Standard Library Imports
# ==============================
import json
import logging
import os
import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from math import atan2, cos, radians, sin, sqrt
from typing import List, Optional

import requests
# ==============================
# 📌 Third-Party Imports
# ==============================
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from core.schemas import *

channel_layer = get_channel_layer()
import logging

from asgiref.sync import async_to_sync
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
# ==============================
# 📌 Django Core Imports
# ==============================
from ninja import File, Query, Router
from ninja.files import UploadedFile
from ninja.responses import Response
from ninja.security import django_auth
from pydantic import BaseModel, ConfigDict, field_validator
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken

from .applicant import *
from .client import *
from .models import *
from .schemas import *
from .utils import *

logger = logging.getLogger(__name__)


User = get_user_model()
# ==============================
# 📌 Local Application Imports
# ==============================
WEIGHT_RATING = 3
WEIGHT_DISTANCE = 2
WEIGHT_EXPERIENCE = 1.5
WEIGHT_COMPLETION_RATE = 2

core_router = Router(tags=["Core"])


# ==============================
# 📌 Core Endpoints
# ==============================
# In your views:


# ==============================
# 📌 Job Endpoints
# ==============================
@core_router.get("/all-users", tags=["Job"])
def get_all_users_view(request):
    """GET /jobs/all-users - Returns list of all users"""
    return {"users": fetch_all_users()}


@core_router.get("/alljobs", tags=["Jobs"])
def get_jobs(request):
    jobs = Job.objects.select_related("client__profile").all()
    serialized = [serialize_job(job, include_extra=True) for job in jobs]
    return {"jobs": serialized}


@core_router.get("/{job_id}", response=JobDetailSchema, tags=["Jobs"])
def job_detail(request, job_id: int):
    """GET /jobs/<job_id> - Returns details for a single job"""
    job = get_object_or_404(Job.objects.select_related("client__profile"), id=job_id)
    return serialize_job(job, include_extra=True)


# ===============================================================
@core_router.put(
    "/job/cancel/{job_id}/",
    response={
        200: JobCancellationSuccessSchema,
        400: ErrorResponseSchema,
        403: ErrorResponseSchema,
        404: ErrorResponseSchema,
    },
    summary="Cancel a job posting",
    description="""Cancels an active job posting. 
    Only the job creator can cancel a job, and only if it hasn't started or completed.""",
    tags=["Job Management"],
)
def cancel_job(request, job_id: int):
    # Authentication check
    if not request.user.is_authenticated:
        return 403, {
            "error": "Authentication required",
            "details": "Please log in to cancel jobs",
        }

    # Get job or return 404
    job = get_object_or_404(Job, id=job_id)

    # Authorization check - only job creator can cancel
    if job.client != request.user:
        return 403, {
            "error": "Permission denied",
            "details": "Only the job creator can cancel this job",
        }

    # Business logic validation
    if job.status in [JobStatusEnum.COMPLETED, JobStatusEnum.CANCELED]:
        return 400, {
            "error": "Job cannot be canceled",
            "details": f"Job is already {job.status}",
        }

    if job.status == JobStatusEnum.ONGOING:
        return 400, {
            "error": "Job cannot be canceled",
            "details": "Job is currently ongoing and cannot be canceled",
        }

    # Update job status
    job.status = JobStatusEnum.CANCELED
    job.save()

    # Return success response with job details
    return 200, {
        "message": "Job has been successfully canceled",
        "job_id": job.id,
        "new_status": job.status,
        "job_details": {
            "title": job.title,
            "original_status": job.status,
            "cancellation_time": job.updated_at.isoformat(),
            "affected_applicants": job.applicants.count(),
        },
    }


@core_router.delete(
    "/job/delete/{job_id}", summary="Delete a Job", tags=["Job Management"]
)
def delete_job(request, job_id: int):
    """
    Deletes a job by its ID.
    """
    job = get_object_or_404(Job, id=job_id)
    job.delete()
    return {"message": "Job deleted successfully"}


# --- GET: Job Industries ---
@core_router.get("/job-industries/", response=list[IndustrySchema], tags=["Jobs"])
def get_job_industries(request):
    return JobIndustry.objects.all()


# --- GET: Job Subcategories with Industry ---
@core_router.get("/job-subcategories/", response=list[SubCategorySchema], tags=["Jobs"])
def get_job_subcategories(request):
    return JobSubCategory.objects.select_related("industry").all()


# --- POST: Create Job ---
@core_router.post("/create-job", tags=["Job Management"])
def create_job(request, payload: CreateJobSchema):
    """Create a job, ensuring the user is authenticated."""

    user = get_object_or_404(User, id=request.user.id)

    # Parse and validate job date/time
    try:
        job_date = datetime.strptime(payload.date, "%Y-%m-%d").date()
        start_time = datetime.strptime(payload.start_time, "%H:%M").time()
        end_time = datetime.strptime(payload.end_time, "%H:%M").time()
    except ValueError as e:
        logger.error(f"Invalid date/time format: {e}")
        return JsonResponse(
            {"error": f"Invalid date/time format: {str(e)}"}, status=400
        )

    if end_time <= start_time:
        return JsonResponse(
            {"error": "End time must be later than start time"}, status=400
        )

    duration_hours = round(
        (
            datetime.combine(job_date, end_time)
            - datetime.combine(job_date, start_time)
        ).total_seconds()
        / 3600,
        2,
    )

    # Get address coordinates (optional enhancement: cache or validate via Redis or geocoding API)
    try:
        get_address_coordinates(payload.location)
    except Exception as e:
        logger.warning(f"Address resolution failed for '{payload.location}': {e}")

    # Resolve industry and subcategory
    industry_obj = resolve_industry(payload.industry)
    subcategory_obj = resolve_subcategory(payload.subcategory)

    transaction_ref = str(uuid.uuid4())

    # Create job atomically
    with transaction.atomic():
        job = Job.objects.create(
            client=user,
            title=payload.title,
            industry=industry_obj,
            subcategory=subcategory_obj,
            applicants_needed=payload.applicants_needed,
            job_type=payload.job_type,
            shift_type=payload.shift_type,
            date=job_date,
            start_time=start_time,
            end_time=end_time,
            rate=Decimal(str(payload.rate)),
            location=payload.location,
            payment_status="Pending",
            status="pending",
        )

    return JsonResponse(
        {
            "success": True,
            "message": "Job created successfully. Proceed to payment.",
            "job_id": job.id,
            "transaction_ref": transaction_ref,
            "duration": duration_hours,
        },
        status=201,
    )


# --- Helpers ---


def resolve_industry(industry):
    if not industry:
        return None
    try:
        return JobIndustry.objects.get(id=int(industry))
    except (ValueError, JobIndustry.DoesNotExist):
        return JobIndustry.objects.filter(name__iexact=industry.strip()).first()


def resolve_subcategory(subcategory):
    if not subcategory:
        return None
    try:
        return JobSubCategory.objects.get(id=int(subcategory))
    except (ValueError, JobSubCategory.DoesNotExist):
        return JobSubCategory.objects.filter(name__iexact=subcategory.strip()).first()


# ================================================================
# General Jobs
# ================================================================


# ==============================
# 📌 Save/Bookmark Jobs Endpoints
# ==============================
@core_router.post("/save-job/add/", tags=["Saved Jobs"])
def save_job_enhanced(request, payload: SaveJobRequestSchema):
    try:
        user = User.objects.get(id=payload.user_id)
    except User.DoesNotExist:
        return {"error": "User not found."}
    try:
        job = Job.objects.get(id=payload.job_id)
    except Job.DoesNotExist:
        return {"error": "Job not found."}

    saved_job, created = SavedJob.objects.get_or_create(user=user, job=job)
    return {"saved": True, "created": created}


@core_router.delete("/unsave-job/", tags=["Saved Jobs"])
def unsave_job(request, payload: UnsaveJobRequestSchema):
    """Removes a job from the saved list based on user_id and job_id."""

    try:
        user = User.objects.get(id=payload.user_id)
    except User.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)
    job = get_object_or_404(Job, id=payload.job_id)

    saved_record = SavedJob.objects.filter(user=user, job=job).first()

    if saved_record:
        saved_record.delete()
        return JsonResponse({"message": "Job unsaved successfully"}, status=200)

    return JsonResponse({"error": "Job not found in your saved list"}, status=404)


@core_router.get("/saved-jobs/{user_id}", tags=["Saved Jobs"])
def user_saved_jobs(request, user_id: int):
    """Lists all saved jobs for the authenticated user."""

    # Optimize query with select_related() and only()
    saved_jobs = (
        SavedJob.objects.select_related("job__industry")
        .filter(user_id=user_id)
        .only(
            "id",
            "saved_at",
            "job__id",
            "job__title",
            "job__status",
            "job__industry__name",
        )
    )

    # Use list comprehension for efficient serialization
    saved_jobs_list = [
        {
            "saved_job_id": record.id,
            "saved_at": record.saved_at.strftime("%Y-%m-%d %H:%M:%S"),
            "job": {
                "id": record.job.id,
                "title": record.job.title,
                "industry": record.job.industry.name if record.job.industry else None,
                "status": record.job.status,
            },
        }
        for record in saved_jobs
    ]

    return JsonResponse({"saved_jobs": saved_jobs_list}, status=200)


@core_router.get("/saved-jobs/{job_id}", tags=["Saved Jobs"])
def saved_job_detail(request, job_id: int):
    """
    GET /jobs/saved-jobs/{job_id}
    Retrieves details of a specific saved job for the authenticated user.

    Parameters:
    - job_id: int (path parameter) - ID of the saved job to retrieve

    Returns:
    - 200: Saved job details
    - 403: If user not authenticated
    - 404: If saved job not found
    """
    # Authenticate user
    session_user_id = request.session.get("user_id")
    if session_user_id:
        user = get_object_or_404(User, id=session_user_id)
    elif request.user.is_authenticated:
        user = request.user
    else:
        return JsonResponse({"error": "User not authenticated"}, status=403)

    # Get the saved job record
    try:
        saved_record = SavedJob.objects.get(user=user, job_id=job_id)
    except SavedJob.DoesNotExist:
        return JsonResponse({"error": "Saved job not found"}, status=404)

    # Serialize the response
    response_data = {
        "saved_job_id": saved_record.id,
        "saved_at": saved_record.saved_at.strftime("%Y-%m-%d %H:%M:%S"),
        "job": {
            "id": saved_record.job.id,
            "title": saved_record.job.title,
            "description": saved_record.job.description,
            "industry": (
                saved_record.job.industry.name if saved_record.job.industry else None
            ),
            "subcategory": (
                saved_record.job.subcategory.name
                if saved_record.job.subcategory
                else None
            ),
            "status": saved_record.job.status,
            "date": (
                saved_record.job.date.isoformat() if saved_record.job.date else None
            ),
            "start_time": (
                saved_record.job.start_time.isoformat()
                if saved_record.job.start_time
                else None
            ),
            "end_time": (
                saved_record.job.end_time.isoformat()
                if saved_record.job.end_time
                else None
            ),
            "location": saved_record.job.location,
            "rate": str(saved_record.job.rate),
        },
    }

    return JsonResponse(response_data, status=200)


@core_router.post(
    "/jobs/{job_id}/update-location", auth=ClientAuth(), tags=["Job Management"]
)
def update_job_location(
    request, job_id: int, data: LocationUpdateSchema
) -> JsonResponse:
    """
    Update job location with coordinates and optional address.

    Parameters:
    - job_id: ID of the job to update
    - data: LocationUpdateSchema containing latitude, longitude, and optional location string

    Returns:
    - JSON response with success or error message
    """
    try:
        job = get_object_or_404(Job, id=job_id)

        # Permission check (adjust if `created_by` is the actual field)
        if job.client != request.user:
            return JsonResponse({"error": "Permission denied"}, status=403)

        # Update coordinates
        job.latitude = data.latitude
        job.longitude = data.longitude

        # Optionally update human-readable address
        if data.location:
            job.location = data.location

        job.save()

        return JsonResponse({"message": "Location updated successfully"}, status=200)

    except Exception as e:
        logger.exception(f"Failed to update job location: {e}")
        return JsonResponse({"error": "Internal server error"}, status=500)


@core_router.put("/edit-ob/{job_id}", tags=["Job Management"])
def edit_job(request, job_id: int, payload: JobUpdateSchema):
    """
    Update an existing job posting.
    Only the job creator can edit their job, and only if it hasn't started or completed.
    """
    # Authentication check
    if not request.user.is_authenticated:
        return {"error": "Authentication required"}, 401

    # Get job or return 404
    job = get_object_or_404(Job, id=job_id)

    # Authorization check - only job creator can edit
    if job.client != request.user:
        return {"error": "Only the job creator can edit this job"}, 403

    # Business logic validation
    if job.status in [Job.Status.COMPLETED, Job.Status.CANCELED, Job.Status.ONGOING]:
        return {
            "error": f"Job cannot be edited",
            "details": f"Job is {job.status} and cannot be modified",
        }, 400

    try:
        with transaction.atomic():
            # Update basic fields if provided
            if payload.title is not None:
                job.title = payload.title
            if payload.description is not None:
                job.description = payload.description
            if payload.applicants_needed is not None:
                job.applicants_needed = payload.applicants_needed
            if payload.job_type is not None:
                job.job_type = payload.job_type
            if payload.shift_type is not None:
                job.shift_type = payload.shift_type
            if payload.rate is not None:
                job.rate = payload.rate
            if payload.location is not None:
                job.location = payload.location
            if payload.is_active is not None:
                job.is_active = payload.is_active

            # Handle date and time fields
            if payload.date is not None:
                job.date = payload.date
            if payload.start_time is not None:
                try:
                    job.start_time = datetime.strptime(
                        payload.start_time, "%H:%M"
                    ).time()
                except ValueError:
                    return {"error": "Invalid start time format. Use HH:MM"}, 400
            if payload.end_time is not None:
                try:
                    job.end_time = datetime.strptime(payload.end_time, "%H:%M").time()
                except ValueError:
                    return {"error": "Invalid end time format. Use HH:MM"}, 400

            # Validate time range
            if job.start_time and job.end_time and job.end_time <= job.start_time:
                return {"error": "End time must be later than start time"}, 400

            # Handle relationships
            if payload.industry_id is not None:
                try:
                    job.industry = JobIndustry.objects.get(id=payload.industry_id)
                except JobIndustry.DoesNotExist:
                    return {
                        "error": f"Industry with ID {payload.industry_id} not found"
                    }, 404

            if payload.subcategory_id is not None:
                try:
                    subcategory = JobSubCategory.objects.get(id=payload.subcategory_id)
                    if job.industry and subcategory.industry != job.industry:
                        return {
                            "error": "Subcategory must belong to the selected industry"
                        }, 400
                    job.subcategory = subcategory
                except JobSubCategory.DoesNotExist:
                    return {
                        "error": f"Subcategory with ID {payload.subcategory_id} not found"
                    }, 404

            # Calculate duration
            if job.start_time and job.end_time:
                duration = datetime.combine(job.date, job.end_time) - datetime.combine(
                    job.date, job.start_time
                )
                job.duration_hours = duration.total_seconds() / 3600

            # Save changes
            job.save()

            # Return updated job details
            return {
                "message": "Job updated successfully",
                "job": {
                    "id": job.id,
                    "title": job.title,
                    "description": job.description,
                    "industry": job.industry.name if job.industry else None,
                    "subcategory": job.subcategory.name if job.subcategory else None,
                    "applicants_needed": job.applicants_needed,
                    "job_type": job.job_type,
                    "shift_type": job.shift_type,
                    "date": job.date.isoformat() if job.date else None,
                    "start_time": (
                        job.start_time.strftime("%H:%M") if job.start_time else None
                    ),
                    "end_time": (
                        job.end_time.strftime("%H:%M") if job.end_time else None
                    ),
                    "rate": str(job.rate),
                    "location": job.location,
                    "status": job.status,
                    "is_active": job.is_active,
                    "duration_hours": (
                        round(job.duration_hours, 2) if job.duration_hours else None
                    ),
                    "updated_at": (
                        job.updated_at.isoformat() if job.updated_at else None
                    ),
                },
            }, 200

    except Exception as e:
        return {"error": f"Failed to update job: {str(e)}"}, 500


# ==============================
# 📌 Utility Functions
# ==============================
def user_profile_pic_path(instance, filename):
    """Generates unique upload path for profile pictures"""
    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(
        "profile_pics", f"user_{instance.user.id}", f"{timestamp}_{filename}"
    )


# ==============================
# 📌 Auth Endpoints
# ==============================
@accounts_router.post("/change-password", tags=["Auth"])
def change_password(request, data: PasswordResetSchema):
    """Reset user password after verifying old password"""
    try:
        user = User.objects.get(pk=data.user_id)

        if not user.check_password(data.old_password):
            return JsonResponse({"error": "Old password is incorrect"}, status=400)

        user.set_password(data.new_password)
        user.save()
        return JsonResponse({"message": "Password reset successfully"}, status=200)

    except User.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": f"Something went wrong: {str(e)}"}, status=500)


@accounts_router.post("/request-password", tags=["Auth"])
def email_request_password(request, payload: PasswordResetRequestSchema):
    """Initiate password reset process with email"""
    try:
        user = User.objects.get(email=payload.email)
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        reset_link = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}/"

        send_mail(
            subject="Password Reset Request",
            message=f"Click to reset your password: {reset_link}\n"
            f"Link expires in {settings.PASSWORD_RESET_TIMEOUT//3600} hours.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[payload.email],
            fail_silently=False,
        )

        return {
            "message": "Password reset link sent to your email",
            "email": payload.email,
        }

    except User.DoesNotExist:
        return {
            "message": "If an account exists with this email, a reset link has been sent"
        }


@accounts_router.get("/whoami/{user_id}", tags=["Auth"])
def whoami(request, user_id: int):
    """Get user details and activity stats"""
    user = get_object_or_404(User, id=user_id)
    return get_user_response(user)


@accounts_router.post("/signup", tags=["Auth"])
def signup_view(request, payload: SignupSchema):
    """Create new user and profile"""
    try:
        user = User.objects.create_user(
            username=payload.email,
            email=payload.email,
            password=payload.password,
            first_name=payload.first_name,
            last_name=payload.last_name,
        )
        user.backend = get_backends()[0].__class__.__name__
        login(request, user)
        return JsonResponse({"message": "success"}, status=200)

    except IntegrityError:
        return JsonResponse({"error": "Email already exists"}, status=400)
    except Exception as e:
        return JsonResponse({"error": f"Unexpected error: {str(e)}"}, status=500)


@accounts_router.post("/login", tags=["Auth"])
def login_view(request, payload: LoginSchema):
    """Authenticate user and return JWT tokens"""
    user = authenticate(request, username=payload.email, password=payload.password)
    if not user:
        return JsonResponse({"error": "Invalid credentials"}, status=401)

    login(request, user)
    refresh = RefreshToken.for_user(user)
    request.session["user_id"] = user.id
    request.session.modified = True

    profile, _ = Profile.objects.get_or_create(user=user)
    return JsonResponse(
        {
            "message": "Login successful",
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "user_id": user.id,
            "role": profile.role,
        },
        status=200,
    )


@accounts_router.post("/logout", tags=["Auth"])
def logout_view(request: HttpRequest):
    """Log out current user"""
    logout(request)
    request.session.flush()
    return JsonResponse({"message": "Logged out successfully"}, status=200)


@accounts_router.put("/profile")
def update_profile(request, data: UserProfileUpdateSchema):
    """Update user profile information"""
    try:
        user = User.objects.get(pk=data.user_id)
    except User.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)

    # Update basic info
    if data.first_name:
        user.first_name = data.first_name
    if data.last_name:
        user.last_name = data.last_name

    # Handle email update
    if data.email and data.email != user.email:
        if User.objects.filter(username=data.email).exclude(pk=user.pk).exists():
            return JsonResponse({"error": "Email already in use"}, status=400)
        user.email = user.username = data.email

    # Handle profile picture
    if data.profile_pic:
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.profile_pic = data.profile_pic
        profile.save()

    user.save()
    return {"message": "Profile updated successfully"}

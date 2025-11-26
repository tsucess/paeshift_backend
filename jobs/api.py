# ==
# 📌 Python Standard Library Imports
# ==
import json
import logging
import os
import time as time_module  # Rename the time module import to avoid conflict
import uuid
from datetime import date, datetime as datetime_date, time as datetime_time, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple

# ==
# 📌 Django Core Imports
# ==
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import transaction
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from geopy.exc import GeocoderServiceError, GeocoderTimedOut, GeocoderUnavailable
from geopy.geocoders import Nominatim
from ninja import Router, Query

from accounts.models import CustomUser
from rating.models import Review
from userlocation.models import UserLocation

from .applicant import applicant_router
from .client import client_router
from .models import Job, JobIndustry, JobSubCategory, User, SavedJob, Application
from .schemas import (
    JobDetailSchema, JobCancellationSuccessSchema, ErrorResponseSchema, IndustrySchema, SubCategorySchema,
    SaveJobRequestSchema, UnsaveJobRequestSchema, LocationUpdateSchema, GeocodeResponse, GeocodeRequest,
    CreateJobSchema, EditJobSchema, MarkArrivedSchema, JobPaymentDetailSchema, GetJobsRequestSchema
)
from .tasks import *
from .utils import fetch_all_users, serialize_job, resolve_industry, resolve_subcategory

# Import error handling and logging utilities
from core.exceptions import (
    ResourceNotFoundError,
    InternalServerError,
    ValidationError as PaeshiftValidationError,
    AuthenticationError,
    AuthorizationError,
)

# Import caching utilities for Phase 2.2c
from core.cache_utils import (
    cache_api_response,
    invalidate_cache,
    CACHE_TTL_JOBS,
)
from core.logging_utils import log_endpoint, logger as core_logger, api_logger

logger = logging.getLogger(__name__)
core_router = Router(tags=["Core"])

from core.cache import invalidate_cache_pattern

# ==
# 📌 Custom Classes
# ==

class Point:
    def __init__(self, longitude, latitude):
        self.x = longitude
        self.y = latitude


# ==
# 📌 Helper Functions
# ==


def authenticated_user_or_error(request, message="You must be logged in"):
    """Check if user is authenticated, return user or error response"""

    if not request.user.is_authenticated:
        return None, JsonResponse({"error": message}, status=401)

    return request.user, None  # Always return a tuple


def fetch_all_users():
    """Fetch all users from the database"""
    return list(
        User.objects.all().values(
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "date_joined",
            "role"
        )
    )


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


def sort_jobs_recent_first(jobs):
    """
    Sort jobs so that those posted today or in the last 2 days appear first, then others by date descending.
    """
    today = date.today()
    recent_days = today - timedelta(days=2)
    def job_sort_key(job):
        job_start_date = getattr(job, 'start_date', None)
        if not job_start_date:
            return (2, None)  # Put jobs with no date at the end
        if job_start_date == today:
            return (0, job_start_date)
        if job_start_date >= recent_days:
            return (1, job_start_date)
        return (2, job_start_date)
    return sorted(jobs, key=job_sort_key)

# ==
# 📌 Core Endpoints
# ==

@core_router.get("/all-users", tags=["Job"], response={200: dict})
def get_all_users_view(request):
    # Use the correct fetch_all_users from jobs/utils.py, which includes profile_pic_url
    from .utils import fetch_all_users
    users = fetch_all_users()
    return {"users": users}



@log_endpoint(core_logger)
@core_router.get("/alljobs", tags=["Jobs"], response={200: dict})
def get_jobs(request, page: int = Query(1, gt=0), page_size: int = Query(20, gt=0, le=100)):
    """
    Get all jobs with their details.
    Fetches directly from the database without Redis caching.
    """
    try:
        from jobs.models import Job  # Make sure you import your Job model
        # from jobs.serializers import serialize_job  # Adjust to your actual import
        from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage

        # Fetch jobs with related fields for efficiency
        jobs = Job.objects.select_related(
            "client__profile",
            "industry",
            "subcategory"
        ).prefetch_related("applications").all().order_by("-date")

        user_id = request.user.id if hasattr(request, "user") and request.user and request.user.is_authenticated else None

        # Apply pagination
        paginator = Paginator(jobs, page_size)
        try:
            jobs_page = paginator.page(page)
        except PageNotAnInteger:
            jobs_page = paginator.page(1)
        except EmptyPage:
            jobs_page = paginator.page(paginator.num_pages)

        # Log the request
        core_logger.info(
            "Jobs list retrieved",
            page=page,
            page_size=page_size,
            total_jobs=paginator.count,
            user_id=user_id
        )

        # Serialize results
        serialized = [serialize_job(job, include_extra=True, user_id=user_id) for job in jobs_page]

        return {
            "status": "success",
            "message": f"{paginator.count} jobs available in database",
            "jobs": serialized,
            "pagination": {
                "current_page": page,
                "total_pages": paginator.num_pages,
                "total_items": paginator.count,
                "items_per_page": page_size,
                "has_next": jobs_page.has_next(),
                "has_previous": jobs_page.has_previous()
            }
        }

    except Exception as e:
        import logging
        logger = logging.getLogger("ninja")  # fallback logger
        logger.error(f"Failed to fetch jobs: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": f"Error fetching jobs: {str(e)}"
        }
        



@core_router.get("/alljobsmatched", tags=["Jobs"], response={200: dict})
def get_jobs_filtered_for_user(request, query: Query[GetJobsRequestSchema], page: int = Query(1, gt=0), page_size: int = Query(20, gt=0, le=100)):
    from jobs.matching import get_applicant_matches
    from jobs.models import Job

    user_id = query.user_id

    try:
        if user_id:
            user_id = int(user_id)

            # Get matched jobs
            matches = get_applicant_matches(user_id, limit=50)

            # Only keep matched jobs with payment_status="paid"
            filtered = [
                m for m in matches
                if Job.objects.filter(id=m["job_id"], payment_status="paid").exists()
            ]

            matched_job_ids = {m["job_id"] for m in filtered}

            if not filtered:
                # No matched jobs → return ALL paid jobs with pagination
                from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage

                jobs = Job.objects.filter(payment_status="paid")
                jobs = sort_jobs_recent_first(jobs)

                paginator = Paginator(jobs, page_size)
                try:
                    jobs_page = paginator.page(page)
                except PageNotAnInteger:
                    jobs_page = paginator.page(1)
                except EmptyPage:
                    jobs_page = paginator.page(paginator.num_pages)

                jobs_list = [serialize_job(job, user_id=user_id) for job in jobs_page]

                return {
                    "status": "success",
                    "message": f"No matched jobs for user {user_id}. Showing all PAID jobs.",
                    "jobs": jobs_list,
                    "other_jobs_list": [],
                    "pagination": {
                        "current_page": page,
                        "total_pages": paginator.num_pages,
                        "total_items": paginator.count,
                        "items_per_page": page_size,
                        "has_next": jobs_page.has_next(),
                        "has_previous": jobs_page.has_previous()
                    }
                }

            else:
                # Return matched + other paid jobs with pagination
                from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage

                matched_jobs = Job.objects.filter(id__in=matched_job_ids, payment_status="paid")
                matched_jobs = sort_jobs_recent_first(matched_jobs)

                # Exclude matched IDs to get other paid jobs
                other_jobs = Job.objects.filter(payment_status="paid").exclude(id__in=matched_job_ids)
                other_jobs = sort_jobs_recent_first(other_jobs)

                # Combine matched jobs first, then other jobs
                all_jobs = list(matched_jobs) + list(other_jobs)

                paginator = Paginator(all_jobs, page_size)
                try:
                    jobs_page = paginator.page(page)
                except PageNotAnInteger:
                    jobs_page = paginator.page(1)
                except EmptyPage:
                    jobs_page = paginator.page(paginator.num_pages)

                jobs_list = [serialize_job(job, user_id=user_id) for job in jobs_page]

                # Sort so jobs with has_applied=True appear first within the page
                jobs_list.sort(key=lambda x: not x.get("has_applied", False))

                return {
                    "status": "success",
                    "message": f"{len(filtered)} matched PAID jobs fetched for user {user_id}, "
                               f"plus {len(other_jobs)} other PAID jobs.",
                    "jobs": jobs_list,
                    "other_jobs_list": [],  # No longer needed as we combine them
                    "pagination": {
                        "current_page": page,
                        "total_pages": paginator.num_pages,
                        "total_items": paginator.count,
                        "items_per_page": page_size,
                        "has_next": jobs_page.has_next(),
                        "has_previous": jobs_page.has_previous(),
                        "matched_jobs_count": len(matched_jobs),
                        "other_jobs_count": len(other_jobs)
                    }
                }

        # No user_id provided → return ALL paid jobs with pagination
        from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage

        jobs = Job.objects.filter(payment_status="paid")
        jobs = sort_jobs_recent_first(jobs)

        paginator = Paginator(jobs, page_size)
        try:
            jobs_page = paginator.page(page)
        except PageNotAnInteger:
            jobs_page = paginator.page(1)
        except EmptyPage:
            jobs_page = paginator.page(paginator.num_pages)

        jobs_list = [serialize_job(job) for job in jobs_page]

        return {
            "status": "success",
            "message": f"{paginator.count} PAID jobs available (no user_id provided).",
            "jobs": jobs_list,
            "other_jobs_list": [],
            "pagination": {
                "current_page": page,
                "total_pages": paginator.num_pages,
                "total_items": paginator.count,
                "items_per_page": page_size,
                "has_next": jobs_page.has_next(),
                "has_previous": jobs_page.has_previous()
            }
        }

    except Exception as e:
        logger = logging.getLogger("ninja")
        logger.error(f"Failed to fetch matched jobs: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": f"Error fetching matched jobs: {str(e)}"
        }
   

# Import Redis decorators
from core.redis_decorators import time_view, track_user_activity

# ==
# 📌 Job Endpoints
# ==
@log_endpoint(core_logger)
@cache_api_response(timeout=CACHE_TTL_JOBS, prefix='job:detail')
@core_router.get("/{job_id}", response=JobDetailSchema, tags=["Jobs"])
@track_user_activity("view_job_detail")
def job_detail(request, job_id: int):
    """
    GET /jobs/<job_id> - Returns details for a single job

    This endpoint uses Redis caching to improve performance.
    """
    try:
        # Get the job with optimized related fields
        job = get_object_or_404(
            Job.objects.select_related(
                'client__profile',
                'industry',
                'subcategory',
                'created_by__profile'
            ).prefetch_related('applications'),
            id=job_id
        )

        user_id = request.user.id if hasattr(request, "user") and request.user and request.user.is_authenticated else None

        # Log job view
        core_logger.info(
            "Job details retrieved",
            job_id=job_id,
            user_id=user_id
        )

        # Serialize the job
        serialized_job = serialize_job(job, include_extra=True, user_id=user_id)

        return serialized_job
    except Http404:
        core_logger.warning(f"Job not found: job_id={job_id}")
        raise ResourceNotFoundError("Job", job_id)
    except Exception as e:
        core_logger.error(f"Error getting job details for job_id={job_id}: {str(e)}", exc_info=True)
        raise InternalServerError("Failed to retrieve job details")





@log_endpoint(core_logger)
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
    try:
        # Authentication check
        if not request.user.is_authenticated:
            raise AuthenticationError("Authentication required to cancel jobs")

        # Get job or return 404
        try:
            job = Job.objects.get(id=job_id)
        except Job.DoesNotExist:
            raise ResourceNotFoundError("Job", job_id)

        # Authorization check - only job creator can cancel
        if job.client != request.user:
            raise AuthorizationError("Only the job creator can cancel this job")

        # Business logic validation
        if job.status in [JobStatusEnum.COMPLETED, JobStatusEnum.CANCELLED]:
            raise PaeshiftValidationError(
                f"Job cannot be canceled. Job is already {job.status}",
                {"status": job.status}
            )

        if job.status == JobStatusEnum.ONGOING:
            raise PaeshiftValidationError(
                "Job is currently ongoing and cannot be canceled",
                {"status": job.status}
            )

        # Update job status
        job.status = JobStatusEnum.CANCELLED
        job.save()

        # Log job cancellation
        core_logger.info(
            "Job canceled successfully",
            job_id=job.id,
            client_id=job.client.id,
            title=job.title
        )

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
    except (AuthenticationError, ResourceNotFoundError, AuthorizationError, PaeshiftValidationError):
        raise
    except Exception as e:
        core_logger.error(f"Error canceling job: {str(e)}", exc_info=True)
        raise InternalServerError("Failed to cancel job")



@log_endpoint(core_logger)
@core_router.delete(
    "/job/delete/{job_id}",
    summary="Delete a Job",
    tags=["Job Management"],
    response={200: dict, 404: dict}
)
def delete_job(request, job_id: int):
    """
    Deletes a job by its ID.

    This endpoint ensures proper cache invalidation when a job is deleted.
    The job's cache entries are automatically invalidated by the Job model's delete method,
    which uses the RedisCachedModelMixin and RedisSyncMixin.

    Additionally, the client jobs cache is invalidated to ensure that the client jobs
    endpoint returns the most up-to-date data.
    """
    try:
        # Fetch job or return 404
        try:
            job = Job.objects.get(id=job_id)
        except Job.DoesNotExist:
            raise ResourceNotFoundError("Job", job_id)

        # Store client ID for cache invalidation
        client_id = job.client.id if job.client else None

        # Delete the job (triggers post_delete signal)
        job.delete()

        # Invalidate client jobs cache if needed
        if client_id:
            invalidate_cache_pattern(f"clientjobs:u:{client_id}:*")
            core_logger.info(f"Invalidated client jobs cache for client {client_id} after job deletion")

        # Log successful deletion
        core_logger.info(
            "Job deleted successfully",
            job_id=job_id,
            client_id=client_id
        )

        return {"message": f"Job {job_id} deleted successfully"}

    except ResourceNotFoundError:
        raise
    except Exception as e:
        core_logger.error(f"Error deleting job {job_id}: {str(e)}", exc_info=True)
        raise InternalServerError("Failed to delete job")




# @core_router.delete(
#     "/job/delete/{job_id}", summary="Delete a Job", tags=["Job Management"], response={200: dict}
# )
# def delete_job(request, job_id: int):
#     """
#     Deletes a job by its ID.

#     This endpoint ensures proper cache invalidation when a job is deleted.
#     The job's cache entries are automatically invalidated by the Job model's delete method,
#     which uses the RedisCachedModelMixin and RedisSyncMixin.

#     Additionally, the client jobs cache is invalidated to ensure that the client jobs
#     endpoint returns the most up-to-date data.
#     """
#     # Get the job
#     # Store client ID for cache invalidation
#     client_id = job.client.id if job.client else None

#     # Delete the job (this will trigger the post_delete signal handler)
#     job.delete()

#     # Additional cache invalidation for client jobs
#     if client_id:
#         from core.cache import invalidate_cache_pattern
#         invalidate_cache_pattern(f"clientjobs:u:{client_id}:*")
#         logger.info(f"Invalidated client jobs cache for client {client_id} after job deletion")

#     return {"message": "Job deleted successfully"}


# --- GET: Job Industries ---
@core_router.get("/job-industries/", response=list[IndustrySchema], tags=["Jobs"])
def get_job_industries(request):
    """
    Get all job industries.

    This endpoint uses Redis caching to improve performance.
    The response is automatically cached by the cache_api_response decorator.
    """
    logger.debug("Cache miss for job industries, fetching from database")
    industries = JobIndustry.objects.all()

    # Cache each industry individually if the cache method exists
    for industry in industries:
        if hasattr(industry, 'cache'):
            try:
                industry.cache()
            except Exception as e:
                logger.warning(f"Failed to cache industry {industry.id}: {str(e)}")

    return list(industries)


# --- GET: Job Subcategories with Industry ---
@core_router.get("/job-subcategories/", response=list[SubCategorySchema], tags=["Jobs"])
def get_job_subcategories(request):
    """
    Get all job subcategories with their industries.

    This endpoint uses Redis caching to improve performance.
    The response is automatically cached by the cache_api_response decorator.
    """
    logger.debug("Cache miss for job subcategories, fetching from database")
    subcategories = JobSubCategory.objects.select_related("industry").all()

    # Cache each subcategory individually if the cache method exists
    for subcategory in subcategories:
        if hasattr(subcategory, 'cache'):
            try:
                subcategory.cache()
            except Exception as e:
                logger.warning(f"Failed to cache subcategory {subcategory.id}: {str(e)}")

    return list(subcategories)





from django.db.models import Q

@core_router.get("/application/status/{job_id}/{user_id}/", response={200: dict, 404: dict})
def get_application_status_by_job_and_user(request, job_id: int, user_id: int):
    """
    Retrieve application status based on job and user ID (either client or applicant).
    Returns a friendly message if no application exists.
    """
    application = (
        Application.objects
        .filter(job_id=job_id)
        .filter(Q(applicant_id=user_id) | Q(job__client_id=user_id))
        .order_by("-created_at")
        .first()  # safer than latest(), avoids DoesNotExist error
    )

    if not application:
        return 200, {
            "message": "No application yet.",
            "application_status": None,
            "job_id": job_id,
            "user_id": user_id,
        }

    return 200, {
        "application_id": application.id,
        "client_id": application.job.client_id,
        "applicant_id": application.applicant_id,
        "job_id": application.job_id,
        "application_status": application.status,
    }



# @core_router.get("/application/status/{job_id}/{user_id}/", response={200: dict, 404: dict})
# def get_application_status_by_job_and_user(request, job_id: int, user_id: int):
  
  
#     """
#     Retrieve application status based on job and user ID (either client or applicant).
#     """
#     try:
#         application = (
#             Application.objects
#             .filter(job_id=job_id)
#             .filter(Q(applicant_id=user_id) | Q(job__client_id=user_id))
#             .latest("created_at")  # Or use `.first()` if not ordering
#         )
#     except Application.DoesNotExist:
#         return 404, {"error": "Application not found."}

#     return {
#         "application_id": application.id,
#         "client_id": application.job.client_id,
#         "applicant_id": application.applicant_id,
#         "job_id": application.job_id,
#         "application_status": application.status,
#     }


# --- Helpers ---

# =
# General Jobs
# =


# ==
# 📌 Save/Bookmark Jobs Endpoints
# ==
@core_router.post("/save-job/add/", tags=["Saved Jobs"], response={200: dict, 404: dict})
def save_job_enhanced(request, payload: SaveJobRequestSchema):
    """
    Save a job for a user.

    This endpoint uses the RedisSyncMixin on the SavedJob model to automatically
    sync the saved job between the database and Redis.
    """
    try:
        user = User.objects.get(id=payload.user_id)
    except User.DoesNotExist:
        return {"error": "User not found."}
    try:
        job = Job.objects.get(id=payload.job_id)
    except Job.DoesNotExist:
        return {"error": "Job not found."}

    # Create the saved job (will automatically sync to Redis via RedisSyncMixin)
    saved_job, created = SavedJob.objects.get_or_create(user=user, job=job)

    # Invalidate the user's saved jobs list cache
    from core.cache import delete_cached_data
    cache_key = f"saved_jobs:user:{user.id}"
    delete_cached_data(cache_key)

    logger.info(f"User {user.id} saved job {job.id} (created={created})")

    return {"saved": True, "created": created, "saved_job_id": saved_job.id}


@core_router.delete("/unsave-job/", tags=["Saved Jobs"], response={200: dict, 404: dict})
def unsave_job(request, payload: UnsaveJobRequestSchema):
    """
    Removes a job from the saved list based on user_id and job_id.

    This endpoint uses the RedisSyncMixin on the SavedJob model to automatically
    sync the saved job between the database and Redis.
    """
    try:
        user = User.objects.get(id=payload.user_id)
    except User.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)
    job = get_object_or_404(Job, id=payload.job_id)

    saved_record = SavedJob.objects.filter(user=user, job=job).first()

    if saved_record:
        # Delete the saved job (will automatically invalidate Redis cache via RedisSyncMixin)
        saved_record.delete()

        # Invalidate the user's saved jobs list cache
        from core.cache import delete_cached_data
        cache_key = f"saved_jobs:user:{user.id}"
        delete_cached_data(cache_key)

        logger.info(f"User {user.id} unsaved job {job.id}")

        return JsonResponse({"message": "Job unsaved successfully"}, status=200)

    return JsonResponse({"error": "Job not found in your saved list"}, status=404)


@core_router.get("/saved-jobs/{user_id}", tags=["Saved Jobs"], response={200: dict})
def user_saved_jobs(request, user_id: int):
    """
    Lists all saved jobs for the authenticated user.

    This endpoint uses Redis caching to improve performance.
    The saved jobs are automatically synced between the database and Redis
    using the RedisSyncMixin on the SavedJob model.
    """
    # Import Redis caching utilities
    from core.cache import get_cached_data, set_cached_data

    # Generate cache key
    cache_key = f"saved_jobs:user:{user_id}"

    # Try to get from cache first
    cached_data = get_cached_data(cache_key)
    if cached_data:
        logger.debug(f"Cache hit for saved jobs user_id={user_id}")
        return JsonResponse({"saved_jobs": cached_data}, status=200)

    # Cache miss, get from database
    logger.debug(f"Cache miss for saved jobs user_id={user_id}")

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

    # Cache the response (30 minutes timeout)
    set_cached_data(cache_key, saved_jobs_list, 60 * 30)

    return JsonResponse({"saved_jobs": saved_jobs_list}, status=200)


@core_router.get("/saved-jobs/{job_id}", tags=["Saved Jobs"], response={200: dict, 403: dict, 404: dict})
def saved_job_detail(request, job_id: int):
    """
    GET /jobs/saved-jobs/{job_id}
    Retrieves details of a specific saved job for the authenticated user.

    Parameters:
    - job_id: int (path parameter) - ID of the saved job to retrieve

    Returns:
    - 200: Saved job details
    - 403: If user not authenticated

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
            "start_date": (
                saved_record.job.start_date.isoformat() if saved_record.job.start_date else None
            ),
            "end_date": (
                saved_record.job.end_date.isoformat() if saved_record.job.end_date else None
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


@core_router.get("/jobs/{job_id}/location", tags=["Job Management"], response={200: dict, 404: dict, 500: dict})
def get_job_location(request, job_id: int):
    """
    Get the location details for a specific job.

    This endpoint provides the job's location coordinates and address information.
    It also indicates whether the current user can update the location (only clients can).

    Parameters:
        job_id: ID of the job to get location for

    Returns:
        JSON with location details and permissions
    """
    try:
        job = get_object_or_404(Job, id=job_id)

        # Check if user is authenticated and is the job's client
        can_update = False
        if request.user.is_authenticated:
            # Check if user has a profile with role information
            if hasattr(request.user, 'profile') and hasattr(request.user.profile, 'role'):
                role = request.user.profile.role
                is_client = role == "client" or (hasattr(role, 'role_name') and role.role_name.lower() == "client")
            # Fallback to user's role field if profile doesn't exist
            elif hasattr(request.user, 'role'):
                is_client = request.user.role == "client"
            else:
                is_client = False

            # Only the job's client can update the location
            can_update = is_client and job.client == request.user

        # Format the response
        response = {
            "job_id": job.id,
            "title": job.title,
            "location": {
                "address": job.location,
                "latitude": float(job.latitude) if job.latitude is not None else None,
                "longitude": float(job.longitude) if job.longitude is not None else None,
                "last_updated": job.last_location_update.isoformat() if job.last_location_update else None
            },
            "permissions": {
                "can_update_location": can_update,
                "is_client": can_update,  # If can update, must be client
                "is_job_owner": request.user.is_authenticated and job.client == request.user
            }
        }

        return JsonResponse(response, status=200)

    except Job.DoesNotExist:
        return JsonResponse({"error": "Job not found"}, status=404)
    except Exception as e:
        logger.exception(f"Error retrieving job location: {e}")
        return JsonResponse({"error": "Internal server error"}, status=500)


@core_router.put(
    "/jobs/{job_id}/update-location", tags=["Job Management"], response={200: dict, 403: dict, 500: dict}
)
def update_job_location(
    request, job_id: int, data: LocationUpdateSchema
):
    """
    Update job location with coordinates and optional address.

    Only clients can update job locations. The marker is draggable only for clients.

    Parameters:
    - job_id: ID of the job to update
    - data: LocationUpdateSchema containing latitude, longitude, and optional location string

    Returns:
    - JSON response with success or error message and updated coordinates
    """
    try:
        job = get_object_or_404(Job, id=job_id)

        # Permission check - only clients can update job locations
        if job.client != request.user:
            return JsonResponse({
                "error": "Permission denied",
                "detail": "Only the job creator can update the job location"
            }, status=403)

        # Store previous coordinates for response
        previous_coords = {
            "latitude": float(job.latitude) if job.latitude is not None else None,
            "longitude": float(job.longitude) if job.longitude is not None else None,
            "location": job.location
        }

        # Update coordinates
        job.latitude = data.latitude
        job.longitude = data.longitude

        # Optionally update human-readable address
        if data.location:
            job.location = data.location

        # Update last_location_update timestamp
        job.last_location_update = timezone.now()
        job.save()

        # Prepare success response with previous and new coordinates
        return JsonResponse({
            "message": "Location updated successfully",
            "previous_coordinates": previous_coords,
            "new_coordinates": {
                "latitude": float(job.latitude),
                "longitude": float(job.longitude),
                "location": job.location
            }
        }, status=200)

    except Exception as e:
        logger.exception(f"Failed to update job location: {e}")
        return JsonResponse({"error": "Internal server error"}, status=500)


@core_router.get("/check-user-role/", tags=["User"], response={200: dict, 401: dict})
def check_user_role(request):
    """
    Check if the authenticated user is a client or applicant.

    This endpoint is used by the frontend to determine if the job location marker
    should be draggable (only for clients) or static (for applicants).

    Returns:
        - 200: JSON with user role information
        - 401: Error if user is not authenticated
    """
    if not request.user.is_authenticated:
        return 401, {"error": "Authentication required"}

    # Get user profile to determine role
    try:
        # Check if user has a profile with role information
        if hasattr(request.user, 'profile') and hasattr(request.user.profile, 'role'):
            role = request.user.profile.role
            is_client = role == "client" or (hasattr(role, 'role_name') and role.role_name.lower() == "client")
        # Fallback to user's role field if profile doesn't exist
        elif hasattr(request.user, 'role'):
            is_client = request.user.role == "client"
        else:
            is_client = False

        return 200, {
            "user_id": request.user.id,
            "username": request.user.username,
            "is_client": is_client,
            "is_applicant": not is_client,
            "can_update_location": is_client,
            "role": str(role) if 'role' in locals() else request.user.role if hasattr(request.user, 'role') else "unknown"
        }
    except Exception as e:
        logger.exception(f"Error checking user role: {e}")
        return 200, {
            "user_id": request.user.id,
            "username": request.user.username,
            "is_client": False,
            "is_applicant": False,
            "can_update_location": False,
            "role": "error",
            "error": str(e)
        }


@core_router.get("/jobs/{job_id}/location-history", tags=["Job Management"], response={200: dict, 404: dict})
def get_job_location_history(request, job_id: int):
    """
    Get the location history for a specific job.

    This endpoint provides a list of location updates for a job, including timestamps.
    It's useful for tracking how a job's location has changed over time.

    Parameters:
        job_id: ID of the job to get location history for

    Returns:
        JSON with location history
    """
    try:
        # Check if job exists
        job = get_object_or_404(Job, id=job_id)

        # Get location history from jobchat app's LocationHistory model
        from jobchat.models import LocationHistory

        # Get the most recent 50 location updates
        location_history = LocationHistory.objects.filter(job_id=job_id).order_by('-timestamp')[:50]

        # Format the response
        history_data = []
        for entry in location_history:
            history_data.append({
                "latitude": float(entry.latitude),
                "longitude": float(entry.longitude),
                "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
                "user_id": entry.user_id,
                "username": entry.user.username if hasattr(entry.user, 'username') else f"User {entry.user_id}"
            })

        return JsonResponse({
            "job_id": job_id,
            "location_history": history_data,
            "count": len(history_data)
        }, status=200)

    except Job.DoesNotExist:
        return JsonResponse({"error": "Job not found"}, status=404)
    except Exception as e:
        logger.exception(f"Error retrieving job location history: {e}")
        return JsonResponse({"error": str(e)}, status=500)


# @core_router.post("/geocode/", response={200: GeocodeResponse}, tags=["Utility"])
# def geocode_api(request, payload: GeocodeRequest):
#     result = get_address_coordinates_helper(payload.address)
#     return result


@core_router.put("/update-payment-status/{job_id}", tags=["Job Management"], response={200: dict, 400: dict, 404: dict})
def update_payment_status(request, job_id: int, data: dict):
    """
    Update the payment status and job status of a job.

    This endpoint is called after a successful payment to update the job's payment status
    and also change the job status from 'pending' to 'upcoming'.

    Args:
        job_id: The ID of the job to update
        data: Dictionary containing payment_status and status fields

    Returns:
        JSON response with success or error message
    """
    try:
        # Get the job
        job = get_object_or_404(Job, id=job_id)

        # Update payment status
        if "payment_status" in data:
            job.payment_status = data["payment_status"]

        # Update job status if provided
        if "status" in data:
            job.status = data["status"]

        # Save the job
        job.save()

        # --- NEW LOGIC: Distribute payment to accepted applicants ---
        from payment.models import Wallet, Transaction
        from django.db import transaction as db_transaction
        from decimal import Decimal
        from django.utils import timezone
        # Only trigger if payment is marked as paid or completed
        if job.payment_status in [Job.PaymentStatus.PAID, Job.PaymentStatus.COMPLETED]:
            accepted_apps = job.applications.filter(status="Accepted")
            num_accepted = accepted_apps.count()
            if num_accepted > 0 and job.total_amount > 0:
                share = (job.total_amount / num_accepted).quantize(Decimal("0.01"))
                for app in accepted_apps:
                    applicant = app.applicant
                    if not applicant:
                        continue
                    try:
                        with db_transaction.atomic():
                            wallet, _ = Wallet.objects.get_or_create(user=applicant)
                            wallet.add_funds(share)
                            # Create transaction record
                            Transaction.objects.create(
                                wallet=wallet,
                                amount=share,
                                transaction_type=Transaction.Type.CREDIT,
                                status=Transaction.Status.COMPLETED,
                                reference=f"job_{job.id}_pay_{applicant.id}_{timezone.now().timestamp()}",
                                description=f"Payment for job '{job.title}' (ID: {job.id})",
                                metadata={"job_id": job.id, "applicant_id": applicant.id}
                            )
                            # Optionally: send notification here
                    except Exception as e:
                        logger.error(f"Failed to credit wallet for applicant {applicant.id}: {e}")

        # Return success response
        return JsonResponse({
            "success": True,
            "message": "Job payment status updated successfully",
            "job_id": job.id,
            "payment_status": job.payment_status,
            "status": job.status
        }, status=200)

    except Job.DoesNotExist:
        return JsonResponse({
            "error": "Job not found",
            "details": f"No job exists with ID {job_id}"
        }, status=404)
    except Exception as e:
        logger.error(f"Error updating job payment status: {str(e)}", exc_info=True)
        return JsonResponse({
            "error": "Server error",
            "message": "An unexpected error occurred while updating the job payment status",
            "details": str(e)
        }, status=400)


@log_endpoint(core_logger)
@core_router.post("/jobs/create-job", tags=["Job Management"], response={201: dict, 400: dict, 404: dict, 500: dict})
def create_job(request, payload: CreateJobSchema):
    """
    Create a new job with enhanced validation and error handling.

    This endpoint accepts job details and creates a new job in the system.
    It supports flexible time formats (HH:MM, HH:MM:SS, etc.) and provides
    detailed validation error messages.

    Args:
        request: The HTTP request
        payload: The job creation payload

    Returns:
        JSON response with job creation result or error details
    """
    try:
        # Import validation utilities
        from .validation import (format_validation_errors, validate_date,
                                 validate_job_times, validate_time)

        # Validate user
        try:
            user = CustomUser.objects.get(id=payload.user_id)
        except CustomUser.DoesNotExist:
            raise ResourceNotFoundError("User", payload.user_id)

        # Validate input data
        validation_errors = {}

        # Validate date
        is_valid_date, job_start_date, date_error = validate_date(payload.start_date)
        if not is_valid_date:
            validation_errors["start_date"] = date_error

        # Validate date
        is_valid_date, job_end_date, date_error = validate_date(payload.end_date)
        if not is_valid_date:
            validation_errors["end_date"] = date_error

        # Validate times
        is_valid_start, start_time, start_error = validate_time(payload.start_time)
        if not is_valid_start:
            validation_errors["start_time"] = start_error

        is_valid_end, end_time, end_error = validate_time(payload.end_time)
        if not is_valid_end:
            validation_errors["end_time"] = end_error

        # Validate time relationship if both times are valid
        if is_valid_start and is_valid_end:
            is_valid_times, times_error = validate_job_times(start_time, end_time)
            if not is_valid_times:
                validation_errors["time_relationship"] = times_error

        # Return validation errors if any
        if validation_errors:
            raise PaeshiftValidationError(format_validation_errors(validation_errors))

        # Create job inside a DB transaction
        with transaction.atomic():
            # Set payment status based on pay_later flag
            payment_status = "pending"
            if hasattr(payload, 'pay_later') and payload.pay_later:
                payment_status = "pending"  # Keep as pending for pay later

            job = Job.objects.create(
                client=user,
                created_by=user,
                title=payload.title,
                industry=resolve_industry(payload.industry),
                subcategory=resolve_subcategory(payload.subcategory),
                applicants_needed=payload.applicants_needed,
                job_type=payload.job_type.value,
                shift_type=payload.shift_type.value,
                start_date=job_start_date,
                end_date=job_end_date,
                start_time=start_time,
                end_time=end_time,
                rate=Decimal(str(payload.rate)),
                location=payload.location.strip(),
                payment_status=payment_status,
                status="pending",
                latitude=None,
                longitude=None,
            )

            # Calculate service fee and total amount
            job.calculate_service_fee_and_total()
            job.save(update_fields=["total_amount", "service_fee"])

            # Dispatch background geocoding job with Django Q
            from django_q.tasks import async_task
            async_task(
                "jobs.tasks.geocode_job",
                job.id,
                hook="jobs.hooks.handle_geocode_result",
            )

            # Calculate duration for response
            duration_hours = job.duration_hours if hasattr(job, "duration_hours") else 0

            # Determine if payment is required immediately
            payment_required = not (hasattr(payload, 'pay_later') and payload.pay_later)

            # Return detailed success response
            return JsonResponse(
                {
                    "success": True,
                    "id": job.id,
                    "title": job.title,
                    "start_date": job.start_date.isoformat(),
                    "end_date": job.end_date.isoformat(),
                    "start_time": job.start_time.strftime("%I:%M %p"),
                    "end_time": job.end_time.strftime("%I:%M %p"),
                    "duration_hours": round(duration_hours, 2),
                    "rate": str(job.rate),
                    "total_amount": str(job.total_amount),
                    "service_fee": str(job.service_fee),
                    "location": job.location,
                    "payment_required": payment_required,
                    "payment_status": job.payment_status,
                    "message": "Job created successfully. Geocoding in progress.",
                },
                status=201,
            )
    except ValueError as e:
        # Handle specific validation errors
        core_logger.error(f"Validation error creating job: {str(e)}")
        raise PaeshiftValidationError(
            "Validation error creating job",
            {"details": str(e)}
        )
    except (PaeshiftValidationError, InternalServerError):
        raise
    except Exception as e:
        core_logger.error(f"Error creating job: {str(e)}", exc_info=True)
        raise InternalServerError("Failed to create job")

        

@log_endpoint(core_logger)
@core_router.put(
    "/jobs/edit-job",
    tags=["Job Management"],
    response={200: dict, 400: dict, 404: dict, 500: dict},
)
def edit_job(request, payload: EditJobSchema):
    try:
        from .validation import (
            format_validation_errors,
            validate_date,
            validate_time,
            validate_job_times,
        )
        from django_q.tasks import async_task
        from accounts.models import CustomUser
        from jobs.models import Job
        from jobs.utils import resolve_industry, resolve_subcategory
        from django.http import JsonResponse
        from decimal import Decimal
        import uuid, logging

        logger = logging.getLogger(__name__)

        # Validate job exists
        try:
            job = Job.objects.get(id=payload.job_id)
        except Job.DoesNotExist:
            raise ResourceNotFoundError("Job", payload.job_id)

        # Validate user exists
        try:
            CustomUser.objects.get(id=payload.user_id)
        except CustomUser.DoesNotExist:
            raise ResourceNotFoundError("User", payload.user_id)

        validation_errors = {}

        # Validate optional fields
        if payload.start_date:
            is_valid_date, job_start_date, date_error = validate_date(payload.start_date)
            if not is_valid_date:
                validation_errors["start_date"] = date_error
        else:
            job_start_date = job.start_date
        # Validate optional fields

        if payload.end_date:
            is_valid_date, job_end_date, date_error = validate_date(payload.end_date)
            if not is_valid_date:
                validation_errors["end_date"] = date_error
        else:
            job_end_date = job.start_date

        if payload.start_time:
            is_valid_start, start_time, start_error = validate_time(payload.start_time)
            if not is_valid_start:
                validation_errors["start_time"] = start_error
        else:
            start_time = job.start_time

        if payload.end_time:
            is_valid_end, end_time, end_error = validate_time(payload.end_time)
            if not is_valid_end:
                validation_errors["end_time"] = end_error
        else:
            end_time = job.end_time

        # Validate time relationship
        if "start_time" not in validation_errors and "end_time" not in validation_errors:
            is_valid_times, times_error = validate_job_times(start_time, end_time)
            if not is_valid_times:
                validation_errors["time_relationship"] = times_error

        if validation_errors:
            raise PaeshiftValidationError(format_validation_errors(validation_errors))

        # Update fields if provided
        if payload.title is not None:
            job.title = payload.title
        if payload.industry is not None:
            job.industry = resolve_industry(payload.industry)
        if payload.subcategory is not None:
            job.subcategory = resolve_subcategory(payload.subcategory)
        if payload.applicants_needed is not None:
            job.applicants_needed = payload.applicants_needed
        if payload.job_type is not None:
            job.job_type = payload.job_type
        if payload.shift_type is not None:
            job.shift_type = payload.shift_type

        job.start_date = job_start_date
        job.end_date = job_end_date
        job.start_time = start_time
        job.end_time = end_time

        if payload.rate is not None:
            job.rate = Decimal(str(payload.rate))
        if payload.location is not None and payload.location.strip() != job.location:
            job.location = payload.location.strip()
            # Dispatch geocoding if location changed
            async_task(
                "jobs.tasks.geocode_job",
                job.id,
                hook="jobs.hooks.handle_geocode_result",
            )

        if payload.pay_later is not None:
            job.payment_status = "pending" if payload.pay_later else "pending"

        # Recalculate fees and totals
        job.calculate_service_fee_and_total()
        job.save()

        duration_hours = getattr(job, "duration_hours", 0)
        payment_required = not payload.pay_later if payload.pay_later is not None else True

        return JsonResponse(
            {
                "success": True,
                "job_id": job.id,
                "title": job.title,
                "start_date": job.start_date.isoformat(),
                "start_date": job.end_date.isoformat(),
                "end_time": job.start_time.strftime("%I:%M %p"),
                "end_time": job.end_time.strftime("%I:%M %p"),
                "duration_hours": round(duration_hours, 2),
                "rate": str(job.rate),
                "total_amount": str(job.total_amount),
                "service_fee": str(job.service_fee),
                "location": job.location,
                "payment_required": payment_required,
                "payment_status": job.payment_status,
                "message": "Job updated successfully.",
            },
            status=200,
        )
    except ValueError as e:
        core_logger.error(f"Validation error updating job: {str(e)}")
        raise PaeshiftValidationError(
            "Validation error updating job",
            {"details": str(e)}
        )
    except (ResourceNotFoundError, PaeshiftValidationError, InternalServerError):
        raise
    except Exception as e:
        core_logger.error(f"Error updating job: {str(e)}", exc_info=True)
        raise InternalServerError("Failed to update job")





@core_router.post(
    "/application/mark-arrived/",
    response={200: dict, 400: ErrorResponseSchema, 500: ErrorResponseSchema},
    summary="Mark an applicant as arrived",
    description="Accepts applicant_id and client_id to mark the related application as 'arrived'."
)
def mark_arrived(request, payload: MarkArrivedSchema):
    """
    Payload:
    {
      "applicant_id": int,
      "client_id": int
    }

    Response on success:
    {
      "message": "Applicant marked as arrived.",
      "application_id": int,
      "job_id": int,
      "status": str
    }
    """
    try:
        # 1) Ensure both users exist
        applicant = get_object_or_404(CustomUser, id=payload.applicant_id)
        client = get_object_or_404(CustomUser, id=payload.client_id)

        # 2) Find the Application linking this applicant to a job posted by this client
        application_qs = Application.objects.filter(
            applicant=applicant,
            job__client=client
        )

        if not application_qs.exists():
            return 400, {"error": "No matching application found for this applicant and client."}

        # If multiple, take the most recent
        application = application_qs.latest("created_at")

        # 3) Update the status to 'arrived'
        with transaction.atomic():
            application.status = Application.Status.ACCEPTED  # or another status if you track arrival separately
            application.status_changed_at = timezone.now()
            application.save(update_fields=["status", "status_changed_at"])

        return {
            "message": "Applicant marked as arrived.",
            "application_id": application.id,
            "job_id": application.job.id,
            "status": application.status,
        }

    except Exception as e:
        return 500, {"error": f"An unexpected error occurred: {str(e)}"}






@core_router.get(
    "/job/{job_id}/payment-details",
    response={200: JobPaymentDetailSchema, 404: dict},
    summary="Get Payment Details for a Job",
    description="Returns payment details for a specific job."
)
def get_job_payment_details(request, job_id: int):
    from payment.models import Payment  # adjust import based on your structure
    from decimal import Decimal

    # Confirm job exists
    job = get_object_or_404(Job, id=job_id)

    # Get payment
    payment = Payment.objects.filter(job=job).first()
    if not payment:
        return 404, {"message": "No payment found for this job."}

    # Calculate service_fee if it's 0 (for backward compatibility)
    service_fee = payment.service_fee
    if service_fee == Decimal("0.00") and payment.original_amount:
        service_fee = (payment.original_amount * Decimal("0.10")).quantize(Decimal("0.00"))

    return {
        "job_id": job.id,
        "amount": payment.final_amount,
        "service_fee": float(service_fee),
        "method": payment.payment_method,
        "status": payment.status,
        "reference": payment.pay_code,
        "created_at": payment.created_at,
    }


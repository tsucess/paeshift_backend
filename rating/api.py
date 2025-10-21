# ==
# 📌 Python Standard Library Imports
# ==
import json
import logging
import os
import random
import sys
import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from math import atan2, cos, radians, sin, sqrt
from typing import List, Optional

import requests
# ==
# 📌 Third-Party Imports
# ==
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
from django.db import IntegrityError
from django.db.models import Avg, Count, F, Max, Q, Sum
from django.http import HttpRequest, JsonResponse
from django.middleware.csrf import CsrfViewMiddleware
# ==
# 📌 Django Core Imports
# ==
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

from accounts.models import CustomUser as User
from jobs.schemas import *
from jobs.models import Job

# ==
# 📌 Local Application Imports
# ==
from .models import *
from .schemas import *
from jobs.models import Job  # adjust import to your app structure

# Import error handling and logging utilities
from core.exceptions import (
    ResourceNotFoundError,
    InternalServerError,
    ValidationError as PaeshiftValidationError,
    ConflictError,
    AuthenticationError,
    AuthorizationError,
)
from core.logging_utils import log_endpoint, logger as core_logger, api_logger

# Import caching utilities for Phase 2.2c
from core.cache_utils import (
    cache_query_result,
    cache_api_response,
    invalidate_cache,
    CACHE_TTL_REVIEWS,
)

rating_router = Router()
logger = logging.getLogger(__name__)
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.db.models import Avg
from django.utils import timezone
from datetime import timedelta
import time
import logging

logger = logging.getLogger(__name__)

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
import time
from django.db.models import Avg

# ----------------------------------------------------------------------
# Review Endpoints
# ----------------------------------------------------------------------

def get_user_credit_score(user):
    jobs = user.jobs_completed
    rating = user.average_rating
    earnings = user.total_earnings
    return 300 + 3 * jobs + 100 * rating + 0.001 * earnings



@log_endpoint(core_logger)
@rating_router.post(
    "/ratings/",
    response={201: ReviewCreatedResponseSchema},
    summary="Submit user rating(s)",
    description="Create rating(s) for one or multiple users.",
)
def create_rating(request, payload: ReviewCreateSchema):
    try:
        sender_id = payload.sender_id
        receivers = payload.receiver_id
        if isinstance(receivers, int):
            receivers = [receivers]

        try:
            reviewer = User.objects.get(pk=sender_id)
        except User.DoesNotExist:
            raise ResourceNotFoundError("User", sender_id)

        job = None
        if payload.job_id:
            try:
                job = Job.objects.get(pk=payload.job_id)
            except Job.DoesNotExist:
                raise ResourceNotFoundError("Job", payload.job_id)

        results = []

        for rid in receivers:
            if rid == sender_id:
                results.append({
                    "receiver_id": rid,
                    "status": "error",
                    "rating_id": None,
                    "message": "You cannot rate yourself.",
                })
                continue

            try:
                try:
                    reviewed_user = User.objects.get(pk=rid)
                except User.DoesNotExist:
                    raise ResourceNotFoundError("User", rid)

                # Check for existing review
                existing_review = Review.objects.filter(
                    reviewer=reviewer,
                    reviewed=reviewed_user,
                    job=job,
                ).first()

                if existing_review:
                    results.append({
                        "receiver_id": rid,
                        "status": "error",
                        "rating_id": existing_review.id,
                        "message": "You have already rated this user for this job.",
                    })
                    continue

                # Create new rating
                new_rating = Review.objects.create(
                    reviewer=reviewer,
                    reviewed=reviewed_user,
                    rating=payload.rating,
                    feedback=payload.feedback or "",
                    job=job,
                )

                # Trigger sentiment analysis (optional async task)
                from .tasks import analyze_review_sentiment
                analyze_review_sentiment.delay(new_rating.id)

                # Log successful rating
                api_logger.log_rating(sender_id, rid, payload.rating, "Rating submitted")
                core_logger.info(
                    "Rating submitted successfully",
                    reviewer_id=sender_id,
                    reviewed_id=rid,
                    rating=payload.rating,
                    job_id=payload.job_id
                )

                results.append({
                    "receiver_id": rid,
                    "status": "success",
                    "rating_id": new_rating.id,
                    "message": "Rating submitted successfully",
                })

            except Exception as e:
                core_logger.error(f"Error creating rating for user {rid}: {str(e)}", exc_info=True)
                results.append({
                    "receiver_id": rid,
                    "status": "error",
                    "rating_id": None,
                    "message": f"Validation error: {str(e)}",
                })

        return 201, {"results": results}

    except (ResourceNotFoundError, PaeshiftValidationError):
        raise
    except Exception as e:
        core_logger.error(f"Error creating ratings: {str(e)}", exc_info=True)
        raise InternalServerError("Failed to create ratings")









@log_endpoint(core_logger)
@cache_api_response(timeout=CACHE_TTL_REVIEWS, prefix='reviews:user')
@rating_router.get("/reviews/{user_id}", tags=["Review"])
def get_user_ratings_and_reviews(request, user_id: int, filter: str = "all"):
    """
    GET /reviews/{user_id}?filter={filter} - Get user ratings and filtered reviews

    Retrieves all ratings and reviews for a user with optional filtering:
    - all: All reviews (default)
    - unread: Only unread reviews
    - recent: Reviews from the last 7 days

    Returns average rating, total reviews count, and detailed reviews.
    """
    try:
        start_time = time.time()

        # Get user
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise ResourceNotFoundError("User", user_id)

        # Base query: reviews for this user with optimized related fields
        reviews_qs = Review.objects.filter(reviewed=user).select_related(
            "reviewer__profile",
            "reviewed__profile",
            "job"
        )

        # Apply filter
        if filter == "unread":
            reviews_qs = reviews_qs.filter(is_read=False)
        elif filter == "recent":
            seven_days_ago = timezone.now() - timedelta(days=7)
            reviews_qs = reviews_qs.filter(created_at__gte=seven_days_ago)

        reviews_qs = reviews_qs.order_by("-created_at")

        # Calculate average rating from filtered reviews
        average_rating = reviews_qs.aggregate(avg_rating=Avg("rating"))["avg_rating"] or 0.0

        # Prepare reviews list
        from accounts.models import Profile, ProfilePicture
        reviews_list = []
        for r in reviews_qs:
            # Get reviewer's profile picture
            profile_pic_url = None
            if hasattr(r.reviewer, "profile"):
                profile = r.reviewer.profile
                active_pic = getattr(profile, "pictures", None)
                if active_pic:
                    active_pic = active_pic.filter(is_active=True).first()
                    if active_pic:
                        profile_pic_url = active_pic.url
            reviews_list.append({
                "id": r.id,
                "reviewer_id": r.reviewer.id,
                "reviewer_name": f"{r.reviewer.first_name} {r.reviewer.last_name}".strip(),
                "reviewer_avatar": profile_pic_url,  # Now includes avatar
                "rating": float(r.rating),
                "feedback": r.feedback,
                "job_id": r.job.id if r.job else None,
                "job_title": r.job.title if r.job else None,
                "sentiment": getattr(r, "sentiment", "neutral"),
                "review_type": getattr(r, "review", "average"),
                "created_at": r.created_at.isoformat(),
                "is_read": getattr(r, "is_read", False),
            })

        response_data = {
            "status": "success",
            "message": "Ratings and reviews retrieved successfully",
            "data": {
                "user_id": user.id,
                "username": user.username,
                "full_name": f"{user.first_name} {user.last_name}".strip(),
                "average_rating": round(average_rating, 2),
                "total_reviews": reviews_qs.count(),
                "filter": filter,
                "reviews": reviews_list,
            }
        }

        duration = time.time() - start_time
        core_logger.info(
            "User ratings and reviews retrieved",
            user_id=user_id,
            review_count=reviews_qs.count(),
            filter=filter,
            duration=f"{duration:.2f}s"
        )

        return JsonResponse(response_data)

    except ResourceNotFoundError:
        raise
    except Exception as e:
        core_logger.error(f"Error retrieving ratings and reviews: {str(e)}", exc_info=True)
        raise InternalServerError("Failed to retrieve ratings and reviews")


@log_endpoint(core_logger)
@cache_api_response(timeout=CACHE_TTL_REVIEWS, prefix='reviews:reviewer')
@rating_router.get("/ratings/reviewer_{user_id}/", tags=["Review"])
def get_reviews_by_user(request, user_id: int):
    """
    GET /ratings/reviewer_{user_id}/ - Get reviews submitted by a user (where they are the reviewer)

    Retrieves all reviews that a user has submitted to others.
    Returns the reviews where the specified user is the reviewer.
    """
    try:
        start_time = time.time()

        # Get user
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise ResourceNotFoundError("User", user_id)

        # Base query: reviews by this user (where they are the reviewer) with optimized related fields
        reviews_qs = Review.objects.filter(reviewer=user).select_related(
            "reviewer__profile",
            "reviewed__profile",
            "job"
        ).order_by("-created_at")

        # Prepare reviews list
        from accounts.models import Profile, ProfilePicture
        reviews_list = []
        for r in reviews_qs:
            # Get reviewed user's profile picture
            profile_pic_url = None
            if hasattr(r.reviewed, "profile"):
                profile = r.reviewed.profile
                active_pic = getattr(profile, "pictures", None)
                if active_pic:
                    active_pic = active_pic.filter(is_active=True).first()
                    if active_pic:
                        profile_pic_url = active_pic.url

            reviews_list.append({
                "id": r.id,
                "reviewed_id": r.reviewed.id,
                "reviewed_name": f"{r.reviewed.first_name} {r.reviewed.last_name}".strip(),
                "reviewed_avatar": profile_pic_url,
                "rating": float(r.rating),
                "feedback": r.feedback,
                "job_id": r.job.id if r.job else None,
                "job_title": r.job.title if r.job else None,
                "created_at": r.created_at.isoformat(),
            })

        response_data = {
            "user_id": user.id,
            "username": user.username,
            "full_name": f"{user.first_name} {user.last_name}".strip(),
            "total_reviews_given": reviews_qs.count(),
            "reviews": reviews_list,
        }

        duration = time.time() - start_time
        core_logger.info(
            "Reviews by user retrieved",
            user_id=user_id,
            review_count=reviews_qs.count(),
            duration=f"{duration:.2f}s"
        )

        return JsonResponse(response_data)

    except ResourceNotFoundError:
        raise
    except Exception as e:
        core_logger.error(f"Error retrieving reviews by user: {str(e)}", exc_info=True)
        raise InternalServerError("Failed to retrieve reviews")


@log_endpoint(core_logger)
@rating_router.post(
    "/ratings/mark-read/",
    response={200: MarkReadResponseSchema},
    tags=["Review"],
    summary="Mark rating as read",
    description="Marks a specific review as read by the reviewed user."
)
def mark_rating_as_read(request, payload: MarkReadSchema):
    try:
        try:
            review = Review.objects.get(pk=payload.review_id)
        except Review.DoesNotExist:
            raise ResourceNotFoundError("Review", payload.review_id)

        if review.reviewed.id != payload.user_id:
            raise PaeshiftValidationError(
                "Unauthorized to mark this review as read",
                {"user_id": payload.user_id, "review_id": payload.review_id}
            )

        if not hasattr(review, 'is_read'):
            raise InternalServerError("The 'is_read' field does not exist on the Review model")

        review.is_read = True
        review.save(update_fields=["is_read"])

        # Log successful action
        core_logger.info(
            "Review marked as read",
            review_id=payload.review_id,
            user_id=payload.user_id
        )

        return 200, {
            "status": "success",
            "message": f"Review {payload.review_id} marked as read by user {payload.user_id}"
        }

    except (ResourceNotFoundError, PaeshiftValidationError):
        raise
    except Exception as e:
        core_logger.error(f"Error marking review as read: {str(e)}", exc_info=True)
        raise InternalServerError("Failed to mark review as read")




@rating_router.put(
    "/ratings/update/",
    response={200: UpdateRatingResponseSchema},
    tags=["Review"],
    summary="Update a rating",
    description="Allows a user to update their own review/rating."
)
def update_rating(request, payload: ReviewUpdateSchema):
    review = get_object_or_404(Review, pk=payload.review_id)

    if review.reviewer.id != payload.user_id:
        return JsonResponse({
            "error": "Unauthorized",
            "details": "Only the user who created the review can update it."
        }, status=401)

    feedback_updated = False

    if payload.rating is not None:
        review.rating = payload.rating

    if payload.feedback is not None and payload.feedback != review.feedback:
        review.feedback = payload.feedback
        feedback_updated = True

    review.save()

    if feedback_updated:
        from .tasks import analyze_review_sentiment
        analyze_review_sentiment.delay(review.id)

    return 200, {
        "status": "success",
        "message": "Rating updated successfully",
        "review": {
            "id": review.id,
            "rating": float(review.rating),
            "feedback": review.feedback,
            "sentiment": getattr(review, "sentiment", "neutral"),
            "review_type": getattr(review, "review", "average"),
            "updated_at": timezone.now().isoformat()
        }
    }












# # Import the hibernate decorator
# from core.redis_hibernate import hibernate
# from accounts.models import CustomUser as User
# from rating.models import Review

# @hibernate(depends_on=[User, Review])
# def get_hibernated_user_ratings(user_id: int):
#     """
#     Get user ratings with hibernation.

#     This function is decorated with @hibernate, which means:
#     1. Results are cached permanently
#     2. Cache is automatically invalidated when User or Review models change
#     3. Function is only called once for each user until the cache is invalidated

#     Args:
#         user_id: User ID

#     Returns:
#         User ratings response dict
#     """
#     logger.debug(f"Generating hibernated user ratings for user_id={user_id}")

#     # Get user and ratings from database
#     reviewed_user = get_object_or_404(User, pk=user_id)

#     # Use select_related to optimize query
#     all_ratings = Review.objects.filter(reviewed=reviewed_user).select_related("reviewer")

#     # Calculate average rating
#     average_rating = Review.get_average_rating(reviewed_user)

#     # Cache individual reviews if they have a cache method
#     for review in all_ratings:
#         if hasattr(review, 'cache'):
#             review.cache()

#     # Format response
#     response = {
#         "user_id": reviewed_user.id,
#         "username": reviewed_user.username,
#         "full_name": f"{reviewed_user.first_name} {reviewed_user.last_name}".strip(),
#         "average_rating": average_rating,
#         "total_reviews": all_ratings.count(),
#         "ratings": [
#             {
#                 "id": r.id,
#                 "reviewer": {
#                     "id": r.reviewer.id,
#                     "username": r.reviewer.username,
#                     "name": f"{r.reviewer.first_name} {r.reviewer.last_name}".strip(),
#                 },
#                 "rating": r.rating,
#                 "feedback": r.feedback,
#                 "sentiment": getattr(r, "sentiment", "neutral"),
#                 "review_type": getattr(r, "review", "average"),
#                 "created_at": r.created_at.isoformat(),
#                 "job_id": r.job.id if r.job else None,
#             }
#             for r in all_ratings
#         ],
#     }

#     return response







# ----------------------------------------------------------------------
# Feedback Endpoints
# ----------------------------------------------------------------------

@log_endpoint(core_logger)
@rating_router.post(
    "company/feedback/",
    response={
        201: FeedbackResponseSchema,
        400: ErrorResponseSchema,
        401: UnauthorizedResponseSchema,
        422: ErrorResponseSchema,
    },
    summary="Submit company feedback",
    description="Creates feedback for the company. User can be specified by user_id in the payload or taken from authenticated user.",
    tags=["Feedback"]
)
def create_company_feedback(request, payload: CompanyFeedbackSchema):
    """
    Create company feedback.

    This endpoint allows users to submit feedback about the company/platform.
    The feedback includes a rating, message, and category.

    The user can be specified in three ways:
    1. By providing a user_id in the payload
    2. By using the authenticated user (if logged in)
    3. Anonymous feedback (if no user_id is provided and not authenticated)

    Args:
        request: The HTTP request
        payload: Feedback details including optional user_id, message, rating, and category

    Returns:
        201: Feedback created successfully
        400: Invalid user_id
        401: Authentication required (if authentication is needed)
        422: Validation error
    """
    try:
        # Determine the user
        user = None

        # If user_id is provided in the payload, use that user
        if payload.user_id:
            try:
                user = User.objects.get(pk=payload.user_id)
            except User.DoesNotExist:
                raise ResourceNotFoundError("User", payload.user_id)
        # Otherwise, use the authenticated user if available
        elif request.user.is_authenticated:
            user = request.user

        # Validate rating
        if payload.rating < 1 or payload.rating > 5:
            raise PaeshiftValidationError("Rating must be between 1 and 5", {"rating": payload.rating})

        # Create the feedback
        feedback = Feedback.objects.create(
            user=user,
            message=payload.message,
            rating=payload.rating,
            category=payload.category
        )

        # Log successful feedback creation
        core_logger.info(
            "Company feedback created successfully",
            feedback_id=feedback.id,
            user_id=user.id if user else None,
            rating=payload.rating,
            category=payload.category
        )

        # Return success response
        return 201, {
            "message": "Feedback submitted successfully",
            "feedback_id": feedback.id,
            "user_id": user.id if user else None,
            "rating": feedback.rating,
            "category": feedback.category,
            "created_at": feedback.created_at.isoformat()
        }

    except (ResourceNotFoundError, PaeshiftValidationError):
        raise
    except Exception as e:
        core_logger.error(f"Error creating feedback: {str(e)}", exc_info=True)
        raise InternalServerError("Failed to create feedback")


@log_endpoint(core_logger)
@rating_router.get(
    "/feedback/{user_id}/",
    response={200: dict, 401: UnauthorizedResponseSchema, 404: ErrorResponseSchema},
    summary="Get all feedback",
    description="Retrieves all feedback submitted to the company. Requires admin authentication or matching user_id.",
    tags=["Feedback"]
)
def get_company_feedback(request, user_id: int):
    """
    Get feedback for a specific user or all feedback if admin.

    This endpoint allows:
    - Users to view their own feedback
    - Admins to view all feedback or a specific user's feedback

    Args:
        request: The HTTP request
        user_id: ID of the user whose feedback to retrieve

    Returns:
        200: List of feedback
        401: Authentication required
        404: User not found
    """
    try:
        # Check if user is authenticated
        if not request.user.is_authenticated:
            raise AuthenticationError("Authentication required to view feedback")

        # If not admin and not the requested user, deny access
        if not request.user.is_staff and str(request.user.id) != str(user_id):
            raise AuthorizationError("You can only view your own feedback unless you're an admin")

        # Get the user
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise ResourceNotFoundError("User", user_id)

        # Get feedback - if admin, get all feedback; otherwise get only user's feedback
        if request.user.is_staff:
            feedback_list = Feedback.objects.filter(user=user).order_by('-created_at')
        else:
            feedback_list = Feedback.objects.filter(user=request.user).order_by('-created_at')

        # Format response
        response_data = {
            "status": "success",
            "message": f"Retrieved {feedback_list.count()} feedback items for user {user.username}",
            "user": {
                "id": user.id,
                "username": user.username,
                "name": user.get_full_name()
            },
            "count": feedback_list.count(),
            "feedback": [
                {
                    "id": f.id,
                    "message": f.message,
                    "rating": f.rating,
                    "category": f.category,
                    "created_at": f.created_at.isoformat(),
                    "is_resolved": f.is_resolved,
                    "admin_notes": f.admin_notes if request.user.is_staff else None
                }
                for f in feedback_list
            ]
        }

        # Log successful retrieval
        core_logger.info(
            "Feedback retrieved",
            user_id=user_id,
            feedback_count=feedback_list.count(),
            is_admin=request.user.is_staff
        )

        return response_data

    except (ResourceNotFoundError, AuthenticationError, AuthorizationError):
        raise
    except Exception as e:
        core_logger.error(f"Error retrieving feedback: {str(e)}", exc_info=True)
        raise InternalServerError("Failed to retrieve feedback")


@rating_router.get(
    "/feedback/user/{user_id}/",
    response={301: dict},
    summary="Get user feedback (Deprecated)",
    description="This endpoint is deprecated. Use /feedback/{user_id}/ instead.",
    tags=["Feedback"]
)
def get_user_feedback(request, user_id: int):
    """
    Deprecated endpoint. Redirects to /feedback/{user_id}/.

    Args:
        request: The HTTP request (unused)
        user_id: ID of the user whose feedback to retrieve

    Returns:
        301: Redirect to new endpoint
    """
    return 301, {
        "message": "This endpoint is deprecated",
        "redirect_to": f"/rating/feedback/{user_id}/",
        "details": "Please update your API calls to use the new endpoint"
    }


@rating_router.patch(
    "/feedback/{feedback_id}/resolve/",
    response={200: dict, 401: UnauthorizedResponseSchema, 404: ErrorResponseSchema},
    summary="Mark feedback as resolved",
    description="Marks a feedback item as resolved. Requires admin authentication. Admin notes can be provided in the request body.",
    tags=["Feedback"]
)
def resolve_feedback(request, feedback_id: int, payload: AdminNotesSchema = None):
    """
    Mark feedback as resolved.

    This endpoint allows admins to mark feedback as resolved and add optional notes.

    Args:
        request: The HTTP request
        feedback_id: ID of the feedback to resolve
        payload: Optional AdminNotesSchema containing admin notes

    Returns:
        200: Feedback resolved successfully
        401: Authentication required
        404: Feedback not found
    """
    # Check if user is authenticated and is an admin
    if not request.user.is_authenticated or not request.user.is_staff:
        return 401, {
            "error": "Unauthorized",
            "details": "You must be an admin to resolve feedback"
        }

    try:
        # Get the feedback
        feedback = get_object_or_404(Feedback, pk=feedback_id)

        # Mark as resolved
        feedback.is_resolved = True

        # Add admin notes if provided in payload
        if payload and payload.admin_notes:
            feedback.admin_notes = payload.admin_notes

        # Save the feedback
        feedback.save()

        return {
            "status": "success",
            "message": f"Feedback {feedback_id} marked as resolved",
            "feedback": {
                "id": feedback.id,
                "is_resolved": feedback.is_resolved,
                "admin_notes": feedback.admin_notes
            }
        }

    except Feedback.DoesNotExist:
        return 404, {
            "error": "Feedback not found",
            "details": f"No feedback found with ID {feedback_id}"
        }

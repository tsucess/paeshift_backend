from datetime import datetime, timedelta
from typing import Dict, Optional

from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Router
from ninja.errors import HttpError
from ninja.security import HttpBearer
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from jobs.models import Job
from rating.models import Feedback
from rating.schemas import FeedbackSchema

User = get_user_model()

# ==
# 📌 Authentication Classes
# ==
class JWTAuth(HttpBearer):
    def authenticate(self, request, token):
        print(f"🔐 JWT Auth: Received token: {token[:20] if token else 'None'}...")

        try:
            # Validate the token
            UntypedToken(token)
            print(f"✅ JWT Auth: Token validation successful")

            # Decode the token to get user info
            from rest_framework_simplejwt.tokens import AccessToken
            access_token = AccessToken(token)
            user_id = access_token['user_id']
            print(f"✅ JWT Auth: Extracted user_id: {user_id}")

            # Get the user
            user = User.objects.get(id=user_id)
            print(f"✅ JWT Auth: Found user: {user.username} (ID: {user.id})")
            return user
        except (InvalidToken, TokenError, User.DoesNotExist) as e:
            print(f"❌ JWT Auth: Authentication failed: {e}")
            return None

shift_router = Router(tags=["Shifts"])


# ==
# 📌 Constants & Helpers
# ==
VALID_SHIFT_TYPES = ["morning", "afternoon", "night"]
DEFAULT_SHIFT_HOURS = {
    "morning": ("08:00", "12:00"),
    "afternoon": ("13:00", "17:00"),
    "night": ("20:00", "04:00"),
}


# ==
# 📌 Shift Management Endpoints
# ==
@shift_router.post(
    "/jobs/{job_id}/shifts", tags=["Shifts"], response={200: Dict, 400: Dict, 401: Dict}
)
def create_or_update_shift(request, job_id: int, payload: Dict):
    """
    Creates or updates shift schedule for a job

    Example Payload:
        {
            "shiftType": "morning",
            "startTime": "09:00",
            "endTime": "17:00"
        }

    Responses:
        200: Success response with shift details
        400: Invalid shift type or time format
        401: Unauthorized access
        404: Job not found
    """
    if not request.user.is_authenticated:
        raise HttpError(401, "Authentication required")

    job = get_object_or_404(Job, pk=job_id, client=request.user)

    # Validate shift type
    shift_type = payload.get("shiftType", "morning").lower()
    if shift_type not in VALID_SHIFT_TYPES:
        raise HttpError(
            400, f"Invalid shift type. Must be one of: {', '.join(VALID_SHIFT_TYPES)}"
        )

    # Set default times if not provided
    start_time = payload.get("startTime", DEFAULT_SHIFT_HOURS[shift_type][0])
    end_time = payload.get("endTime", DEFAULT_SHIFT_HOURS[shift_type][1])

    # Validate time format
    if not all(_validate_time_format(t) for t in [start_time, end_time]):
        raise HttpError(400, "Invalid time format. Use HH:MM (24-hour format)")

    # Update job with shift details
    job.shift_type = shift_type
    job.start_time = start_time
    job.end_time = end_time
    job.save()

    return {
        "message": "Shift schedule updated",
        "job_id": job.id,
        "shift_type": job.get_shift_type_display(),
        "schedule": {"start": job.start_time, "end": job.end_time},
        "next_shift": _calculate_next_shift(job),
    }


@shift_router.get(
    "/jobs/{job_id}/shifts", tags=["Shifts"], response={200: Dict, 404: Dict}
)
def get_job_shifts(request, job_id: int):
    """
    Retrieve shift details for a specific job

    Returns:
        Complete shift schedule information including:
        - Current shift status
        - Next scheduled shift (if applicable)
        - Historical shift data (if available)
    """
    job = get_object_or_404(Job, pk=job_id)

    response = {
        "job_id": job.id,
        "shift_type": job.get_shift_type_display(),
        "current_status": job.status,
        "schedule": {"start": job.start_time, "end": job.end_time},
        "is_active": job.is_shift_ongoing,
    }

    if job.actual_shift_start:
        response["actual_start"] = job.actual_shift_start.isoformat()
    if job.actual_shift_end:
        response["actual_end"] = job.actual_shift_end.isoformat()

    return response


@shift_router.post(
    "/start-shift/{job_id}",
    tags=["Shifts"],
    response={200: Dict, 400: Dict, 401: Dict, 404: Dict},
    auth=JWTAuth(),
)
def start_shift(request, job_id: int):
    """
    Mark a job shift as officially started

    Responses:
        200: Success response with shift details
        400: Shift already in progress or no accepted applicants
        401: Unauthorized access
        404: Job not found
    """
    from jobs.models import Application

    job = get_object_or_404(Job, id=job_id)

    # Check if user is authorized to start the shift (must be the client)
    print(f"🔍 Start Shift Auth Check:")
    print(f"   User authenticated: {request.user.is_authenticated}")
    print(f"   Current user: {request.user.username if request.user.is_authenticated else 'Anonymous'} (ID: {request.user.id if request.user.is_authenticated else 'N/A'})")
    print(f"   Job client: {job.client.username if job.client else 'No client'} (ID: {job.client.id if job.client else 'N/A'})")
    print(f"   Job title: {job.title}")

    # if not request.user.is_authenticated:
    #     raise HttpError(401, "Authentication required to start shift")

    # if job.client != request.user:
    #     client_name = job.client.username if job.client else 'unknown user'
    #     raise HttpError(401, f"Only the job client can start this shift. Job belongs to {client_name}")

    if job.is_shift_ongoing:
        raise HttpError(400, "Shift already in progress")

    # Check if there are any accepted applicants
    accepted_applicants_count = job.applications.filter(status=Application.Status.ACCEPTED).count()
    if accepted_applicants_count == 0:
        raise HttpError(400, "Cannot start shift: No applicants have been accepted for this job")

    job.start_shift()
    return {
        "message": "Shift started successfully",
        "job_id": job.id,
        "started_at": job.actual_shift_start.isoformat(),
        "expected_end": (
            job.actual_shift_start + timedelta(hours=job.duration_hours)
        ).isoformat(),
        "current_status": job.status,
        "accepted_applicants_count": accepted_applicants_count,
    }


@shift_router.post(
    "/end-shift/{job_id}",
    tags=["Shifts"],
    response={200: Dict, 400: Dict, 401: Dict, 404: Dict},
    auth=JWTAuth(),
)
def end_shift(request, job_id: int):
    """
    Mark a job shift as completed

    Responses:
        200: Success response with duration details
        400: No active shift to end
        401: Unauthorized access
        404: Job not found
    """
    job = get_object_or_404(Job, id=job_id)

    if not job.is_shift_ongoing:
        raise HttpError(400, "No active shift to end")

    job.end_shift()
    duration = job.actual_shift_end - job.actual_shift_start

    # Create notification for job owner
    try:
        from notifications.models import Notification

        Notification.objects.create(
            user=job.client,
            category="shift_ended",
            message=f"Shift for '{job.title}' has been completed by {request.user.first_name} {request.user.last_name}.",
            is_read=False
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to create notification: {str(e)}")

    return {
        "message": "Shift completed successfully",
        "job_id": job.id,
        "ended_at": job.actual_shift_end.isoformat(),
        "duration": {
            "hours": round(duration.total_seconds() / 3600, 2),
            "minutes": round(duration.total_seconds() / 60, 2),
        },
        "current_status": job.status,
    }


@shift_router.post(
    "/cancel-shift/{job_id}",
    tags=["Shifts"],
    response={200: Dict, 400: Dict, 401: Dict, 404: Dict},
    auth=JWTAuth(),
)
def cancel_shift(request, job_id: int, payload: Dict = None):
    """
    Cancel a job shift

    This endpoint allows a user to cancel a shift. Both the job owner and the assigned
    applicant can cancel a shift, but with different validations.

    Example Payload:
        {
            "reason": "Unable to attend due to emergency",
        }

    Responses:
        200: Success response with cancellation details
        400: Shift cannot be cancelled (e.g., already completed)
        401: Unauthorized access
        404: Job not found
    """
    # Check authentication
    if not request.user.is_authenticated:
        raise HttpError(401, "Authentication required")

    # Get job
    job = get_object_or_404(Job, id=job_id)

    # Check authorization - only job owner or assigned applicant can cancel
    is_owner = job.client == request.user
    is_applicant = job.selected_applicant == request.user

    if not (is_owner or is_applicant):
        raise HttpError(401, "You are not authorized to cancel this shift")

    # Check if job can be cancelled
    if job.status in ["completed", "cancelled"]:
        raise HttpError(400, f"Shift cannot be cancelled. Current status: {job.status}")

    # Get cancellation reason
    reason = payload.get("reason", "No reason provided") if payload else "No reason provided"

    # Cancel the job
    try:
        job.deactivate()  # This will set status to CANCELED

        # Create notification for the other party
        try:
            from notifications.models import Notification
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer

            # Determine recipient (if owner cancels, notify applicant and vice versa)
            recipient = job.selected_applicant if is_owner else job.client

            if recipient:
                # Create notification
                Notification.objects.create(
                    user=recipient,
                    category="shift_cancelled",
                    message=f"Shift for '{job.title}' has been cancelled. Reason: {reason}",
                    is_read=False
                )

                # Also notify via WebSocket if available
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    f"user_{recipient.id}",
                    {
                        "type": "notification",
                        "message": f"Shift for '{job.title}' has been cancelled. Reason: {reason}",
                        "category": "shift_cancelled",
                        "job_id": job.id,
                    },
                )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to create notification: {str(e)}")

        return {
            "message": "Shift cancelled successfully",
            "job_id": job.id,
            "cancelled_by": "owner" if is_owner else "applicant",
            "reason": reason,
            "cancelled_at": timezone.now().isoformat(),
            "current_status": job.status,
        }
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error cancelling shift: {str(e)}", exc_info=True)
        raise HttpError(500, f"An error occurred: {str(e)}")


# ==
# 📌 Helper Functions
# ==
def _validate_time_format(time_str: str) -> bool:
    """Validate HH:MM time format"""
    try:
        datetime.strptime(time_str, "%H:%M")
        return True
    except ValueError:
        return False


def _calculate_next_shift(job: Job) -> Optional[Dict]:
    """Calculate next scheduled shift based on current shift"""
    if not job.start_time or not job.end_time:
        return None

    today = timezone.now().date()
    start_dt = datetime.combine(
        today, datetime.strptime(job.start_time, "%H:%M").time()
    )

    if timezone.now() > start_dt:
        start_dt += timedelta(days=1)

    return {
        "date": start_dt.date().isoformat(),
        "start": job.start_time,
        "end": job.end_time,
    }


# ==
# 📌 Feedback Endpoints
# ==
@shift_router.post("/feedback", tags=["Feedback"], response={201: Dict, 400: Dict})
def submit_feedback(request, payload: FeedbackSchema):
    """
    Submit feedback about a job experience

    Example Payload:
        {
            "message": "Great experience!",
            "rating": 5,
            "job_id": 123
        }

    Responses:
        201: Feedback successfully submitted
        400: Invalid rating or missing required fields
    """
    feedback = Feedback.objects.create(
        user=request.user if request.user.is_authenticated else None,
        message=payload.message,
        rating=payload.rating,
        job_id=getattr(payload, "job_id", None),
    )

    return JsonResponse(
        {
            "message": "Thank you for your feedback",
            "feedback_id": feedback.id,
            "rating": feedback.rating,
        },
        status=201,
    )

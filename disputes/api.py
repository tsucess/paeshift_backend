# ==
# 📌 Python Standard Library Imports
# ==
from datetime import datetime
from typing import List

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
# ==
# 📌 Django Core Imports
# ==
from ninja import Router
# ==
# 📌 Third-Party Imports
# ==
from pydantic import BaseModel

# ==
# 📌 Local Application Imports
# ==
from .models import Dispute, Job
from .schemas import (ConflictResponseSchema, DisputeCreatedResponseSchema,
                      DisputeCreateSchema, DisputeUpdateSchema,
                      ErrorResponseSchema)

# ==
# 📌 Initialize Router
# ==
disputes_router = Router(tags=["Dispute"])
User = get_user_model()


# ==
# 📌 Helper Functions
# ==
def authenticated_user_or_error(request):
    """Check if user is authenticated, return user or error response"""
    if not request.user.is_authenticated:
        return None, JsonResponse({"error": "Authentication required"}, status=401)
    return request.user, None


# ==
# 📌 Dispute Endpoints
# ==
@disputes_router.post(
    "/jobs/disputes",
    response={
        201: DisputeCreatedResponseSchema,
        400: ConflictResponseSchema,
        401: ErrorResponseSchema,
        403: ErrorResponseSchema,
        404: ErrorResponseSchema,
        422: ErrorResponseSchema,
    },
    summary="Create a job dispute",
    description="Creates a dispute for a specific job. Each user can only create one dispute per job.",
)
def create_dispute(request, payload: DisputeCreateSchema):
    """
    POST /jobs/disputes
    Body: { "job_id": ..., "user_id": ..., "title": ..., "description": ... }
    """
    # Authentication and authorization
    user, error = authenticated_user_or_error(request)
    if error:
        return 401, {
            "error": "Authentication required",
            "details": "Please log in to create disputes",
        }

    if user.id != payload.user_id:
        return 403, {
            "error": "Permission denied",
            "details": "You can only create disputes for your own account",
        }

    # Get job and check for existing dispute
    job = get_object_or_404(Job, pk=payload.job_id)
    if Dispute.objects.filter(job=job, created_by=user).exists():
        return 400, {
            "error": "Dispute already exists",
            "details": "You have already created a dispute for this job",
            "resolution": "Contact support if you need to modify your dispute",
        }

    # Create dispute
    dispute = Dispute.objects.create(
        job=job,
        created_by=user,
        title=payload.title.strip(),
        description=payload.description.strip(),
    )

    return 201, {
        "message": "Dispute created successfully",
        "dispute_id": dispute.id,
        "status": dispute.status,
        "created_at": dispute.created_at.isoformat(),
        "job_details": {
            "job_id": job.id,
            "job_title": job.title,
            "employer": job.client.get_full_name(),
        },
    }


@disputes_router.post(
    "/jobs/{job_id}/raise-dispute",
    response={
        201: dict,
        400: dict,
        401: dict,
        404: dict,
    },
    summary="Raise a dispute for a job",
    description="Raises a dispute for a specific job and assigns an admin with the lowest workload.",
)
def raise_dispute(request, job_id: int):
    """
    POST /jobs/{job_id}/raise-dispute
    Body: { "title": "Dispute Title", "description": "Detailed description of the issue" }
    """
    # Authentication check
    user, error = authenticated_user_or_error(request)
    if error:
        return 401, {
            "error": "Authentication required",
            "details": "Please log in to raise a dispute",
        }

    # Get job
    try:
        job = Job.objects.get(id=job_id)
    except Job.DoesNotExist:
        return 404, {
            "error": "Job not found",
            "details": f"No job found with ID {job_id}",
        }

    # Check if user is related to the job
    is_client = job.client_id == user.id
    is_applicant = job.applications.filter(applicant=user).exists()

    if not (is_client or is_applicant):
        return 403, {
            "error": "Permission denied",
            "details": "You must be the job client or an applicant to raise a dispute",
        }

    # Check for existing open disputes by this user
    if Dispute.objects.filter(
        job=job, raised_by=user, status=Dispute.Status.OPEN
    ).exists():
        return 400, {
            "error": "Dispute already exists",
            "details": "You already have an open dispute for this job",
        }

    # Get data from request
    try:
        data = request.data
        title = data.get("title", "").strip()
        description = data.get("description", "").strip()

        if not title:
            return 400, {
                "error": "Missing title",
                "details": "A title is required for the dispute",
            }

        if not description:
            return 400, {
                "error": "Missing description",
                "details": "A description is required for the dispute",
            }
    except Exception as e:
        return 400, {"error": "Invalid request data", "details": str(e)}

    # Create dispute
    dispute = Dispute.objects.create(
        job=job,
        raised_by=user,
        title=title,
        description=description,
        status=Dispute.Status.OPEN,
    )

    # The signal will trigger the admin assignment task

    return 201, {
        "success": True,
        "message": "Dispute raised successfully. An admin will be assigned shortly.",
        "dispute_id": dispute.id,
        "job_id": job.id,
        "status": dispute.status,
    }


@disputes_router.get("/jobs/{job_id}/disputes", tags=["Disputes"])
def list_job_disputes(request, job_id: int):
    """GET /jobs/{job_id}/disputes - Lists all disputes for a job"""
    job = get_object_or_404(Job, pk=job_id)
    disputes = job.disputes.select_related("created_by").all()
    return [
        {
            "id": d.id,
            "title": d.title,
            "description": d.description,
            "status": d.status,
            "created_by": d.created_by.username,
            "created_at": d.created_at.isoformat(),
            "updated_at": d.updated_at.isoformat(),
        }
        for d in disputes
    ]


@disputes_router.get("/disputes/{dispute_id}", tags=["Disputes"])
def dispute_detail(request, dispute_id: int):
    """GET /disputes/{dispute_id} - Fetches details for a dispute"""
    dispute = get_object_or_404(Dispute, pk=dispute_id)
    return {
        "id": dispute.id,
        "title": dispute.title,
        "description": dispute.description,
        "status": dispute.status,
        "created_by": dispute.created_by.username,
        "created_at": dispute.created_at.isoformat(),
        "updated_at": dispute.updated_at.isoformat(),
    }


@disputes_router.put("/disputes/{dispute_id}", tags=["Disputes"])
def update_dispute(request, dispute_id: int, payload: DisputeUpdateSchema):
    """PUT /disputes/{dispute_id} - Updates an existing dispute"""
    user, error = authenticated_user_or_error(request)
    if error:
        return error

    dispute = get_object_or_404(Dispute, pk=dispute_id)

    # Verify user owns the dispute
    if dispute.created_by_id != user.id:
        return 403, {
            "error": "Permission denied",
            "details": "You can only update your own disputes",
        }

    # Update fields from payload
    if payload.title:
        dispute.title = payload.title.strip()
    if payload.description:
        dispute.description = payload.description.strip()
    if payload.status:
        dispute.status = payload.status

    dispute.save()
    return {"message": "Dispute updated", "dispute_id": dispute.id}

from asgiref.sync import async_to_sync
from django.conf import settings

# Define a custom channel layer function to work with newer channels version
def get_channel_layer():
    from channels.layers import get_channel_layer as gcl
    return gcl()

# Initialize channel_layer lazily to avoid import errors
channel_layer = None
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.http import JsonResponse
from django.utils import timezone
# jobs/applicant.py
from ninja import Router

from rating.schemas import *

from .models import *
from .schemas import *
from .utils import *

applicant_router = Router()
User = get_user_model()


# ==
# 📌 Authentication Classes
# ==
class AppliacantAuth(HttpBearer):
    def authenticate(self, request, token):
        if token == "supersecret":
            user = request.user
            if user.is_authenticated and user.role == "appplicant":
                return user
        return None





@applicant_router.post(
    "/apply-jobs/",
    response=List[ApplicationListSchema]
)
def list_applicant_jobs(request, payload: ApplicantInput):
    # Optimize query with select_related for related objects
    applications = (
        Application.objects
        .select_related(
            "job__client__profile",
            "job__industry",
            "job__subcategory",
            "applicant__profile"
        )
        .filter(applicant_id=payload.user_id)
    )

    return [
        ApplicationListSchema(
            application_id=app.id,
            job_id=app.job.id,
            job_title=app.job.title,
            applicant_name=f"{app.applicant.first_name} {app.applicant.last_name}",
            status=app.get_status_display(),
            applied_at=app.created_at
        )
        for app in applications
    ]














# ==
# 📌 Applicant Jobs Endpoints
# ==
@applicant_router.post(
    "/applications/apply-job/", tags=["Applicant Endpoint"], response=ApplyJobResponse
)
def apply_for_job(request, payload: ApplyJobSchema):
    """
    POST /apply-job/
    Allows a user to apply for a job. Accepts job_id via payload.
    """

    try:
        user = User.objects.get(id=payload.user_id)
    except User.DoesNotExist:
        return ApplyJobResponse(detail="User not found.")

    job = get_object_or_404(Job, id=payload.job_id, is_active=True)

    # Check if user has already applied (but allow re-application if previously rejected)
    existing_application = job.applications.filter(applicant=user).first()
    if existing_application:
        # Allow re-application only if the previous application was rejected
        if existing_application.status != Application.Status.REJECTED:
            return ApplyJobResponse(detail="You have already applied for this job.")
        else:
            # Update the rejected application back to Applied status
            existing_application.status = Application.Status.APPLIED
            existing_application.applied_at = timezone.now()
            existing_application.save(update_fields=["status", "applied_at"])

            return ApplyJobResponse(
                detail="Application resubmitted successfully.", application_id=existing_application.id
            )

    try:
        application = Application.objects.create(
            job=job,
            applicant=user,
            # employer=job.client,  # Assuming 'client' is the employer on Job model
            applied_at=timezone.now(),
            status=Application.Status.APPLIED,
        )

        # Notify the job owner in real time
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{job.client.id}",
            {
                "type": "job_application_notification",
                "message": f"{user} applied for your job: {job.title}",
                "applicant_id": user.id,
            },
        )

        return ApplyJobResponse(
            detail="Application submitted successfully.", application_id=application.id
        )

    except IntegrityError:
        return ApplyJobResponse(detail="You have already applied for this job.")

    except Exception as e:
        return ApplyJobResponse(detail=f"An unexpected error occurred: {str(e)}")


@applicant_router.get(
    "/applications/getnearbyjobs/{user_id}", tags=["Applicant Endpoints"]
)
def get_nearby_jobs(request, user_id: int):
    """
    GET /jobs/get-nearby-jobs?lat=...&lng=...&radius_km=...
    Returns jobs within the specified radius using the Haversine formula.
    """
    try:
        lat = float(request.GET.get("lat", 0))
        lng = float(request.GET.get("lng", 0))
        radius_km = float(request.GET.get("radius_km", 5))  # Default radius: 5km
    except ValueError:
        return JsonResponse(
            {"error": "Invalid latitude, longitude, or radius"}, status=400
        )

    # Get all active jobs
    jobs = Job.objects.filter(status="upcoming")

    def haversine(lat1, lon1, lat2, lon2):
        """
        Calculate the great-circle distance between two points
        on the Earth using the Haversine formula.
        """
        R = 6371.0  # Radius of Earth in KM
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return R * c

    nearby_jobs = []
    for job in jobs:
        if not job.latitude or not job.longitude:
            continue

        distance = haversine(lat, lng, job.latitude, job.longitude)
        if distance <= radius_km:
            nearby_jobs.append(
                {
                    "id": job.id,
                    "title": job.title,
                    "distance_km": round(distance, 2),
                    "rate": str(job.rate),
                    "location": job.location,
                    "start_time": (
                        job.start_time.isoformat() if job.start_time else None
                    ),
                    "end_time": job.end_time.isoformat() if job.end_time else None,
                }
            )

    # Sort jobs by distance (nearest first)
    nearby_jobs.sort(key=lambda x: x["distance_km"])

    return JsonResponse({"jobs": nearby_jobs}, safe=False)


@applicant_router.get("/accepted-list", tags=["Applicant Jobs"])
def list_accepted_applications(request):
    """Returns accepted applications with detailed job and applicant metrics"""
    apps_qs = (
        Application.objects.filter(status=Application.Status.ACCEPTED)
        .select_related("job", "applicant", "job__client")
        .annotate(
            total_applicants_for_job=Count("job__applications"),
            accepted_applicants_for_job=Count(
                "job__applications",
                filter=Q(job__applications__status=Application.Status.ACCEPTED),
            ),
        )
    )

    applications = []
    for app in apps_qs:
        applications.append(
            {
                "application_id": app.id,
                "applicant_info": {
                    "id": app.applicant.id,
                    "name": app.applicant.get_full_name(),
                    "completed_jobs": Application.objects.filter(
                        applicant=app.applicant, status="completed"
                    ).count(),
                },
                "job_info": serialize_job(app.job),
                "application_metrics": {
                    "applied_at": app.applied_at.isoformat(),
                    "days_since_posted": (timezone.now() - app.job.created_at).days,
                    "competitiveness": f"{app.accepted_applicants_for_job}/{app.total_applicants_for_job} accepted",
                    "acceptance_rate": round(
                        (
                            (
                                app.accepted_applicants_for_job
                                / app.total_applicants_for_job
                                * 100
                            )
                            if app.total_applicants_for_job > 0
                            else 0
                        ),
                        2,
                    ),
                },
                "client_info": {
                    "id": app.job.client.id if app.job.client else None,
                    "name": (
                        app.job.client.get_full_name()
                        if app.job.client
                        else "Unknown Client"
                    ),
                    "rating": Review.objects.filter(reviewed=app.job.client).aggregate(
                        Avg("rating")
                    )["rating__avg"]
                    or "Not rated",
                },
            }
        )

    return {
        "meta": {
            "total_accepted": len(applications),
            "unique_applicants": len(
                {app["applicant_info"]["id"] for app in applications}
            ),
            "unique_clients": len(
                {
                    app["client_info"]["id"]
                    for app in applications
                    if app["client_info"]["id"]
                }
            ),
        },
        "applications": applications,
    }


@applicant_router.get(
    "/applicant/jobs/details/{applicant_id}/", tags=["Applicant Jobs"]
)
def get_jobs_applied_by_applicant(request, applicant_id: int):
    """Retrieves comprehensive job application history with statistics"""
    applicant = get_object_or_404(User, id=applicant_id)

    applied_jobs = (
        Job.objects.filter(applications__applicant=applicant)
        .select_related("client", "industry", "subcategory")
        .annotate(
            application_status=Max(
                "applications__status", filter=Q(applications__applicant=applicant)
            ),
            total_applicants=Count("applications"),
            accepted_applicants=Count(
                "applications", filter=Q(applications__status="accepted")
            ),
        )
        .order_by("-date")
    )

    jobs_list = []
    for job in applied_jobs:
        jobs_list.append(
            {
                "job_id": job.id,
                "title": job.title,
                "status": job.status,
                "application_status": job.application_status,
                "dates": {
                    "posted": job.created_at.date().isoformat(),
                    "start_date": job.date.isoformat() if job.date else None,
                },
                "metrics": {
                    "total_applicants": job.total_applicants,
                    "accepted_applicants": job.accepted_applicants,
                    "acceptance_rate": round(
                        (
                            (job.accepted_applicants / job.total_applicants * 100)
                            if job.total_applicants > 0
                            else 0
                        ),
                        2,
                    ),
                    "client_rating": Review.objects.filter(
                        reviewed=job.client
                    ).aggregate(Avg("rating"))["rating__avg"]
                    or "Not rated",
                },
            }
        )

    status_counts = {
        "accepted": sum(
            1 for job in jobs_list if job["application_status"] == "accepted"
        ),
        "completed": sum(1 for job in jobs_list if job["status"] == "completed"),
        "pending": sum(
            1 for job in jobs_list if job["application_status"] == "pending"
        ),
    }

    return JsonResponse(
        {
            "applicant": {
                "id": applicant.id,
                "username": applicant.username,
                "full_name": applicant.get_full_name(),
            },
            "statistics": {
                "total_applications": len(jobs_list),
                "status_breakdown": status_counts,
                "success_rate": round(
                    (
                        (status_counts["completed"] / status_counts["accepted"] * 100)
                        if status_counts["accepted"] > 0
                        else 0
                    ),
                    2,
                ),
            },
            "jobs": jobs_list,
        },
        status=200,
    )


@applicant_router.get("/applicant/jobs/count/{applicant_id}/", tags=["Applicant Jobs"])
def get_total_jobs_taken(request, applicant_id: int):
    """Provides detailed statistics about job applications and outcomes"""
    applicant = get_object_or_404(User, id=applicant_id)

    status_counts = (
        Application.objects.filter(applicant=applicant)
        .values("status")
        .annotate(count=Count("status"))
        .order_by()
    )

    status_dict = {item["status"]: item["count"] for item in status_counts}
    total_applications = sum(status_dict.values())

    return JsonResponse(
        {
            "applicant_id": applicant.id,
            "statistics": {
                "application_counts": {
                    "total": total_applications,
                    "accepted": status_dict.get("accepted", 0),
                    "completed": status_dict.get("completed", 0),
                    "rejected": status_dict.get("rejected", 0),
                    "pending": status_dict.get("pending", 0),
                },
                "success_metrics": {
                    "acceptance_rate": round(
                        (
                            status_dict.get("accepted", 0) / total_applications * 100
                            if total_applications > 0
                            else 0
                        ),
                        2,
                    ),
                    "completion_rate": round(
                        (
                            status_dict.get("completed", 0)
                            / status_dict.get("accepted", 1)
                            * 100
                            if status_dict.get("accepted", 0) > 0
                            else 0
                        ),
                        2,
                    ),
                },
            },
        },
        status=200,
    )


@applicant_router.get("/applicant/profile/{applicant_id}/", tags=["Applicant"])
def get_applicant_profile(request, applicant_id: int):
    """
    Get detailed profile information for an applicant.

    This endpoint returns comprehensive profile information including:
    - Personal details
    - Job statistics
    - Ratings and reviews
    - Payment history
    - Skills and qualifications

    Args:
        applicant_id: The ID of the applicant

    Returns:
        Detailed applicant profile information
    """
    # Check if applicant exists
    applicant = get_object_or_404(User, id=applicant_id)

    # Get profile information
    try:
        from accounts.models import Profile
        profile = Profile.objects.get(user=applicant)
    except:
        profile = None

    # Get job statistics
    job_stats = {
        "total_applications": Application.objects.filter(applicant=applicant).count(),
        "accepted_jobs": Application.objects.filter(applicant=applicant, status="accepted").count(),
        "completed_jobs": Application.objects.filter(applicant=applicant, status="completed").count(),
        "cancelled_jobs": Application.objects.filter(applicant=applicant, status="cancelled").count(),
    }

    # Get ratings and reviews
    from rating.models import Review
    reviews = Review.objects.filter(reviewed=applicant).order_by('-created_at')[:5]
    avg_rating = reviews.aggregate(Avg('rating'))['rating__avg'] or 0

    # Get payment history
    from payment.models import Payment
    payments = Payment.objects.filter(recipient=applicant).order_by('-created_at')[:5]
    total_earnings = payments.aggregate(Sum('final_amount'))['final_amount__sum'] or 0

    # Format response
    response_data = {
        "personal_info": {
            "id": applicant.id,
            "username": applicant.username,
            "email": applicant.email,
            "first_name": applicant.first_name,
            "last_name": applicant.last_name,
            "full_name": f"{applicant.first_name} {applicant.last_name}",
            "profile_pic": profile.profile_pic.url if profile and hasattr(profile, 'profile_pic') else None,
            "date_joined": applicant.date_joined.isoformat(),
        },
        "job_statistics": job_stats,
        "ratings": {
            "average_rating": round(avg_rating, 1),
            "total_reviews": reviews.count(),
            "recent_reviews": [
                {
                    "id": review.id,
                    "rating": review.rating,
                    "comment": review.comment,
                    "reviewer": f"{review.reviewer.first_name} {review.reviewer.last_name}" if review.reviewer else "Anonymous",
                    "date": review.created_at.isoformat(),
                }
                for review in reviews
            ],
        },
        "payment_info": {
            "total_earnings": float(total_earnings),
            "recent_payments": [
                {
                    "id": payment.id,
                    "amount": float(payment.final_amount),
                    "date": payment.created_at.isoformat(),
                    "status": payment.status,
                    "job_title": payment.job.title if payment.job else "N/A",
                }
                for payment in payments
            ],
        },
    }

    return JsonResponse(response_data, status=200)


@applicant_router.get("/applicant/clients/list/{applicant_id}/", tags=["Applicant"])
def get_clients_worked_with(request, applicant_id: int):
    """Retrieves client engagement history with performance metrics"""
    applicant = get_object_or_404(User, id=applicant_id)

    clients = (
        Job.objects.filter(status="completed", applications__applicant=applicant)
        .values(
            "client__id", "client__username", "client__first_name", "client__last_name"
        )
        .annotate(
            jobs_completed=Count("id"),
            total_earnings=Sum("total_amount"),
            avg_rating=Avg(
                "applications__rating", filter=Q(applications__applicant=applicant)
            ),
        )
        .distinct()
    )

    clients_list = []
    for client in clients:
        clients_list.append(
            {
                "client_id": client["client__id"],
                "username": client["client__username"],
                "full_name": f"{client['client__first_name']} {client['client__last_name']}".strip(),
                "engagement_metrics": {
                    "jobs_completed": client["jobs_completed"],
                    "total_earnings": float(client["total_earnings"] or 0),
                    "average_rating": (
                        round(client["avg_rating"], 2) if client["avg_rating"] else None
                    ),
                    "last_job_date": Job.objects.filter(
                        client__id=client["client__id"],
                        applications__applicant=applicant,
                        status="completed",
                    )
                    .latest("date")
                    .date.isoformat(),
                },
            }
        )

    total_earnings = sum(
        client["engagement_metrics"]["total_earnings"] for client in clients_list
    )

    return JsonResponse(
        {
            "applicant_id": applicant.id,
            "summary": {
                "total_clients": len(clients_list),
                "total_jobs_completed": sum(
                    c["engagement_metrics"]["jobs_completed"] for c in clients_list
                ),
                "total_earnings": total_earnings,
                "average_per_client": (
                    round(total_earnings / len(clients_list), 2) if clients_list else 0
                ),
            },
            "clients": sorted(
                clients_list,
                key=lambda x: x["engagement_metrics"]["jobs_completed"],
                reverse=True,
            ),
        },
        status=200,
    )


@applicant_router.get("/applicantjobs/{user_id}", tags=["Applicant Endpoints"])
def get_applied_jobs_by_user(
    request, user_id: int, page: int = Query(1, gt=0), page_size: int = Query(50, gt=0)
):
    """
    Retrieve all jobs that a user (applicant) has applied to.
    """
    from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator

    user = get_object_or_404(User, id=user_id)

    # Fetch applications made by this user
    qs = Application.objects.filter(applicant=user).select_related(
        "job", "job__industry", "job__subcategory", "job__client"
    )

    paginator = Paginator(qs, page_size)

    try:
        applications_page = paginator.page(page)
    except PageNotAnInteger:
        applications_page = paginator.page(1)
    except EmptyPage:
        applications_page = []

    jobs_data = []
    for application in applications_page:
        job = application.job
        jobs_data.append(
            serialize_job(job, include_extra=True)
        )  # reuse your serialize_job

    return JsonResponse(
        {
            "applicant_id": user.id,
            "applicant_username": user.username,
            "jobs_applied": jobs_data,
            "page": page,
            "total_pages": paginator.num_pages,
            "total_jobs": paginator.count,
        },
        status=200,
    )

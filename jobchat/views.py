from django.http import JsonResponse
from django.shortcuts import render

from jobs.models import Job

from .models import LocationHistory, Message

from django.shortcuts import render, get_object_or_404
from accounts.models import CustomUser, Profile


def profile(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)
    profile, _ = Profile.objects.get_or_create(user=user)

    context = {
        "user": user,
        "profile": profile,
    }
    return render(request, "accounts/profile.html", context)


def chat_room(request, job_id):
    job = Job.objects.get(id=job_id)
    return render(request, "chat_room.html", {"job_id": job.id})


def get_messages(request, job_id):
    """Fetches all messages for a job chat."""
    messages = Message.objects.filter(job_id=job_id).order_by("timestamp")
    return JsonResponse(
        [
            {
                "sender": m.sender.username,
                "content": m.content,
                "timestamp": m.timestamp,
            }
            for m in messages
        ],
        safe=False,
    )


def get_job_locations(request, job_id):
    """
    Fetches the latest location updates for a job.

    Args:
        request: The HTTP request
        job_id: The ID of the job to get locations for
    """
    locations = LocationHistory.objects.filter(job_id=job_id).order_by("-timestamp")
    return JsonResponse(
        [
            {
                "latitude": loc.latitude,
                "longitude": loc.longitude,
                "address": loc.address,
            }
            for loc in locations
        ],
        safe=False,
    )

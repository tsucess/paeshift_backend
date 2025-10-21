from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from jobs.models import User  # Adjust according to your project structure

from .models import NotificationPreference
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from jobs.models import User  # Adjust according to your project structure

from .models import NotificationPreference


def set_notification_preferences(request, user_id, preference_type, category, value):
    """
    View to create or update a user's notification preferences.

    :param request: HTTP request object
    :param user_id: The ID of the user whose preferences are being updated
    :param preference_type: "push" or "email"
    :param category: The category of the notification (e.g., "new_job_alert")
    :param value: True (enable) or False (disable)
    """
    user = get_object_or_404(User, id=user_id)

    # Get or create preferences for the user
    user_pref, created = NotificationPreference.objects.get_or_create(user=user)

    try:
        # Update preferences dynamically
        user_pref.update_preferences(preference_type, category, value)
        return JsonResponse(
            {"message": "Notification preferences updated successfully"}, status=200
        )
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)


def set_notification_preferences(request, user_id, preference_type, category, value):
    """
    View to create or update a user's notification preferences.

    :param request: HTTP request object
    :param user_id: The ID of the user whose preferences are being updated
    :param preference_type: "push" or "email"
    :param category: The category of the notification (e.g., "new_job_alert")
    :param value: True (enable) or False (disable)
    """
    user = get_object_or_404(User, id=user_id)

    # Get or create preferences for the user
    user_pref, created = NotificationPreference.objects.get_or_create(user=user)

    try:
        # Update preferences dynamically
        user_pref.update_preferences(preference_type, category, value)
        return JsonResponse(
            {"message": "Notification preferences updated successfully"}, status=200
        )
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)

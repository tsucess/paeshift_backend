from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import models, transaction
from django.db.models import Q, Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.errors import HttpError

from jobs.models import *
from .models import *
from .schemas import (
    NotificationSchema,
    NotificationSettingsSchema,
    NotificationUpdateSchema,
    NotificationCountResponse,
    SinglePreferenceUpdateSchema
)

User = get_user_model()
notifications_router = Router(tags=["Notifications"])


# ✅ Helper function to get authenticated user
def get_authenticated_user(request):
    """Retrieve the authenticated user from session or request headers."""
    # For development, allow access without authentication
    if settings.DEBUG:
        # First try to get user_id from query params or session
        user_id = request.GET.get('user_id') or request.session.get('user_id')
        if user_id:
            try:
                return User.objects.get(id=user_id)
            except User.DoesNotExist:
                pass

        # If no user_id in query params or session, try to get from Authorization header
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            # Extract token
            token = auth_header.split(' ')[1]
            # In a real implementation, you would validate the token
            # For now, just check if it's not empty
            if token:
                # Try to get user_id from request body for POST requests
                if request.method == 'POST':
                    try:
                        # Try to parse JSON body
                        import json
                        body = json.loads(request.body)
                        if 'user_id' in body:
                            try:
                                return User.objects.get(id=body['user_id'])
                            except User.DoesNotExist:
                                pass
                    except:
                        pass

                # If we couldn't get user_id from body, try to get from query params
                user_id = request.GET.get('user_id')
                if user_id:
                    try:
                        return User.objects.get(id=user_id)
                    except User.DoesNotExist:
                        pass

    # Regular authentication check
    user_id = request.session.get("_auth_user_id")
    if not user_id:
        return None
    return get_object_or_404(User, id=user_id)


# ✅ Get All Notifications
@notifications_router.get("/{user_id}/")
def get_notifications(request, user_id: int):
    """
    Retrieve notifications for a specific user with optional filtering.

    Path Parameters:
        user_id: The ID of the user whose notifications to retrieve

    Query Parameters:
        is_read: Filter by read status (true/false)
        category: Filter by notification category
        limit: Maximum number of results to return (default: 50)
        page: Page number for pagination (default: 1)
    """
    from django.core.cache import cache
    import logging
    logger = logging.getLogger(__name__)

    # Get user by ID
    try:
        user = User.objects.get(id=user_id)
        logger.info(f"Retrieved notifications for user {user_id}")
    except User.DoesNotExist:
        logger.warning(f"User with ID {user_id} not found")
        return JsonResponse({"error": f"User with ID {user_id} not found"}, status=404)

    # Get query parameters
    is_read_param = request.GET.get('is_read')
    category = request.GET.get('category')
    limit = int(request.GET.get('limit', 50))
    page = int(request.GET.get('page', 1))

    # Calculate offset for pagination
    offset = (page - 1) * limit

    # Build cache key
    cache_key = f"notifications:list:{user.id}:{is_read_param or 'all'}:{category or 'all'}:{page}:{limit}"

    # Try to get from cache
    cached_data = cache.get(cache_key)
    if cached_data:
        return JsonResponse(cached_data)

    # Build query
    query = Q(user=user)

    if is_read_param is not None:
        is_read = is_read_param.lower() == 'true'
        query &= Q(is_read=is_read)

    if category:
        query &= Q(category=category)

    # Get total count for pagination
    total_count = Notification.objects.filter(query).count()

    # Calculate pagination info
    total_pages = (total_count + limit - 1) // limit  # Ceiling division
    has_next = page < total_pages
    has_previous = page > 1

    # Execute query with pagination
    notifications = Notification.objects.filter(query).order_by("-created_at")[offset:offset + limit]

    # Format response
    notification_data = []
    for n in notifications:
        notification_item = {
            "id": n.id,
            "message": n.message,
            "category": n.category,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat(),
        }

        # Check if this notification is related to a job
        if n.category in [NotificationCategory.NEW_JOB_ALERT,
                         NotificationCategory.JOB_REMINDER,
                         NotificationCategory.JOB_ACCEPTANCE]:

            # First, try to extract job information from the message using regex
            import re
            job_title_match = re.search(r"'([^']*)'", n.message)

            if job_title_match:
                # Try to find the job by title
                job_title = job_title_match.group(1)
                try:
                    # Find the job that matches this title
                    job = Job.objects.filter(title=job_title).first()
                    if job:
                        notification_item["job_id"] = job.id
                        notification_item["job_title"] = job.title
                except Exception as e:
                    logger.error(f"Error finding job for notification {n.id}: {str(e)}")

            # If we couldn't find a job by title, try to find the most recent job for this user
            # This is a fallback mechanism
            if "job_id" not in notification_item:
                try:
                    # Find the most recent job for this user
                    recent_job = Job.objects.filter(client=n.user).order_by('-created_at').first()
                    if recent_job:
                        notification_item["job_id"] = recent_job.id
                        notification_item["job_title"] = recent_job.title
                except Exception as e:
                    logger.error(f"Error finding recent job for notification {n.id}: {str(e)}")

        notification_data.append(notification_item)

    response_data = {
        "status": "success",
        "message": "Notifications retrieved successfully",
        "data": {
            "total_count": total_count,
            "total_pages": total_pages,
            "current_page": page,
            "has_next": has_next,
            "has_previous": has_previous,
            "next_page": page + 1 if has_next else None,
            "previous_page": page - 1 if has_previous else None,
            "notifications": notification_data,
        }
    }

    # Cache the response for 5 minutes
    cache.set(cache_key, response_data, timeout=60 * 5)

    return JsonResponse(response_data)


# ✅ Get Unread Notification Count
@notifications_router.get("/notifications/{user_id}/unread-count/", response=dict)
def get_unread_notification_count(request, user_id: int):
    """
    Get the count of unread notifications for a specific user.

    Path Parameters:
        user_id: The ID of the user whose unread notification count to retrieve

    Returns:
        - total_unread: Total count of unread notifications
        - unread_by_type: Count of unread notifications grouped by category
    """
    from django.core.cache import cache
    import logging
    logger = logging.getLogger(__name__)

    # Get user by ID
    try:
        user = User.objects.get(id=user_id)
        logger.info(f"Retrieved unread notification count for user {user_id}")
    except User.DoesNotExist:
        logger.warning(f"User with ID {user_id} not found")
        return {"error": f"User with ID {user_id} not found", "status": "error"}

    # Try to get from cache first
    cache_key = f"notifications:unread_count:{user.id}"
    cached_data = cache.get(cache_key)

    if cached_data:
        return cached_data

    # If not in cache, query the database
    unread_notifications = Notification.objects.filter(user=user, is_read=False)
    total_count = unread_notifications.count()

    # Group by category and count
    category_counts = unread_notifications.values('category').annotate(count=Count('id'))

    # Format the response
    unread_by_type = {item['category']: item['count'] for item in category_counts}

    response_data = {
        "status": "success",
        "message": "Unread notification count retrieved successfully",
        "data": {
            "count": total_count,
            "unread_by_type": unread_by_type
        },
        "results": []
    }

    # Cache the result for 5 minutes
    cache.set(cache_key, response_data, timeout=60 * 5)

    return response_data


# ✅ Mark Notification as Read
@notifications_router.post("/notifications/{user_id}/{notification_id}/mark-as-read/")
def mark_notification_as_read(request, user_id: int, notification_id: int):
    """
    Mark a specific notification as read.

    Path Parameters:
        user_id: The ID of the user who owns the notification
        notification_id: The ID of the notification to mark as read

    This endpoint updates the read status of a notification and invalidates related caches.
    """
    from django.core.cache import cache
    import logging
    logger = logging.getLogger(__name__)

    # Log the request for debugging
    logger.info(f"Mark notification as read request: notification_id={notification_id}, user_id={user_id}")

    # Get user by ID
    try:
        user = User.objects.get(id=user_id)
        logger.info(f"Found user: {user.id}")
    except User.DoesNotExist:
        logger.warning(f"User with ID {user_id} not found")
        return JsonResponse({"error": f"User with ID {user_id} not found"}, status=404)

    # Try to find the notification
    try:
        notification = Notification.objects.get(id=notification_id, user=user)
    except Notification.DoesNotExist:
        logger.warning(f"Notification {notification_id} not found for user {user.id}")
        return JsonResponse({
            "error": "Notification not found",
            "details": f"No notification with ID {notification_id} found for this user"
        }, status=404)

    # Mark as read
    notification.is_read = True
    notification.save(update_fields=['is_read'])
    logger.info(f"Marked notification {notification_id} as read for user {user.id}")

    # Invalidate the unread count cache
    cache_key = f"notifications:unread_count:{user.id}"
    cache.delete(cache_key)
    logger.debug(f"Invalidated cache key: {cache_key}")

    # Also invalidate the notifications list cache
    try:
        list_cache_key = f"notifications:list:{user.id}:*"
        for key in cache.keys(list_cache_key):
            cache.delete(key)
            logger.debug(f"Invalidated cache key: {key}")
    except Exception as e:
        logger.error(f"Error invalidating list cache: {str(e)}")

    return JsonResponse({
        "status": "success",
        "message": "Notification marked as read",
        "notification_id": notification_id
    })


# ✅ Mark All Notifications as Read
@notifications_router.post("/notifications/{user_id}/mark-all-read/")
def mark_all_notifications_as_read(request, user_id: int):
    """
    Mark all notifications for a specific user as read.

    Path Parameters:
        user_id: The ID of the user whose notifications to mark as read
    """
    from django.core.cache import cache
    import logging
    logger = logging.getLogger(__name__)

    # Get user by ID
    try:
        user = User.objects.get(id=user_id)
        logger.info(f"Marking all notifications as read for user {user_id}")
    except User.DoesNotExist:
        logger.warning(f"User with ID {user_id} not found")
        return JsonResponse({"error": f"User with ID {user_id} not found"}, status=404)

    # Update all unread notifications
    count = Notification.objects.filter(user=user, is_read=False).update(is_read=True)

    # Invalidate the unread count cache
    cache_key = f"notifications:unread_count:{user.id}"
    cache.delete(cache_key)

    return JsonResponse({
        "status": "success",
        "message": f"Marked {count} notifications as read"
    })


# ✅ Mark Notifications as Read by Category
@notifications_router.post("/notifications/{user_id}/mark-category-read/{category}/")
def mark_category_notifications_as_read(request, user_id: int, category: str):
    """
    Mark all notifications of a specific category as read for a specific user.

    Path Parameters:
        user_id: The ID of the user whose notifications to mark as read
        category: The category of notifications to mark as read
    """
    from django.core.cache import cache
    import logging
    logger = logging.getLogger(__name__)

    # Get user by ID
    try:
        user = User.objects.get(id=user_id)
        logger.info(f"Marking category {category} notifications as read for user {user_id}")
    except User.DoesNotExist:
        logger.warning(f"User with ID {user_id} not found")
        return JsonResponse({"error": f"User with ID {user_id} not found"}, status=404)

    # Validate category
    from .models import NotificationCategory
    if category not in NotificationCategory.values:
        logger.warning(f"Invalid category: {category}")
        return JsonResponse({"error": f"Invalid category: {category}"}, status=400)

    # Update all unread notifications of the specified category
    count = Notification.objects.filter(
        user=user,
        is_read=False,
        category=category
    ).update(is_read=True)

    # Invalidate the unread count cache
    cache_key = f"notifications:unread_count:{user.id}"
    cache.delete(cache_key)

    return JsonResponse({
        "status": "success",
        "message": f"Marked {count} notifications of category '{category}' as read"
    })


# ✅ Get Notification Preferences
@notifications_router.get("/{user_id}/settings", url_name="get_notification_settings")
def get_notification_settings(request, user_id: int):
    """
    Retrieve the notification settings for a specific user.

    Path Parameters:
        user_id: The ID of the user whose notification settings to retrieve
    """
    import logging
    logger = logging.getLogger(__name__)

    # Get user by ID
    try:
        user = User.objects.get(id=user_id)
        logger.info(f"Retrieved notification settings for user {user_id}")
    except User.DoesNotExist:
        logger.warning(f"User with ID {user_id} not found")
        return JsonResponse({"error": f"User with ID {user_id} not found"}, status=404)

    settings, _ = NotificationPreference.objects.get_or_create(user=user)

    return JsonResponse({
        "status": "success",
        "message": "Notification settings retrieved successfully",
        "data": {
            "push": settings.push_preferences,
            "email": settings.email_preferences
        }
    })


# ✅ Update Notification Preferences
@notifications_router.put("/notifications/{user_id}/settings")
def update_notification_settings(request, user_id: int, data: NotificationSettingsSchema = None):
    """
    Update notification preferences for a specific user.

    Path Parameters:
        user_id: The ID of the user whose notification settings to update

    This endpoint allows updating all notification preferences at once using either:
    1. A structured schema (NotificationSettingsSchema)
    2. Form data with checkbox values ('on' or empty string)
    """
    import logging
    logger = logging.getLogger(__name__)

    # Get user by ID
    try:
        user = User.objects.get(id=user_id)
        logger.info(f"Updating notification settings for user {user_id}")
    except User.DoesNotExist:
        logger.warning(f"User with ID {user_id} not found")
        return JsonResponse({"error": f"User with ID {user_id} not found"}, status=404)

    settings, _ = NotificationPreference.objects.get_or_create(user=user)

    # Check if we're receiving form data or schema data
    if data is None and request.method == 'POST':
        # Handle form data format
        form_data = request.POST

        # Convert form data to boolean values
        # Form checkboxes send 'on' when checked, and are absent when unchecked
        push_preferences = {
            "new_job_alert": form_data.get('newjob') == 'on',
            "job_reminder": form_data.get('newjobreminder') == 'on',
            "job_acceptance": form_data.get('jobrequest') == 'on',
            "settings_changes": form_data.get('settings') == 'on',
        }

        email_preferences = {
            "new_job_alert": form_data.get('emailnewjob') == 'on',
            "job_reminder": form_data.get('emailjobreminder') == 'on',
            "job_acceptance": form_data.get('jobacceptance') == 'on',
            "settings_changes": form_data.get('emailsettings') == 'on',
        }

        # Update preferences
        settings.push_preferences = push_preferences
        settings.email_preferences = email_preferences
    elif data:
        # Handle schema data format
        # Update push preferences
        settings.push_preferences = {
            "new_job_alert": data.push_new_job_alert,
            "job_reminder": data.push_job_reminder,
            "job_acceptance": data.push_job_acceptance,
            "settings_changes": data.push_settings_changes,
        }

        # Update email preferences
        settings.email_preferences = {
            "new_job_alert": data.email_new_job_alert,
            "job_reminder": data.email_job_reminder,
            "job_acceptance": data.email_job_acceptance,
            "settings_changes": data.email_settings_changes,
        }
    else:
        return JsonResponse({
            "status": "error",
            "message": "No data provided"
        }, status=400)

    # Save the updated preferences
    settings.save()

    return JsonResponse({
        "status": "success",
        "message": "Notification settings updated successfully",
        "data": {
            "push": settings.push_preferences,
            "email": settings.email_preferences
        }
    })


# ✅ Update Notification Preferences (Form Data)
@notifications_router.post("/notifications/{user_id}/settings")
def update_notification_settings_form(request, user_id: int):
    """
    Update notification preferences using form data for a specific user.

    Path Parameters:
        user_id: The ID of the user whose notification settings to update

    This endpoint is specifically designed to handle form submissions with checkbox values.
    """
    # Delegate to the main update function
    return update_notification_settings(request, user_id)


# ✅ Update Single Notification Preference
@notifications_router.post("/notifications/{user_id}/preferences", url_name="update_single_preference")
def update_single_preference(request, user_id: int, data: SinglePreferenceUpdateSchema):
    """
    Update a single notification preference for a specific user.

    Path Parameters:
        user_id: The ID of the user whose notification preference to update

    Request Body:
    {
        "preference_type": "push",
        "category": "job_acceptance",
        "value": false
    }
    """
    # Log the request for debugging
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Updating notification preference for user {user_id}: {data.dict()}")

    # Get user by ID
    try:
        user = User.objects.get(id=user_id)
        logger.info(f"Found user: {user.id}")
    except User.DoesNotExist:
        logger.warning(f"User with ID {user_id} not found")
        return JsonResponse({"error": f"User with ID {user_id} not found"}, status=404)

    # Get or create notification preferences for the user
    settings, _ = NotificationPreference.objects.get_or_create(user=user)

    # Validate preference type
    if data.preference_type not in ["push", "email"]:
        return JsonResponse({"error": f"Invalid preference type: {data.preference_type}"}, status=400)

    # Validate category
    valid_categories = ["new_job_alert", "job_reminder", "job_acceptance", "settings_changes"]
    if data.category not in valid_categories:
        # Try to convert from frontend format to backend format
        category_mapping = {
            "newjob": "new_job_alert",
            "newjobreminder": "job_reminder",
            "jobrequest": "job_acceptance",
            "settings": "settings_changes",
            "emailnewjob": "new_job_alert",
            "emailjobreminder": "job_reminder",
            "jobacceptance": "job_acceptance",
            "emailsettings": "settings_changes"
        }

        if data.category in category_mapping:
            data.category = category_mapping[data.category]
        else:
            return JsonResponse({"error": f"Invalid category: {data.category}"}, status=400)

    # Update the preference
    if data.preference_type == "push":
        settings.push_preferences[data.category] = data.value
    else:  # email
        settings.email_preferences[data.category] = data.value

    # Save the updated preferences
    settings.save()

    return JsonResponse({
        "status": "success",
        "message": f"{data.preference_type.capitalize()} notification for {data.category} updated successfully",
        "data": {
            "push": settings.push_preferences,
            "email": settings.email_preferences
        }
    })


# ✅ Send Notifications (Push & Email)
def send_notification(user, category, message):
    """Send push/email notifications based on user preferences."""
    settings = NotificationPreference.objects.filter(user=user).first()

    if not settings:
        return  # No settings available

    # Determine if push or email should be sent
    send_push = settings.push_preferences.get(category, False)
    send_email = settings.email_preferences.get(category, False)

    # Send push notification (implement your push service here)
    if send_push:
        print(f"🔔 Push notification sent to {user.username}: {message}")

    # Send email notification
    if send_email:
        send_mail(
            subject=f"{category.replace('_', ' ').title()} Notification",
            message=message,
            from_email="noreply@yourapp.com",
            recipient_list=[user.email],
        )

    # Save the notification in DB
    Notification.objects.create(user=user, category=category, message=message)

    return {"push_sent": send_push, "email_sent": send_email}



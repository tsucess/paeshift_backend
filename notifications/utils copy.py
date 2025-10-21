# notifications/utils.py

import json
import subprocess
import logging
from jobchat.models import LocationHistory
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)
def create_notification(user, message, title=None, notification_type=None, importance=None, **kwargs):
    from .models import Notification  # Import locally to avoid circular imports
    Notification.objects.create(
        user=user,
        message=message,
        title=title,
        category=notification_type or "general",
        metadata={"importance": importance} if importance else None
    )
    
    
def get_nearby_applicants(job):
    try:
        job_location = json.loads(job.location) if isinstance(job.location, str) else job.location

        if not job_location or "latitude" not in job_location or "longitude" not in job_location:
            return []

        lat = float(job_location["latitude"])
        lng = float(job_location["longitude"])

        return LocationHistory.objects.filter(
            latitude__range=(lat - 0.1, lat + 0.1),
            longitude__range=(lng - 0.1, lng + 0.1),
        ).select_related("user")

    except Exception as e:
        logger.error(f"Error getting nearby applicants: {e}")
        return []

def notify_nearby_applicants_via_mojo(job):
    nearby_users = get_nearby_applicants(job)
    for loc in nearby_users:
        user = loc.user
        if user and user.profile and user.profile.mobile:
            try:
                subprocess.Popen(
                    [
                        "mojo",
                        "push",
                        "send",
                        "--user",
                        user.profile.mobile,
                        "--message",
                        f"New job near you: {job.title}",
                    ]
                )
            except Exception as e:
                logger.error(f"Failed to send mojo push notification to {user}: {e}")

def send_websocket_notification(user, notification):
    """
    Push a notification to the user's WebSocket group.
    """
    channel_layer = get_channel_layer()
    group_name = f"user_notifications_{user.id}"
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": "notification_message",
            "id": notification.id,
            "title": getattr(notification, "title", ""),
            "message": notification.message,
            "category": getattr(notification, "category", None),
            "created_at": str(notification.created_at),
            "metadata": getattr(notification, "metadata", None),
        },
    )

def send_job_websocket_notification(user, notification):
    channel_layer = get_channel_layer()
    group_name = f"user_job_notifications_{user.id}"
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": "job_notification",
            "id": notification.id,
            "title": getattr(notification, "title", ""),
            "message": notification.message,
            "category": getattr(notification, "category", None),
            "created_at": str(notification.created_at),
            "metadata": getattr(notification, "metadata", None),
        },
    )

def send_review_websocket_notification(user, notification):
    channel_layer = get_channel_layer()
    group_name = f"user_review_notifications_{user.id}"
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": "review_notification",
            "id": notification.id,
            "title": getattr(notification, "title", ""),
            "message": notification.message,
            "category": getattr(notification, "category", None),
            "created_at": str(notification.created_at),
            "metadata": getattr(notification, "metadata", None),
        },
    )

def send_dispute_websocket_notification(user, notification):
    channel_layer = get_channel_layer()
    group_name = f"user_dispute_notifications_{user.id}"
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": "dispute_notification",
            "id": notification.id,
            "title": getattr(notification, "title", ""),
            "message": notification.message,
            "category": getattr(notification, "category", None),
            "created_at": str(notification.created_at),
            "metadata": getattr(notification, "metadata", None),
        },
    )

def send_wallet_websocket_notification(user, notification):
    channel_layer = get_channel_layer()
    group_name = f"user_wallet_notifications_{user.id}"
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": "wallet_notification",
            "id": notification.id,
            "title": getattr(notification, "title", ""),
            "message": notification.message,
            "category": getattr(notification, "category", None),
            "created_at": str(notification.created_at),
            "metadata": getattr(notification, "metadata", None),
        },
    )

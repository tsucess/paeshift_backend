from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()

from .models import Notification


@shared_task
def send_notification_task(user_id, message):
    """Background task to send a notification"""
    user = User.objects.get(id=user_id)
    Notification.objects.create(user=user, message=message)
    print(f"✅ Notification sent to {user.username}: {message}")

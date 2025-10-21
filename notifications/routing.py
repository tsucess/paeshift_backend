from django.urls import re_path

from jobchat.consumers import JobMatchingConsumer
from notifications.consumers import (
    NotificationConsumer,
    JobNotificationConsumer,
    ReviewNotificationConsumer,
    DisputeNotificationConsumer,
    WalletNotificationConsumer,
)

websocket_urlpatterns = [
    re_path(r"ws/job_matching/$", JobMatchingConsumer.as_asgi()),  # ✅ FIXED
    re_path(r"ws/notifications/$", NotificationConsumer.as_asgi()),  # ✅ USER NOTIFICATIONS
    re_path(r"ws/job_notifications/$", JobNotificationConsumer.as_asgi()),
    re_path(r"ws/review_notifications/$", ReviewNotificationConsumer.as_asgi()),
    re_path(r"ws/dispute_notifications/$", DisputeNotificationConsumer.as_asgi()),
    re_path(r"ws/wallet_notifications/$", WalletNotificationConsumer.as_asgi()),
]

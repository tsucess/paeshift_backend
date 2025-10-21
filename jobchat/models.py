from math import atan2, cos, radians, sin, sqrt

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import models
from geopy.geocoders import Nominatim

from jobs.models import Job

User = get_user_model()


# ===
# ✅ HELPER FUNCTION: Haversine Distance Calculation
# ===
def haversine(lat1, lon1, lat2, lon2):
    """Calculate the great circle distance between two points on the earth (in km)."""
    R = 6371.0  # Radius of the Earth in km
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c  # Distance in km


# ===
# ✅ MESSAGE MODEL (Job Chat System)
# ===
class Message(models.Model):
    """Stores messages exchanged in job chats."""

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="sent_messages"
    )
    content = models.TextField()
    timestamp = models.DateTimeField(
        auto_now_add=True, db_index=True
    )  # Indexed for faster queries

    def __str__(self):
        return f"{self.sender.username}: {self.content[:50]}"

    def clean(self):
        """Ensure the message content is within a reasonable length."""
        if len(self.content) > 1000:
            raise ValidationError("Message content is too long.")


# ===
# ✅ LOCATION HISTORY MODEL (Real-time Tracking)
# ===
class LocationHistory(models.Model):
    """Stores users' location history for jobs."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="location_histories"
    )
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="locations")
    latitude = models.FloatField()
    longitude = models.FloatField()
    timestamp = models.DateTimeField(
        auto_now_add=True, db_index=True
    )  # Indexed for performance

    class Meta:
        ordering = ["-timestamp"]  # Always fetch latest first

    def __str__(self):
        return f"{self.user.username} - {self.job.title} @ ({self.latitude}, {self.longitude})"

    def distance_to(self, other_location):
        """Calculate the distance between two locations."""
        return haversine(
            self.latitude,
            self.longitude,
            other_location.latitude,
            other_location.longitude,
        )

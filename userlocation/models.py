from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from geopy.exc import GeocoderTimedOut
from geopy.geocoders import Nominatim

from jobs.models import Job
# RedisSyncMixin functionality is now part of RedisCachedModelMixin


User = get_user_model()


# ===
# 📌 Job Tracker Model
# ===
class JobTracker(models.Model):
    """Tracks the status and progress of jobs with timestamps."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ONGOING = "ongoing", "Ongoing"
        COMPLETED = "completed", "Completed"
        CANCELED = "canceled", "Canceled"

    job = models.OneToOneField(
        "jobs.Job",
        on_delete=models.CASCADE,
        related_name="tracker",
        verbose_name="Associated Job",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="Start Time")
    ended_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Completion Time"
    )
    last_updated = models.DateTimeField(auto_now=True, verbose_name="Last Updated")

    class Meta:
        verbose_name = "Job Tracker"
        verbose_name_plural = "Job Trackers"
        ordering = ["-last_updated"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["started_at"]),
        ]

    def __str__(self):
        return f"{self.job.title} - {self.get_status_display()}"

    def start_job(self):
        """Mark job as started with current timestamp."""
        if self.status != self.Status.ONGOING:
            self.status = self.Status.ONGOING
            self.started_at = timezone.now()
            self.save()

    def complete_job(self):
        """Mark job as completed with current timestamp."""
        if self.status != self.Status.COMPLETED:
            self.status = self.Status.COMPLETED
            self.ended_at = timezone.now()
            self.save()

    def cancel_job(self):
        """Mark job as canceled."""
        if self.status != self.Status.CANCELED:
            self.status = self.Status.CANCELED
            self.save()


# ===
# 📌 User Location Model
# ===
class UserLocation(models.Model):
    """
    Tracks real-time user locations with geocoding capabilities.

    # Removed RedisSyncMixin/RedisCachedModelMixin references
    """

    # Redis sync configuration removed

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="locations",
        verbose_name="User",
    )
    name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Human-readable location identifier",
    )
    latitude = models.FloatField(
        validators=[MinValueValidator(-90.0), MaxValueValidator(90.0)],
        help_text="Latitude in decimal degrees (-90 to +90)",
    )
    longitude = models.FloatField(
        validators=[MinValueValidator(-180.0), MaxValueValidator(180.0)],
        help_text="Longitude in decimal degrees (-180 to +180)",
    )
    address = models.TextField(
        blank=True, null=True, help_text="Full address from reverse geocoding"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    last_updated = models.DateTimeField(
        auto_now=True, db_index=True, verbose_name="Last Updated"
    )

    class Meta:
        verbose_name = "User Location"
        verbose_name_plural = "User Locations"
        ordering = ["-last_updated"]
        indexes = [
            models.Index(fields=["user", "-last_updated"]),
            models.Index(fields=["address", "-last_updated"]),
            models.Index(fields=["latitude", "longitude"]),
        ]
        unique_together = ["user"]

    def __str__(self):
        location = self.address or f"{self.latitude}, {self.longitude}"
        return f"{self.user.username} @ {location}"

    @property
    def coordinates(self):
        """Return coordinates as (lat, lng) tuple if valid."""
        if None not in (self.latitude, self.longitude):
            return (self.latitude, self.longitude)
        return None

    def reverse_geocode(self):
        """Convert coordinates to human-readable address."""
        if not self.coordinates:
            return None

        try:
            geolocator = Nominatim(user_agent="payshift-location-resolver", timeout=10)
            location = geolocator.reverse(
                self.coordinates, exactly_one=True, language="en"
            )
            return location.address if location else None
        except GeocoderTimedOut:
            # logger.warning("Geocoding service timed out")
            return None
        except Exception as e:
            # logger.error(f"Geocoding error: {str(e)}")
            return None

    @classmethod
    def get_nearby_users(cls, latitude, longitude, radius_km=5):
        """Find users within radius using Haversine formula."""
        from django.db import connection

        query = """
        SELECT id, user_id,
               (6371 * acos(cos(radians(%s)) * cos(radians(latitude)) *
                cos(radians(longitude) - radians(%s)) +
                sin(radians(%s)) * sin(radians(latitude)))) AS distance
        FROM jobs_userlocation
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        HAVING distance < %s
        ORDER BY distance
        """

        with connection.cursor() as cursor:
            cursor.execute(query, [latitude, longitude, latitude, radius_km])
            return [
                {"id": row[0], "user_id": row[1], "distance": row[2]}
                for row in cursor.fetchall()
            ]

    def save(self, *args, **kwargs):
        """Auto-populate address from coordinates if missing."""
        if self.coordinates and not self.address:
            self.address = self.reverse_geocode()
        super().save(*args, **kwargs)

    # to_dict method removed (was only for Redis caching)


class LocationHistory(models.Model):
    """
    Tracks user location history.

    # Removed RedisSyncMixin/RedisCachedModelMixin references
    """

    # Redis sync configuration removed

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    latitude = models.FloatField(
        validators=[MinValueValidator(-90.0), MaxValueValidator(90.0)],
        help_text="Latitude in decimal degrees (-90 to +90)",
    )
    longitude = models.FloatField(
        validators=[MinValueValidator(-180.0), MaxValueValidator(180.0)],
        help_text="Longitude in decimal degrees (-180 to +180)",
    )
    location = models.CharField(max_length=255, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["user", "-timestamp"]),
            models.Index(fields=["latitude", "longitude"]),
        ]

    def __str__(self):
        return f"{self.user.username} @ {self.timestamp}"

    # to_dict method removed (was only for Redis caching)

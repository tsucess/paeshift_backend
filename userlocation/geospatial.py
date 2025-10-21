import math
from typing import Dict, List, Tuple

from django.db.models import Avg, Count, QuerySet
from django.utils import timezone

from jobs.models import Application, Job, User, UserLocation


class GeospatialMatcher:
    """Handles geospatial matching between jobs and applicants using Haversine formula."""

    def __init__(self, max_distance_km: float = 10.0):
        self.max_distance_km = max_distance_km
        self.earth_radius_km = 6371.0

    def haversine_distance(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Calculate the Haversine distance between two points in kilometers."""
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))
        return self.earth_radius_km * c

    def find_nearby_applicants(
        self, job: Job, max_distance: float = None
    ) -> List[Dict]:
        """Find applicants within the specified distance of a job location."""
        if not job.latitude or not job.longitude:
            return []

        # Use provided max_distance or default
        max_distance = max_distance or self.max_distance_km

        # Get all active applicants with their locations
        applicants = Application.objects.filter(
            status="active", is_online=True
        ).select_related("applicant", "applicant__profile")

        nearby_applicants = []
        for applicant in applicants:
            # Get applicant's last known location
            location = (
                UserLocation.objects.filter(user=applicant.applicant)
                .order_by("-last_location_update")
                .first()
            )

            if not location or not location.latitude or not location.longitude:
                continue

            distance = self.haversine_distance(
                job.latitude, job.longitude, location.latitude, location.longitude
            )

            if distance <= max_distance:
                nearby_applicants.append(
                    {
                        "applicant_id": applicant.applicant_id,
                        "distance_km": round(distance, 2),
                        "rating": applicant.applicant.profile.rating or 0,
                        "is_premium": applicant.applicant.profile.is_premium,
                        "last_active": location.last_location_update,
                    }
                )

        # Sort by distance, then by premium status, then by rating
        return sorted(
            nearby_applicants,
            key=lambda x: (x["distance_km"], not x["is_premium"], -x["rating"]),
        )

    def update_applicant_location(
        self, applicant: User, latitude: float, longitude: float
    ) -> None:
        """Update an applicant's location in the database."""
        UserLocation.objects.update_or_create(
            user=applicant,
            defaults={
                "latitude": latitude,
                "longitude": longitude,
                "last_location_update": timezone.now(),
                "is_online": True,
            },
        )

    def get_job_coverage(self, job: Job) -> Dict:
        """Get statistics about job coverage in the area."""
        nearby_applicants = self.find_nearby_applicants(job)

        if not nearby_applicants:
            return {
                "total_applicants": 0,
                "premium_applicants": 0,
                "average_rating": 0,
                "coverage_radius_km": self.max_distance_km,
            }

        return {
            "total_applicants": len(nearby_applicants),
            "premium_applicants": sum(1 for a in nearby_applicants if a["is_premium"]),
            "average_rating": sum(a["rating"] for a in nearby_applicants)
            / len(nearby_applicants),
            "coverage_radius_km": self.max_distance_km,
        }

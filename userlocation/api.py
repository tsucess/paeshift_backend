# ==
# 📌 Standard Imports
# ==
import math
from typing import Any, Dict, Optional

import googlemaps
# ==
# 📌 Django & Third-Party Imports
# ==
from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
# from django.contrib.gis.geos import Point
from ninja import Router
from ninja.security import HttpBearer, django_auth

# ==
# 📌 Local Imports
# ==
from jobs.models import Job
from userlocation.models import LocationHistory, UserLocation
from userlocation.schemas import *
from userlocation.schemas import SuccessMessageSchema

# ==
# 📌 Initialize Router & Constants
# ==
location_router = Router(tags=["User"])
User = get_user_model()
GOOGLE_MAPS_API_KEY = settings.GOOGLE_MAPS_API_KEY


# ==
# 📌 Helper Functions
# ==
def haversine(coord1: tuple, coord2: tuple) -> float:
    """
    Calculate the great-circle distance between two points
    on the Earth's surface using the Haversine formula.

    Args:
        coord1: Tuple of (latitude, longitude) for first point
        coord2: Tuple of (latitude, longitude) for second point

    Returns:
        Distance in kilometers
    """
    lat1, lon1 = coord1
    lat2, lon2 = coord2

    R = 6371  # Earth radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def geocode_address(address: str) -> Optional[Dict[str, Any]]:
    """
    Convert address to coordinates using Google Maps API.

    Args:
        address: String of address to geocode

    Returns:
        Dictionary with lat/lng and formatted address or None if failed
    """
    try:
        gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
        geocode_result = gmaps.geocode(address)
        if geocode_result:
            loc = geocode_result[0]["geometry"]["location"]
            return {
                "lat": loc["lat"],
                "lng": loc["lng"],
                "formatted_address": geocode_result[0]["formatted_address"],
            }
    except Exception as e:
        print(f"Google Maps API Error: {e}")
    return None


# ==
# 📌 Authentication Classes
# ==
class ClientAuth(HttpBearer):
    def authenticate(self, request, token):
        if token == "supersecret":
            user = request.user
            if user.is_authenticated and user.role == "client":
                return user
        return None


# ==
# 📌 Tracker Endpoints
# ==
@location_router.get("/jobs/{job_id}/location")
def get_job_location(request, job_id: int) -> Dict[str, Any]:
    """
    Retrieve the current location of a job.

    Parameters:
        job_id: ID of the job

    Returns:
        Dictionary with location data or error message
    """
    # Import Redis caching tools
    from core.redis_hibernate import hibernate
    from core.cache import get_cached_data, set_cached_data

    # Try to get from cache first
    cache_key = f"job_location:{job_id}"
    cached_data = get_cached_data(cache_key)
    if cached_data:
        return cached_data

    try:
        job = get_object_or_404(Job, id=job_id)
        response = {
            "status": "success",
            "data": {
                "latitude": job.latitude,
                "longitude": job.longitude,
                "location": job.location,
            },
        }

        # Cache the response for 15 minutes
        set_cached_data(cache_key, response, timeout=60*15)

        return response
    except Exception as e:
        return {"error": str(e)}, 500


@location_router.get("/track-applicant/{applicant_id}")
def track_applicant(request, applicant_id: int) -> Dict[str, Any]:
    """
    Retrieve the last known location of an applicant.

    Parameters:
        applicant_id: ID of the applicant user

    Returns:
        Dictionary with coordinates and timestamp or error message
    """
    # Import Redis caching tools
    from core.redis_hibernate import hibernate
    from core.cache import get_cached_data, set_cached_data

    # Try to get from cache first
    cache_key = f"applicant_location:{applicant_id}"
    cached_data = get_cached_data(cache_key)
    if cached_data:
        return cached_data

    location_record = (
        LocationHistory.objects.filter(user_id=applicant_id)
        .order_by("-timestamp")
        .first()
    )

    if not location_record:
        return {"error": "No location data available"}, 404

    response = {
        "coordinates": {
            "lat": location_record.latitude,
            "lng": location_record.longitude,
        },
        "last_updated": location_record.timestamp.isoformat() if hasattr(location_record.timestamp, 'isoformat') else str(location_record.timestamp),
    }

    # Cache the response for 5 minutes (locations change frequently)
    set_cached_data(cache_key, response, timeout=60*5)

    return response


# ==
# 📌 Location Endpoints
# ==
@location_router.post(
    "/update-location", response=SuccessMessageSchema, auth=django_auth
)
def update_location(request, lat: float, lng: float) -> Dict[str, str]:
    """
    Update the authenticated user's current location.

    Parameters:
        lat: Latitude coordinate
        lng: Longitude coordinate

    Returns:
        Success message
    """
    # Import Redis caching tools
    from core.cache import invalidate_cache_pattern

    # Create a location object (commented out Point usage)
    # location = Point(lng, lat, srid=4326)
    #use harversine instead

    # Update or create the user location
    user_location, created = UserLocation.objects.update_or_create(
        user=request.user,
        defaults={
            "latitude": lat,
            "longitude": lng,
            "is_online": True,
            "last_seen": datetime.now()
        }
    )

    # Create a location history record
    LocationHistory.objects.create(
        user=request.user,
        latitude=lat,
        longitude=lng,
        timestamp=datetime.now()
    )

    # Invalidate any cached location data for this user
    invalidate_cache_pattern(f"applicant_location:{request.user.id}")

    return {"message": "Location successfully updated"}

import logging

from django.core.exceptions import ObjectDoesNotExist
from django.core.management import call_command
from django.utils import timezone

from .geocoding import geocode_address
from .models import Job

logger = logging.getLogger(__name__)


def geocode_job(job_id):
    """
    Enhanced geocoding function with Redis caching and multiple provider support.

    This function uses the enhanced geocoding module with Redis caching and
    multiple provider support (Google Maps, Nominatim, Mapbox).

    Args:
        job_id: The ID of the job to geocode

    Returns:
        Dictionary with geocoding results including status, coordinates, and error info
    """
    if not job_id:
        return {
            "status": "error",
            "error": "No job ID provided",
            "job_id": None,
            "latitude": None,
            "longitude": None,
            "provider": None,
        }

    response = {
        "status": "processing",
        "job_id": job_id,
        "latitude": None,
        "longitude": None,
        "provider": None,
        "error": None,
        "cached": False,
    }

    try:
        # Validate job ID
        try:
            job_id_int = int(job_id)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid job ID format: {job_id} ({str(e)})") from e

        # Fetch job
        try:
            job = Job.objects.get(id=job_id_int)
        except ObjectDoesNotExist:
            raise ObjectDoesNotExist(f"Job {job_id_int} does not exist")

        if not job.location or not isinstance(job.location, str):
            raise ValueError("Job location is empty or invalid")

        # Make sure we have a valid location string
        if not job.location or not isinstance(job.location, str):
            logger.warning(f"Invalid location for job {job_id}: {job.location}")
            response.update(
                {"status": "error", "error": f"Invalid location: {type(job.location)}"}
            )
            return response

        # Clean the location string
        clean_location = job.location.strip()
        if len(clean_location) < 3:
            logger.warning(f"Location too short for job {job_id}: '{clean_location}'")
            response.update({"status": "error", "error": "Location string too short"})
            return response

        # Use the enhanced geocoding module with Redis caching
        try:
            # Get coordinates using the enhanced geocoding function
            coords = geocode_address(clean_location)

            if coords and coords.get("success"):
                # Update job with coordinates (already in Decimal format)
                job.latitude = coords["latitude"]
                job.longitude = coords["longitude"]
                job.save(update_fields=["latitude", "longitude"])

                # Update response with success info
                response.update(
                    {
                        "status": "success",
                        "latitude": coords["latitude"],
                        "longitude": coords["longitude"],
                        "provider": coords.get("provider", "unknown"),
                        "cached": coords.get("cached_at")
                        is not None,  # Check if result was from cache
                    }
                )

                # Log success with provider info
                provider = coords.get("provider", "unknown")
                cached = " (cached)" if coords.get("cached_at") else ""
                logger.info(
                    f"Successfully geocoded job {job_id} using {provider}{cached}: {coords['latitude']}, {coords['longitude']}"
                )

                return response
            else:
                # All providers failed
                error_msg = (
                    coords.get("error", "Unknown error")
                    if coords
                    else "No coordinates returned"
                )
                logger.warning(f"Geocoding failed for job {job_id}: {error_msg}")
                response.update({"status": "error", "error": error_msg})
                return response
        except Exception as e:
            logger.error(f"Geocoding error for job {job_id}: {str(e)}", exc_info=True)
            response.update({"status": "error", "error": f"Geocoding error: {str(e)}"})
            return response

    except Exception as e:
        error_msg = str(e)
        response.update({"status": "error", "error": error_msg})
        logger.error(f"Geocoding failed for job {job_id}: {error_msg}")

    return response


def warm_job_cache():
    """
    Warm the job cache by proactively caching frequently accessed data.

    This task is scheduled to run periodically to ensure the cache is always warm.
    """
    try:
        logger.info("Starting scheduled job cache warming...")

        # Call the management command to warm the cache
        call_command('warm_job_cache', days=7, limit=100)

        logger.info("Scheduled job cache warming completed successfully")
        return {"success": True, "timestamp": timezone.now().isoformat()}
    except Exception as e:
        logger.error(f"Error warming job cache: {str(e)}")
        return {"success": False, "error": str(e)}


def reconcile_job_cache():
    """
    Reconcile job cache with database to ensure consistency.

    This task is scheduled to run periodically to ensure that the cache is consistent
    with the database, particularly for cases where jobs are deleted directly from
    the database (e.g., by an admin) without triggering the cache invalidation signals.
    """
    try:
        logger.info("Starting scheduled job cache reconciliation...")

        # Call the management command to reconcile the cache
        call_command('reconcile_job_cache')

        logger.info("Scheduled job cache reconciliation completed successfully")
        return {"success": True, "timestamp": timezone.now().isoformat()}
    except Exception as e:
        logger.error(f"Error reconciling job cache: {str(e)}")
        return {"success": False, "error": str(e)}

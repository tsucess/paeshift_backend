"""
Enhanced geocoding module with multiple providers, Redis caching, and detailed monitoring.

This module provides geocoding functionality with support for:
1. Redis-based caching to reduce API calls
2. Multiple geocoding providers (Google Maps, Nominatim)
3. Consistent coordinate precision
4. Improved error handling and validation
5. Detailed performance monitoring and metrics
"""

import json
import logging
import random
import time
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional, Tuple

import requests
from django.conf import settings
from geopy.exc import (GeocoderServiceError, GeocoderTimedOut,
                       GeocoderUnavailable)
from geopy.geocoders import Nominatim

# Import the Redis cache module
from .geocoding_cache import (cache_coordinates, get_cache_stats,
                              get_cached_coordinates)

# Import the monitoring module
from .geocoding_monitor import GeocodingMetrics

logger = logging.getLogger(__name__)

# Geocoding settings
# GOOGLE_MAPS_API_KEY = getattr(settings, "GOOGLE_MAPS_API_KEY", None)

# Google Maps API Key
GOOGLE_MAPS_API_KEY = settings.GOOGLE_MAPS_API_KEY
MAPBOX_API_KEY = getattr(settings, "MAPBOX_API_KEY", None)
GEOCODING_TIMEOUT = getattr(settings, "GEOCODING_TIMEOUT", 15)  # seconds
GEOCODING_PROVIDERS = getattr(settings, "GEOCODING_PROVIDERS", ["google", "nominatim"])
GEOCODING_RETRY_DELAY = getattr(settings, "GEOCODING_RETRY_DELAY", 1)  # seconds
GEOCODING_MAX_RETRIES = getattr(settings, "GEOCODING_MAX_RETRIES", 3)


def geocode_address(address: str, provider: str = None) -> Dict[str, Any]:
    """
    Geocode an address using the specified provider or the default provider order.

    This function implements a multi-provider geocoding strategy with Redis caching
    and comprehensive error handling.

    Args:
        address: The address to geocode
        provider: Optional specific provider to use (google, nominatim, mapbox)

    Returns:
        Dictionary with geocoding results including success status, coordinates, and error info
    """
    start_time = time.time()
    request_id = f"geo_{int(start_time * 1000)}"

    # Validate input
    if not address:
        logger.warning(f"[{request_id}] Empty address provided for geocoding")
        return {
            "success": False,
            "error": "Address is empty",
            "latitude": None,
            "longitude": None,
            "provider": None,
            "error_type": "empty_input",
            "request_id": request_id,
        }

    if not isinstance(address, str):
        logger.warning(
            f"[{request_id}] Non-string address provided: {type(address).__name__}"
        )
        return {
            "success": False,
            "error": f"Address must be a string, got {type(address).__name__}",
            "latitude": None,
            "longitude": None,
            "provider": None,
            "error_type": "invalid_input_type",
            "request_id": request_id,
        }

    # Clean and validate address string
    clean_address = address.strip()
    if len(clean_address) < 5:
        logger.warning(f"[{request_id}] Address too short: '{clean_address}'")
        return {
            "success": False,
            "error": f"Address too short: '{clean_address}'",
            "latitude": None,
            "longitude": None,
            "provider": None,
            "error_type": "address_too_short",
            "request_id": request_id,
        }

    logger.info(f"[{request_id}] Geocoding address: '{clean_address}'")

    # Check cache first
    cached_result = get_cached_coordinates(clean_address)
    if cached_result:
        elapsed_time = time.time() - start_time
        logger.info(
            f"[{request_id}] Cache hit for address: '{clean_address}' ({elapsed_time:.3f}s)"
        )

        # Add request metadata to cached result
        cached_result["request_id"] = request_id
        cached_result["response_time"] = elapsed_time
        cached_result["cache_hit"] = True
        cached_result["total_time"] = elapsed_time

        # Record operation for monitoring
        GeocodingMetrics.record_operation({
            "address": clean_address,
            "provider": cached_result.get("provider", "unknown"),
            "success": cached_result.get("success", True),
            "cache_hit": True,
            "total_time": elapsed_time,
            "timestamp": time.time(),
            "request_id": request_id,
        })

        return cached_result

    logger.info(
        f"[{request_id}] Cache miss for address: '{clean_address}', using providers"
    )

    # If a specific provider is requested, use only that provider
    if provider and provider in GEOCODING_PROVIDERS:
        providers = [provider]
        logger.info(f"[{request_id}] Using specified provider: {provider}")
    else:
        providers = GEOCODING_PROVIDERS
        logger.info(f"[{request_id}] Using provider order: {', '.join(providers)}")

    # Try each provider in order
    result = None
    errors = []
    provider_times = {}

    for provider_name in providers:
        provider_start = time.time()
        try:
            logger.info(f"[{request_id}] Trying provider: {provider_name}")

            if provider_name == "google":
                result = _geocode_google(clean_address)
            elif provider_name == "nominatim":
                result = _geocode_nominatim(clean_address)
            elif provider_name == "mapbox":
                result = _geocode_mapbox(clean_address)
            else:
                logger.warning(
                    f"[{request_id}] Unknown geocoding provider: {provider_name}"
                )
                continue

            provider_elapsed = time.time() - provider_start
            provider_times[provider_name] = provider_elapsed

            if result and result.get("success"):
                # Add timing information
                result["provider_time"] = provider_elapsed
                result["total_time"] = time.time() - start_time
                result["request_id"] = request_id
                result["cache_hit"] = False

                # Cache successful result
                cache_coordinates(clean_address, result)

                # Record operation for monitoring
                GeocodingMetrics.record_operation({
                    "address": clean_address,
                    "provider": provider_name,
                    "success": True,
                    "cache_hit": False,
                    "total_time": result["total_time"],
                    "provider_time": provider_elapsed,
                    "timestamp": time.time(),
                    "request_id": request_id,
                })

                logger.info(
                    f"[{request_id}] Successfully geocoded with {provider_name} in {provider_elapsed:.3f}s"
                )

                # Log metrics summary periodically
                if random.random() < 0.05:  # ~5% of successful operations
                    GeocodingMetrics.log_metrics_summary()

                return result
            else:
                error_type = (
                    result.get("error_type", "unknown_error")
                    if result
                    else "unknown_error"
                )
                error_msg = (
                    result.get("error", "Unknown error") if result else "Unknown error"
                )
                logger.warning(
                    f"[{request_id}] {provider_name} geocoding failed: {error_msg} (type: {error_type}) in {provider_elapsed:.3f}s"
                )
                errors.append(
                    {
                        "provider": provider_name,
                        "error": error_msg,
                        "error_type": error_type,
                        "time": provider_elapsed,
                    }
                )
        except Exception as e:
            provider_elapsed = time.time() - provider_start
            logger.error(
                f"[{request_id}] Unexpected error with {provider_name} geocoding: {str(e)}",
                exc_info=True,
            )
            errors.append(
                {
                    "provider": provider_name,
                    "error": str(e),
                    "error_type": "exception",
                    "exception_type": e.__class__.__name__,
                    "time": provider_elapsed,
                }
            )
            provider_times[provider_name] = provider_elapsed

    # If we get here, all providers failed
    total_time = time.time() - start_time
    error_summary = ", ".join([f"{e['provider']}: {e['error']}" for e in errors])
    logger.error(
        f"[{request_id}] All geocoding providers failed for address: '{clean_address}' in {total_time:.3f}s"
    )
    logger.error(f"[{request_id}] Error details: {error_summary}")

    # Create detailed error response
    error_result = {
        "success": False,
        "error": f"All geocoding providers failed",
        "error_details": errors,
        "latitude": None,
        "longitude": None,
        "provider": None,
        "provider_times": provider_times,
        "total_time": total_time,
        "request_id": request_id,
        "error_type": "all_providers_failed",
        "cache_hit": False,
    }

    # Record operation for monitoring
    GeocodingMetrics.record_operation({
        "address": clean_address,
        "provider": "multiple",
        "success": False,
        "cache_hit": False,
        "total_time": total_time,
        "error_type": "all_providers_failed",
        "timestamp": time.time(),
        "request_id": request_id,
        "provider_times": provider_times,
    })

    return error_result


def _geocode_google(address: str) -> Dict[str, Any]:
    """
    Geocode an address using Google Maps API with improved error handling.

    Args:
        address: The address to geocode

    Returns:
        Dictionary with geocoding results
    """
    if not GOOGLE_MAPS_API_KEY:
        logger.error("Google Maps API key is missing in settings")
        return {
            "success": False,
            "error": "Google Maps API key is missing",
            "latitude": None,
            "longitude": None,
            "provider": "google",
            "error_type": "configuration_error",
        }

    # Set up request parameters
    base_url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": address,
        "key": GOOGLE_MAPS_API_KEY,
    }

    for attempt in range(GEOCODING_MAX_RETRIES):
        try:
            # Make the request to Google Maps API
            logger.debug(
                f"Making Google Maps API request for address: {address} (attempt {attempt+1}/{GEOCODING_MAX_RETRIES})"
            )
            response = requests.get(base_url, params=params, timeout=GEOCODING_TIMEOUT)
            response.raise_for_status()  # Raise exception for HTTP errors

            # Check for empty response
            if not response.text:
                logger.warning(
                    f"Empty response from Google Maps API for address: {address}"
                )
                if attempt < GEOCODING_MAX_RETRIES - 1:
                    time.sleep(
                        GEOCODING_RETRY_DELAY * (2**attempt)
                    )  # Exponential backoff
                    continue
                return {
                    "success": False,
                    "error": "Empty response from API",
                    "latitude": None,
                    "longitude": None,
                    "provider": "google",
                    "error_type": "empty_response",
                }

            # Parse JSON response with better error handling
            try:
                data = json.loads(response.text)
            except json.JSONDecodeError as json_error:
                logger.error(
                    f"JSON parsing error for address '{address}': {str(json_error)}"
                )
                logger.debug(f"Response content: {response.text[:200]}...")

                if attempt < GEOCODING_MAX_RETRIES - 1:
                    time.sleep(
                        GEOCODING_RETRY_DELAY * (2**attempt)
                    )  # Exponential backoff
                    continue

                return {
                    "success": False,
                    "error": f"Invalid JSON response: {str(json_error)}",
                    "latitude": None,
                    "longitude": None,
                    "provider": "google",
                    "error_type": "json_parse_error",
                    "response_sample": response.text[:100] if response.text else None,
                }

            # Check for valid results
            if (
                data.get("status") == "OK"
                and data.get("results")
                and len(data["results"]) > 0
            ):
                try:
                    # Extract location data
                    location = data["results"][0]["geometry"]["location"]

                    # Validate coordinates
                    lat = float(location["lat"])
                    lng = float(location["lng"])

                    # Check for zero coordinates (often indicates an error)
                    if lat == 0 and lng == 0:
                        logger.warning(
                            f"Zero coordinates returned for address: {address}"
                        )
                        if attempt < GEOCODING_MAX_RETRIES - 1:
                            time.sleep(GEOCODING_RETRY_DELAY * (2**attempt))
                            continue
                        return {
                            "success": False,
                            "error": "Zero coordinates returned",
                            "latitude": None,
                            "longitude": None,
                            "provider": "google",
                            "error_type": "zero_coordinates",
                        }

                    # Validate coordinate ranges
                    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                        logger.warning(
                            f"Invalid coordinates for address '{address}': {lat}, {lng}"
                        )
                        return {
                            "success": False,
                            "error": f"Invalid coordinates: {lat}, {lng}",
                            "latitude": None,
                            "longitude": None,
                            "provider": "google",
                            "error_type": "invalid_coordinates",
                        }

                    # Format coordinates with proper precision (6 decimal places)
                    lat_decimal = Decimal(str(lat)).quantize(
                        Decimal("0.000001"), rounding=ROUND_HALF_UP
                    )
                    lng_decimal = Decimal(str(lng)).quantize(
                        Decimal("0.000001"), rounding=ROUND_HALF_UP
                    )

                    # Return successful result
                    logger.info(
                        f"Successfully geocoded address '{address}' with Google Maps: {lat_decimal}, {lng_decimal}"
                    )
                    return {
                        "success": True,
                        "latitude": lat_decimal,
                        "longitude": lng_decimal,
                        "accuracy": data["results"][0]
                        .get("geometry", {})
                        .get("location_type", "APPROXIMATE"),
                        "provider": "google",
                        "formatted_address": data["results"][0].get(
                            "formatted_address", address
                        ),
                    }
                except (KeyError, TypeError, ValueError) as extraction_error:
                    logger.error(
                        f"Error extracting location data for address '{address}': {str(extraction_error)}"
                    )
                    return {
                        "success": False,
                        "error": f"Error extracting location data: {str(extraction_error)}",
                        "latitude": None,
                        "longitude": None,
                        "provider": "google",
                        "error_type": "data_extraction_error",
                    }

            # Handle API error responses
            error_message = data.get("error_message", "No results found")
            status = data.get("status", "UNKNOWN_ERROR")

            # If this is a rate limit error, retry after a delay with exponential backoff
            if status in ["OVER_QUERY_LIMIT", "OVER_DAILY_LIMIT"]:
                if attempt < GEOCODING_MAX_RETRIES - 1:
                    retry_delay = GEOCODING_RETRY_DELAY * (
                        2**attempt
                    )  # Exponential backoff
                    logger.warning(
                        f"Google API rate limit hit for address '{address}', retrying in {retry_delay}s (attempt {attempt+1}/{GEOCODING_MAX_RETRIES})"
                    )
                    time.sleep(retry_delay)
                    continue

            logger.warning(
                f"Google Maps API error for address '{address}': {status} - {error_message}"
            )
            return {
                "success": False,
                "error": f"{status}: {error_message}",
                "latitude": None,
                "longitude": None,
                "provider": "google",
                "error_type": f"api_error_{status.lower()}",
            }

        except requests.exceptions.Timeout:
            logger.warning(f"Google Maps API request timed out for address '{address}'")
            if attempt < GEOCODING_MAX_RETRIES - 1:
                retry_delay = GEOCODING_RETRY_DELAY * (
                    2**attempt
                )  # Exponential backoff
                logger.warning(
                    f"Retrying in {retry_delay}s (attempt {attempt+1}/{GEOCODING_MAX_RETRIES})"
                )
                time.sleep(retry_delay)
                continue
            return {
                "success": False,
                "error": "Request timed out",
                "latitude": None,
                "longitude": None,
                "provider": "google",
                "error_type": "timeout",
            }
        except requests.exceptions.HTTPError as http_error:
            logger.error(f"HTTP error for address '{address}': {str(http_error)}")
            return {
                "success": False,
                "error": f"HTTP error: {str(http_error)}",
                "latitude": None,
                "longitude": None,
                "provider": "google",
                "error_type": "http_error",
                "status_code": getattr(http_error.response, "status_code", None),
            }
        except requests.exceptions.ConnectionError as conn_error:
            logger.error(f"Connection error for address '{address}': {str(conn_error)}")
            if attempt < GEOCODING_MAX_RETRIES - 1:
                retry_delay = GEOCODING_RETRY_DELAY * (
                    2**attempt
                )  # Exponential backoff
                logger.warning(
                    f"Retrying in {retry_delay}s (attempt {attempt+1}/{GEOCODING_MAX_RETRIES})"
                )
                time.sleep(retry_delay)
                continue
            return {
                "success": False,
                "error": f"Connection error: {str(conn_error)}",
                "latitude": None,
                "longitude": None,
                "provider": "google",
                "error_type": "connection_error",
            }
        except Exception as e:
            logger.error(
                f"Unexpected error geocoding address '{address}' with Google Maps: {str(e)}",
                exc_info=True,
            )
            return {
                "success": False,
                "error": f"Geocoding error: {str(e)}",
                "latitude": None,
                "longitude": None,
                "provider": "google",
                "error_type": "unexpected_error",
                "error_class": e.__class__.__name__,
            }


def _geocode_nominatim(address: str) -> Dict[str, Any]:
    """
    Geocode an address using Nominatim (OpenStreetMap) with improved error handling.

    Args:
        address: The address to geocode

    Returns:
        Dictionary with geocoding results
    """
    for attempt in range(GEOCODING_MAX_RETRIES):
        try:
            # Initialize Nominatim geocoder with a unique user agent
            logger.debug(
                f"Making Nominatim request for address: {address} (attempt {attempt+1}/{GEOCODING_MAX_RETRIES})"
            )
            geolocator = Nominatim(
                user_agent="payshift_app/1.0", timeout=GEOCODING_TIMEOUT
            )

            # Try to geocode the location
            location = geolocator.geocode(address)

            if location:
                try:
                    # Validate coordinates
                    lat = float(location.latitude)
                    lng = float(location.longitude)

                    # Check for zero coordinates (often indicates an error)
                    if lat == 0 and lng == 0:
                        logger.warning(
                            f"Zero coordinates returned from Nominatim for address: {address}"
                        )
                        if attempt < GEOCODING_MAX_RETRIES - 1:
                            time.sleep(
                                GEOCODING_RETRY_DELAY * (2**attempt)
                            )  # Exponential backoff
                            continue
                        return {
                            "success": False,
                            "error": "Zero coordinates returned",
                            "latitude": None,
                            "longitude": None,
                            "provider": "nominatim",
                            "error_type": "zero_coordinates",
                        }

                    # Validate coordinate ranges
                    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                        logger.warning(
                            f"Invalid coordinates from Nominatim for address '{address}': {lat}, {lng}"
                        )
                        return {
                            "success": False,
                            "error": f"Invalid coordinates: {lat}, {lng}",
                            "latitude": None,
                            "longitude": None,
                            "provider": "nominatim",
                            "error_type": "invalid_coordinates",
                        }

                    # Format coordinates with proper precision (6 decimal places)
                    lat_decimal = Decimal(str(lat)).quantize(
                        Decimal("0.000001"), rounding=ROUND_HALF_UP
                    )
                    lng_decimal = Decimal(str(lng)).quantize(
                        Decimal("0.000001"), rounding=ROUND_HALF_UP
                    )

                    logger.info(
                        f"Successfully geocoded address '{address}' with Nominatim: {lat_decimal}, {lng_decimal}"
                    )
                    return {
                        "success": True,
                        "latitude": lat_decimal,
                        "longitude": lng_decimal,
                        "accuracy": "APPROXIMATE",  # Nominatim doesn't provide accuracy info
                        "provider": "nominatim",
                        "formatted_address": location.address,
                    }
                except (AttributeError, TypeError, ValueError) as extraction_error:
                    logger.error(
                        f"Error extracting Nominatim location data for address '{address}': {str(extraction_error)}"
                    )
                    return {
                        "success": False,
                        "error": f"Error extracting location data: {str(extraction_error)}",
                        "latitude": None,
                        "longitude": None,
                        "provider": "nominatim",
                        "error_type": "data_extraction_error",
                    }
            else:
                logger.warning(
                    f"No results found from Nominatim for address: {address}"
                )
                return {
                    "success": False,
                    "error": "No results found",
                    "latitude": None,
                    "longitude": None,
                    "provider": "nominatim",
                    "error_type": "no_results",
                }
        except GeocoderTimedOut:
            logger.warning(f"Nominatim request timed out for address: {address}")
            if attempt < GEOCODING_MAX_RETRIES - 1:
                retry_delay = GEOCODING_RETRY_DELAY * (
                    2**attempt
                )  # Exponential backoff
                logger.warning(
                    f"Retrying in {retry_delay}s (attempt {attempt+1}/{GEOCODING_MAX_RETRIES})"
                )
                time.sleep(retry_delay)
                continue
            return {
                "success": False,
                "error": "Geocoder timed out",
                "latitude": None,
                "longitude": None,
                "provider": "nominatim",
                "error_type": "timeout",
            }
        except GeocoderUnavailable as unavailable_error:
            logger.error(
                f"Nominatim service unavailable for address '{address}': {str(unavailable_error)}"
            )
            if attempt < GEOCODING_MAX_RETRIES - 1:
                retry_delay = GEOCODING_RETRY_DELAY * (
                    2**attempt
                )  # Exponential backoff
                logger.warning(
                    f"Retrying in {retry_delay}s (attempt {attempt+1}/{GEOCODING_MAX_RETRIES})"
                )
                time.sleep(retry_delay)
                continue
            return {
                "success": False,
                "error": f"Geocoder unavailable: {str(unavailable_error)}",
                "latitude": None,
                "longitude": None,
                "provider": "nominatim",
                "error_type": "service_unavailable",
            }
        except GeocoderServiceError as service_error:
            logger.error(
                f"Nominatim service error for address '{address}': {str(service_error)}"
            )
            if attempt < GEOCODING_MAX_RETRIES - 1:
                retry_delay = GEOCODING_RETRY_DELAY * (
                    2**attempt
                )  # Exponential backoff
                logger.warning(
                    f"Retrying in {retry_delay}s (attempt {attempt+1}/{GEOCODING_MAX_RETRIES})"
                )
                time.sleep(retry_delay)
                continue
            return {
                "success": False,
                "error": f"Geocoder service error: {str(service_error)}",
                "latitude": None,
                "longitude": None,
                "provider": "nominatim",
                "error_type": "service_error",
            }
        except Exception as e:
            logger.error(
                f"Unexpected error geocoding address '{address}' with Nominatim: {str(e)}",
                exc_info=True,
            )
            return {
                "success": False,
                "error": f"Nominatim geocoding error: {str(e)}",
                "latitude": None,
                "longitude": None,
                "provider": "nominatim",
                "error_type": "unexpected_error",
                "error_class": e.__class__.__name__,
            }


def _geocode_mapbox(address: str) -> Dict[str, Any]:
    """
    Geocode an address using Mapbox API with improved error handling.

    Args:
        address: The address to geocode

    Returns:
        Dictionary with geocoding results
    """
    if not MAPBOX_API_KEY:
        logger.error("Mapbox API key is missing in settings")
        return {
            "success": False,
            "error": "Mapbox API key is missing",
            "latitude": None,
            "longitude": None,
            "provider": "mapbox",
            "error_type": "configuration_error",
        }

    # Set up request parameters
    base_url = "https://api.mapbox.com/geocoding/v5/mapbox.places/"
    url = f"{base_url}{address}.json"
    params = {
        "access_token": MAPBOX_API_KEY,
        "limit": 1,
    }

    for attempt in range(GEOCODING_MAX_RETRIES):
        try:
            # Make the request to Mapbox API
            logger.debug(
                f"Making Mapbox API request for address: {address} (attempt {attempt+1}/{GEOCODING_MAX_RETRIES})"
            )
            response = requests.get(url, params=params, timeout=GEOCODING_TIMEOUT)
            response.raise_for_status()

            # Check for empty response
            if not response.text:
                logger.warning(f"Empty response from Mapbox API for address: {address}")
                if attempt < GEOCODING_MAX_RETRIES - 1:
                    time.sleep(
                        GEOCODING_RETRY_DELAY * (2**attempt)
                    )  # Exponential backoff
                    continue
                return {
                    "success": False,
                    "error": "Empty response from API",
                    "latitude": None,
                    "longitude": None,
                    "provider": "mapbox",
                    "error_type": "empty_response",
                }

            # Parse JSON response with better error handling
            try:
                data = json.loads(response.text)
            except json.JSONDecodeError as json_error:
                logger.error(
                    f"JSON parsing error for address '{address}': {str(json_error)}"
                )
                logger.debug(f"Response content: {response.text[:200]}...")

                if attempt < GEOCODING_MAX_RETRIES - 1:
                    time.sleep(
                        GEOCODING_RETRY_DELAY * (2**attempt)
                    )  # Exponential backoff
                    continue

                return {
                    "success": False,
                    "error": f"Invalid JSON response: {str(json_error)}",
                    "latitude": None,
                    "longitude": None,
                    "provider": "mapbox",
                    "error_type": "json_parse_error",
                    "response_sample": response.text[:100] if response.text else None,
                }

            # Check for valid results
            if data.get("features") and len(data["features"]) > 0:
                try:
                    # Extract location data
                    feature = data["features"][0]
                    coordinates = feature["geometry"]["coordinates"]

                    # Mapbox returns [longitude, latitude]
                    lng = float(coordinates[0])
                    lat = float(coordinates[1])

                    # Check for zero coordinates (often indicates an error)
                    if lat == 0 and lng == 0:
                        logger.warning(
                            f"Zero coordinates returned from Mapbox for address: {address}"
                        )
                        if attempt < GEOCODING_MAX_RETRIES - 1:
                            time.sleep(
                                GEOCODING_RETRY_DELAY * (2**attempt)
                            )  # Exponential backoff
                            continue
                        return {
                            "success": False,
                            "error": "Zero coordinates returned",
                            "latitude": None,
                            "longitude": None,
                            "provider": "mapbox",
                            "error_type": "zero_coordinates",
                        }

                    # Validate coordinate ranges
                    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                        logger.warning(
                            f"Invalid coordinates from Mapbox for address '{address}': {lat}, {lng}"
                        )
                        return {
                            "success": False,
                            "error": f"Invalid coordinates: {lat}, {lng}",
                            "latitude": None,
                            "longitude": None,
                            "provider": "mapbox",
                            "error_type": "invalid_coordinates",
                        }

                    # Format coordinates with proper precision (6 decimal places)
                    lat_decimal = Decimal(str(lat)).quantize(
                        Decimal("0.000001"), rounding=ROUND_HALF_UP
                    )
                    lng_decimal = Decimal(str(lng)).quantize(
                        Decimal("0.000001"), rounding=ROUND_HALF_UP
                    )

                    logger.info(
                        f"Successfully geocoded address '{address}' with Mapbox: {lat_decimal}, {lng_decimal}"
                    )
                    return {
                        "success": True,
                        "latitude": lat_decimal,
                        "longitude": lng_decimal,
                        "accuracy": "APPROXIMATE",  # Mapbox doesn't provide accuracy info in the same way
                        "provider": "mapbox",
                        "formatted_address": feature.get("place_name", address),
                    }
                except (
                    KeyError,
                    TypeError,
                    ValueError,
                    IndexError,
                ) as extraction_error:
                    logger.error(
                        f"Error extracting Mapbox location data for address '{address}': {str(extraction_error)}"
                    )
                    return {
                        "success": False,
                        "error": f"Error extracting location data: {str(extraction_error)}",
                        "latitude": None,
                        "longitude": None,
                        "provider": "mapbox",
                        "error_type": "data_extraction_error",
                    }
            else:
                logger.warning(f"No results found from Mapbox for address: {address}")
                return {
                    "success": False,
                    "error": "No results found",
                    "latitude": None,
                    "longitude": None,
                    "provider": "mapbox",
                    "error_type": "no_results",
                }
        except requests.exceptions.Timeout:
            logger.warning(f"Mapbox API request timed out for address: {address}")
            if attempt < GEOCODING_MAX_RETRIES - 1:
                retry_delay = GEOCODING_RETRY_DELAY * (
                    2**attempt
                )  # Exponential backoff
                logger.warning(
                    f"Retrying in {retry_delay}s (attempt {attempt+1}/{GEOCODING_MAX_RETRIES})"
                )
                time.sleep(retry_delay)
                continue
            return {
                "success": False,
                "error": "Request timed out",
                "latitude": None,
                "longitude": None,
                "provider": "mapbox",
                "error_type": "timeout",
            }
        except requests.exceptions.HTTPError as http_error:
            logger.error(f"HTTP error for address '{address}': {str(http_error)}")
            # Check for rate limiting (429) or server errors (5xx)
            status_code = getattr(http_error.response, "status_code", 0)
            if (
                status_code in [429, 500, 502, 503, 504]
                and attempt < GEOCODING_MAX_RETRIES - 1
            ):
                retry_delay = GEOCODING_RETRY_DELAY * (
                    2**attempt
                )  # Exponential backoff
                logger.warning(
                    f"Retrying in {retry_delay}s (attempt {attempt+1}/{GEOCODING_MAX_RETRIES})"
                )
                time.sleep(retry_delay)
                continue
            return {
                "success": False,
                "error": f"HTTP error: {str(http_error)}",
                "latitude": None,
                "longitude": None,
                "provider": "mapbox",
                "error_type": "http_error",
                "status_code": status_code,
            }
        except requests.exceptions.ConnectionError as conn_error:
            logger.error(f"Connection error for address '{address}': {str(conn_error)}")
            if attempt < GEOCODING_MAX_RETRIES - 1:
                retry_delay = GEOCODING_RETRY_DELAY * (
                    2**attempt
                )  # Exponential backoff
                logger.warning(
                    f"Retrying in {retry_delay}s (attempt {attempt+1}/{GEOCODING_MAX_RETRIES})"
                )
                time.sleep(retry_delay)
                continue
            return {
                "success": False,
                "error": f"Connection error: {str(conn_error)}",
                "latitude": None,
                "longitude": None,
                "provider": "mapbox",
                "error_type": "connection_error",
            }
        except Exception as e:
            logger.error(
                f"Unexpected error geocoding address '{address}' with Mapbox: {str(e)}",
                exc_info=True,
            )
            return {
                "success": False,
                "error": f"Geocoding error: {str(e)}",
                "latitude": None,
                "longitude": None,
                "provider": "mapbox",
                "error_type": "unexpected_error",
                "error_class": e.__class__.__name__,
            }

"""
Monitoring module for system health and cache statistics.

This module provides views for monitoring system health and cache statistics.
"""

import json
import logging
import os
import platform
import sys
import time
from typing import Dict, List, Optional, Union

from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.core.cache import cache
from django.http import HttpRequest, JsonResponse
from django.utils import timezone

logger = logging.getLogger(__name__)


def is_staff_or_superuser(user):
    """Check if user is staff or superuser."""
    return user.is_authenticated and (user.is_staff or user.is_superuser)


@user_passes_test(is_staff_or_superuser)
def cache_stats_view(request: HttpRequest) -> JsonResponse:
    """
    View for cache statistics.

    Args:
        request: HTTP request

    Returns:
        JSON response with cache statistics
    """
    try:
        # Get cache statistics
        stats = get_cache_stats()
        
        # Add additional information
        stats["timestamp"] = timezone.now().isoformat()
        stats["cache_backend"] = settings.CACHES["default"]["BACKEND"]
        stats["cache_location"] = settings.CACHES["default"].get("LOCATION", "N/A")
        
        return JsonResponse(stats)
    except Exception as e:
        logger.error(f"Error getting cache statistics: {str(e)}")
        return JsonResponse(
            {"error": f"Error getting cache statistics: {str(e)}"}, status=500
        )


@user_passes_test(is_staff_or_superuser)
def clear_cache_view(request: HttpRequest) -> JsonResponse:
    """
    View for clearing the cache.

    Args:
        request: HTTP request

    Returns:
        JSON response with result
    """
    try:
        # Clear the cache
        cache.clear()
        
        return JsonResponse({"message": "Cache cleared successfully"})
    except Exception as e:
        logger.error(f"Error clearing cache: {str(e)}")
        return JsonResponse(
            {"error": f"Error clearing cache: {str(e)}"}, status=500
        )


@user_passes_test(is_staff_or_superuser)
def system_health_view(request: HttpRequest) -> JsonResponse:
    """
    View for system health.

    Args:
        request: HTTP request

    Returns:
        JSON response with system health information
    """
    try:
        # Get system information
        system_info = {
            "timestamp": timezone.now().isoformat(),
            "python_version": sys.version,
            "platform": platform.platform(),
            "hostname": platform.node(),
            "cpu_count": os.cpu_count(),
            "memory_usage": get_memory_usage(),
            "disk_usage": get_disk_usage(),
            "uptime": get_uptime(),
        }
        
        # Check database connection
        db_status = check_database_connection()
        system_info["database"] = db_status
        
        # Check cache connection
        cache_status = check_cache_connection()
        system_info["cache"] = cache_status
        
        # Overall status
        system_info["status"] = "healthy" if db_status["connected"] and cache_status["connected"] else "unhealthy"
        
        return JsonResponse(system_info)
    except Exception as e:
        logger.error(f"Error getting system health: {str(e)}")
        return JsonResponse(
            {"error": f"Error getting system health: {str(e)}"}, status=500
        )


def get_cache_stats() -> Dict[str, Union[int, float, str]]:
    """
    Get cache statistics.

    Returns:
        Dictionary with cache statistics
    """
    # This is a placeholder - in a real implementation, you would
    # get actual statistics from Redis
    return {
        "hits": 0,
        "misses": 0,
        "hit_rate": 0,
        "size": 0,
        "keys_count": 0,
    }


def get_memory_usage() -> Dict[str, Union[int, float, str]]:
    """
    Get memory usage.

    Returns:
        Dictionary with memory usage information
    """
    # This is a placeholder - in a real implementation, you would
    # get actual memory usage information
    return {
        "total": "N/A",
        "used": "N/A",
        "free": "N/A",
        "percent": "N/A",
    }


def get_disk_usage() -> Dict[str, Union[int, float, str]]:
    """
    Get disk usage.

    Returns:
        Dictionary with disk usage information
    """
    # This is a placeholder - in a real implementation, you would
    # get actual disk usage information
    return {
        "total": "N/A",
        "used": "N/A",
        "free": "N/A",
        "percent": "N/A",
    }


def get_uptime() -> Dict[str, Union[int, float, str]]:
    """
    Get system uptime.

    Returns:
        Dictionary with uptime information
    """
    # This is a placeholder - in a real implementation, you would
    # get actual uptime information
    return {
        "days": "N/A",
        "hours": "N/A",
        "minutes": "N/A",
        "seconds": "N/A",
    }


def check_database_connection() -> Dict[str, Union[bool, str]]:
    """
    Check database connection.

    Returns:
        Dictionary with database connection status
    """
    try:
        from django.db import connection
        
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
        
        return {
            "connected": True,
            "message": "Database connection successful",
            "engine": connection.vendor,
        }
    except Exception as e:
        logger.error(f"Error connecting to database: {str(e)}")
        return {
            "connected": False,
            "message": f"Error connecting to database: {str(e)}",
            "engine": "N/A",
        }


def check_cache_connection() -> Dict[str, Union[bool, str]]:
    """
    Check cache connection.

    Returns:
        Dictionary with cache connection status
    """
    try:
        # Try to set and get a value from the cache
        test_key = "cache_connection_test"
        test_value = f"test_{time.time()}"
        
        cache.set(test_key, test_value, 10)
        retrieved_value = cache.get(test_key)
        
        if retrieved_value == test_value:
            return {
                "connected": True,
                "message": "Cache connection successful",
                "backend": settings.CACHES["default"]["BACKEND"],
            }
        else:
            return {
                "connected": False,
                "message": "Cache connection failed: value mismatch",
                "backend": settings.CACHES["default"]["BACKEND"],
            }
    except Exception as e:
        logger.error(f"Error connecting to cache: {str(e)}")
        return {
            "connected": False,
            "message": f"Error connecting to cache: {str(e)}",
            "backend": settings.CACHES["default"]["BACKEND"] if hasattr(settings, "CACHES") else "N/A",
        }

"""
Core monitoring module for the entire application.

This module provides monitoring endpoints and utilities for the application,
including cache statistics, performance metrics, and system health.
"""

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from core.cache import get_cache_stats, invalidate_cache_pattern

logger = logging.getLogger(__name__)


@staff_member_required
@never_cache
@require_GET
def cache_stats_view(request):
    """
    View function for displaying cache statistics.

    This endpoint is only accessible to staff members and provides detailed
    statistics about the Redis cache.
    """
    # Get cache statistics
    cache_stats = get_cache_stats()

    # Prepare the response
    response_data = {
        "cache_stats": cache_stats,
        "timestamp": datetime.now().isoformat(),
    }

    return JsonResponse(response_data)


@staff_member_required
@require_GET
def clear_cache_view(request):
    """
    View function for clearing the Redis cache.

    This endpoint is only accessible to staff members and clears all
    or specific types of cache entries.
    """
    cache_type = request.GET.get("type", "all")

    try:
        if cache_type == "all":
            # Clear all cache entries
            total_cleared = invalidate_cache_pattern("*")
            message = f"Cleared {total_cleared} cache entries"
        else:
            # Clear specific type of cache entries
            from core.cache import CACHE_PREFIXES

            prefix = CACHE_PREFIXES.get(cache_type)
            if prefix:
                total_cleared = invalidate_cache_pattern(f"{prefix}*")
                message = f"Cleared {total_cleared} {cache_type} cache entries"
            else:
                return JsonResponse(
                    {
                        "success": False,
                        "error": f"Unknown cache type: {cache_type}",
                        "valid_types": list(CACHE_PREFIXES.keys()),
                        "timestamp": datetime.now().isoformat(),
                    },
                    status=400,
                )

        return JsonResponse(
            {
                "success": True,
                "message": message,
                "cache_type": cache_type,
                "entries_cleared": total_cleared,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        logger.error(f"Error clearing cache: {str(e)}")
        return JsonResponse(
            {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            },
            status=500,
        )


@staff_member_required
@never_cache
@require_GET
def system_health_view(request):
    """
    View function for displaying system health information.

    This endpoint is only accessible to staff members and provides information
    about the system's health, including Redis, database, and API status.
    """
    from django.db import connection
    from django.db.utils import OperationalError

    health_data = {
        "status": "healthy",
        "components": {},
        "timestamp": datetime.now().isoformat(),
    }

    # Check Redis health
    try:
        from core.cache import redis_client

        if redis_client and redis_client.ping():
            redis_info = redis_client.info()
            health_data["components"]["redis"] = {
                "status": "healthy",
                "version": redis_info.get("redis_version", "unknown"),
                "uptime_seconds": redis_info.get("uptime_in_seconds", 0),
                "connected_clients": redis_info.get("connected_clients", 0),
            }
        else:
            health_data["components"]["redis"] = {
                "status": "unhealthy",
                "error": "Redis connection failed",
            }
            health_data["status"] = "degraded"
    except Exception as e:
        health_data["components"]["redis"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        health_data["status"] = "degraded"

    # Check database health
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            health_data["components"]["database"] = {
                "status": "healthy",
                "backend": connection.vendor,
            }
    except OperationalError as e:
        health_data["components"]["database"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        health_data["status"] = "critical"
    except Exception as e:
        health_data["components"]["database"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        health_data["status"] = "critical"

    # Check API health (simplified)
    health_data["components"]["api"] = {
        "status": "healthy",
    }

    return JsonResponse(health_data)

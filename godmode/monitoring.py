"""
Monitoring module for the jobs application.

This module provides endpoints and utilities for monitoring the application,
including cache statistics, geocoding performance, and system health.
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from jobs.geocoding import geocode_address
from jobs.geocoding_cache import clear_geocoding_cache, get_cache_stats

logger = logging.getLogger(__name__)

# In-memory storage for recent geocoding operations
# Limited to 1000 entries to avoid memory issues
_recent_geocoding_operations = []
_MAX_RECENT_OPERATIONS = 1000


def record_geocoding_operation(operation_data: Dict[str, Any]) -> None:
    """
    Record a geocoding operation for monitoring purposes.

    Args:
        operation_data: Data about the geocoding operation
    """
    global _recent_geocoding_operations

    # Add timestamp if not present
    if "timestamp" not in operation_data:
        operation_data["timestamp"] = datetime.now().isoformat()

    # Add to the beginning of the list
    _recent_geocoding_operations.insert(0, operation_data)

    # Limit the size of the list
    if len(_recent_geocoding_operations) > _MAX_RECENT_OPERATIONS:
        _recent_geocoding_operations = _recent_geocoding_operations[
            :_MAX_RECENT_OPERATIONS
        ]


@staff_member_required
@never_cache
@require_GET
def geocoding_stats_view(request):
    """
    View function for displaying geocoding statistics.

    This endpoint is only accessible to staff members and provides detailed
    statistics about the geocoding cache and recent operations.
    """
    # Get cache statistics
    cache_stats = get_cache_stats()

    # Get recent operations (last 100)
    recent_operations = _recent_geocoding_operations[:100]

    # Calculate success rate
    total_ops = len(_recent_geocoding_operations)
    successful_ops = sum(
        1 for op in _recent_geocoding_operations if op.get("success", False)
    )
    success_rate = (successful_ops / total_ops * 100) if total_ops > 0 else 0

    # Calculate provider distribution
    provider_counts = {}
    for op in _recent_geocoding_operations:
        provider = op.get("provider", "unknown")
        if provider in provider_counts:
            provider_counts[provider] += 1
        else:
            provider_counts[provider] = 1

    # Calculate cache hit rate
    cache_hits = sum(
        1 for op in _recent_geocoding_operations if op.get("cache_hit", False)
    )
    cache_hit_rate = (cache_hits / total_ops * 100) if total_ops > 0 else 0

    # Calculate average response time
    response_times = [
        op.get("total_time", 0)
        for op in _recent_geocoding_operations
        if "total_time" in op
    ]
    avg_response_time = (
        sum(response_times) / len(response_times) if response_times else 0
    )

    # Prepare the response
    response_data = {
        "cache_stats": cache_stats,
        "geocoding_stats": {
            "total_operations": total_ops,
            "successful_operations": successful_ops,
            "success_rate": round(success_rate, 2),
            "cache_hit_rate": round(cache_hit_rate, 2),
            "average_response_time": round(avg_response_time, 3),
            "provider_distribution": provider_counts,
        },
        "recent_operations": recent_operations,
        "timestamp": datetime.now().isoformat(),
    }

    return JsonResponse(response_data)


@staff_member_required
@require_GET
def clear_cache_view(request):
    """
    View function for clearing the geocoding cache.

    This endpoint is only accessible to staff members and clears all
    entries from the geocoding cache.
    """
    try:
        clear_geocoding_cache()
        return JsonResponse(
            {
                "success": True,
                "message": "Geocoding cache cleared successfully",
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        logger.error(f"Error clearing geocoding cache: {str(e)}")
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
def test_geocoding_view(request):
    """
    View function for testing geocoding with different providers.

    This endpoint is only accessible to staff members and allows testing
    geocoding with different providers and addresses.
    """
    address = request.GET.get("address", "")
    provider = request.GET.get("provider", None)

    if not address:
        return JsonResponse(
            {
                "success": False,
                "error": "Address parameter is required",
                "timestamp": datetime.now().isoformat(),
            },
            status=400,
        )

    try:
        start_time = time.time()
        result = geocode_address(address, provider)
        elapsed_time = time.time() - start_time

        # Record the operation for monitoring
        operation_data = {
            "address": address,
            "provider": result.get("provider", provider),
            "success": result.get("success", False),
            "cache_hit": result.get("cache_hit", False),
            "total_time": elapsed_time,
            "timestamp": datetime.now().isoformat(),
            "request_id": result.get("request_id", ""),
        }
        record_geocoding_operation(operation_data)

        # Add elapsed time to the result
        result["elapsed_time"] = elapsed_time

        return JsonResponse(result)
    except Exception as e:
        logger.error(f"Error testing geocoding: {str(e)}")
        return JsonResponse(
            {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            },
            status=500,
        )

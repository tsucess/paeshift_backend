"""
Redis admin module.

This module provides admin views for monitoring Redis cache health and performance.
"""

import json
import logging
from datetime import datetime

from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import path
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.redis.client import redis_client
from core.redis.monitoring import (
    get_cache_stats,
    get_dashboard_data,
    analyze_key_size,
    check_alerts,
    trigger_alert,
)
from core.redis.settings import CACHE_ENABLED
from core.redis.telemetry import (
    get_slow_operations,
    analyze_slow_operations,
)
from core.redis.warming import (
    warm_cache,
    warm_critical_models,
)

# Set up logging
logger = logging.getLogger(__name__)


@staff_member_required
def redis_dashboard_view(request):
    """
    Render the Redis dashboard.
    """
    if not CACHE_ENABLED:
        return render(
            request,
            "admin/error.html",
            {"title": "Redis Error", "error": "Redis cache is disabled"},
        )

    # Get initial stats
    try:
        stats = get_cache_stats()
    except Exception as e:
        logger.error(f"Error getting Redis stats: {str(e)}")
        stats = {"error": str(e)}

    context = {
        "title": "Redis Dashboard",
        "stats": stats,
        "timestamp": timezone.now().isoformat(),
    }

    return render(request, "admin/redis_dashboard.html", context)


@staff_member_required
def redis_dashboard_api(request):
    """
    API endpoint to get Redis dashboard data.
    """
    try:
        # Get dashboard data
        data = get_dashboard_data()
        return JsonResponse(data)
    except Exception as e:
        logger.error(f"Error getting Redis dashboard data: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


@staff_member_required
def redis_stats_api(request):
    """
    API endpoint to get Redis cache statistics.
    """
    try:
        # Get Redis stats
        stats = get_cache_stats()

        # Get largest keys
        largest_keys = analyze_key_size("*", 100)

        # Add largest keys to stats
        stats["largest_keys"] = largest_keys

        return JsonResponse(stats)
    except Exception as e:
        logger.error(f"Error getting Redis stats: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


@staff_member_required
def redis_slow_operations_api(request):
    """
    API endpoint to get slow Redis operations.
    """
    try:
        # Get days parameter
        days = int(request.GET.get("days", 1))

        # Get slow operations
        slow_operations = get_slow_operations(days)

        # Analyze slow operations
        analysis = analyze_slow_operations(days)

        return JsonResponse({
            "slow_operations": slow_operations,
            "analysis": analysis,
        })
    except Exception as e:
        logger.error(f"Error getting slow Redis operations: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


@staff_member_required
@require_POST
@csrf_exempt
def redis_warm_cache_api(request):
    """
    API endpoint to warm the Redis cache.
    """
    try:
        # Get type parameter
        warm_type = request.POST.get("type", "full")

        if warm_type == "critical":
            # Warm critical models
            result = warm_critical_models()
        else:
            # Warm full cache
            result = warm_cache()

        return JsonResponse({
            "success": True,
            "message": f"Cache warming ({warm_type}) completed successfully",
            "result": result,
        })
    except Exception as e:
        logger.error(f"Error warming Redis cache: {str(e)}")
        return JsonResponse({
            "success": False,
            "error": str(e),
        }, status=500)


@staff_member_required
@require_POST
@csrf_exempt
def redis_clear_cache_api(request):
    """
    API endpoint to clear the Redis cache.
    """
    try:
        # Get pattern parameter
        pattern = request.POST.get("pattern", "*")

        # Clear cache
        if not redis_client:
            return JsonResponse({
                "success": False,
                "error": "Redis client not available",
            }, status=500)

        # Get keys matching pattern
        keys = redis_client.keys(pattern)
        if not keys:
            return JsonResponse({
                "success": True,
                "message": f"No keys found matching pattern {pattern}",
                "count": 0,
            })

        # Delete keys
        count = redis_client.delete(*keys)

        return JsonResponse({
            "success": True,
            "message": f"Cleared {count} keys matching pattern {pattern}",
            "count": count,
        })
    except Exception as e:
        logger.error(f"Error clearing Redis cache: {str(e)}")
        return JsonResponse({
            "success": False,
            "error": str(e),
        }, status=500)


@staff_member_required
@require_POST
@csrf_exempt
def redis_optimize_memory_api(request):
    """
    API endpoint to optimize Redis memory usage.
    """
    try:
        if not redis_client:
            return JsonResponse({
                "success": False,
                "error": "Redis client not available",
            }, status=500)

        # Run memory optimization
        redis_client.config_set("maxmemory-policy", "volatile-lru")
        redis_client.config_set("activedefrag", "yes")

        return JsonResponse({
            "success": True,
            "message": "Memory optimization started",
        })
    except Exception as e:
        logger.error(f"Error optimizing Redis memory: {str(e)}")
        return JsonResponse({
            "success": False,
            "error": str(e),
        }, status=500)


class RedisAdmin(admin.ModelAdmin):
    """
    Redis admin interface.
    """

    def get_urls(self):
        """
        Get admin URLs.
        """
        urls = super().get_urls()
        custom_urls = [
            path(
                "redis/dashboard/",
                self.admin_site.admin_view(redis_dashboard_view),
                name="redis_dashboard",
            ),
            path(
                "redis/dashboard/api/",
                self.admin_site.admin_view(redis_dashboard_api),
                name="redis_dashboard_api",
            ),
            path(
                "redis/stats/api/",
                self.admin_site.admin_view(redis_stats_api),
                name="redis_stats_api",
            ),
            path(
                "redis/slow-operations/api/",
                self.admin_site.admin_view(redis_slow_operations_api),
                name="redis_slow_operations_api",
            ),
            path(
                "redis/warm-cache/api/",
                self.admin_site.admin_view(redis_warm_cache_api),
                name="redis_warm_cache_api",
            ),
            path(
                "redis/clear-cache/api/",
                self.admin_site.admin_view(redis_clear_cache_api),
                name="redis_clear_cache_api",
            ),
            path(
                "redis/optimize-memory/api/",
                self.admin_site.admin_view(redis_optimize_memory_api),
                name="redis_optimize_memory_api",
            ),
        ]
        return custom_urls + urls

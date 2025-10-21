"""
Redis monitoring views for the God Mode dashboard.

This module provides views for monitoring Redis cache health and performance.
"""

import json
import logging
from datetime import datetime

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.cache import get_cache_stats, redis_client
from core.management.commands.warm_model_cache import Command as WarmCacheCommand
from core.redis_settings import REDIS_DB_CACHE, get_redis_connection_params

logger = logging.getLogger(__name__)


@staff_member_required
def redis_monitor_view(request):
    """
    Render the Redis monitor dashboard.
    """
    return render(request, "godmode/redis_monitor.html")


@staff_member_required
def redis_stats_api(request):
    """
    API endpoint to get Redis cache statistics.
    """
    try:
        # Get Redis stats
        stats = get_cache_stats()

        # Get largest keys
        largest_keys = _get_largest_keys(10)

        # Add largest keys to stats
        stats["largest_keys"] = largest_keys

        return JsonResponse(stats)
    except Exception as e:
        logger.error(f"Error getting Redis stats: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


@staff_member_required
@require_POST
@csrf_exempt
def warm_cache_api(request):
    """
    API endpoint to warm the Redis cache.
    """
    try:
        # Parse request body
        data = json.loads(request.body)
        models = data.get("models", [])

        if not models:
            return JsonResponse(
                {"error": "No models specified for cache warming"}, status=400
            )

        # Run cache warming command
        command = WarmCacheCommand()
        command.handle(models=models, limit=1000, recent=True, days=7, batch_size=100)

        return JsonResponse(
            {"message": f"Cache warmed for {len(models)} models", "models": models}
        )
    except Exception as e:
        logger.error(f"Error warming cache: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


@staff_member_required
@require_POST
@csrf_exempt
def clear_cache_api(request):
    """
    API endpoint to clear the Redis cache.
    """
    try:
        # Get Redis connection
        connection_params = get_redis_connection_params(REDIS_DB_CACHE)
        redis = redis_client

        # Get key count before clearing
        key_count = redis.dbsize()

        # Clear all keys
        redis.flushdb()

        return JsonResponse(
            {"message": f"Cleared {key_count} keys from Redis cache"}
        )
    except Exception as e:
        logger.error(f"Error clearing cache: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


@staff_member_required
@require_POST
@csrf_exempt
def delete_key_api(request):
    """
    API endpoint to delete a specific key from Redis.
    """
    try:
        # Parse request body
        data = json.loads(request.body)
        key = data.get("key")

        if not key:
            return JsonResponse({"error": "No key specified for deletion"}, status=400)

        # Delete key
        deleted = redis_client.delete(key)

        if deleted:
            return JsonResponse({"message": f"Key '{key}' deleted successfully"})
        else:
            return JsonResponse({"message": f"Key '{key}' not found"}, status=404)
    except Exception as e:
        logger.error(f"Error deleting key: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


def _get_largest_keys(limit=10):
    """
    Get the largest keys in Redis by memory usage.

    Args:
        limit: Maximum number of keys to return

    Returns:
        List of dictionaries with key, type, size, and ttl
    """
    try:
        # Get all keys
        keys = redis_client.keys("*")

        # Sample keys if there are too many
        if len(keys) > 1000:
            import random

            keys = random.sample(keys, 1000)

        # Get memory usage for each key
        key_info = []
        for key in keys:
            try:
                # Get key type
                key_type = redis_client.type(key).decode("utf-8")

                # Get memory usage in bytes
                size = redis_client.memory_usage(key)
                if size:
                    # Convert to KB
                    size_kb = size / 1024

                    # Get TTL
                    ttl = redis_client.ttl(key)

                    key_info.append(
                        {
                            "key": key.decode("utf-8") if isinstance(key, bytes) else key,
                            "type": key_type,
                            "size": size_kb,
                            "ttl": ttl,
                        }
                    )
            except Exception:
                pass

        # Sort by size (descending) and return top N
        return sorted(key_info, key=lambda x: x["size"], reverse=True)[:limit]
    except Exception as e:
        logger.error(f"Error getting largest keys: {str(e)}")
        return []

"""
Redis API module for Redis monitoring and management.

This module provides API endpoints for Redis monitoring and management.
"""

import json
import logging
from typing import Dict, List, Optional, Union

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, JsonResponse
from ninja import Router
from ninja.security import django_auth

logger = logging.getLogger(__name__)

redis_router = Router(tags=["Redis"])


@redis_router.get("/stats", auth=django_auth)
def redis_stats(request: HttpRequest) -> Dict[str, Union[int, float, str]]:
    """
    Get Redis statistics.

    Args:
        request: HTTP request

    Returns:
        Dictionary with Redis statistics
    """
    try:
        # Get Redis statistics
        stats = get_redis_stats()
        
        return stats
    except Exception as e:
        logger.error(f"Error getting Redis statistics: {str(e)}")
        return {
            "error": f"Error getting Redis statistics: {str(e)}",
            "status": "error",
        }


@redis_router.get("/keys", auth=django_auth)
def redis_keys(
    request: HttpRequest, pattern: str = "*", limit: int = 100
) -> Dict[str, Union[List[str], int, str]]:
    """
    Get Redis keys matching a pattern.

    Args:
        request: HTTP request
        pattern: Pattern to match keys
        limit: Maximum number of keys to return

    Returns:
        Dictionary with Redis keys
    """
    try:
        # Get Redis keys
        keys = get_redis_keys(pattern, limit)
        
        return {
            "keys": keys,
            "count": len(keys),
            "pattern": pattern,
            "limit": limit,
        }
    except Exception as e:
        logger.error(f"Error getting Redis keys: {str(e)}")
        return {
            "error": f"Error getting Redis keys: {str(e)}",
            "status": "error",
        }


@redis_router.get("/key/{key}", auth=django_auth)
def redis_key(request: HttpRequest, key: str) -> Dict[str, Union[str, int, float, bool]]:
    """
    Get Redis key value.

    Args:
        request: HTTP request
        key: Redis key

    Returns:
        Dictionary with Redis key value
    """
    try:
        # Get Redis key value
        value = cache.get(key)
        
        if value is None:
            return {
                "key": key,
                "exists": False,
                "value": None,
                "type": "none",
            }
        
        # Determine value type
        if isinstance(value, str):
            value_type = "string"
        elif isinstance(value, int):
            value_type = "integer"
        elif isinstance(value, float):
            value_type = "float"
        elif isinstance(value, bool):
            value_type = "boolean"
        elif isinstance(value, list):
            value_type = "list"
        elif isinstance(value, dict):
            value_type = "dict"
        else:
            value_type = "unknown"
        
        return {
            "key": key,
            "exists": True,
            "value": value,
            "type": value_type,
        }
    except Exception as e:
        logger.error(f"Error getting Redis key value: {str(e)}")
        return {
            "error": f"Error getting Redis key value: {str(e)}",
            "status": "error",
        }


@redis_router.delete("/key/{key}", auth=django_auth)
def redis_delete_key(request: HttpRequest, key: str) -> Dict[str, Union[str, bool]]:
    """
    Delete Redis key.

    Args:
        request: HTTP request
        key: Redis key

    Returns:
        Dictionary with result
    """
    try:
        # Check if key exists
        exists = cache.get(key) is not None
        
        # Delete key
        cache.delete(key)
        
        return {
            "key": key,
            "deleted": exists,
            "message": f"Key '{key}' deleted successfully" if exists else f"Key '{key}' not found",
        }
    except Exception as e:
        logger.error(f"Error deleting Redis key: {str(e)}")
        return {
            "error": f"Error deleting Redis key: {str(e)}",
            "status": "error",
        }


@redis_router.post("/clear", auth=django_auth)
def redis_clear(request: HttpRequest) -> Dict[str, str]:
    """
    Clear Redis cache.

    Args:
        request: HTTP request

    Returns:
        Dictionary with result
    """
    try:
        # Clear Redis cache
        cache.clear()
        
        return {
            "message": "Redis cache cleared successfully",
            "status": "success",
        }
    except Exception as e:
        logger.error(f"Error clearing Redis cache: {str(e)}")
        return {
            "error": f"Error clearing Redis cache: {str(e)}",
            "status": "error",
        }


def get_redis_stats() -> Dict[str, Union[int, float, str]]:
    """
    Get Redis statistics.

    Returns:
        Dictionary with Redis statistics
    """
    # This is a placeholder - in a real implementation, you would
    # get actual statistics from Redis
    return {
        "status": "connected",
        "version": "6.0.0",
        "uptime_days": 0,
        "connected_clients": 1,
        "used_memory_human": "1M",
        "used_memory_peak_human": "1M",
        "total_commands_processed": 0,
        "total_connections_received": 0,
        "instantaneous_ops_per_sec": 0,
        "hit_rate": 0,
        "miss_rate": 0,
    }


def get_redis_keys(pattern: str = "*", limit: int = 100) -> List[str]:
    """
    Get Redis keys matching a pattern.

    Args:
        pattern: Pattern to match keys
        limit: Maximum number of keys to return

    Returns:
        List of Redis keys
    """
    # This is a placeholder - in a real implementation, you would
    # use Redis's SCAN command to find keys matching the pattern
    return []

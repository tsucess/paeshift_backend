"""
Compatibility module for core.cache.

This module provides backward compatibility with the old caching system.
It imports and re-exports the caching functions from the new standardized Redis caching module.
"""

import logging
import json
import hashlib
import redis
from typing import Any, Callable, Dict, List, Optional, Union

from django.conf import settings

# Try to import from the new module, but provide fallbacks if it doesn't exist
try:
    from core.redis.decorators import (
        cache_api_response,
        cache_function,
        no_cache,
        cache_method_result,
    )
except ImportError:
    # Fallback implementations
    def cache_api_response(timeout=300, key_prefix=""):
        def decorator(func):
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return decorator

    def cache_function(timeout=300, key_prefix=""):
        def decorator(func):
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return decorator

    def no_cache(func):
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper

    def cache_method_result(timeout=300, key_prefix=""):
        def decorator(func):
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return decorator

try:
    from core.redis.utils import (
        get_cached_data,
        set_cached_data,
        delete_cached_data,
        invalidate_cache_pattern,
        cache_permanently,
        get_permanent_cache,
        delete_permanent_cache,
    )
except ImportError:
    # Fallback implementations
    def get_cached_data(key):
        return None

    def set_cached_data(key, data, timeout=None):
        pass

    def delete_cached_data(key):
        pass

    def invalidate_cache_pattern(pattern):
        pass

    def cache_permanently(key, data):
        pass

    def get_permanent_cache(key):
        return None

    def delete_permanent_cache(key):
        pass

# Set up logging
logger = logging.getLogger(__name__)

# Set up Redis client
try:
    REDIS_HOST = getattr(settings, "REDIS_HOST", "localhost")
    REDIS_PORT = getattr(settings, "REDIS_PORT", 6379)
    REDIS_DB = getattr(settings, "REDIS_DB", 0)
    REDIS_PASSWORD = getattr(settings, "REDIS_PASSWORD", None)

    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        password=REDIS_PASSWORD,
        decode_responses=True,
    )

    # Test connection
    redis_client.ping()
    logger.info(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")
except Exception as e:
    logger.warning(f"Failed to connect to Redis: {str(e)}")
    redis_client = None

def generate_cache_key(prefix: str, *args) -> str:
    """
    Generate a cache key from a prefix and arguments.

    Args:
        prefix: The prefix for the cache key
        *args: Additional arguments to include in the key

    Returns:
        A cache key string
    """
    # Convert all arguments to strings and join with colons
    key_parts = [prefix]
    for arg in args:
        if isinstance(arg, dict):
            # Sort dictionary items for consistent keys
            arg_str = json.dumps(arg, sort_keys=True)
        else:
            arg_str = str(arg)
        key_parts.append(arg_str)

    key = ":".join(key_parts)

    # If the key is too long, hash it
    if len(key) > 200:
        key = f"{prefix}:hash:{hashlib.md5(key.encode()).hexdigest()}"

    return key

def get_cache_stats():
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
    }

# Re-export all functions
__all__ = [
    "cache_api_response",
    "cache_function",
    "no_cache",
    "cache_method_result",
    "get_cached_data",
    "set_cached_data",
    "delete_cached_data",
    "invalidate_cache_pattern",
    "cache_permanently",
    "get_permanent_cache",
    "delete_permanent_cache",
    "generate_cache_key",
    "get_cache_stats",
    "redis_client",
]
def invalidate_user_cache(user_id):
    """
    Invalidate all cache entries related to a user.
    
    Args:
        user_id: The ID of the user whose cache should be invalidated
    """
    cache_keys = [
        f"user:{user_id}",
        f"profile:{user_id}",
        f"whoami:{user_id}",
        f"user_logged_in:{user_id}",
        f"last_seen:{user_id}",
        f"hibernate:get_hibernated_user_response_by_id:{user_id}",
        # Legacy keys
        f"user_{user_id}_logged_in"
    ]

    for key in cache_keys:
        cache.delete(key)
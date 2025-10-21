"""
Redis utilities module.

This module provides utility functions for working with Redis.
"""

import hashlib
import json
import logging
import time
import traceback
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Union

from django.db.models.fields.files import ImageFieldFile, FileField

from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Model, QuerySet
from django.utils import timezone

from core.redis.client import redis_client, with_redis_retry
from core.redis.settings import (
    CACHE_DEFAULT_TIMEOUT,
    CACHE_ENABLED,
    CACHE_STATS_INTERVAL,
)

# Set up logging
logger = logging.getLogger(__name__)

# Global counters for cache statistics
_cache_operations_counter = 0
_cache_hits = 0
_cache_misses = 0
_last_stats_time = time.time()

class CustomJSONEncoder(DjangoJSONEncoder):
    """
    Custom JSON encoder that handles additional types.
    """

    def default(self, obj):
        # Handle Django FileField/ImageField
        if isinstance(obj, (ImageFieldFile, FileField)):
            return obj.url if obj and hasattr(obj, 'url') else None

        # Handle QuerySet
        if isinstance(obj, QuerySet):
            return list(obj)

        # Handle Django model instances
        if isinstance(obj, Model):
            return {
                "id": obj.pk,
                "model": obj.__class__.__name__,
                "app": obj._meta.app_label,
            }

        # Handle datetime and date
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()

        # Handle Decimal
        if isinstance(obj, Decimal):
            return float(obj)

        # Handle bytes
        if isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")

        # Handle sets
        if isinstance(obj, set):
            return list(obj)

        # Fall back to parent implementation
        return super().default(obj)





def generate_cache_key(prefix: str, *args) -> str:
    """
    Generate a cache key.

    Args:
        prefix: Key prefix
        *args: Additional key components

    Returns:
        Cache key string
    """
    # Convert args to strings
    key_parts = [str(arg) for arg in args]

    # Join with colons
    key = f"{prefix}:{':'.join(key_parts)}"

    # Hash long keys
    if len(key) > 200:
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return f"{prefix}:{key_hash}"

    return key


@with_redis_retry()
def get_cached_data(key: str, bypass_cache: bool = False) -> Optional[Any]:
    """
    Get data from the Redis cache.

    Args:
        key: The cache key
        bypass_cache: If True, bypass the cache and return None

    Returns:
        The cached data or None if not found
    """
    global _cache_hits, _cache_misses
    start_time = time.time()
    operation_id = hashlib.md5(f"{key}:{time.time()}".encode()).hexdigest()[:8]

    if not CACHE_ENABLED or not redis_client or bypass_cache:
        logger.debug(f"Cache disabled, Redis client not available, or bypass requested [op_id={operation_id}]")
        return None

    try:
        # Get data from Redis
        data = redis_client.get(key)

        if data is None:
            # Cache miss
            _cache_misses += 1
            duration_ms = round((time.time() - start_time) * 1000, 2)
            logger.debug(
                f"Cache MISS: key={key} [op_id={operation_id}, duration_ms={duration_ms}]"
            )
            return None

        # Cache hit
        _cache_hits += 1

        # Parse JSON
        try:
            parsed_data = json.loads(data)
        except json.JSONDecodeError:
            # Not JSON, return as is
            parsed_data = data.decode("utf-8") if isinstance(data, bytes) else data

        # Log cache stats periodically
        log_cache_stats()

        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.debug(
            f"Cache HIT: key={key} [op_id={operation_id}, duration_ms={duration_ms}]"
        )

        return parsed_data
    except Exception as e:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.error(
            f"Unexpected error getting data from cache for key={key}: {str(e)} "
            f"[op_id={operation_id}, duration_ms={duration_ms}]\n{traceback.format_exc()}"
        )
        return None


@with_redis_retry()
def set_cached_data(key: str, data: Any, timeout: Optional[int] = None) -> bool:
    """
    Store data in the Redis cache.

    Args:
        key: The cache key
        data: The data to cache
        timeout: Optional timeout in seconds

    Returns:
        True if successful, False otherwise
    """
    start_time = time.time()
    operation_id = hashlib.md5(f"{key}:{time.time()}".encode()).hexdigest()[:8]

    if not CACHE_ENABLED or not redis_client:
        logger.debug(f"Cache disabled or Redis client not available [op_id={operation_id}]")
        return False

    if timeout is None:
        timeout = CACHE_DEFAULT_TIMEOUT

    try:
        # Serialize the data to JSON
        serialized_data = json.dumps(data, cls=CustomJSONEncoder)
        data_size_bytes = len(serialized_data.encode('utf-8'))

        # Store in Redis with expiration
        redis_client.setex(key, timeout, serialized_data)

        # Log cache stats periodically
        log_cache_stats()

        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.debug(
            f"Cache SET: key={key} size={data_size_bytes}B timeout={timeout}s "
            f"[op_id={operation_id}, duration_ms={duration_ms}]"
        )

        # Log warning for large objects
        if data_size_bytes > 1024 * 100:  # 100KB
            logger.warning(
                f"Large object cached: key={key} size={round(data_size_bytes/1024, 2)}KB "
                f"[op_id={operation_id}]"
            )

        return True
    except Exception as e:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.error(
            f"Unexpected error setting data in cache for key={key}: {str(e)} "
            f"[op_id={operation_id}, duration_ms={duration_ms}]\n{traceback.format_exc()}"
        )
        return False


@with_redis_retry()
def delete_cached_data(key: str) -> bool:
    """
    Delete data from the Redis cache.

    Args:
        key: The cache key

    Returns:
        True if successful, False otherwise
    """
    start_time = time.time()
    operation_id = hashlib.md5(f"{key}:{time.time()}".encode()).hexdigest()[:8]

    if not CACHE_ENABLED or not redis_client:
        logger.debug(f"Cache disabled or Redis client not available [op_id={operation_id}]")
        return False

    try:
        # Delete from Redis
        result = redis_client.delete(key)

        # Log cache stats periodically
        log_cache_stats()

        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.debug(
            f"Cache DELETE: key={key} result={result} "
            f"[op_id={operation_id}, duration_ms={duration_ms}]"
        )

        return result > 0
    except Exception as e:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.error(
            f"Unexpected error deleting data from cache for key={key}: {str(e)} "
            f"[op_id={operation_id}, duration_ms={duration_ms}]\n{traceback.format_exc()}"
        )
        return False


@with_redis_retry()
def invalidate_cache_pattern(pattern: str) -> int:
    """
    Invalidate all cache keys matching a pattern.

    Args:
        pattern: The pattern to match (e.g., "user:*")

    Returns:
        Number of keys invalidated
    """
    start_time = time.time()
    operation_id = hashlib.md5(f"{pattern}:{time.time()}".encode()).hexdigest()[:8]

    if not CACHE_ENABLED or not redis_client:
        logger.debug(f"Cache disabled or Redis client not available [op_id={operation_id}]")
        return 0

    try:
        # Get keys matching pattern
        keys = redis_client.keys(pattern)

        if not keys:
            logger.debug(f"No keys found matching pattern {pattern} [op_id={operation_id}]")
            return 0

        # Delete keys
        result = redis_client.delete(*keys)

        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.info(
            f"Invalidated {result} keys matching pattern {pattern} "
            f"[op_id={operation_id}, duration_ms={duration_ms}]"
        )

        return result
    except Exception as e:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.error(
            f"Unexpected error invalidating cache pattern {pattern}: {str(e)} "
            f"[op_id={operation_id}, duration_ms={duration_ms}]\n{traceback.format_exc()}"
        )
        return 0


def log_cache_stats():
    """
    Log cache statistics periodically.
    """
    global _cache_operations_counter, _last_stats_time

    # Increment operations counter
    _cache_operations_counter += 1

    # Check if it's time to log stats
    if _cache_operations_counter % CACHE_STATS_INTERVAL == 0:
        # Calculate hit rate
        total = _cache_hits + _cache_misses
        hit_rate = (_cache_hits / total) * 100 if total > 0 else 0

        # Calculate operations per second
        now = time.time()
        elapsed = now - _last_stats_time
        ops_per_second = CACHE_STATS_INTERVAL / elapsed if elapsed > 0 else 0

        # Log stats
        logger.info(
            f"Cache stats: hits={_cache_hits}, misses={_cache_misses}, "
            f"hit_rate={hit_rate:.2f}%, ops_per_second={ops_per_second:.2f}"
        )

        # Reset last stats time
        _last_stats_time = now


def get_cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics.

    Returns:
        Dictionary with cache statistics
    """
    # Calculate hit rate
    total = _cache_hits + _cache_misses
    hit_rate = (_cache_hits / total) * 100 if total > 0 else 0

    # Get Redis info
    info = {}
    if CACHE_ENABLED and redis_client:
        try:
            info = redis_client.info()
        except Exception as e:
            logger.error(f"Error getting Redis info: {str(e)}")

    return {
        "hits": _cache_hits,
        "misses": _cache_misses,
        "hit_rate": f"{hit_rate:.2f}%",
        "operations": _cache_operations_counter,
        "redis_info": info,
        "timestamp": timezone.now().isoformat(),
    }


def cache_permanently(data: Any, key: str) -> bool:
    """
    Cache data permanently (no expiration).

    Args:
        data: Data to cache
        key: Cache key

    Returns:
        True if successful, False otherwise
    """
    start_time = time.time()
    operation_id = hashlib.md5(f"{key}:{time.time()}".encode()).hexdigest()[:8]

    if not CACHE_ENABLED or not redis_client:
        logger.debug(f"Cache disabled or Redis client not available [op_id={operation_id}]")
        return False

    try:
        # Serialize the data to JSON
        serialized_data = json.dumps(data, cls=CustomJSONEncoder)
        data_size_bytes = len(serialized_data.encode('utf-8'))

        # Store in Redis without expiration
        redis_client.set(key, serialized_data)

        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.debug(
            f"Cache SET (permanent): key={key} size={data_size_bytes}B "
            f"[op_id={operation_id}, duration_ms={duration_ms}]"
        )

        return True
    except Exception as e:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.error(
            f"Unexpected error setting permanent data in cache for key={key}: {str(e)} "
            f"[op_id={operation_id}, duration_ms={duration_ms}]\n{traceback.format_exc()}"
        )
        return False


def get_permanent_cache(key: str) -> Optional[Any]:
    """
    Get permanently cached data.

    Args:
        key: Cache key

    Returns:
        Cached data or None if not found
    """
    return get_cached_data(key)


def delete_permanent_cache(key: str) -> bool:
    """
    Delete permanently cached data.

    Args:
        key: Cache key

    Returns:
        True if successful, False otherwise
    """
    return delete_cached_data(key)


# List utilities
def add_to_list(key: str, value: str, max_length: int = 100, expiration: int = None) -> bool:
    """
    Add a value to a Redis list.

    Args:
        key: List key
        value: Value to add
        max_length: Maximum length of the list
        expiration: Expiration time in seconds

    Returns:
        True if successful, False otherwise
    """
    if not CACHE_ENABLED or not redis_client:
        return False

    try:
        # Add to list (at the beginning)
        redis_client.lpush(key, value)

        # Trim list to max length
        if max_length > 0:
            redis_client.ltrim(key, 0, max_length - 1)

        # Set expiration if provided
        if expiration is not None:
            redis_client.expire(key, expiration)

        return True
    except Exception as e:
        logger.error(f"Error adding to list {key}: {str(e)}")
        return False


def get_list_range(key: str, start: int = 0, end: int = -1) -> List[str]:
    """
    Get a range of values from a Redis list.

    Args:
        key: List key
        start: Start index
        end: End index

    Returns:
        List of values
    """
    if not CACHE_ENABLED or not redis_client:
        return []

    try:
        # Get range from list
        values = redis_client.lrange(key, start, end)

        # Convert bytes to strings
        return [v.decode('utf-8') if isinstance(v, bytes) else v for v in values]
    except Exception as e:
        logger.error(f"Error getting list range for {key}: {str(e)}")
        return []


def publish_notification(channel: str, data: Any) -> bool:
    """
    Publish a notification to a Redis channel.

    Args:
        channel: Channel name
        data: Data to publish

    Returns:
        True if successful, False otherwise
    """
    if not CACHE_ENABLED or not redis_client:
        return False

    try:
        # Convert data to JSON string
        if isinstance(data, (dict, list)):
            data_str = json.dumps(data, cls=CustomJSONEncoder)
        else:
            data_str = str(data)

        # Publish to channel
        redis_client.publish(channel, data_str)

        return True
    except Exception as e:
        logger.error(f"Error publishing notification to {channel}: {str(e)}")
        return False


# Re-export all functions
__all__ = [
    "CustomJSONEncoder",
    "generate_cache_key",
    "set_cached_data",
    "get_cached_data",
    "delete_cached_data",
    "invalidate_cache_pattern",
    "cache_permanently",
    "get_permanent_cache",
    "delete_permanent_cache",
    "add_to_list",
    "get_list_range",
    "publish_notification",
]

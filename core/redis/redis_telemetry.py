"""
Redis telemetry module.

This module provides tools for detailed logging and telemetry of Redis operations.
"""

import functools
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from django.conf import settings
from django.utils import timezone

from core.redis.client import redis_client
from core.redis.settings import CACHE_ENABLED

logger = logging.getLogger(__name__)

# Constants
TELEMETRY_ENABLED = getattr(settings, "REDIS_TELEMETRY_ENABLED", True)
TELEMETRY_SAMPLE_RATE = getattr(settings, "REDIS_TELEMETRY_SAMPLE_RATE", 0.1)  # 10% of operations
TELEMETRY_SLOW_THRESHOLD_MS = getattr(settings, "REDIS_TELEMETRY_SLOW_THRESHOLD_MS", 100)
TELEMETRY_KEY_PREFIX = "telemetry:"
TELEMETRY_MAX_ENTRIES = getattr(settings, "REDIS_TELEMETRY_MAX_ENTRIES", 1000)


def should_sample() -> bool:
    """
    Determine if an operation should be sampled based on sample rate.

    Returns:
        True if operation should be sampled, False otherwise
    """
    if not TELEMETRY_ENABLED:
        return False

    import random
    return random.random() < TELEMETRY_SAMPLE_RATE


def log_operation(
    operation: str,
    key: str,
    success: bool,
    duration_ms: float,
    context: Optional[str] = None,
    data_size: Optional[int] = None,
) -> None:
    """
    Log a Redis operation for telemetry.

    Args:
        operation: Operation type (get, set, delete, etc.)
        key: Redis key
        success: Whether the operation was successful
        duration_ms: Duration of the operation in milliseconds
        context: Optional context information
        data_size: Optional size of the data in bytes
    """
    if not TELEMETRY_ENABLED or not should_sample():
        return

    try:
        # Create telemetry data
        telemetry = {
            "operation": operation,
            "key": key,
            "success": success,
            "duration_ms": duration_ms,
            "context": context,
            "data_size": data_size,
            "timestamp": timezone.now().isoformat(),
        }

        # Log telemetry data
        logger.info(f"REDIS_TELEMETRY: {json.dumps(telemetry)}")

        # Store in Redis if it's a slow operation
        if duration_ms >= TELEMETRY_SLOW_THRESHOLD_MS:
            store_slow_operation(telemetry)

    except Exception as e:
        logger.error(f"Error logging Redis operation: {str(e)}")


def store_slow_operation(telemetry: Dict) -> None:
    """
    Store a slow Redis operation in Redis for analysis.

    Args:
        telemetry: Telemetry data dictionary
    """
    if not CACHE_ENABLED or not redis_client:
        return

    try:
        # Generate a unique key
        timestamp = datetime.fromisoformat(telemetry["timestamp"])
        key = f"{TELEMETRY_KEY_PREFIX}slow:{timestamp.strftime('%Y%m%d%H%M%S')}:{telemetry['operation']}"

        # Store in Redis with 7-day expiration
        redis_client.setex(key, 60 * 60 * 24 * 7, json.dumps(telemetry))

        # Trim if too many entries
        trim_telemetry_entries()

    except Exception as e:
        logger.error(f"Error storing slow operation: {str(e)}")


def trim_telemetry_entries() -> None:
    """
    Trim telemetry entries if there are too many.
    """
    if not CACHE_ENABLED or not redis_client:
        return

    try:
        # Get all telemetry keys
        keys = redis_client.keys(f"{TELEMETRY_KEY_PREFIX}*")

        # If there are too many, delete the oldest ones
        if len(keys) > TELEMETRY_MAX_ENTRIES:
            # Sort by timestamp (oldest first)
            keys.sort()

            # Delete the oldest ones
            to_delete = keys[:len(keys) - TELEMETRY_MAX_ENTRIES]
            if to_delete:
                redis_client.delete(*to_delete)

    except Exception as e:
        logger.error(f"Error trimming telemetry entries: {str(e)}")


def get_slow_operations(
    operation_type: Optional[str] = None,
    min_duration_ms: float = TELEMETRY_SLOW_THRESHOLD_MS,
    limit: int = 100,
) -> List[Dict]:
    """
    Get slow Redis operations from telemetry data.

    Args:
        operation_type: Optional operation type filter
        min_duration_ms: Minimum duration in milliseconds
        limit: Maximum number of operations to return

    Returns:
        List of slow operations
    """
    if not CACHE_ENABLED or not redis_client:
        return []

    try:
        # Build pattern
        pattern = f"{TELEMETRY_KEY_PREFIX}slow:*"
        if operation_type:
            pattern = f"{TELEMETRY_KEY_PREFIX}slow:*:{operation_type}"

        # Get matching keys
        keys = redis_client.keys(pattern)

        # Sort by timestamp (newest first)
        keys.sort(reverse=True)

        # Limit number of keys
        keys = keys[:limit]

        # Get data for each key
        operations = []
        for key in keys:
            data = redis_client.get(key)
            if data:
                operation = json.loads(data)
                if operation["duration_ms"] >= min_duration_ms:
                    operations.append(operation)

        return operations
    except Exception as e:
        logger.error(f"Error getting slow operations: {str(e)}")
        return []


def telemetry_decorator(operation_type: str, context: Optional[str] = None) -> Callable:
    """
    Decorator to add telemetry to Redis operations.

    Args:
        operation_type: Operation type (get, set, delete, etc.)
        context: Optional context information

    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not TELEMETRY_ENABLED or not should_sample():
                return func(*args, **kwargs)

            # Extract key from args or kwargs
            key = None
            if len(args) > 0 and isinstance(args[0], str):
                key = args[0]
            elif "key" in kwargs:
                key = kwargs["key"]

            # Get data size if available
            data_size = None
            if operation_type == "set" and len(args) > 1:
                data = args[1]
                if isinstance(data, (str, bytes)):
                    data_size = len(data)
                elif isinstance(data, dict):
                    data_size = len(json.dumps(data))

            # Measure operation time
            start_time = time.time()
            success = True

            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000

                # Log operation
                log_operation(
                    operation=operation_type,
                    key=key,
                    success=success,
                    duration_ms=duration_ms,
                    context=context,
                    data_size=data_size,
                )

        return wrapper
    return decorator


# Apply telemetry to Redis client methods
if TELEMETRY_ENABLED and redis_client:
    # Backup original methods
    original_get = redis_client.get
    original_set = redis_client.set
    original_setex = redis_client.setex
    original_delete = redis_client.delete
    original_exists = redis_client.exists
    original_expire = redis_client.expire
    original_ttl = redis_client.ttl

    # Replace with telemetry-enhanced versions
    redis_client.get = telemetry_decorator("get")(original_get)
    redis_client.set = telemetry_decorator("set")(original_set)
    redis_client.setex = telemetry_decorator("setex")(original_setex)
    redis_client.delete = telemetry_decorator("delete")(original_delete)
    redis_client.exists = telemetry_decorator("exists")(original_exists)
    redis_client.expire = telemetry_decorator("expire")(original_expire)
    redis_client.ttl = telemetry_decorator("ttl")(original_ttl)


def get_telemetry_stats() -> Dict:
    """
    Get telemetry statistics.

    Returns:
        Dictionary with telemetry statistics
    """
    if not CACHE_ENABLED or not redis_client:
        return {"error": "Redis client not available"}

    try:
        # Get all telemetry keys
        keys = redis_client.keys(f"{TELEMETRY_KEY_PREFIX}*")

        # Count by operation type
        operation_counts = {}
        slow_operation_counts = {}

        for key in keys:
            key_str = key.decode("utf-8")

            # Extract operation type
            parts = key_str.split(":")
            if len(parts) >= 3:
                operation_type = parts[-1]

                # Count slow operations
                if "slow" in key_str:
                    slow_operation_counts[operation_type] = slow_operation_counts.get(operation_type, 0) + 1
                else:
                    operation_counts[operation_type] = operation_counts.get(operation_type, 0) + 1

        return {
            "total_telemetry_entries": len(keys),
            "operation_counts": operation_counts,
            "slow_operation_counts": slow_operation_counts,
            "telemetry_enabled": TELEMETRY_ENABLED,
            "telemetry_sample_rate": TELEMETRY_SAMPLE_RATE,
            "slow_threshold_ms": TELEMETRY_SLOW_THRESHOLD_MS,
        }
    except Exception as e:
        logger.error(f"Error getting telemetry stats: {str(e)}")
        return {"error": str(e)}

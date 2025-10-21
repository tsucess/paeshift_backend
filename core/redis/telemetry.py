"""
Redis telemetry module.

This module provides utilities for tracking Redis cache performance and usage.
"""

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from django.utils import timezone

from core.redis.client import redis_client
from core.redis.settings import CACHE_ENABLED

# Set up logging
logger = logging.getLogger(__name__)

# Constants
TELEMETRY_KEY_PREFIX = "redis:telemetry:"
TELEMETRY_RETENTION = 60 * 60 * 24 * 7  # 7 days
SLOW_OPERATION_THRESHOLD = 100.0  # 100ms


def log_operation(
    operation: str,
    key: str,
    success: bool,
    duration_ms: float,
    context: Optional[str] = None,
) -> None:
    """
    Log a Redis operation for telemetry purposes.

    Args:
        operation: Operation type (get, set, delete, etc.)
        key: Cache key
        success: Whether the operation was successful
        duration_ms: Duration of the operation in milliseconds
        context: Optional context information
    """
    if not CACHE_ENABLED:
        return

    try:
        # Create telemetry data
        telemetry = {
            "operation": operation,
            "key": key,
            "success": success,
            "duration_ms": duration_ms,
            "context": context,
            "timestamp": timezone.now().isoformat(),
        }

        # Log telemetry data
        logger.debug(f"REDIS_TELEMETRY: {json.dumps(telemetry)}")

        # Store slow operations in Redis for analysis
        if duration_ms > SLOW_OPERATION_THRESHOLD:
            store_slow_operation(telemetry)
    except Exception as e:
        logger.error(f"Error logging Redis operation: {str(e)}")


def store_slow_operation(telemetry: Dict[str, Any]) -> bool:
    """
    Store a slow Redis operation for analysis.

    Args:
        telemetry: Telemetry data

    Returns:
        True if successful, False otherwise
    """
    if not CACHE_ENABLED or not redis_client:
        return False

    try:
        # Generate key
        key = f"{TELEMETRY_KEY_PREFIX}slow:{timezone.now().strftime('%Y%m%d')}"

        # Store in Redis
        redis_client.lpush(key, json.dumps(telemetry))
        redis_client.expire(key, TELEMETRY_RETENTION)

        # Log slow operation
        logger.warning(
            f"Slow Redis operation: {telemetry['operation']} {telemetry['key']} "
            f"({telemetry['duration_ms']:.2f}ms)"
        )

        return True
    except Exception as e:
        logger.error(f"Error storing slow operation: {str(e)}")
        return False


def get_slow_operations(days: int = 1) -> List[Dict[str, Any]]:
    """
    Get slow Redis operations for analysis.

    Args:
        days: Number of days to look back

    Returns:
        List of slow operations
    """
    if not CACHE_ENABLED or not redis_client:
        return []

    try:
        # Calculate start date
        start_date = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = start_date - timezone.timedelta(days=days-1)

        # Get keys for the period
        keys = []
        current_date = start_date
        end_date = timezone.now()

        while current_date <= end_date:
            key = f"{TELEMETRY_KEY_PREFIX}slow:{current_date.strftime('%Y%m%d')}"
            keys.append(key)
            current_date += timezone.timedelta(days=1)

        # Get slow operations for each key
        slow_operations = []
        for key in keys:
            if redis_client.exists(key):
                data = redis_client.lrange(key, 0, -1)
                for item in data:
                    try:
                        slow_operations.append(json.loads(item))
                    except json.JSONDecodeError:
                        logger.error(f"Error parsing slow operation data: {item}")

        return slow_operations
    except Exception as e:
        logger.error(f"Error getting slow operations: {str(e)}")
        return []


def analyze_slow_operations(days: int = 1) -> Dict[str, Any]:
    """
    Analyze slow Redis operations.

    Args:
        days: Number of days to look back

    Returns:
        Analysis results
    """
    slow_operations = get_slow_operations(days)

    if not slow_operations:
        return {
            "count": 0,
            "message": "No slow operations found",
            "timestamp": timezone.now().isoformat(),
        }

    try:
        # Group by operation type
        by_operation = {}
        for op in slow_operations:
            operation = op.get("operation", "unknown")
            if operation not in by_operation:
                by_operation[operation] = []
            by_operation[operation].append(op)

        # Group by key prefix
        by_prefix = {}
        for op in slow_operations:
            key = op.get("key", "")
            prefix = key.split(":")[0] if ":" in key else key
            if prefix not in by_prefix:
                by_prefix[prefix] = []
            by_prefix[prefix].append(op)

        # Calculate statistics
        total_duration = sum(op.get("duration_ms", 0) for op in slow_operations)
        avg_duration = total_duration / len(slow_operations)
        max_duration = max(op.get("duration_ms", 0) for op in slow_operations)
        min_duration = min(op.get("duration_ms", 0) for op in slow_operations)

        # Find slowest operations
        slowest_operations = sorted(
            slow_operations,
            key=lambda x: x.get("duration_ms", 0),
            reverse=True,
        )[:10]

        # Find most frequent keys
        key_counts = {}
        for op in slow_operations:
            key = op.get("key", "")
            if key not in key_counts:
                key_counts[key] = 0
            key_counts[key] += 1

        most_frequent_keys = sorted(
            key_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        return {
            "count": len(slow_operations),
            "total_duration_ms": total_duration,
            "avg_duration_ms": avg_duration,
            "max_duration_ms": max_duration,
            "min_duration_ms": min_duration,
            "by_operation": {
                op: len(ops) for op, ops in by_operation.items()
            },
            "by_prefix": {
                prefix: len(ops) for prefix, ops in by_prefix.items()
            },
            "slowest_operations": slowest_operations,
            "most_frequent_keys": most_frequent_keys,
            "timestamp": timezone.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error analyzing slow operations: {str(e)}")
        return {
            "error": str(e),
            "count": len(slow_operations),
            "timestamp": timezone.now().isoformat(),
        }


def record_telemetry_stats() -> bool:
    """
    Record telemetry statistics for historical tracking.

    Returns:
        True if successful, False otherwise
    """
    if not CACHE_ENABLED or not redis_client:
        return False

    try:
        # Analyze slow operations
        analysis = analyze_slow_operations(days=1)

        # Store in Redis
        key = f"{TELEMETRY_KEY_PREFIX}stats:{timezone.now().strftime('%Y%m%d')}"
        redis_client.lpush(key, json.dumps(analysis))
        redis_client.expire(key, TELEMETRY_RETENTION)

        return True
    except Exception as e:
        logger.error(f"Error recording telemetry stats: {str(e)}")
        return False


def get_telemetry_stats(days: int = 7) -> List[Dict[str, Any]]:
    """
    Get telemetry statistics for historical tracking.

    Args:
        days: Number of days to look back

    Returns:
        List of telemetry statistics
    """
    if not CACHE_ENABLED or not redis_client:
        return []

    try:
        # Calculate start date
        start_date = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = start_date - timezone.timedelta(days=days-1)

        # Get keys for the period
        keys = []
        current_date = start_date
        end_date = timezone.now()

        while current_date <= end_date:
            key = f"{TELEMETRY_KEY_PREFIX}stats:{current_date.strftime('%Y%m%d')}"
            keys.append(key)
            current_date += timezone.timedelta(days=1)

        # Get telemetry stats for each key
        stats = []
        for key in keys:
            if redis_client.exists(key):
                data = redis_client.lrange(key, 0, -1)
                for item in data:
                    try:
                        stats.append(json.loads(item))
                    except json.JSONDecodeError:
                        logger.error(f"Error parsing telemetry stats data: {item}")

        return stats
    except Exception as e:
        logger.error(f"Error getting telemetry stats: {str(e)}")
        return []

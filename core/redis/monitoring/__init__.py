"""
Redis monitoring module.

This module provides utilities for monitoring Redis cache health and performance.
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from django.utils import timezone

from core.redis.client import redis_client
from core.redis.settings import CACHE_ENABLED
from core.redis.utils import get_cache_stats

# Set up logging
logger = logging.getLogger(__name__)

# Constants
STATS_KEY_PREFIX = "redis:stats:"
STATS_RETENTION = 60 * 60 * 24 * 30  # 30 days
ALERT_COOLDOWN = 60 * 60  # 1 hour


def record_stats() -> bool:
    """
    Record cache statistics for historical tracking.
    Returns:
        True if successful, False otherwise
    """
    if not CACHE_ENABLED or not redis_client:
        return False

    try:
        # Get current stats
        stats = get_cache_stats()

        # Add timestamp
        stats["timestamp"] = timezone.now().isoformat()

        # Store in Redis
        key = f"{STATS_KEY_PREFIX}{timezone.now().strftime('%Y%m%d%H')}"
        redis_client.lpush(key, json.dumps(stats))
        redis_client.expire(key, STATS_RETENTION)

        return True
    except Exception as e:
        logger.error(f"Error recording cache stats: {str(e)}")
        return False


def get_historical_stats(period: str = "hourly", days: int = 7) -> List[Dict[str, Any]]:
    """
    Get historical cache statistics.
    Args:
        period: Period to group by ("hourly" or "daily")
        days: Number of days to look back
    Returns:
        List of stats dictionaries
    """
    if not CACHE_ENABLED or not redis_client:
        return []

    try:
        # Calculate start date
        start_date = timezone.now() - timedelta(days=days)

        # Get keys for the period
        keys = []
        current_date = start_date
        end_date = timezone.now()

        while current_date <= end_date:
            if period == "hourly":
                key = f"{STATS_KEY_PREFIX}{current_date.strftime('%Y%m%d%H')}"
                keys.append(key)
                current_date += timedelta(hours=1)
            else:
                # Daily
                key = f"{STATS_KEY_PREFIX}{current_date.strftime('%Y%m%d')}"
                keys.append(key)
                current_date += timedelta(days=1)

        # Get stats for each key
        stats = []
        for key in keys:
            if redis_client.exists(key):
                data = redis_client.lrange(key, 0, -1)
                for item in data:
                    try:
                        stats.append(json.loads(item))
                    except json.JSONDecodeError:
                        logger.error(f"Error parsing stats data: {item}")

        return stats
    except Exception as e:
        logger.error(f"Error getting historical stats: {str(e)}")
        return []


def check_alerts() -> List[Dict[str, Any]]:
    """
    Check for Redis cache alerts.
    Returns:
        List of alerts
    """
    if not CACHE_ENABLED or not redis_client:
        return []

    try:
        # Get current stats
        stats = get_cache_stats()
        redis_info = stats.get("redis_info", {})

        alerts = []

        # Check memory usage
        if "used_memory" in redis_info and "maxmemory" in redis_info:
            used_memory = int(redis_info["used_memory"])
            max_memory = int(redis_info["maxmemory"])
            memory_usage_percent = (used_memory / max_memory) * 100 if max_memory > 0 else 0

            if memory_usage_percent > 90:
                alerts.append({
                    "type": "memory_usage_critical",
                    "message": f"Redis memory usage is critical: {memory_usage_percent:.2f}%",
                    "severity": "critical",
                    "timestamp": timezone.now().isoformat(),
                })
            elif memory_usage_percent > 80:
                alerts.append({
                    "type": "memory_usage_warning",
                    "message": f"Redis memory usage is high: {memory_usage_percent:.2f}%",
                    "severity": "warning",
                    "timestamp": timezone.now().isoformat(),
                })

        # Check hit rate
        if "hits" in stats and "misses" in stats:
            hits = stats["hits"]
            misses = stats["misses"]
            total = hits + misses
            hit_rate = (hits / total) * 100 if total > 0 else 0

            if hit_rate < 50:
                alerts.append({
                    "type": "hit_rate_low",
                    "message": f"Redis hit rate is low: {hit_rate:.2f}%",
                    "severity": "warning",
                    "timestamp": timezone.now().isoformat(),
                })

        # Check evicted keys
        if "evicted_keys" in redis_info:
            evicted_keys = int(redis_info["evicted_keys"])
            if evicted_keys > 1000:
                alerts.append({
                    "type": "evicted_keys_high",
                    "message": f"Redis has evicted {evicted_keys} keys",
                    "severity": "warning",
                    "timestamp": timezone.now().isoformat(),
                })

        # Check rejected connections
        if "rejected_connections" in redis_info:
            rejected_connections = int(redis_info["rejected_connections"])
            if rejected_connections > 0:
                alerts.append({
                    "type": "rejected_connections",
                    "message": f"Redis has rejected {rejected_connections} connections",
                    "severity": "critical",
                    "timestamp": timezone.now().isoformat(),
                })

        return alerts
    except Exception as e:
        logger.error(f"Error checking alerts: {str(e)}")
        return []


def trigger_alert(alert: Dict[str, Any]) -> bool:
    """
    Trigger a Redis cache alert.
    Args:
        alert: Alert dictionary
    Returns:
        True if successful, False otherwise
    """
    if not CACHE_ENABLED or not redis_client:
        return False

    try:
        # Check if this alert type was recently triggered
        alert_key = f"{STATS_KEY_PREFIX}alert:{alert['type']}"

        # Check if alert is in cooldown
        if redis_client.exists(alert_key):
            logger.debug(
                f"Alert {alert['type']} is in cooldown, not triggering"
            )
            return False

        # Log the alert
        if alert["severity"] == "critical":
            logger.critical(f"REDIS ALERT: {alert['message']}")
        else:
            logger.warning(f"REDIS ALERT: {alert['message']}")

        # Store the alert
        redis_client.setex(
            alert_key,
            ALERT_COOLDOWN,
            json.dumps(alert),
        )

        # Store in alerts history
        history_key = f"{STATS_KEY_PREFIX}alerts:{timezone.now().strftime('%Y%m%d')}"
        redis_client.lpush(history_key, json.dumps(alert))
        redis_client.expire(history_key, STATS_RETENTION)

        # TODO: Send alert to external monitoring system
        # This could be Slack, email, PagerDuty, etc.

        return True
    except Exception as e:
        logger.error(f"Error triggering alert: {str(e)}")
        return False


def analyze_key_size(pattern: str = "*", sample_size: int = 100) -> Dict:
    """
    Analyze the size of keys matching a pattern.

    Args:
        pattern: Key pattern to match
        sample_size: Number of keys to sample

    Returns:
        Dictionary with key size statistics
    """
    if not CACHE_ENABLED or not redis_client:
        return {"error": "Redis client not available"}

    try:
        # Get keys matching pattern
        keys = redis_client.keys(pattern)
        if not keys:
            return {"keys": 0, "message": f"No keys found matching pattern {pattern}"}

        # Sample keys if there are too many
        if len(keys) > sample_size:
            import random
            keys = random.sample(keys, sample_size)

        # Get size of each key
        sizes = []
        for key in keys:
            # Get key type
            key_type = redis_client.type(key)

            # Get size based on type
            if key_type == b"string":
                value = redis_client.get(key)
                size = len(value) if value else 0
            elif key_type == b"hash":
                size = sum(len(k) + len(v) for k, v in redis_client.hgetall(key).items())
            elif key_type == b"list":
                size = sum(len(item) for item in redis_client.lrange(key, 0, -1))
            elif key_type == b"set":
                size = sum(len(item) for item in redis_client.smembers(key))
            elif key_type == b"zset":
                size = sum(len(item) for item in redis_client.zrange(key, 0, -1))
            else:
                size = 0

            sizes.append({"key": key, "size": size, "type": key_type})

        # Calculate statistics
        total_size = sum(item["size"] for item in sizes)
        avg_size = total_size / len(sizes) if sizes else 0
        max_size = max(item["size"] for item in sizes) if sizes else 0
        min_size = min(item["size"] for item in sizes) if sizes else 0

        # Sort by size
        sizes.sort(key=lambda x: x["size"], reverse=True)

        return {
            "keys": len(keys),
            "total_size": total_size,
            "avg_size": avg_size,
            "max_size": max_size,
            "min_size": min_size,
            "largest_keys": sizes[:10],
            "sample_size": len(sizes),
        }
    except Exception as e:
        logger.error(f"Error analyzing key size: {str(e)}")
        return {"error": str(e)}


def log_telemetry(
    operation: str,
    key: str,
    success: bool,
    duration_ms: float,
    context: Optional[str] = None,
) -> None:
    """
    Log telemetry data for a cache operation.
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
        logger.info(f"CACHE_TELEMETRY: {json.dumps(telemetry)}")

    except Exception as e:
        logger.error(f"Error logging telemetry: {str(e)}")


def get_slow_operations(threshold_ms: float = 100.0, days: int = 1) -> List[Dict]:
    """
    Get slow cache operations from logs.

    Args:
        threshold_ms: Threshold in milliseconds
        days: Number of days to look back

    Returns:
        List of slow operations
    """
    # This is a placeholder. In a real implementation, you would parse logs
    # or use a dedicated telemetry storage system.
    return [
        {
            "operation": "get",
            "key": "example:key",
            "duration_ms": 150.5,
            "timestamp": "2023-01-01T12:00:00",
        }
    ]


def get_recent_alerts(days: int = 7) -> List[Dict[str, Any]]:
    """
    Get recent alerts.

    Args:
        days: Number of days to look back

    Returns:
        List of recent alerts
    """
    if not CACHE_ENABLED or not redis_client:
        return []

    try:
        # Calculate start date
        start_date = timezone.now() - timedelta(days=days)

        # Get keys for the period
        keys = []
        current_date = start_date
        end_date = timezone.now()

        while current_date <= end_date:
            key = f"{STATS_KEY_PREFIX}alerts:{current_date.strftime('%Y%m%d')}"
            keys.append(key)
            current_date += timedelta(days=1)

        # Get alerts for each key
        alerts = []
        for key in keys:
            if redis_client.exists(key):
                data = redis_client.lrange(key, 0, -1)
                for item in data:
                    try:
                        alerts.append(json.loads(item))
                    except json.JSONDecodeError:
                        logger.error(f"Error parsing alert data: {item}")

        return alerts
    except Exception as e:
        logger.error(f"Error getting recent alerts: {str(e)}")
        return []


def get_dashboard_data() -> Dict[str, Any]:
    """
    Get data for the Redis dashboard.

    Returns:
        Dictionary with dashboard data
    """
    if not CACHE_ENABLED or not redis_client:
        return {"error": "Redis client not available"}

    try:
        # Get current stats
        current_stats = get_cache_stats()

        # Get historical stats
        historical_stats = get_historical_stats(period="hourly", days=1)

        # Get recent alerts
        recent_alerts = get_recent_alerts(days=7)

        # Get key size distribution
        key_size_distribution = analyze_key_size()

        # Get slow operations
        slow_operations = get_slow_operations(threshold_ms=100.0, days=1)

        # Calculate hit rate over time
        hit_rate_over_time = []
        memory_usage_over_time = []
        keys_over_time = []

        for stat in historical_stats:
            timestamp = stat.get("timestamp")
            if not timestamp:
                continue

            # Hit rate
            hits = stat.get("hits", 0)
            misses = stat.get("misses", 0)
            total = hits + misses
            hit_rate = (hits / total) * 100 if total > 0 else 0
            hit_rate_over_time.append({
                "timestamp": timestamp,
                "hit_rate": hit_rate,
            })

            # Memory usage
            redis_info = stat.get("redis_info", {})
            if "used_memory" in redis_info and "maxmemory" in redis_info:
                used_memory = int(redis_info["used_memory"])
                max_memory = int(redis_info["maxmemory"])
                memory_usage_percent = (used_memory / max_memory) * 100 if max_memory > 0 else 0
                memory_usage_over_time.append({
                    "timestamp": timestamp,
                    "memory_usage_percent": memory_usage_percent,
                })

            # Keys
            if "keyspace_hits" in redis_info and "keyspace_misses" in redis_info:
                keys = int(redis_info.get("db0", {}).get("keys", 0))
                keys_over_time.append({
                    "timestamp": timestamp,
                    "keys": keys,
                })

        return {
            "current_stats": current_stats,
            "historical_stats": {
                "hit_rate_over_time": hit_rate_over_time,
                "memory_usage_over_time": memory_usage_over_time,
                "keys_over_time": keys_over_time,
            },
            "recent_alerts": recent_alerts,
            "key_size_distribution": key_size_distribution,
            "slow_operations": slow_operations,
            "timestamp": timezone.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error getting dashboard data: {str(e)}")
        return {"error": str(e)}

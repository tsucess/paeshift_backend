"""
Redis monitoring and telemetry module.

This module provides comprehensive tools for monitoring Redis cache performance,
tracking cache hit rates, analyzing memory usage, generating alerts, and
creating dashboards for observability.
"""

import json
import logging
import time
import traceback
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from django.conf import settings
from django.utils import timezone

from core.cache import redis_client, CACHE_PREFIXES
from core.redis_keys import CacheNamespace, generate_key
from core.redis_settings import (
    CACHE_ENABLED,
    REDIS_DB_CACHE,
    get_redis_connection_params,
)

logger = logging.getLogger(__name__)

# Constants
STATS_NAMESPACE = CacheNamespace.TELEMETRY
STATS_KEY_PREFIX = "cache:stats:"
HOURLY_STATS_KEY = f"{STATS_KEY_PREFIX}hourly:"
DAILY_STATS_KEY = f"{STATS_KEY_PREFIX}daily:"
WEEKLY_STATS_KEY = f"{STATS_KEY_PREFIX}weekly:"
STATS_RETENTION = 60 * 60 * 24 * 7  # 7 days

# Monitoring settings
MONITOR_MEMORY_USAGE = getattr(settings, "MONITOR_MEMORY_USAGE", True)
MONITOR_HIT_RATE = getattr(settings, "MONITOR_HIT_RATE", True)
MONITOR_OPERATION_COUNT = getattr(settings, "MONITOR_OPERATION_COUNT", True)
MEMORY_USAGE_THRESHOLD = getattr(settings, "MEMORY_USAGE_THRESHOLD", 80)  # percentage
HIT_RATE_THRESHOLD = getattr(settings, "HIT_RATE_THRESHOLD", 50)  # percentage
ALERT_THRESHOLD_EVICTIONS = getattr(settings, "ALERT_THRESHOLD_EVICTIONS", 1000)  # per minute
ALERT_COOLDOWN = getattr(settings, "ALERT_COOLDOWN", 60 * 15)  # 15 minutes between alerts


def get_redis_info() -> Dict:
    """
    Get Redis server information.
    Returns:
        Dictionary with Redis server information
    """
    if not CACHE_ENABLED or not redis_client:
        return {"error": "Redis client not available"}
    try:
        return redis_client.info()
    except Exception as e:
        logger.error(f"Error getting Redis info: {str(e)}")
        return {"error": str(e)}


def get_memory_usage() -> Dict:
    """
    Get Redis memory usage statistics.
    Returns:
        Dictionary with memory usage statistics
    """
    if not CACHE_ENABLED or not redis_client:
        return {"error": "Redis client not available"}

    try:
        info = redis_client.info()

        # Get memory usage
        used_memory = info.get("used_memory", 0)
        used_memory_peak = info.get("used_memory_peak", 0)
        used_memory_rss = info.get("used_memory_rss", 0)
        maxmemory = info.get("maxmemory", 0)

        # Calculate percentages
        memory_usage_percent = (used_memory / maxmemory * 100) if maxmemory > 0 else 0
        peak_usage_percent = (used_memory_peak / maxmemory * 100) if maxmemory > 0 else 0

        return {
            "used_memory_bytes": used_memory,
            "used_memory_human": f"{used_memory / (1024 * 1024):.2f} MB",
            "used_memory_peak_bytes": used_memory_peak,
            "used_memory_peak_human": f"{used_memory_peak / (1024 * 1024):.2f} MB",
            "used_memory_rss_bytes": used_memory_rss,
            "used_memory_rss_human": f"{used_memory_rss / (1024 * 1024):.2f} MB",
            "maxmemory_bytes": maxmemory,
            "maxmemory_human": f"{maxmemory / (1024 * 1024):.2f} MB" if maxmemory > 0 else "Unlimited",
            "memory_usage_percent": f"{memory_usage_percent:.2f}%",
            "peak_usage_percent": f"{peak_usage_percent:.2f}%",
            "memory_fragmentation_ratio": info.get("mem_fragmentation_ratio", 0),
        }
    except Exception as e:
        logger.error(f"Error getting memory usage: {str(e)}")
        return {"error": str(e)}


def get_key_count_by_prefix() -> Dict:
    """
    Get count of keys by prefix.
    Returns:
        Dictionary with key counts by prefix
    """
    if not CACHE_ENABLED or not redis_client:
        return {"error": "Redis client not available"}

    try:
        key_counts = {}
        total_keys = 0

        # Count keys by prefix
        for prefix_name, prefix in CACHE_PREFIXES.items():
            pattern = f"{prefix}*"
            count = len(redis_client.keys(pattern))
            key_counts[prefix_name] = count
            total_keys += count
        # Add permanent cache keys
        permanent_pattern = "permanent:*"
        permanent_count = len(redis_client.keys(permanent_pattern))
        key_counts["permanent"] = permanent_count
        total_keys += permanent_count
        # Add hibernate cache keys
        hibernate_pattern = "hibernate:*"
        hibernate_count = len(redis_client.keys(hibernate_pattern))
        key_counts["hibernate"] = hibernate_count
        total_keys += hibernate_count
        return {
            "total_keys": total_keys,
            "key_counts_by_prefix": key_counts,
        }
    except Exception as e:
        logger.error(f"Error getting key count by prefix: {str(e)}")
        return {"error": str(e)}


def get_hit_rate() -> Dict:
    """
    Get cache hit rate statistics.
    Returns:
        Dictionary with hit rate statistics
    """
    if not CACHE_ENABLED or not redis_client:
        return {"error": "Redis client not available"}

    try:
        info = redis_client.info()

        # Get hit rate
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        total_ops = hits + misses
        hit_rate = (hits / total_ops * 100) if total_ops > 0 else 0
        return {
            "hits": hits,
            "misses": misses,
            "total_operations": total_ops,
            "hit_rate": f"{hit_rate:.2f}%",
            "hit_rate_numeric": hit_rate,
        }
    except Exception as e:
        logger.error(f"Error getting hit rate: {str(e)}")
        return {"error": str(e)}


def get_cache_stats() -> Dict:
    """
    Get comprehensive cache statistics.
    Returns:
        Dictionary with cache statistics
    """
    if not CACHE_ENABLED or not redis_client:
        return {"error": "Redis client not available"}

    try:
        # Get Redis info
        info = redis_client.info()

        # Get memory usage
        memory_stats = get_memory_usage()

        # Get key counts
        key_stats = get_key_count_by_prefix()

        # Get hit rate
        hit_rate_stats = get_hit_rate()

        # Get uptime
        uptime_seconds = info.get("uptime_in_seconds", 0)
        uptime_days = uptime_seconds / (24 * 60 * 60)

        # Get client connections
        connected_clients = info.get("connected_clients", 0)

        # Get Redis version
        redis_version = info.get("redis_version", "unknown")

        # Get evicted keys
        evicted_keys = info.get("evicted_keys", 0)

        # Get expired keys
        expired_keys = info.get("expired_keys", 0)

        # Combine all stats
        return {
            **memory_stats,
            **key_stats,
            **hit_rate_stats,
            "uptime_seconds": uptime_seconds,
            "uptime_days": f"{uptime_days:.2f}",
            "connected_clients": connected_clients,
            "redis_version": redis_version,
            "evicted_keys": evicted_keys,
            "expired_keys": expired_keys,
            "timestamp": timezone.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {str(e)}")
        return {"error": str(e)}


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

        # Get current time
        now = timezone.now()
        hour_key = now.strftime("%Y-%m-%d-%H")
        day_key = now.strftime("%Y-%m-%d")
        week_key = f"{now.year}-{now.isocalendar()[1]}"  # ISO week number
        # Record hourly stats
        hourly_key = f"{HOURLY_STATS_KEY}{hour_key}"
        redis_client.set(hourly_key, json.dumps(stats))
        redis_client.expire(hourly_key, 60 * 60 * 24 * 7)  # Keep for 7 days
        # Record daily stats
        daily_key = f"{DAILY_STATS_KEY}{day_key}"
        redis_client.set(daily_key, json.dumps(stats))
        redis_client.expire(daily_key, 60 * 60 * 24 * 30)  # Keep for 30 days
        # Record weekly stats
        weekly_key = f"{WEEKLY_STATS_KEY}{week_key}"
        redis_client.set(weekly_key, json.dumps(stats))
        redis_client.expire(weekly_key, 60 * 60 * 24 * 90)  # Keep for 90 days

        logger.info(f"Recorded cache stats for {now.isoformat()}")

        # Check for alerts
        check_alerts(stats)

        return True
    except Exception as e:
        logger.error(f"Error recording stats: {str(e)}")
        return False


def get_historical_stats(period: str = "hourly", days: int = 1) -> List[Dict]:
    """
    Get historical cache statistics.

    Args:
        period: "hourly", "daily", or "weekly"
        days: Number of days to look back

    Returns:
        List of statistics dictionaries
    """
    if not CACHE_ENABLED or not redis_client:
        return [{"error": "Redis client not available"}]

    try:
        # Get current time
        now = timezone.now()

        # Determine key prefix based on period
        if period == "hourly":
            key_prefix = HOURLY_STATS_KEY
        elif period == "daily":
            key_prefix = DAILY_STATS_KEY
        elif period == "weekly":
            key_prefix = WEEKLY_STATS_KEY
        else:
            return [{"error": f"Invalid period: {period}"}]

        # Get keys for the specified period and days
        keys = redis_client.keys(f"{key_prefix}*")

        # Sort keys by timestamp (newest first)
        keys.sort(reverse=True)

        # Limit to the specified number of days
        if period == "hourly":
            # For hourly, we need to calculate how many hours in the days
            limit = days * 24
            keys = keys[:limit]
        else:
            # For daily and weekly, just use days directly
            keys = keys[:days]
        # Get stats for each key
        stats = []
        for key in keys:
            data = redis_client.get(key)
            if data:
                stats.append(json.loads(data))
        return stats
    except Exception as e:
        logger.error(f"Error getting historical stats: {str(e)}")
        return [{"error": str(e)}]


def check_alerts(stats: Dict) -> List[Dict[str, Any]]:
    """
    Check for alert conditions in cache statistics.

    Args:
        stats: Cache statistics dictionary

    Returns:
        List of triggered alerts
    """
    alerts = []

    try:
        # Check memory usage
        if MONITOR_MEMORY_USAGE:
            memory_usage = float(stats.get("memory_usage_percent", "0").rstrip("%"))
            if memory_usage > MEMORY_USAGE_THRESHOLD:
                alert = {
                    "type": "memory_usage",
                    "severity": "warning" if memory_usage < 90 else "critical",
                    "message": f"Redis memory usage ({memory_usage:.2f}%) exceeds threshold ({MEMORY_USAGE_THRESHOLD}%)",
                    "threshold": MEMORY_USAGE_THRESHOLD,
                    "value": memory_usage,
                    "timestamp": timezone.now().isoformat(),
                }
                alerts.append(alert)
                trigger_alert(alert)

        # Check hit rate
        if MONITOR_HIT_RATE:
            hit_rate = stats.get("hit_rate_numeric", 0)
            if hit_rate < HIT_RATE_THRESHOLD:
                alert = {
                    "type": "hit_rate",
                    "severity": "warning",
                    "message": f"Redis hit rate ({hit_rate:.2f}%) below threshold ({HIT_RATE_THRESHOLD}%)",
                    "threshold": HIT_RATE_THRESHOLD,
                    "value": hit_rate,
                    "timestamp": timezone.now().isoformat(),
                }
                alerts.append(alert)
                trigger_alert(alert)

        # Check evictions
        evicted_keys = stats.get("evicted_keys", 0)
        if evicted_keys > ALERT_THRESHOLD_EVICTIONS:
            alert = {
                "type": "evictions",
                "severity": "warning",
                "message": f"High number of evictions: {evicted_keys}",
                "threshold": ALERT_THRESHOLD_EVICTIONS,
                "value": evicted_keys,
                "timestamp": timezone.now().isoformat(),
            }
            alerts.append(alert)
            trigger_alert(alert)

        return alerts
    except Exception as e:
        logger.error(f"Error checking alerts: {str(e)}")
        return []


def trigger_alert(alert: Dict[str, Any]) -> bool:
    """
    Trigger an alert.

    Args:
        alert: Alert data

    Returns:
        True if alert was triggered, False otherwise
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
        # Get keys matching the pattern
        keys = redis_client.keys(pattern)

        # If there are too many keys, sample them
        if len(keys) > sample_size:
            import random
            keys = random.sample(keys, sample_size)
        # Get size of each key
        key_sizes = []
        for key in keys:
            # Get the type of the key
            key_type = redis_client.type(key)
            # Get the size based on the type
            if key_type == b"string":
                size = len(redis_client.get(key) or b"")
            elif key_type == b"hash":
                size = sum(len(k) + len(v) for k, v in redis_client.hgetall(key).items())
            elif key_type == b"list":
                size = sum(len(item) for item in redis_client.lrange(key, 0, -1))
            elif key_type == b"set":
                size = sum(len(member) for member in redis_client.smembers(key))
            elif key_type == b"zset":
                size = sum(len(member) for member in redis_client.zrange(key, 0, -1))
            else:
                size = 0

            key_sizes.append({"key": key, "size": size, "type": key_type})

        # Calculate statistics
        if key_sizes:
            total_size = sum(item["size"] for item in key_sizes)
            avg_size = total_size / len(key_sizes)
            max_size = max(item["size"] for item in key_sizes)
            min_size = min(item["size"] for item in key_sizes)

            # Sort by size (largest first)
            key_sizes.sort(key=lambda x: x["size"], reverse=True)

            return {
                "total_keys": len(keys),
                "sampled_keys": len(key_sizes),
                "total_size_bytes": total_size,
                "total_size_human": f"{total_size / (1024 * 1024):.2f} MB" if total_size > 1024 * 1024 else f"{total_size / 1024:.2f} KB",
                "avg_size_bytes": avg_size,
                "avg_size_human": f"{avg_size / 1024:.2f} KB" if avg_size > 1024 else f"{avg_size:.2f} bytes",
                "max_size_bytes": max_size,
                "max_size_human": f"{max_size / (1024 * 1024):.2f} MB" if max_size > 1024 * 1024 else f"{max_size / 1024:.2f} KB",
                "min_size_bytes": min_size,
                "min_size_human": f"{min_size / 1024:.2f} KB" if min_size > 1024 else f"{min_size:.2f} bytes",
                "largest_keys": key_sizes[:10],  # Top 10 largest keys
            }
        else:
            return {"error": f"No keys found matching pattern: {pattern}"}
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
        # Calculate time range
        end_time = timezone.now()
        start_time = end_time - timedelta(days=days)

        # Generate keys for the time range
        keys = []
        current_time = start_time

        while current_time <= end_time:
            date_str = current_time.strftime("%Y%m%d")
            key = f"{STATS_KEY_PREFIX}alerts:{date_str}"
            keys.append(key)
            current_time += timedelta(days=1)

        # Get alerts for each key
        result = []

        for key in keys:
            alerts = redis_client.lrange(key, 0, -1)
            for alert_data in alerts:
                try:
                    alert = json.loads(alert_data)
                    result.append(alert)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in alert: {alert_data}")

        # Sort by timestamp
        result.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        return result
    except Exception as e:
        logger.error(f"Error getting recent alerts: {str(e)}")
        return []


def get_dashboard_data() -> Dict[str, Any]:
    """
    Get data for the Redis cache dashboard.

    Returns:
        Dashboard data
    """
    if not CACHE_ENABLED or not redis_client:
        return {"error": "Redis not available"}

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

        for stats in historical_stats:
            timestamp = stats.get("timestamp")
            hit_rate = stats.get("hit_rate_numeric", 0)
            memory_used_mb = float(stats.get("used_memory_human", "0").split()[0])
            total_keys = stats.get("total_keys", 0)

            if timestamp:
                if hit_rate is not None:
                    hit_rate_over_time.append({
                        "timestamp": timestamp,
                        "hit_rate": hit_rate,
                    })

                if memory_used_mb:
                    memory_usage_over_time.append({
                        "timestamp": timestamp,
                        "memory_used_mb": memory_used_mb,
                    })

                if total_keys:
                    keys_over_time.append({
                        "timestamp": timestamp,
                        "total_keys": total_keys,
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
        }
    except Exception as e:
        logger.error(f"Error getting dashboard data: {str(e)}")
        return {"error": str(e)}

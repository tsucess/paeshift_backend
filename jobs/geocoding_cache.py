"""
Redis-based geocoding cache module for caching geocoded addresses to reduce API calls.

This module provides a caching mechanism for geocoded addresses using Redis,
with support for multiple geocoding providers, fallback mechanisms, and cache eviction policies.

Features:
- Efficient caching of geocoding results
- Automatic cache expiration
- Memory usage monitoring
- Cache eviction policies to prevent memory issues
- Detailed statistics for monitoring
"""

import hashlib
import json
import logging
import random
import time
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional, Tuple

import redis
from django.conf import settings

logger = logging.getLogger(__name__)

# Redis connection settings
REDIS_HOST = getattr(settings, "REDIS_HOST", "localhost")
REDIS_PORT = getattr(settings, "REDIS_PORT", 6379)
REDIS_DB = getattr(settings, "REDIS_GEOCODE_DB", 1)  # Use a separate DB for geocoding
REDIS_PASSWORD = getattr(settings, "REDIS_PASSWORD", None)

# Cache settings
GEOCODE_CACHE_TIMEOUT = getattr(
    settings, "GEOCODE_CACHE_TIMEOUT", 60 * 60 * 24 * 30
)  # 30 days by default
GEOCODE_CACHE_PREFIX = "geocode:"
GEOCODE_CACHE_MAX_ENTRIES = getattr(
    settings, "GEOCODE_CACHE_MAX_ENTRIES", 100000
)  # Maximum number of cache entries
GEOCODE_CACHE_MAX_MEMORY_MB = getattr(
    settings, "GEOCODE_CACHE_MAX_MEMORY_MB", 100
)  # Maximum memory usage in MB
GEOCODE_CACHE_EVICTION_POLICY = getattr(
    settings, "GEOCODE_CACHE_EVICTION_POLICY", "lru"
)  # LRU, random, or ttl
GEOCODE_CACHE_STATS_INTERVAL = getattr(
    settings, "GEOCODE_CACHE_STATS_INTERVAL", 100
)  # Log stats every N operations

# Monitoring settings
_cache_operations_counter = 0  # Counter for cache operations
_last_eviction_check = 0  # Timestamp of last eviction check

# Initialize Redis connection
try:
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        password=REDIS_PASSWORD,
        decode_responses=True,
        socket_timeout=5,
        health_check_interval=30,  # Check connection health every 30 seconds
    )
    # Test connection
    redis_client.ping()
    logger.info(f"Successfully connected to Redis for geocoding cache (DB: {REDIS_DB})")

    # Log cache configuration
    logger.info(f"Geocoding cache configuration:")
    logger.info(
        f"  - Timeout: {GEOCODE_CACHE_TIMEOUT} seconds ({GEOCODE_CACHE_TIMEOUT/86400:.1f} days)"
    )
    logger.info(f"  - Max entries: {GEOCODE_CACHE_MAX_ENTRIES}")
    logger.info(f"  - Max memory: {GEOCODE_CACHE_MAX_MEMORY_MB} MB")
    logger.info(f"  - Eviction policy: {GEOCODE_CACHE_EVICTION_POLICY}")

except redis.ConnectionError as e:
    logger.warning(f"Could not connect to Redis for geocoding cache: {str(e)}")
    redis_client = None
except Exception as e:
    logger.error(f"Unexpected error connecting to Redis: {str(e)}")
    redis_client = None


def get_cache_key(address: str) -> str:
    """
    Generate a cache key for an address.

    Args:
        address: The address to generate a cache key for

    Returns:
        A cache key string
    """
    # Normalize the address to ensure consistent cache keys
    normalized_address = address.lower().strip()

    # Use MD5 hash to create a fixed-length key that works well with Redis
    address_hash = hashlib.md5(normalized_address.encode()).hexdigest()
    return f"{GEOCODE_CACHE_PREFIX}{address_hash}"


def check_cache_limits() -> None:
    """
    Check if the cache has exceeded its limits and apply eviction policy if needed.

    This function implements various cache eviction policies to prevent memory issues:
    - LRU: Evict least recently used entries
    - Random: Evict random entries
    - TTL: Evict entries with the shortest TTL
    """
    global _last_eviction_check

    # Only check periodically to avoid performance impact
    current_time = time.time()
    if current_time - _last_eviction_check < 60:  # Check at most once per minute
        return

    _last_eviction_check = current_time

    if not redis_client:
        return

    try:
        # Get all cache keys
        pattern = f"{GEOCODE_CACHE_PREFIX}*"
        keys = redis_client.keys(pattern)
        total_entries = len(keys)

        # Check entry count limit
        if total_entries > GEOCODE_CACHE_MAX_ENTRIES:
            entries_to_remove = int(total_entries * 0.2)  # Remove 20% of entries
            logger.warning(
                f"Cache entry limit exceeded ({total_entries}/{GEOCODE_CACHE_MAX_ENTRIES}). Removing {entries_to_remove} entries."
            )

            if GEOCODE_CACHE_EVICTION_POLICY == "random":
                # Random eviction
                keys_to_remove = random.sample(keys, min(entries_to_remove, len(keys)))
                if keys_to_remove:
                    redis_client.delete(*keys_to_remove)
                    logger.info(f"Randomly evicted {len(keys_to_remove)} cache entries")

            elif GEOCODE_CACHE_EVICTION_POLICY == "ttl":
                # TTL-based eviction (remove entries with shortest TTL)
                keys_with_ttl = [(key, redis_client.ttl(key)) for key in keys]
                keys_with_ttl.sort(key=lambda x: x[1])  # Sort by TTL (ascending)
                keys_to_remove = [k[0] for k in keys_with_ttl[:entries_to_remove]]
                if keys_to_remove:
                    redis_client.delete(*keys_to_remove)
                    logger.info(
                        f"Evicted {len(keys_to_remove)} cache entries with shortest TTL"
                    )

            else:  # Default to LRU
                # LRU eviction (implemented by checking access time)
                # This is a simplified LRU implementation
                keys_with_data = []
                for key in keys:
                    data = redis_client.get(key)
                    if data:
                        try:
                            result = json.loads(data)
                            accessed_at = result.get(
                                "last_accessed", result.get("cached_at", "")
                            )
                            keys_with_data.append((key, accessed_at))
                        except:
                            keys_with_data.append((key, ""))

                # Sort by access time (oldest first)
                keys_with_data.sort(key=lambda x: x[1])
                keys_to_remove = [k[0] for k in keys_with_data[:entries_to_remove]]
                if keys_to_remove:
                    redis_client.delete(*keys_to_remove)
                    logger.info(
                        f"Evicted {len(keys_to_remove)} least recently used cache entries"
                    )

        # Check memory usage limit
        memory_used_bytes = sum(
            redis_client.memory_usage(key) or 0 for key in redis_client.keys(pattern)
        )
        memory_used_mb = memory_used_bytes / (1024 * 1024)

        if memory_used_mb > GEOCODE_CACHE_MAX_MEMORY_MB:
            # Calculate how many entries to remove to get below 80% of the limit
            target_memory_mb = GEOCODE_CACHE_MAX_MEMORY_MB * 0.8
            reduction_factor = target_memory_mb / memory_used_mb
            entries_to_remove = int(total_entries * (1 - reduction_factor))

            logger.warning(
                f"Cache memory limit exceeded ({memory_used_mb:.2f}MB/{GEOCODE_CACHE_MAX_MEMORY_MB}MB). Removing {entries_to_remove} entries."
            )

            # Use the same eviction policy as above
            if GEOCODE_CACHE_EVICTION_POLICY == "random":
                keys_to_remove = random.sample(keys, min(entries_to_remove, len(keys)))
            elif GEOCODE_CACHE_EVICTION_POLICY == "ttl":
                keys_with_ttl = [(key, redis_client.ttl(key)) for key in keys]
                keys_with_ttl.sort(key=lambda x: x[1])
                keys_to_remove = [k[0] for k in keys_with_ttl[:entries_to_remove]]
            else:  # LRU
                keys_with_data = []
                for key in random.sample(
                    keys, min(100, len(keys))
                ):  # Sample to avoid checking all keys
                    data = redis_client.get(key)
                    if data:
                        try:
                            result = json.loads(data)
                            accessed_at = result.get(
                                "last_accessed", result.get("cached_at", "")
                            )
                            keys_with_data.append((key, accessed_at))
                        except:
                            keys_with_data.append((key, ""))

                keys_with_data.sort(key=lambda x: x[1])
                keys_to_remove = [k[0] for k in keys_with_data[:entries_to_remove]]

            if keys_to_remove:
                redis_client.delete(*keys_to_remove)
                logger.info(
                    f"Evicted {len(keys_to_remove)} cache entries to reduce memory usage"
                )

    except Exception as e:
        logger.error(f"Error checking cache limits: {str(e)}")


def log_cache_stats() -> None:
    """
    Log cache statistics periodically.
    """
    global _cache_operations_counter

    _cache_operations_counter += 1

    # Log stats periodically
    if _cache_operations_counter % GEOCODE_CACHE_STATS_INTERVAL == 0:
        stats = get_cache_stats()
        memory_mb = stats.get("memory_used_bytes", 0) / (1024 * 1024)
        logger.info(
            f"Geocoding cache stats: {stats.get('total_entries', 0)} entries, {memory_mb:.2f}MB used"
        )


def get_cached_coordinates(address: str) -> Optional[Dict[str, Any]]:
    """
    Get cached coordinates for an address from Redis with enhanced monitoring.

    Args:
        address: The address to get coordinates for

    Returns:
        A dictionary with geocoding results or None if not in cache
    """
    if not redis_client or not address or not isinstance(address, str):
        return None

    cache_key = get_cache_key(address)

    try:
        # Check cache limits periodically
        check_cache_limits()

        # Get data from cache
        cached_data = redis_client.get(cache_key)

        if cached_data:
            # Parse the cached data
            result = json.loads(cached_data)

            # Convert string coordinates back to Decimal for consistency
            if result.get("success") and "latitude" in result and "longitude" in result:
                result["latitude"] = Decimal(result["latitude"])
                result["longitude"] = Decimal(result["longitude"])

            # Update last accessed time and increment hit counter
            if "hit_count" in result:
                result["hit_count"] += 1
            else:
                result["hit_count"] = 1

            result["last_accessed"] = datetime.now().isoformat()

            # Update the cache with the new access time and hit count
            try:
                # Convert Decimal objects to strings for JSON serialization
                serializable_result = {}
                for key, value in result.items():
                    if isinstance(value, Decimal):
                        serializable_result[key] = str(value)
                    else:
                        serializable_result[key] = value

                # Update the cache entry with the new data
                redis_client.setex(
                    cache_key, GEOCODE_CACHE_TIMEOUT, json.dumps(serializable_result)
                )
            except Exception as update_error:
                logger.warning(f"Error updating cache access time: {str(update_error)}")

            # Log the cache hit
            logger.info(
                f"Cache hit for address: {address} (hit #{result.get('hit_count', 1)})"
            )

            # Log cache stats periodically
            log_cache_stats()

            return result

        logger.info(f"Cache miss for address: {address}")

        # Log cache stats periodically
        log_cache_stats()

        return None
    except Exception as e:
        logger.error(f"Error retrieving cached coordinates for {address}: {str(e)}")
        return None


def cache_coordinates(address: str, geocoding_result: Dict[str, Any]) -> None:
    """
    Cache coordinates for an address in Redis with enhanced monitoring.

    Args:
        address: The address to cache coordinates for
        geocoding_result: The geocoding result to cache
    """
    if (
        not redis_client
        or not address
        or not isinstance(address, str)
        or not geocoding_result
    ):
        return

    cache_key = get_cache_key(address)

    # Add metadata to track cache usage
    geocoding_result["cached_at"] = datetime.now().isoformat()
    geocoding_result["last_accessed"] = datetime.now().isoformat()
    geocoding_result["hit_count"] = 0

    try:
        # Check cache limits periodically
        check_cache_limits()

        # Convert Decimal objects to strings for JSON serialization
        serializable_result = {}
        for key, value in geocoding_result.items():
            if isinstance(value, Decimal):
                serializable_result[key] = str(value)
            else:
                serializable_result[key] = value

        # Store in Redis with expiration
        redis_client.setex(
            cache_key, GEOCODE_CACHE_TIMEOUT, json.dumps(serializable_result)
        )

        logger.info(f"Cached coordinates for address: {address}")

        # Log cache stats periodically
        log_cache_stats()

    except Exception as e:
        logger.error(f"Error caching coordinates for address {address}: {str(e)}")


def clear_geocoding_cache() -> None:
    """
    Clear all geocoding cache entries from Redis.
    This is useful for testing or when geocoding data needs to be refreshed.
    """
    if not redis_client:
        logger.warning("Redis client not available, cannot clear cache")
        return

    try:
        # Find all keys with the geocoding prefix
        pattern = f"{GEOCODE_CACHE_PREFIX}*"
        keys = redis_client.keys(pattern)

        if keys:
            redis_client.delete(*keys)
            logger.info(f"Cleared {len(keys)} geocoding cache entries from Redis")
        else:
            logger.info("No geocoding cache entries to clear")

        # Reset monitoring counters
        global _cache_operations_counter, _last_eviction_check
        _cache_operations_counter = 0
        _last_eviction_check = time.time()

    except Exception as e:
        logger.error(f"Error clearing geocoding cache: {str(e)}")


def get_cache_stats() -> Dict[str, Any]:
    """
    Get detailed statistics about the geocoding cache.

    Returns:
        Dictionary with cache statistics
    """
    if not redis_client:
        return {"error": "Redis client not available"}

    try:
        pattern = f"{GEOCODE_CACHE_PREFIX}*"
        keys = redis_client.keys(pattern)

        # Calculate memory usage
        memory_used_bytes = sum(redis_client.memory_usage(key) or 0 for key in keys)
        memory_used_mb = memory_used_bytes / (1024 * 1024)

        # Get server info
        info = redis_client.info()

        # Calculate age distribution (sample up to 100 keys)
        age_distribution = {"<1h": 0, "1-24h": 0, "1-7d": 0, "7-30d": 0, ">30d": 0}
        hit_count_total = 0
        hit_count_keys = 0

        sample_size = min(100, len(keys))
        if sample_size > 0:
            sampled_keys = random.sample(keys, sample_size)
            now = datetime.now()

            for key in sampled_keys:
                data = redis_client.get(key)
                if data:
                    try:
                        result = json.loads(data)
                        cached_at = result.get("cached_at", "")
                        if cached_at:
                            cached_time = datetime.fromisoformat(cached_at)
                            age = now - cached_time

                            if age.total_seconds() < 3600:  # < 1 hour
                                age_distribution["<1h"] += 1
                            elif age.total_seconds() < 86400:  # < 24 hours
                                age_distribution["1-24h"] += 1
                            elif age.days < 7:  # < 7 days
                                age_distribution["1-7d"] += 1
                            elif age.days < 30:  # < 30 days
                                age_distribution["7-30d"] += 1
                            else:  # > 30 days
                                age_distribution[">30d"] += 1

                        # Track hit counts
                        hit_count = result.get("hit_count", 0)
                        hit_count_total += hit_count
                        hit_count_keys += 1
                    except:
                        pass

            # Scale up the distribution to represent the full cache
            if sample_size < len(keys):
                scale_factor = len(keys) / sample_size
                for key in age_distribution:
                    age_distribution[key] = int(age_distribution[key] * scale_factor)

        # Calculate average hit count
        avg_hit_count = hit_count_total / hit_count_keys if hit_count_keys > 0 else 0

        return {
            "total_entries": len(keys),
            "memory_used_bytes": memory_used_bytes,
            "memory_used_mb": round(memory_used_mb, 2),
            "memory_limit_mb": GEOCODE_CACHE_MAX_MEMORY_MB,
            "memory_usage_percent": round(
                (memory_used_mb / GEOCODE_CACHE_MAX_MEMORY_MB) * 100, 2
            )
            if GEOCODE_CACHE_MAX_MEMORY_MB > 0
            else 0,
            "entries_limit": GEOCODE_CACHE_MAX_ENTRIES,
            "entries_usage_percent": round(
                (len(keys) / GEOCODE_CACHE_MAX_ENTRIES) * 100, 2
            )
            if GEOCODE_CACHE_MAX_ENTRIES > 0
            else 0,
            "eviction_policy": GEOCODE_CACHE_EVICTION_POLICY,
            "redis_version": info.get("redis_version", "unknown"),
            "redis_memory_used_mb": round(
                info.get("used_memory", 0) / (1024 * 1024), 2
            ),
            "redis_memory_peak_mb": round(
                info.get("used_memory_peak", 0) / (1024 * 1024), 2
            ),
            "redis_connected_clients": info.get("connected_clients", 0),
            "age_distribution": age_distribution,
            "average_hit_count": round(avg_hit_count, 2),
            "cache_operations": _cache_operations_counter,
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {str(e)}")
        return {"error": str(e)}

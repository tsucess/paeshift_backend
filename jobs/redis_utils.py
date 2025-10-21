"""
Redis caching utilities for the jobs app.

This module provides Redis caching utilities specifically for the jobs app.
It should be updated to use the consolidated core Redis caching functionality.
"""

import pickle
from typing import Any, Dict, List, Optional

from django.core.cache import cache


class RedisCache:
    """Utility class for Redis caching operations."""

    @staticmethod
    def get_key(prefix: str, identifier: Any) -> str:
        """Generate a consistent cache key."""
        return f"{prefix}:{identifier}"

    @staticmethod
    def set_cache(key: str, value: Any, timeout: int = 3600) -> bool:
        """Set cache with serialization support."""
        try:
            serialized_value = pickle.dumps(value)
            return cache.set(key, serialized_value, timeout)
        except Exception as e:
            print(f"Cache set error: {e}")
            return False

    @staticmethod
    def get_cache(key: str) -> Optional[Any]:
        """Get cache with deserialization support."""
        try:
            cached_value = cache.get(key)
            if cached_value:
                return pickle.loads(cached_value)
            return None
        except Exception as e:
            print(f"Cache get error: {e}")
            return None

    @staticmethod
    def delete_cache(key: str) -> bool:
        """Delete cache entry."""
        return cache.delete(key)

    @staticmethod
    def clear_pattern(pattern: str) -> None:
        """Clear all cache keys matching a pattern."""
        keys = cache.keys(pattern)
        if keys:
            cache.delete_many(keys)


class JobCache(RedisCache):
    """Job-specific caching operations."""

    @staticmethod
    def get_job_key(job_id: int) -> str:
        return RedisCache.get_key("job", job_id)

    @staticmethod
    def cache_job(job: Any) -> bool:
        """Cache a job object."""
        key = JobCache.get_job_key(job.id)
        return JobCache.set_cache(key, job, timeout=3600)

    @staticmethod
    def get_cached_job(job_id: int) -> Optional[Any]:
        """Get a cached job."""
        key = JobCache.get_job_key(job_id)
        return JobCache.get_cache(key)

    @staticmethod
    def invalidate_job(job_id: int) -> bool:
        """Invalidate job cache."""
        key = JobCache.get_job_key(job_id)
        return JobCache.delete_cache(key)


class UserCache(RedisCache):
    """User-specific caching operations."""

    @staticmethod
    def get_user_key(user_id: int) -> str:
        return RedisCache.get_key("user", user_id)

    @staticmethod
    def cache_user(user: Any) -> bool:
        """Cache a user object."""
        key = UserCache.get_user_key(user.id)
        return UserCache.set_cache(key, user, timeout=1800)

    @staticmethod
    def get_cached_user(user_id: int) -> Optional[Any]:
        """Get a cached user."""
        key = UserCache.get_user_key(user_id)
        return UserCache.get_cache(key)

    @staticmethod
    def invalidate_user(user_id: int) -> bool:
        """Invalidate user cache."""
        key = UserCache.get_user_key(user_id)
        return UserCache.delete_cache(key)


class LocationCache(RedisCache):
    """Location-specific caching operations."""

    @staticmethod
    def get_location_key(user_id: int) -> str:
        return RedisCache.get_key("location", user_id)

    @staticmethod
    def cache_location(user_id: int, location_data: Dict) -> bool:
        """Cache user location data."""
        key = LocationCache.get_location_key(user_id)
        return LocationCache.set_cache(key, location_data, timeout=300)  # 5 minutes

    @staticmethod
    def get_cached_location(user_id: int) -> Optional[Dict]:
        """Get cached user location."""
        key = LocationCache.get_location_key(user_id)
        return LocationCache.get_cache(key)


class GamificationCache(RedisCache):
    """Gamification-specific caching operations."""

    @staticmethod
    def get_points_key(user_id: int) -> str:
        return RedisCache.get_key("points", user_id)

    @staticmethod
    def get_achievements_key(user_id: int) -> str:
        return RedisCache.get_key("achievements", user_id)

    @staticmethod
    def get_badges_key(user_id: int) -> str:
        return RedisCache.get_key("badges", user_id)

    @staticmethod
    def cache_user_points(user_id: int, points_data: Dict) -> bool:
        """Cache user points data."""
        key = GamificationCache.get_points_key(user_id)
        return GamificationCache.set_cache(key, points_data, timeout=1800)

    @staticmethod
    def cache_user_achievements(user_id: int, achievements: List) -> bool:
        """Cache user achievements."""
        key = GamificationCache.get_achievements_key(user_id)
        return GamificationCache.set_cache(key, achievements, timeout=3600)

    @staticmethod
    def cache_user_badges(user_id: int, badges: List) -> bool:
        """Cache user badges."""
        key = GamificationCache.get_badges_key(user_id)
        return GamificationCache.set_cache(key, badges, timeout=3600)


class RateLimiter:
    """Rate limiting using Redis."""

    @staticmethod
    def is_rate_limited(key: str, limit: int, window: int) -> bool:
        """Check if a request should be rate limited."""
        current = cache.get(key, 0)
        if current >= limit:
            return True
        cache.incr(key)
        cache.expire(key, window)
        return False

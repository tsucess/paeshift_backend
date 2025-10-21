"""
Cache utilities for Phase 2.2c: Caching Implementation

Provides decorators and utilities for caching API responses and query results.
"""

import hashlib
import json
import logging
from functools import wraps
from typing import Any, Callable, Optional

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse

logger = logging.getLogger(__name__)

# Cache TTL constants
CACHE_TTL_PROFILE = getattr(settings, 'CACHE_TTL_PROFILE', 3600)  # 1 hour
CACHE_TTL_REVIEWS = getattr(settings, 'CACHE_TTL_REVIEWS', 1800)  # 30 minutes
CACHE_TTL_PAYMENTS = getattr(settings, 'CACHE_TTL_PAYMENTS', 300)  # 5 minutes
CACHE_TTL_JOBS = getattr(settings, 'CACHE_TTL_JOBS', 1800)  # 30 minutes
CACHE_TTL_APPLICATIONS = getattr(settings, 'CACHE_TTL_APPLICATIONS', 300)  # 5 minutes


class CacheStats:
    """Track cache hit/miss statistics"""
    
    @staticmethod
    def get_stats() -> dict:
        """Get current cache statistics"""
        hits = cache.get('cache_stats:hits', 0)
        misses = cache.get('cache_stats:misses', 0)
        total = hits + misses
        hit_rate = (hits / total * 100) if total > 0 else 0
        
        return {
            'hits': hits,
            'misses': misses,
            'total': total,
            'hit_rate': round(hit_rate, 2),
        }
    
    @staticmethod
    def record_hit():
        """Record a cache hit"""
        hits = cache.get('cache_stats:hits', 0) + 1
        cache.set('cache_stats:hits', hits, None)  # No expiry for stats
    
    @staticmethod
    def record_miss():
        """Record a cache miss"""
        misses = cache.get('cache_stats:misses', 0) + 1
        cache.set('cache_stats:misses', misses, None)  # No expiry for stats
    
    @staticmethod
    def reset():
        """Reset cache statistics"""
        cache.delete('cache_stats:hits')
        cache.delete('cache_stats:misses')


def generate_cache_key(prefix: str, *args, **kwargs) -> str:
    """
    Generate a cache key from prefix and arguments
    
    Args:
        prefix: Cache key prefix (e.g., 'reviews:user')
        *args: Positional arguments to include in key
        **kwargs: Keyword arguments to include in key
    
    Returns:
        Generated cache key
    """
    key_parts = [prefix]
    
    # Add positional arguments
    for arg in args:
        key_parts.append(str(arg))
    
    # Add keyword arguments (sorted for consistency)
    for k in sorted(kwargs.keys()):
        key_parts.append(f"{k}={kwargs[k]}")
    
    # Create hash for long keys
    key = ':'.join(key_parts)
    if len(key) > 250:  # Redis key limit is 512MB, but keep it reasonable
        key_hash = hashlib.md5(key.encode()).hexdigest()
        key = f"{prefix}:{key_hash}"
    
    return key


def cache_query_result(
    timeout: int = 300,
    prefix: str = 'query',
    key_args: Optional[list] = None,
    key_kwargs: Optional[list] = None
):
    """
    Decorator to cache query results
    
    Args:
        timeout: Cache timeout in seconds
        prefix: Cache key prefix
        key_args: List of argument indices to include in cache key
        key_kwargs: List of keyword argument names to include in cache key
    
    Example:
        @cache_query_result(timeout=1800, prefix='reviews:user', key_args=[1])
        def get_user_reviews(user_id):
            return Review.objects.filter(reviewed_id=user_id)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key_args = []
            if key_args:
                for idx in key_args:
                    if idx < len(args):
                        cache_key_args.append(args[idx])
            
            cache_key_kwargs = {}
            if key_kwargs:
                for kwarg_name in key_kwargs:
                    if kwarg_name in kwargs:
                        cache_key_kwargs[kwarg_name] = kwargs[kwarg_name]
            
            cache_key = generate_cache_key(prefix, *cache_key_args, **cache_key_kwargs)
            
            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                CacheStats.record_hit()
                logger.debug(f"Cache hit: {cache_key}")
                return cached_result
            
            # Cache miss - execute function
            CacheStats.record_miss()
            result = func(*args, **kwargs)
            
            # Cache the result
            cache.set(cache_key, result, timeout)
            logger.debug(f"Cache miss: {cache_key} (cached for {timeout}s)")
            
            return result
        
        return wrapper
    return decorator


def cache_api_response(
    timeout: int = 300,
    prefix: str = 'api'
):
    """
    Decorator to cache API responses
    
    Args:
        timeout: Cache timeout in seconds
        prefix: Cache key prefix
    
    Example:
        @cache_api_response(timeout=600, prefix='reviews')
        @core_router.get("/reviews/{user_id}")
        def get_user_reviews(request, user_id: int):
            return {...}
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            # Generate cache key from request path and query params
            cache_key = generate_cache_key(
                prefix,
                request.path,
                request.GET.urlencode() if request.GET else ''
            )
            
            # Try to get from cache
            cached_response = cache.get(cache_key)
            if cached_response is not None:
                CacheStats.record_hit()
                logger.debug(f"Cache hit: {cache_key}")
                return cached_response
            
            # Cache miss - execute function
            CacheStats.record_miss()
            response = func(request, *args, **kwargs)
            
            # Cache the response
            cache.set(cache_key, response, timeout)
            logger.debug(f"Cache miss: {cache_key} (cached for {timeout}s)")
            
            return response
        
        return wrapper
    return decorator


def invalidate_cache(pattern: str = None, keys: list = None):
    """
    Invalidate cache entries
    
    Args:
        pattern: Pattern to match cache keys (e.g., 'reviews:user:*')
        keys: List of specific cache keys to invalidate
    
    Example:
        # Invalidate specific keys
        invalidate_cache(keys=['reviews:user:123', 'reviews:user:123:recent'])
        
        # Invalidate by pattern (requires Redis)
        invalidate_cache(pattern='reviews:user:123:*')
    """
    if keys:
        for key in keys:
            cache.delete(key)
            logger.debug(f"Invalidated cache: {key}")
    
    if pattern:
        try:
            # This requires Redis backend
            from django_redis import get_redis_connection
            redis_conn = get_redis_connection('default')
            
            # Find keys matching pattern
            matching_keys = redis_conn.keys(pattern)
            if matching_keys:
                redis_conn.delete(*matching_keys)
                logger.debug(f"Invalidated {len(matching_keys)} cache entries matching: {pattern}")
        except Exception as e:
            logger.warning(f"Failed to invalidate cache pattern {pattern}: {str(e)}")


def clear_all_cache():
    """Clear all cache entries"""
    try:
        cache.clear()
        logger.info("All cache entries cleared")
    except Exception as e:
        logger.error(f"Failed to clear cache: {str(e)}")


def get_cache_info() -> dict:
    """Get cache information and statistics"""
    stats = CacheStats.get_stats()
    
    return {
        'enabled': getattr(settings, 'CACHE_ENABLED', False),
        'backend': settings.CACHES['default']['BACKEND'],
        'statistics': stats,
        'ttl_settings': {
            'profile': CACHE_TTL_PROFILE,
            'reviews': CACHE_TTL_REVIEWS,
            'payments': CACHE_TTL_PAYMENTS,
            'jobs': CACHE_TTL_JOBS,
            'applications': CACHE_TTL_APPLICATIONS,
        }
    }


"""
Redis-based caching utilities with advanced features.

This module provides utilities for hierarchical caching, cache warming,
and cache stampede protection using Redis.
"""

import logging
import random
import time
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from django.core.cache import cache
from django.db.models import Model, QuerySet
from django.http import HttpRequest, JsonResponse

from core.cache import (
    get_cached_data,
    get_with_stampede_protection,
    set_cached_data,
    warm_cache,
)

logger = logging.getLogger(__name__)


class HierarchicalCache:
    """
    Hierarchical caching with multiple cache levels.
    
    This class provides methods for caching data in multiple levels:
    - L1: Local memory (fastest, but not shared)
    - L2: Redis (shared across servers)
    - L3: Database (slowest, but authoritative)
    """
    
    # Class-level memory cache
    _memory_cache: Dict[str, Tuple[Any, float]] = {}
    
    @classmethod
    def get(cls, key: str, db_func: Callable, timeout: int = 3600, memory_timeout: int = 60) -> Any:
        """
        Get data from cache or database.
        
        Args:
            key: Cache key
            db_func: Function to get data from database
            timeout: Redis cache timeout in seconds
            memory_timeout: Memory cache timeout in seconds
            
        Returns:
            Cached data or data from database
        """
        # Check memory cache (L1)
        memory_data = cls._get_from_memory(key)
        if memory_data is not None:
            logger.debug(f"L1 cache hit for {key}")
            return memory_data
            
        # Check Redis cache (L2)
        redis_data = get_cached_data(key)
        if redis_data is not None:
            logger.debug(f"L2 cache hit for {key}")
            # Update memory cache
            cls._set_in_memory(key, redis_data, memory_timeout)
            return redis_data
            
        # Get from database (L3)
        logger.debug(f"Cache miss for {key}, fetching from database")
        db_data = db_func()
        
        # Update caches
        set_cached_data(key, db_data, timeout)
        cls._set_in_memory(key, db_data, memory_timeout)
        
        return db_data
        
    @classmethod
    def get_with_protection(
        cls, 
        key: str, 
        db_func: Callable, 
        timeout: int = 3600, 
        memory_timeout: int = 60,
        stale_timeout: int = 60
    ) -> Any:
        """
        Get data with cache stampede protection.
        
        Args:
            key: Cache key
            db_func: Function to get data from database
            timeout: Redis cache timeout in seconds
            memory_timeout: Memory cache timeout in seconds
            stale_timeout: How long to serve stale data during recomputation
            
        Returns:
            Cached data or data from database
        """
        # Check memory cache (L1)
        memory_data = cls._get_from_memory(key)
        if memory_data is not None:
            logger.debug(f"L1 cache hit for {key}")
            return memory_data
            
        # Get from Redis with stampede protection (L2)
        redis_data = get_with_stampede_protection(key, db_func, timeout, stale_timeout)
        
        # Update memory cache
        cls._set_in_memory(key, redis_data, memory_timeout)
        
        return redis_data
        
    @classmethod
    def set(cls, key: str, data: Any, timeout: int = 3600, memory_timeout: int = 60) -> bool:
        """
        Set data in cache.
        
        Args:
            key: Cache key
            data: Data to cache
            timeout: Redis cache timeout in seconds
            memory_timeout: Memory cache timeout in seconds
            
        Returns:
            True if successful, False otherwise
        """
        # Set in Redis cache (L2)
        redis_result = set_cached_data(key, data, timeout)
        
        # Set in memory cache (L1)
        cls._set_in_memory(key, data, memory_timeout)
        
        return redis_result
        
    @classmethod
    def invalidate(cls, key: str) -> bool:
        """
        Invalidate cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if successful, False otherwise
        """
        # Remove from memory cache (L1)
        cls._remove_from_memory(key)
        
        # Remove from Redis cache (L2)
        from core.cache import delete_cached_data
        return delete_cached_data(key)
        
    @classmethod
    def _get_from_memory(cls, key: str) -> Optional[Any]:
        """
        Get data from memory cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached data or None if not found or expired
        """
        if key in cls._memory_cache:
            data, expiry = cls._memory_cache[key]
            if expiry > time.time():
                return data
                
            # Expired, remove from memory cache
            del cls._memory_cache[key]
            
        return None
        
    @classmethod
    def _set_in_memory(cls, key: str, data: Any, timeout: int) -> None:
        """
        Set data in memory cache.
        
        Args:
            key: Cache key
            data: Data to cache
            timeout: Cache timeout in seconds
        """
        expiry = time.time() + timeout
        cls._memory_cache[key] = (data, expiry)
        
        # Clean up expired entries periodically
        if random.random() < 0.01:  # 1% chance
            cls._cleanup_memory_cache()
            
    @classmethod
    def _remove_from_memory(cls, key: str) -> None:
        """
        Remove data from memory cache.
        
        Args:
            key: Cache key
        """
        if key in cls._memory_cache:
            del cls._memory_cache[key]
            
    @classmethod
    def _cleanup_memory_cache(cls) -> None:
        """Clean up expired entries from memory cache."""
        now = time.time()
        keys_to_delete = [
            key for key, (_, expiry) in cls._memory_cache.items() if expiry <= now
        ]
        for key in keys_to_delete:
            del cls._memory_cache[key]


def hierarchical_cache(
    key_func: Callable,
    timeout: int = 3600,
    memory_timeout: int = 60,
    use_stampede_protection: bool = True,
):
    """
    Decorator for hierarchical caching.
    
    Args:
        key_func: Function that returns the cache key
        timeout: Redis cache timeout in seconds
        memory_timeout: Memory cache timeout in seconds
        use_stampede_protection: Whether to use cache stampede protection
        
    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get cache key
            key = key_func(*args, **kwargs)
            if not key:
                # No key, no caching
                return func(*args, **kwargs)
                
            # Define database function
            def db_func():
                return func(*args, **kwargs)
                
            # Get from cache
            if use_stampede_protection:
                return HierarchicalCache.get_with_protection(
                    key, db_func, timeout, memory_timeout
                )
            else:
                return HierarchicalCache.get(key, db_func, timeout, memory_timeout)
                
        return wrapper
    return decorator


def warm_cache_for(key: str, data_func: Callable, timeout: int = 3600) -> bool:
    """
    Warm cache for a specific key.
    
    Args:
        key: Cache key
        data_func: Function to generate data
        timeout: Cache timeout in seconds
        
    Returns:
        True if successful, False otherwise
    """
    return warm_cache(key, data_func, timeout)


def warm_model_cache(model_class: type, ids: List[int], timeout: int = 3600) -> int:
    """
    Warm cache for model instances.
    
    Args:
        model_class: Model class
        ids: List of instance IDs
        timeout: Cache timeout in seconds
        
    Returns:
        Number of instances cached
    """
    from core.cache import cache_model_instance
    
    count = 0
    for instance_id in ids:
        try:
            # Get instance from database
            instance = model_class.objects.get(id=instance_id)
            
            # Serialize instance
            if hasattr(instance, "to_dict"):
                data = instance.to_dict()
            else:
                # Basic serialization
                data = {
                    "id": instance.id,
                    "model": model_class.__name__,
                }
                
            # Cache instance
            model_type = model_class.__name__.lower()
            if cache_model_instance(model_type, instance_id, data, timeout):
                count += 1
        except model_class.DoesNotExist:
            logger.warning(f"{model_class.__name__} with ID {instance_id} not found")
        except Exception as e:
            logger.error(f"Error warming cache for {model_class.__name__} {instance_id}: {str(e)}")
            
    return count

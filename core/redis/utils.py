"""
Redis utility functions.

This module provides utility functions for working with Redis.
"""

import json
import logging
import hashlib
from typing import Any, Dict, List, Optional, Union

from core.redis.client import redis_client
from core.redis.settings import CACHE_ENABLED

# Set up logging
logger = logging.getLogger(__name__)

class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles additional types."""
    
    def default(self, obj):
        # Handle datetime objects
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        
        # Handle sets
        if isinstance(obj, set):
            return list(obj)
        
        # Handle bytes
        if isinstance(obj, bytes):
            return obj.decode('utf-8')
        
        # Let the base class handle it
        return super().default(obj)

def generate_cache_key(prefix: str, *args, **kwargs) -> str:
    """
    Generate a cache key from a prefix and arguments.
    
    Args:
        prefix: Cache key prefix
        *args: Positional arguments to include in the key
        **kwargs: Keyword arguments to include in the key
        
    Returns:
        Cache key string
    """
    # Start with the prefix
    key = prefix
    
    # Add args
    if args:
        args_str = str(args)
        args_hash = hashlib.md5(args_str.encode()).hexdigest()
        key = f"{key}:{args_hash}"
    
    # Add kwargs
    if kwargs:
        kwargs_str = str(sorted(kwargs.items()))
        kwargs_hash = hashlib.md5(kwargs_str.encode()).hexdigest()
        key = f"{key}:{kwargs_hash}"
    
    return key

def set_cached_data(key: str, data: Any, timeout: Optional[int] = None) -> bool:
    """
    Set data in the cache.
    
    Args:
        key: Cache key
        data: Data to cache
        timeout: Cache timeout in seconds
        
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
        
        # Set in Redis
        if timeout is None:
            redis_client.set(key, data_str)
        else:
            redis_client.setex(key, timeout, data_str)
        
        logger.debug(f"Cached data with key {key}")
        return True
    except Exception as e:
        logger.error(f"Error caching data with key {key}: {str(e)}")
        return False

def get_cached_data(key: str) -> Optional[Any]:
    """
    Get data from the cache.
    
    Args:
        key: Cache key
        
    Returns:
        Cached data or None if not found
    """
    if not CACHE_ENABLED or not redis_client:
        return None
    
    try:
        # Get from Redis
        data_str = redis_client.get(key)
        
        # Return None if not found
        if data_str is None:
            return None
        
        # Convert to string
        if isinstance(data_str, bytes):
            data_str = data_str.decode('utf-8')
        
        # Try to parse as JSON
        try:
            return json.loads(data_str)
        except json.JSONDecodeError:
            # Return as string if not valid JSON
            return data_str
    except Exception as e:
        logger.error(f"Error getting cached data with key {key}: {str(e)}")
        return None

def delete_cached_data(key: str) -> bool:
    """
    Delete data from the cache.
    
    Args:
        key: Cache key
        
    Returns:
        True if successful, False otherwise
    """
    if not CACHE_ENABLED or not redis_client:
        return False
    
    try:
        # Delete from Redis
        redis_client.delete(key)
        logger.debug(f"Deleted cached data with key {key}")
        return True
    except Exception as e:
        logger.error(f"Error deleting cached data with key {key}: {str(e)}")
        return False

def invalidate_cache_pattern(pattern: str) -> bool:
    """
    Invalidate all cache keys matching a pattern.
    
    Args:
        pattern: Cache key pattern
        
    Returns:
        True if successful, False otherwise
    """
    if not CACHE_ENABLED or not redis_client:
        return False
    
    try:
        # Get keys matching pattern
        keys = redis_client.keys(pattern)
        
        # Delete keys
        if keys:
            redis_client.delete(*keys)
            logger.debug(f"Invalidated {len(keys)} cache entries matching pattern {pattern}")
        
        return True
    except Exception as e:
        logger.error(f"Error invalidating cache pattern {pattern}: {str(e)}")
        return False

# Permanent caching functions
def cache_permanently(data: Any, key: str) -> bool:
    """
    Cache data permanently (without expiration).
    
    Args:
        data: Data to cache
        key: Cache key
        
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
        
        # Set in Redis without expiration
        redis_client.set(key, data_str)
        logger.debug(f"Permanently cached data with key {key}")
        
        return True
    except Exception as e:
        logger.error(f"Error caching data permanently with key {key}: {str(e)}")
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
]

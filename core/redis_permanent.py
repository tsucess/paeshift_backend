"""
Compatibility module for core.redis_permanent.

This module provides backward compatibility with the old Redis permanent caching system.
"""

import logging
import json
from typing import Any, Dict, Optional, Union

# Set up logging
logger = logging.getLogger(__name__)

# Import Redis client
from core.redis.client import redis_client
from core.redis.settings import CACHE_ENABLED

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
            data_str = json.dumps(data)
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
        logger.error(f"Error getting permanently cached data with key {key}: {str(e)}")
        return None

def delete_permanent_cache(key: str) -> bool:
    """
    Delete permanently cached data.
    
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
        logger.debug(f"Deleted permanently cached data with key {key}")
        
        return True
    except Exception as e:
        logger.error(f"Error deleting permanently cached data with key {key}: {str(e)}")
        return False

# Re-export all functions
__all__ = [
    "cache_permanently",
    "get_permanent_cache",
    "delete_permanent_cache",
]

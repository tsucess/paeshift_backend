"""
Redis-based geocoding cache utilities.

This module provides utilities for caching geocoding results using Redis,
which is useful for reducing API calls to geocoding services.
"""

import json
import logging
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Dict, List, Optional, Tuple, Union

from core.cache import (
    get_cached_data,
    get_with_stampede_protection,
    set_cached_data,
)
from core.redis_metrics import time_function

logger = logging.getLogger(__name__)

# Constants
GEOCODE_EXPIRATION = 60 * 60 * 24 * 30  # 30 days
GEOCODE_PREFIX = "geocode:"


class GeocodingCache:
    """
    Redis-based geocoding cache.
    
    This class provides methods for caching geocoding results using Redis.
    """
    
    def __init__(self, expiration: int = GEOCODE_EXPIRATION):
        """
        Initialize a geocoding cache.
        
        Args:
            expiration: Expiration time in seconds
        """
        self.expiration = expiration
        
    def get(self, address: str, geocoder_func: Optional[callable] = None) -> Optional[Dict[str, Any]]:
        """
        Get geocoding result for an address.
        
        Args:
            address: Address to geocode
            geocoder_func: Function to call if result not in cache
            
        Returns:
            Geocoding result or None if not found and no geocoder function provided
        """
        try:
            # Normalize address
            normalized_address = self._normalize_address(address)
            
            # Generate cache key
            cache_key = f"{GEOCODE_PREFIX}{normalized_address}"
            
            # If geocoder function provided, use stampede protection
            if geocoder_func:
                return get_with_stampede_protection(
                    cache_key,
                    lambda: geocoder_func(address),
                    self.expiration
                )
                
            # Otherwise, just get from cache
            return get_cached_data(cache_key)
        except Exception as e:
            logger.error(f"Error getting geocoding result for {address}: {str(e)}")
            return None
            
    def set(self, address: str, result: Dict[str, Any]) -> bool:
        """
        Set geocoding result for an address.
        
        Args:
            address: Address to geocode
            result: Geocoding result
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Normalize address
            normalized_address = self._normalize_address(address)
            
            # Generate cache key
            cache_key = f"{GEOCODE_PREFIX}{normalized_address}"
            
            # Set in cache
            return set_cached_data(cache_key, result, self.expiration)
        except Exception as e:
            logger.error(f"Error setting geocoding result for {address}: {str(e)}")
            return False
            
    def _normalize_address(self, address: str) -> str:
        """
        Normalize an address for consistent caching.
        
        Args:
            address: Address to normalize
            
        Returns:
            Normalized address
        """
        # Convert to lowercase
        address = address.lower()
        
        # Remove extra whitespace
        address = " ".join(address.split())
        
        # Remove punctuation
        for char in [",", ".", "#", "-", "/"]:
            address = address.replace(char, " ")
            
        # Remove common words
        for word in ["apt", "suite", "unit", "building", "floor"]:
            address = address.replace(f" {word} ", " ")
            
        # Remove extra whitespace again
        address = " ".join(address.split())
        
        return address


# Singleton instance
_geocoding_cache = None


def get_geocoding_cache() -> GeocodingCache:
    """
    Get the singleton geocoding cache instance.
    
    Returns:
        GeocodingCache instance
    """
    global _geocoding_cache
    if _geocoding_cache is None:
        _geocoding_cache = GeocodingCache()
    return _geocoding_cache


@time_function("geocoding", "geocode_address")
def geocode_address(address: str, geocoder_func: callable) -> Optional[Dict[str, Any]]:
    """
    Geocode an address with caching.
    
    Args:
        address: Address to geocode
        geocoder_func: Function to call if result not in cache
        
    Returns:
        Geocoding result or None if not found
    """
    cache = get_geocoding_cache()
    return cache.get(address, geocoder_func)


def cache_geocoding_result(address: str, result: Dict[str, Any]) -> bool:
    """
    Cache a geocoding result.
    
    Args:
        address: Address to geocode
        result: Geocoding result
        
    Returns:
        True if successful, False otherwise
    """
    cache = get_geocoding_cache()
    return cache.set(address, result)


def cached_geocoder(func):
    """
    Decorator for geocoding functions to add caching.
    
    Args:
        func: Geocoding function to decorate
        
    Returns:
        Decorated function
    """
    @wraps(func)
    def wrapper(address, *args, **kwargs):
        return geocode_address(address, lambda addr: func(addr, *args, **kwargs))
    return wrapper

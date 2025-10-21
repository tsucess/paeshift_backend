"""
Redis permanent caching utilities.

This module provides utilities for permanent caching (no timeout) in Redis.
"""

import logging
import functools
import hashlib
import json
from typing import Any, Callable, Dict, List, Optional, Union

from django.http import HttpRequest, JsonResponse

from core.cache import (
    get_cached_data,
    set_cached_data,
    delete_cached_data,
    CACHE_ENABLED,
    redis_client,
    CACHE_PREFIXES,
)

logger = logging.getLogger(__name__)

# Constants
PERMANENT_CACHE_PREFIX = "permanent:"


def generate_permanent_key(key: str) -> str:
    """
    Generate a permanent cache key.
    
    Args:
        key: Original cache key
        
    Returns:
        Permanent cache key
    """
    return f"{PERMANENT_CACHE_PREFIX}{key}"


def cache_permanently(data: Any, key: str) -> bool:
    """
    Cache data permanently (no timeout).
    
    Args:
        data: Data to cache
        key: Cache key
        
    Returns:
        True if successful, False otherwise
    """
    if not CACHE_ENABLED or not redis_client:
        return False
        
    try:
        # Generate permanent key
        permanent_key = generate_permanent_key(key)
        
        # Serialize the data to JSON
        serialized_data = json.dumps(data)
        
        # Store in Redis without expiration
        redis_client.set(permanent_key, serialized_data)
        
        logger.info(f"Data cached permanently with key: {permanent_key}")
        
        return True
    except Exception as e:
        logger.error(f"Error caching data permanently for key {key}: {str(e)}")
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
        # Generate permanent key
        permanent_key = generate_permanent_key(key)
        
        # Get data from Redis
        cached_data = redis_client.get(permanent_key)
        
        if cached_data:
            # Parse the JSON data
            result = json.loads(cached_data)
            
            logger.debug(f"Retrieved permanently cached data for key: {permanent_key}")
            
            return result
            
        return None
    except Exception as e:
        logger.error(f"Error retrieving permanently cached data for key {key}: {str(e)}")
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
        # Generate permanent key
        permanent_key = generate_permanent_key(key)
        
        # Delete from Redis
        result = redis_client.delete(permanent_key)
        
        if result:
            logger.info(f"Permanently cached data deleted for key: {permanent_key}")
            
        return bool(result)
    except Exception as e:
        logger.error(f"Error deleting permanently cached data for key {key}: {str(e)}")
        return False


def cache_api_response_permanently(
    key_prefix: Optional[str] = None,
    namespace: Optional[str] = None,
    vary_on_headers: Optional[List[str]] = None,
    vary_on_cookies: Optional[List[str]] = None,
    vary_on_query_params: Optional[List[str]] = None,
) -> Callable:
    """
    Decorator to permanently cache API responses in Redis.
    
    Args:
        key_prefix: Optional prefix for the cache key
        namespace: Optional namespace for grouping related keys
        vary_on_headers: List of HTTP headers to include in the cache key
        vary_on_cookies: List of cookies to include in the cache key
        vary_on_query_params: List of query parameters to include in the cache key
        
    Returns:
        Decorated function
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            if not CACHE_ENABLED or not redis_client:
                return view_func(request, *args, **kwargs)
                
            # Only cache GET requests
            if request.method != "GET":
                return view_func(request, *args, **kwargs)
                
            # Generate a cache key based on the view function and request
            view_name = view_func.__name__
            module_name = view_func.__module__
            
            # Use provided prefix or get from CACHE_PREFIXES
            prefix = key_prefix or CACHE_PREFIXES.get("api")
            
            # Build key components
            key_parts = [module_name, view_name]
            
            # Add args to key
            if args:
                args_str = str(args)
                key_parts.append(hashlib.md5(args_str.encode()).hexdigest())
                
            # Add kwargs to key
            if kwargs:
                kwargs_str = str(sorted(kwargs.items()))
                key_parts.append(hashlib.md5(kwargs_str.encode()).hexdigest())
                
            # Add headers to key if requested
            if vary_on_headers:
                headers = {
                    header: request.headers.get(header)
                    for header in vary_on_headers
                    if header in request.headers
                }
                if headers:
                    headers_str = str(sorted(headers.items()))
                    key_parts.append(hashlib.md5(headers_str.encode()).hexdigest())
                    
            # Add cookies to key if requested
            if vary_on_cookies:
                cookies = {
                    cookie: request.COOKIES.get(cookie)
                    for cookie in vary_on_cookies
                    if cookie in request.COOKIES
                }
                if cookies:
                    cookies_str = str(sorted(cookies.items()))
                    key_parts.append(hashlib.md5(cookies_str.encode()).hexdigest())
                    
            # Add query params to key if requested
            if vary_on_query_params:
                query_params = {
                    param: request.GET.get(param)
                    for param in vary_on_query_params
                    if param in request.GET
                }
                if query_params:
                    query_params_str = str(sorted(query_params.items()))
                    key_parts.append(hashlib.md5(query_params_str.encode()).hexdigest())
                    
            # Add namespace if provided
            if namespace:
                key_parts.insert(0, namespace)
                
            # Add prefix if provided
            if prefix:
                key_parts.insert(0, prefix)
                
            # Generate the final cache key
            cache_key = ":".join(key_parts)
            
            # Try to get from permanent cache
            cached_data = get_permanent_cache(cache_key)
            if cached_data:
                logger.debug(f"Permanent cache hit for API view {view_name}")
                return JsonResponse(cached_data)
                
            # Cache miss, call the view function
            logger.debug(f"Permanent cache miss for API view {view_name}")
            response = view_func(request, *args, **kwargs)
            
            # Only cache JsonResponse objects
            if isinstance(response, JsonResponse):
                # Extract the response data
                response_data = json.loads(response.content.decode("utf-8"))
                
                # Cache the response data permanently
                cache_permanently(response_data, cache_key)
                
            return response
            
        return wrapper
        
    return decorator


def cache_model_permanently(model_type: str, instance_id: Any, data: Dict[str, Any]) -> bool:
    """
    Cache a model instance permanently.
    
    Args:
        model_type: The type of model (e.g., "user", "job")
        instance_id: The ID of the instance
        data: The data to cache
        
    Returns:
        True if successful, False otherwise
    """
    # Generate the cache key
    cache_key = f"{model_type}:{instance_id}"
    
    # Cache the data permanently
    return cache_permanently(data, cache_key)


def get_permanent_model(model_type: str, instance_id: Any) -> Optional[Dict[str, Any]]:
    """
    Get a permanently cached model instance.
    
    Args:
        model_type: The type of model (e.g., "user", "job")
        instance_id: The ID of the instance
        
    Returns:
        The cached instance data or None if not found
    """
    # Generate the cache key
    cache_key = f"{model_type}:{instance_id}"
    
    # Get the data from permanent cache
    return get_permanent_cache(cache_key)

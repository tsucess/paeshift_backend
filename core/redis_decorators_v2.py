"""
Enhanced Redis cache decorators.

This module provides enhanced decorators for caching function results and API responses,
using standardized cache keys and TTLs.
"""

import functools
import json
import logging
import time
import traceback
from typing import Any, Callable, Dict, List, Optional, Union

from django.http import HttpRequest, JsonResponse

from core.cache import get_cached_data, set_cached_data
from core.redis_keys import (
    CacheNamespace,
    CacheTTL,
    api_cache_key,
    function_cache_key,
)
from core.redis_settings import CACHE_ENABLED

logger = logging.getLogger(__name__)


def cache_function(
    namespace: Optional[Union[str, CacheNamespace]] = None,
    ttl: Optional[int] = None,
    cache_none: bool = False,
    version: Optional[str] = None,
) -> Callable:
    """
    Enhanced decorator to cache function results.
    
    Args:
        namespace: Cache namespace
        ttl: Cache TTL in seconds (overrides namespace default)
        cache_none: Whether to cache None results
        version: Cache version
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not CACHE_ENABLED:
                return func(*args, **kwargs)
            
            start_time = time.time()
            
            # Generate cache key
            cache_key = function_cache_key(
                func, *args, **kwargs, namespace=namespace, version=version
            )
            
            # Determine TTL
            cache_ttl = ttl
            if cache_ttl is None:
                if namespace:
                    cache_ttl = CacheTTL.get_ttl(namespace)
                else:
                    cache_ttl = CacheTTL.DEFAULT
            
            # Try to get from cache
            cached_result = get_cached_data(cache_key)
            if cached_result is not None:
                duration_ms = round((time.time() - start_time) * 1000, 2)
                logger.debug(
                    f"Cache hit for function {func.__name__} "
                    f"[key={cache_key}, duration={duration_ms}ms]"
                )
                return cached_result
            
            # Cache miss, call the function
            logger.debug(f"Cache miss for function {func.__name__} [key={cache_key}]")
            result = func(*args, **kwargs)
            
            # Don't cache None results unless explicitly requested
            if result is not None or cache_none:
                try:
                    set_cached_data(cache_key, result, cache_ttl)
                    duration_ms = round((time.time() - start_time) * 1000, 2)
                    logger.debug(
                        f"Cached result for function {func.__name__} "
                        f"[key={cache_key}, ttl={cache_ttl}s, duration={duration_ms}ms]"
                    )
                except Exception as e:
                    logger.error(
                        f"Error caching result for function {func.__name__}: {str(e)}\n"
                        f"{traceback.format_exc()}"
                    )
            
            return result
        
        # Add metadata to the wrapper function
        wrapper._cache_enabled = True
        wrapper._cache_namespace = namespace
        wrapper._cache_ttl = ttl
        
        # Add method to invalidate cache for specific args
        def invalidate_cache(*args, **kwargs):
            if not CACHE_ENABLED:
                return False
            
            cache_key = function_cache_key(
                func, *args, **kwargs, namespace=namespace, version=version
            )
            
            from core.cache import delete_cached_data
            return delete_cached_data(cache_key)
        
        wrapper.invalidate_cache = invalidate_cache
        
        return wrapper
    
    return decorator


def cache_api(
    ttl: Optional[int] = None,
    namespace: Optional[Union[str, CacheNamespace]] = None,
    vary_on_headers: Optional[List[str]] = None,
    vary_on_cookies: Optional[List[str]] = None,
    vary_on_query_params: Optional[List[str]] = None,
    version: Optional[str] = None,
) -> Callable:
    """
    Enhanced decorator to cache API responses.
    
    Args:
        ttl: Cache TTL in seconds (overrides namespace default)
        namespace: Cache namespace
        vary_on_headers: Headers to include in the cache key
        vary_on_cookies: Cookies to include in the cache key
        vary_on_query_params: Query params to include in the cache key
        version: Cache version
        
    Returns:
        Decorated function
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            if not CACHE_ENABLED:
                return view_func(request, *args, **kwargs)
            
            # Only cache GET requests
            if request.method != "GET":
                return view_func(request, *args, **kwargs)
            
            start_time = time.time()
            
            # Generate cache key
            cache_key = api_cache_key(
                view_func,
                request,
                *args,
                vary_on_headers=vary_on_headers,
                vary_on_cookies=vary_on_cookies,
                vary_on_query_params=vary_on_query_params,
                version=version,
            )
            
            # Determine TTL
            cache_ttl = ttl
            if cache_ttl is None:
                if namespace:
                    cache_ttl = CacheTTL.get_ttl(namespace)
                else:
                    cache_ttl = CacheTTL.get_ttl(CacheNamespace.API)
            
            # Try to get from cache
            cached_response = get_cached_data(cache_key)
            if cached_response is not None:
                duration_ms = round((time.time() - start_time) * 1000, 2)
                logger.debug(
                    f"Cache hit for API view {view_func.__name__} "
                    f"[key={cache_key}, duration={duration_ms}ms]"
                )
                return JsonResponse(cached_response)
            
            # Cache miss, call the view function
            logger.debug(f"Cache miss for API view {view_func.__name__} [key={cache_key}]")
            response = view_func(request, *args, **kwargs)
            
            # Only cache JsonResponse objects
            if isinstance(response, JsonResponse):
                try:
                    # Extract the response data
                    response_data = json.loads(response.content.decode("utf-8"))
                    
                    # Cache the response data
                    set_cached_data(cache_key, response_data, cache_ttl)
                    
                    duration_ms = round((time.time() - start_time) * 1000, 2)
                    logger.debug(
                        f"Cached response for API view {view_func.__name__} "
                        f"[key={cache_key}, ttl={cache_ttl}s, duration={duration_ms}ms]"
                    )
                except Exception as e:
                    logger.error(
                        f"Error caching response for API view {view_func.__name__}: {str(e)}\n"
                        f"{traceback.format_exc()}"
                    )
            
            return response
        
        # Add metadata to the wrapper function
        wrapper._cache_enabled = True
        wrapper._cache_namespace = namespace or CacheNamespace.API
        wrapper._cache_ttl = ttl
        
        return wrapper
    
    return decorator


def no_cache(view_func: Callable) -> Callable:
    """
    Decorator to explicitly disable caching for a view or function.
    
    Args:
        view_func: View or function to decorate
        
    Returns:
        Decorated function
    """
    @functools.wraps(view_func)
    def wrapper(*args, **kwargs):
        return view_func(*args, **kwargs)
    
    # Add metadata to the wrapper function
    wrapper._cache_enabled = False
    
    return wrapper

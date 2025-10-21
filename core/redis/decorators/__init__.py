"""
Redis decorators module.

This module provides decorators for caching function results and API responses.
"""

import functools
import hashlib
import inspect
import json
import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union

from django.db import models
from django.http import HttpRequest, JsonResponse
from django.utils import timezone

from core.redis.client import redis_client, with_redis_retry
from core.redis.settings import (
    CACHE_ENABLED,
    CACHE_PREFIXES,
    CACHE_TIMEOUTS,
    CACHE_VERSION,
)
from core.redis.utils import (
    CustomJSONEncoder,
    generate_cache_key,
    get_cached_data,
    set_cached_data,
    delete_cached_data,
)

# Set up logging
logger = logging.getLogger(__name__)

# Type variable for function return type
T = TypeVar("T")


def use_cached_model(model_param: str, model_class: Type[models.Model], id_param: str = "pk"):
    """
    Decorator to use cached model instances in views.

    This decorator replaces a model parameter in a view with a cached instance.

    Args:
        model_param: Name of the parameter to replace
        model_class: Model class to use
        id_param: Name of the ID parameter

    Returns:
        Decorated function
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(*args, **kwargs):
            if not CACHE_ENABLED or not redis_client:
                return view_func(*args, **kwargs)

            # Check if the model parameter is in kwargs
            if model_param in kwargs:
                # Already have the model instance
                return view_func(*args, **kwargs)

            # Check if the ID parameter is in kwargs
            if id_param not in kwargs:
                # No ID parameter, can't get the model
                return view_func(*args, **kwargs)

            # Get the ID
            instance_id = kwargs[id_param]

            # Try to get the model from cache
            from core.redis.models import get_cached_model
            instance = get_cached_model(model_class, instance_id)

            if instance:
                # Replace the ID parameter with the model instance
                kwargs[model_param] = instance
                del kwargs[id_param]
            else:
                # Fallback to database
                try:
                    instance = model_class.objects.get(pk=instance_id)
                    kwargs[model_param] = instance
                    del kwargs[id_param]

                    # Cache the instance for next time
                    from core.redis.models import cache_model
                    cache_model(instance)
                except model_class.DoesNotExist:
                    # Let the view handle the 404
                    pass

            return view_func(*args, **kwargs)

        return wrapper
    return decorator


def cache_api_response(
    timeout: Optional[int] = None,
    key_prefix: Optional[str] = None,
    namespace: Optional[str] = None,
    vary_on_headers: Optional[List[str]] = None,
    vary_on_cookies: Optional[List[str]] = None,
    vary_on_query_params: Optional[List[str]] = None,
    key_params: Optional[List[str]] = None,
) -> Callable:
    """
    Decorator to cache API responses in Redis.

    Args:
        timeout: Cache timeout in seconds
        key_prefix: Optional prefix for the cache key
        namespace: Optional namespace for grouping related keys
        vary_on_headers: List of HTTP headers to include in the cache key
        vary_on_cookies: List of cookies to include in the cache key
        vary_on_query_params: List of query parameters to include in the cache key
        key_params: List of URL parameters to include in the cache key

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
                # Only include specified parameters if key_params is provided
                if key_params:
                    kwargs_filtered = {k: v for k, v in kwargs.items() if k in key_params}
                else:
                    kwargs_filtered = kwargs

                if kwargs_filtered:
                    kwargs_str = str(sorted(kwargs_filtered.items()))
                    key_parts.append(hashlib.md5(kwargs_str.encode()).hexdigest())

            # Add headers to key
            if vary_on_headers:
                headers = {}
                for header in vary_on_headers:
                    header_value = request.headers.get(header)
                    if header_value:
                        headers[header] = header_value
                if headers:
                    headers_str = str(sorted(headers.items()))
                    key_parts.append(hashlib.md5(headers_str.encode()).hexdigest())

            # Add cookies to key
            if vary_on_cookies:
                cookies = {}
                for cookie in vary_on_cookies:
                    cookie_value = request.COOKIES.get(cookie)
                    if cookie_value:
                        cookies[cookie] = cookie_value
                if cookies:
                    cookies_str = str(sorted(cookies.items()))
                    key_parts.append(hashlib.md5(cookies_str.encode()).hexdigest())

            # Add query parameters to key
            if vary_on_query_params:
                query_params = {}
                for param in vary_on_query_params:
                    param_value = request.GET.get(param)
                    if param_value:
                        query_params[param] = param_value
                if query_params:
                    query_params_str = str(sorted(query_params.items()))
                    key_parts.append(hashlib.md5(query_params_str.encode()).hexdigest())

            # Generate the cache key
            cache_key = f"{prefix}:{':'.join(key_parts)}"

            # Add version to key
            if namespace:
                cache_key = f"{namespace}:{cache_key}"
            cache_key = f"{cache_key}:v{CACHE_VERSION}"

            # Try to get the response from cache
            cached_response = get_cached_data(cache_key)
            if cached_response:
                # Return the cached response
                return JsonResponse(cached_response)

            # Cache miss, call the view function
            start_time = time.time()
            response = view_func(request, *args, **kwargs)

            # Only cache JsonResponse objects
            if isinstance(response, JsonResponse):
                # Get the response data
                response_data = json.loads(response.content.decode("utf-8"))

                # Use provided timeout or get from CACHE_TIMEOUTS
                cache_timeout = timeout or CACHE_TIMEOUTS.get("api")

                # Cache the response
                set_cached_data(cache_key, response_data, cache_timeout)

                # Log cache miss
                duration_ms = (time.time() - start_time) * 1000
                logger.debug(
                    f"Cache miss for API response: {cache_key} "
                    f"(cached in {duration_ms:.2f}ms)"
                )

            return response

        return wrapper

    return decorator


def cache_function(
    namespace: Optional[str] = None,
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
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            if not CACHE_ENABLED or not redis_client:
                return func(*args, **kwargs)

            # Generate cache key
            cache_key = _generate_function_cache_key(
                func, args, kwargs, namespace=namespace, version=version
            )

            # Determine TTL
            cache_ttl = ttl
            if cache_ttl is None:
                # Get default TTL based on namespace or use global default
                cache_ttl = CACHE_TIMEOUTS.get(namespace, CACHE_TIMEOUTS["default"])

            # Try to get from cache
            cached_result = get_cached_data(cache_key)
            if cached_result is not None:
                return cached_result

            # Cache miss, call the function
            result = func(*args, **kwargs)

            # Cache the result if it's not None or cache_none is True
            if result is not None or cache_none:
                set_cached_data(cache_key, result, cache_ttl)

            return result

        return wrapper

    return decorator


def _generate_function_cache_key(
    func: Callable,
    args: tuple,
    kwargs: dict,
    namespace: Optional[str] = None,
    version: Optional[str] = None,
) -> str:
    """
    Generate a cache key for a function call.

    Args:
        func: Function
        args: Positional arguments
        kwargs: Keyword arguments
        namespace: Cache namespace
        version: Cache version

    Returns:
        Cache key
    """
    # Start with namespace and function name
    key_parts = []

    # Add namespace
    if namespace:
        key_parts.append(namespace)
    else:
        key_parts.append(func.__module__)

    # Add function name
    key_parts.append(func.__name__)

    # Format key parts
    def _format_key_part(value):
        if isinstance(value, (str, int, float, bool, type(None))):
            return str(value)
        else:
            # Hash complex objects
            return hashlib.md5(str(value).encode()).hexdigest()

    # Add args
    for arg in args:
        key_parts.append(_format_key_part(arg))

    # Add kwargs
    for k, v in sorted(kwargs.items()):
        key_parts.append(f"{k}:{_format_key_part(v)}")

    # Create the key
    key = ":".join(key_parts)

    # Hash long keys
    if len(key) > 200:
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return f"{namespace or 'func'}:{func.__name__}:{key_hash}"

    # Add version
    if version:
        key = f"{key}:v{version}"
    elif CACHE_VERSION:
        key = f"{key}:v{CACHE_VERSION}"

    return key


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


def cache_method_result(
    timeout: Optional[int] = None,
    prefix: Optional[str] = None,
    version: int = 1,
    cache_type: str = "default",
):
    """
    Cache method results in Redis, using instance attributes for the key.

    This decorator is designed for model methods where the cache key
    should include the model's primary key.

    Args:
        timeout: Cache timeout in seconds (None uses default for cache_type)
        prefix: Key prefix for the cache (defaults to model_name:method_name)
        version: Version for cache invalidation
        cache_type: Type of cache (user, job, api, etc.) for timeout

    Returns:
        Decorated function
    """
    def decorator(method: Callable) -> Callable:
        @functools.wraps(method)
        def wrapper(self, *args, **kwargs):
            if not CACHE_ENABLED or not redis_client:
                return method(self, *args, **kwargs)

            # Get model name and primary key
            model_name = self.__class__.__name__.lower()
            pk = getattr(self, "pk", None)

            if pk is None:
                # Can't cache without a primary key
                return method(self, *args, **kwargs)

            # Generate cache key
            method_name = method.__name__
            key_prefix = prefix or f"{model_name}:{method_name}"
            cache_key = f"{key_prefix}:{pk}:v{version}"

            # Add args and kwargs to key if present
            if args or kwargs:
                # Hash the args and kwargs
                args_kwargs_str = f"{args}:{sorted(kwargs.items())}"
                args_kwargs_hash = hashlib.md5(args_kwargs_str.encode()).hexdigest()
                cache_key = f"{cache_key}:{args_kwargs_hash}"

            # Try to get from cache
            cached_result = get_cached_data(cache_key)
            if cached_result is not None:
                return cached_result

            # Cache miss, call the method
            result = method(self, *args, **kwargs)

            # Determine timeout
            cache_timeout = timeout
            if cache_timeout is None:
                cache_timeout = CACHE_TIMEOUTS.get(cache_type, CACHE_TIMEOUTS["default"])

            # Cache the result
            set_cached_data(cache_key, result, cache_timeout)

            return result

        return wrapper

    return decorator

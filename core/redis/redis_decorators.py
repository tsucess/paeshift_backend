"""
Redis-related decorators for Django views and functions.

This module provides decorators for Django views and functions to easily
integrate with Redis caching and other Redis-based features.

This is a consolidated module that combines functionality from redis_decorators.py
and redis_decorators_v2.py to eliminate redundancy.
"""

import functools
import hashlib
import inspect
import json
import logging
import time
import traceback
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union, cast

from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.http import HttpRequest, HttpResponse, JsonResponse

from core.cache import get_cached_data, set_cached_data, delete_cached_data
from core.redis_models import get_cached_model
from core.redis_rate_limit import rate_limit
from core.redis_settings import CACHE_ENABLED

logger = logging.getLogger(__name__)

# Type variable for function return type
T = TypeVar("T")


def use_cached_model(model_param: str, model_class: Type[models.Model], id_param: str = "pk"):
    """
    Decorator to use cached model instances in views.

    This decorator replaces a model parameter in a view with a cached instance.

    Args:
        model_param: Name of the parameter to replace with a cached model
        model_class: Model class to use
        id_param: Name of the parameter containing the model ID
    Returns:
        Decorated function
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get the model ID from kwargs
            model_id = kwargs.get(id_param)

            if model_id:
                # Get the cached model instance
                instance = get_cached_model(model_class, model_id)

                if instance:
                    # Replace the model ID with the instance
                    kwargs[model_param] = instance
                else:
                    # Model not found, return 404
                    from django.http import Http404
                    raise Http404(f"{model_class.__name__} with ID {model_id} not found")

            # Call the original function
            return func(*args, **kwargs)

        return wrapper
    return decorator


def cache_page_for_user(timeout: int = 60 * 5):
    """
    Decorator to cache a page for a specific user.

    This decorator caches the response of a view for a specific user.

    Args:
        timeout: Cache timeout in seconds

    Returns:
        Decorated function
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            from core.cache import get_cached_data, set_cached_data

            # Skip caching for non-GET requests
            if request.method != "GET":
                return func(request, *args, **kwargs)

            # Skip caching for non-authenticated users
            if not request.user.is_authenticated:
                return func(request, *args, **kwargs)

            # Generate cache key
            cache_key = f"page:{request.path}:user:{request.user.id}"

            # Try to get from cache
            cached_response = get_cached_data(cache_key)
            if cached_response:
                return cached_response

            # Call the original function
            response = func(request, *args, **kwargs)

            # Cache the response
            if hasattr(response, "render"):
                # For TemplateResponse, we need to render it first
                response.render()

            set_cached_data(cache_key, response, timeout)

            return response

        return wrapper
    return decorator


def track_user_activity(activity_type: str):
    """
    Decorator to track user activity.

    This decorator tracks user activity when a view is accessed.

    Args:
        activity_type: Type of activity to track

    Returns:
        Decorated function
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            # Skip for non-authenticated users
            if not request.user.is_authenticated:
                return func(request, *args, **kwargs)

            # Track activity
            from core.redis_accounts import track_user_activity

            # Get metadata from request
            metadata = {
                "path": request.path,
                "method": request.method,
                "ip": request.META.get("REMOTE_ADDR"),
                "user_agent": request.META.get("HTTP_USER_AGENT"),
            }

            # Add any URL parameters
            if kwargs:
                metadata["url_params"] = kwargs

            # Track activity
            track_user_activity(str(request.user.id), activity_type, metadata)

            # Call the original function
            return func(request, *args, **kwargs)

        return wrapper
    return decorator


def with_redis_lock(lock_name: str, timeout: int = 30, wait_timeout: int = 0):
    """
    Decorator to use a Redis lock.

    This decorator acquires a Redis lock before executing a function.

    Args:
        lock_name: Name of the lock
        timeout: Lock timeout in seconds
        wait_timeout: Time to wait for the lock in seconds
    Returns:
        Decorated function
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            from core.redis_lock import redis_lock
            # Format lock name with args and kwargs
            formatted_lock_name = lock_name
            if "{" in lock_name:
                # Get arg and kwarg names from function signature
                import inspect
                sig = inspect.signature(func)
                param_names = list(sig.parameters.keys())
                # Create a dictionary of parameter values
                param_values = {}
                for i, arg in enumerate(args):
                    if i < len(param_names):
                        param_values[param_names[i]] = arg
                param_values.update(kwargs)

                # Format lock name
                formatted_lock_name = lock_name.format(**param_values)

            # Acquire lock
            with redis_lock(formatted_lock_name, timeout, wait_timeout) as acquired:
                if not acquired:
                    # Could not acquire lock
                    logger.warning(f"Could not acquire lock: {formatted_lock_name}")
                    # Return a response indicating the operation is in progress
                    if len(args) > 0 and isinstance(args[0], HttpRequest):
                        from django.http import JsonResponse
                        return JsonResponse({
                            "error": "Operation in progress",
                            "message": "Another request is currently processing this operation"
                        }, status=409)

                    # For non-HTTP requests, raise an exception
                    raise Exception(f"Could not acquire lock: {formatted_lock_name}")

                # Call the original function
                return func(*args, **kwargs)

        return wrapper
    return decorator


def time_view(name: str = None):
    """
    Decorator to time a view.

    This decorator measures the time it takes to execute a view and logs it.

    Args:
        name: Name of the timer (defaults to function name)

    Returns:
        Decorated function
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            # Get timer name
            timer_name = name or func.__name__

            # Start timer
            start_time = time.time()

            try:
                # Call the original function
                response = func(request, *args, **kwargs)

                # Calculate elapsed time
                elapsed_ms = (time.time() - start_time) * 1000

                # Log time
                logger.info(f"View {timer_name} took {elapsed_ms:.2f}ms")

                # Record in Redis metrics
                from core.redis_metrics import record_timer
                record_timer("views", timer_name, elapsed_ms)

                return response
            except Exception as e:
                # Calculate elapsed time
                elapsed_ms = (time.time() - start_time) * 1000

                # Log time and error
                logger.error(f"View {timer_name} failed after {elapsed_ms:.2f}ms: {str(e)}")

                # Record in Redis metrics
                from core.redis_metrics import record_timer, increment_counter
                record_timer("views", timer_name, elapsed_ms)
                increment_counter("views", f"{timer_name}.error")

                # Re-raise the exception
                raise

        return wrapper
    return decorator


def redis_cache(
    timeout: Optional[int] = None,
    prefix: str = "func",
    version: int = 1,
    key_args: Optional[List[int]] = None,
    key_kwargs: Optional[List[str]] = None,
    cache_type: str = "default",
    cache_null: bool = False,
    skip_args: Optional[List[int]] = None,
    skip_kwargs: Optional[List[str]] = None,
):
    """
    Cache function results in Redis.

    Args:
        timeout: Cache timeout in seconds (None uses default for cache_type)
        prefix: Key prefix for the cache
        version: Version for cache invalidation
        key_args: List of positional argument indices to include in cache key
        key_kwargs: List of keyword argument names to include in cache key
        cache_type: Type of cache (user, job, api, etc.) for timeout
        cache_null: Whether to cache None/null results
        skip_args: List of positional argument indices to skip when caching
        skip_kwargs: List of keyword argument names to skip when caching

    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            # Check if caching is enabled
            if not getattr(settings, "CACHE_ENABLED", True):
                return func(*args, **kwargs)

            # Determine cache timeout
            actual_timeout = timeout
            if actual_timeout is None:
                # Get timeouts from settings
                cache_timeouts = getattr(settings, "CACHE_TIMEOUTS", {})
                default_timeout = getattr(settings, "CACHE_DEFAULT_TIMEOUT", 60 * 60 * 24)  # 24 hours
                actual_timeout = cache_timeouts.get(cache_type, default_timeout)

            # Create a unique cache key
            key = _generate_cache_key(
                func, args, kwargs, prefix, version, key_args, key_kwargs
            )

            # Try to get from cache
            cached_result = cache.get(key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {key}")
                try:
                    return json.loads(cached_result)
                except (TypeError, ValueError) as e:
                    logger.warning(f"Error deserializing cached result for {key}: {e}")
                    # Fall through to function call

            # Cache miss, call the function
            logger.debug(f"Cache miss for {key}")
            start_time = time.time()
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time

            # Skip caching for None results if cache_null is False
            if result is None and not cache_null:
                logger.debug(f"Skipping cache for None result: {key}")
                return result

            # Skip caching based on skip_args and skip_kwargs
            if _should_skip_caching(args, kwargs, skip_args, skip_kwargs):
                logger.debug(f"Skipping cache based on skip arguments: {key}")
                return result

            # Cache the result
            try:
                serialized_result = json.dumps(result)
                cache.set(key, serialized_result, timeout=actual_timeout)
                logger.debug(
                    f"Cached result for {key} with timeout {actual_timeout}s "
                    f"(execution: {execution_time:.3f}s)"
                )
            except (TypeError, ValueError) as e:
                logger.warning(f"Could not cache result for {key}: {e}")

            return result

        # Add cache invalidation method to the function
        def invalidate_cache(*args: Any, **kwargs: Any) -> bool:
            """Invalidate the cache for this function with the given arguments."""
            key = _generate_cache_key(
                func, args, kwargs, prefix, version, key_args, key_kwargs
            )
            logger.debug(f"Invalidating cache for {key}")
            return cache.delete(key)

        wrapper.invalidate_cache = invalidate_cache  # type: ignore

        return cast(Callable[..., T], wrapper)

    return decorator


def _generate_cache_key(
    func: Callable,
    args: tuple,
    kwargs: Dict[str, Any],
    prefix: str,
    version: int,
    key_args: Optional[List[int]] = None,
    key_kwargs: Optional[List[str]] = None,
) -> str:
    """
    Generate a cache key for a function call.

    Args:
        func: Function being cached
        args: Positional arguments
        kwargs: Keyword arguments
        prefix: Key prefix
        version: Cache version
        key_args: List of positional argument indices to include in key
        key_kwargs: List of keyword argument names to include in key

    Returns:
        Cache key string
    """
    # Start with basic function info
    key_parts = [prefix, func.__module__, func.__name__, str(version)]

    # Add selected args to key
    if key_args is not None:
        # Only include specified positional arguments
        for i in key_args:
            if i < len(args):
                key_parts.append(_format_key_part(args[i]))
    else:
        # Include all positional arguments
        for arg in args:
            key_parts.append(_format_key_part(arg))

    # Add selected kwargs to key
    if key_kwargs is not None:
        # Only include specified keyword arguments
        for k in key_kwargs:
            if k in kwargs:
                key_parts.append(f"{k}:{_format_key_part(kwargs[k])}")
    else:
        # Include all keyword arguments, sorted for consistency
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}:{_format_key_part(v)}")

    # Create hash for potentially long keys
    key_string = ":".join(key_parts)
    if len(key_string) > 200:  # Avoid very long keys
        key_hash = hashlib.md5(key_string.encode()).hexdigest()
        return f"cache:{prefix}:{func.__name__}:{key_hash}"
    else:
        return f"cache:{key_string}"


def _format_key_part(value: Any) -> str:
    """
    Format a value for inclusion in a cache key.

    Args:
        value: Value to format

    Returns:
        Formatted string
    """
    if isinstance(value, models.Model):
        # For Django models, use app_label, model_name and pk
        return f"{value._meta.app_label}.{value._meta.model_name}:{value.pk}"
    elif hasattr(value, "__dict__"):
        # For objects, use class name and id if available
        obj_id = getattr(value, "id", id(value))
        return f"{value.__class__.__name__}:{obj_id}"
    elif isinstance(value, (list, tuple)):
        # For lists and tuples, format each item
        return f"[{','.join(_format_key_part(item) for item in value)}]"
    elif isinstance(value, dict):
        # For dictionaries, format each key-value pair
        return f"{{{','.join(f'{k}:{_format_key_part(v)}' for k, v in sorted(value.items()))}}}"
    else:
        # For primitive types, use string representation
        return str(value)


def _should_skip_caching(
    args: tuple,
    kwargs: Dict[str, Any],
    skip_args: Optional[List[int]] = None,
    skip_kwargs: Optional[List[str]] = None,
) -> bool:
    """
    Determine if caching should be skipped based on arguments.

    Args:
        args: Positional arguments
        kwargs: Keyword arguments
        skip_args: List of positional argument indices to check
        skip_kwargs: List of keyword argument names to check

    Returns:
        True if caching should be skipped, False otherwise
    """
    # Check positional arguments
    if skip_args:
        for i in skip_args:
            if i < len(args) and args[i] is True:
                return True

    # Check keyword arguments
    if skip_kwargs:
        for k in skip_kwargs:
            if k in kwargs and kwargs[k] is True:
                return True

    return False


def cache_api_response(timeout: int = 60 * 15, key_params: List[str] = None):
    """
    Decorator to cache API responses.

    This decorator caches the response of an API endpoint for a specific time period.
    It uses the request path and query parameters to generate a unique cache key.

    Args:
        timeout: Cache timeout in seconds (default: 15 minutes)
        key_params: List of URL parameters to include in the cache key
                   (if None, all parameters are included)

    Returns:
        Decorated function
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            # Import Redis caching and telemetry tools
            from core.cache import get_cached_data, set_cached_data
            from core.redis_telemetry import log_operation

            # Skip caching for non-GET requests
            if request.method != "GET":
                return func(request, *args, **kwargs)

            # Generate cache key
            cache_key_parts = [f"api:{request.path}"]

            # Add selected URL parameters to the key
            if key_params:
                for param in key_params:
                    if param in kwargs:
                        cache_key_parts.append(f"{param}:{kwargs[param]}")
            else:
                # Include all URL parameters
                for k, v in sorted(kwargs.items()):
                    cache_key_parts.append(f"{k}:{v}")

            # Add query parameters to the key
            if request.GET:
                for k, v in sorted(request.GET.items()):
                    cache_key_parts.append(f"q:{k}:{v}")

            # Add user ID if authenticated
            if request.user.is_authenticated:
                cache_key_parts.append(f"user:{request.user.id}")

            # Create the final cache key
            cache_key = ":".join(cache_key_parts)

            # Hash long keys
            if len(cache_key) > 200:
                key_hash = hashlib.md5(cache_key.encode()).hexdigest()
                cache_key = f"api:{request.path}:{key_hash}"

            # Start timing
            start_time = time.time()

            # Try to get from cache
            cached_data = get_cached_data(cache_key)
            if cached_data:
                logger.debug(f"Cache hit for API response: {cache_key}")

                # Log telemetry for cache hit
                log_operation(
                    operation="get",
                    key=cache_key,
                    success=True,
                    duration_ms=(time.time() - start_time) * 1000,
                    context=f"API endpoint: {request.path}",
                )

                return cached_data

            # Cache miss, call the original function
            logger.debug(f"Cache miss for API response: {cache_key}")

            # Log telemetry for cache miss
            log_operation(
                operation="get",
                key=cache_key,
                success=False,
                duration_ms=(time.time() - start_time) * 1000,
                context=f"API endpoint: {request.path}",
            )

            # Call the original function
            result = func(request, *args, **kwargs)

            # Cache the result
            set_cached_data(cache_key, result, timeout=timeout)

            # Log telemetry for cache set
            log_operation(
                operation="set",
                key=cache_key,
                success=True,
                duration_ms=(time.time() - start_time) * 1000,
                context=f"API endpoint: {request.path}",
            )

            return result

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
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not CACHE_ENABLED:
                return func(*args, **kwargs)

            start_time = time.time()

            # Generate cache key
            cache_key = _generate_function_cache_key(
                func, args, kwargs, namespace=namespace, version=version
            )

            # Determine TTL
            cache_ttl = ttl
            if cache_ttl is None:
                # Get default TTL based on namespace or use global default
                from core.redis_settings import CACHE_TIMEOUTS, CACHE_DEFAULT_TIMEOUT
                cache_ttl = CACHE_TIMEOUTS.get(namespace, CACHE_DEFAULT_TIMEOUT)

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

            cache_key = _generate_function_cache_key(
                func, args, kwargs, namespace=namespace, version=version
            )

            return delete_cached_data(cache_key)

        wrapper.invalidate_cache = invalidate_cache

        return wrapper

    return decorator


def _generate_function_cache_key(
    func: Callable,
    args: tuple,
    kwargs: dict,
    namespace: Optional[str] = None,
    version: Optional[str] = None
) -> str:
    """
    Generate a standardized cache key for a function call.

    Args:
        func: Function being cached
        args: Positional arguments
        kwargs: Keyword arguments
        namespace: Cache namespace
        version: Cache version

    Returns:
        Cache key string
    """
    # Start with namespace and function info
    key_parts = []

    # Add namespace if provided
    if namespace:
        key_parts.append(namespace)
    else:
        key_parts.append("func")

    # Add function module and name
    key_parts.append(func.__module__)
    key_parts.append(func.__name__)

    # Add version if provided
    if version:
        key_parts.append(f"v{version}")

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
        Decorated method
    """
    def decorator(method: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(method)
        def wrapper(self, *args: Any, **kwargs: Any) -> T:
            # Check if caching is enabled
            if not getattr(settings, "CACHE_ENABLED", True):
                return method(self, *args, **kwargs)

            # Determine cache timeout
            actual_timeout = timeout
            if actual_timeout is None:
                # Get timeouts from settings
                cache_timeouts = getattr(settings, "CACHE_TIMEOUTS", {})
                default_timeout = getattr(settings, "CACHE_DEFAULT_TIMEOUT", 60 * 60 * 24)  # 24 hours
                actual_timeout = cache_timeouts.get(cache_type, default_timeout)

            # Determine prefix
            actual_prefix = prefix
            if actual_prefix is None:
                if isinstance(self, models.Model):
                    actual_prefix = f"{self._meta.model_name}:{method.__name__}"
                else:
                    actual_prefix = f"{self.__class__.__name__}:{method.__name__}"

            # Create a unique cache key
            if isinstance(self, models.Model) and self.pk:
                # For Django models, include app_label, model_name and pk
                instance_key = f"{self._meta.app_label}.{self._meta.model_name}:{self.pk}"
            else:
                # For other objects, use class name and id if available
                instance_key = f"{self.__class__.__name__}:{getattr(self, 'id', id(self))}"

            # Add method arguments to key
            arg_parts = []
            for arg in args:
                arg_parts.append(_format_key_part(arg))

            for k, v in sorted(kwargs.items()):
                arg_parts.append(f"{k}:{_format_key_part(v)}")

            arg_key = ":".join(arg_parts) if arg_parts else "noargs"

            # Combine all parts
            key = f"cache:{actual_prefix}:{instance_key}:{arg_key}:v{version}"

            # Hash long keys
            if len(key) > 200:
                key_hash = hashlib.md5(key.encode()).hexdigest()
                key = f"cache:{actual_prefix}:{instance_key}:{key_hash}"

            # Try to get from cache
            cached_result = cache.get(key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {key}")
                try:
                    return json.loads(cached_result)
                except (TypeError, ValueError) as e:
                    logger.warning(f"Error deserializing cached result for {key}: {e}")
                    # Fall through to method call

            # Cache miss, call the method
            logger.debug(f"Cache miss for {key}")
            start_time = time.time()
            result = method(self, *args, **kwargs)
            execution_time = time.time() - start_time

            # Cache the result
            try:
                serialized_result = json.dumps(result)
                cache.set(key, serialized_result, timeout=actual_timeout)
                logger.debug(
                    f"Cached result for {key} with timeout {actual_timeout}s "
                    f"(execution: {execution_time:.3f}s)"
                )
            except (TypeError, ValueError) as e:
                logger.warning(f"Could not cache result for {key}: {e}")

            return result

        return cast(Callable[..., T], wrapper)

    return decorator


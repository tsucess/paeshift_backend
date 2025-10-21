"""
Compatibility module for core.redis_decorators.

This module provides backward compatibility with the old Redis caching system.
It imports and re-exports the decorators from the new standardized Redis caching module.
"""

import logging
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Union

# Import decorators from the new module
try:
    from core.redis.decorators import (
        cache_api_response,
        cache_function,
        no_cache,
        cache_method_result,
        use_cached_model,
    )
except ImportError:
    # Fallback implementations if the new module doesn't exist
    def cache_api_response(timeout=300, key_prefix=""):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return decorator

    def cache_function(timeout=300, key_prefix=""):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return decorator

    def no_cache(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper

    def cache_method_result(timeout=300, key_prefix=""):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return decorator

    def use_cached_model(model_class, timeout=300):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return decorator

# Import time_view from the new module if it exists, otherwise create a compatible version
try:
    from core.redis.decorators import time_view
except ImportError:
    # Create a compatible time_view decorator
    def time_view(name: Optional[str] = None) -> Callable:
        """
        Decorator to measure and log the execution time of a view function.

        This is a compatibility version of the time_view decorator.

        Args:
            name: Optional name for the view (defaults to function name)

        Returns:
            Decorated function
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                import time
                start_time = time.time()
                result = func(*args, **kwargs)
                end_time = time.time()
                view_name = name or func.__name__
                execution_time = end_time - start_time
                logging.info(f"View {view_name} executed in {execution_time:.4f} seconds")
                return result
            return wrapper
        return decorator

# Add track_user_activity decorator
def track_user_activity(activity_type: str = None) -> Callable:
    """
    Decorator to track user activity in Redis.

    This is a compatibility version of the track_user_activity decorator.

    Args:
        activity_type: Type of activity to track

    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Log the activity
            request = next((arg for arg in args if hasattr(arg, 'user')), None)
            user = getattr(request, 'user', None) if request else None

            if user and user.is_authenticated and activity_type:
                user_id = getattr(user, 'id', None)
                if user_id:
                    logging.info(f"User {user_id} performed activity: {activity_type}")
                    # In a real implementation, this would store the activity in Redis

            # Call the original function
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Add redis_cache decorator for backward compatibility
def redis_cache(timeout=300, prefix="", cache_type="", key_kwargs=None, version=1):
    """
    Backward compatibility decorator for redis_cache.

    This is a wrapper around cache_function that maintains the old API.

    Args:
        timeout: Cache timeout in seconds
        prefix: Cache key prefix
        cache_type: Type of cache (unused, for backward compatibility)
        key_kwargs: List of kwarg names to use in the cache key
        version: Cache version number

    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key
            key_parts = [prefix]

            # Add version to key
            key_parts.append(f"v{version}")

            # Add cache type if provided
            if cache_type:
                key_parts.append(cache_type)

            # Add kwargs specified in key_kwargs
            if key_kwargs:
                for kwarg_name in key_kwargs:
                    if kwarg_name in kwargs:
                        key_parts.append(f"{kwarg_name}:{kwargs[kwarg_name]}")

            # Generate final key
            cache_key = ":".join(key_parts)

            # Try to get from cache
            from django.core.cache import cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Call the function
            result = func(*args, **kwargs)

            # Cache the result
            cache.set(cache_key, result, timeout)

            return result
        return wrapper
    return decorator

# Re-export all decorators
__all__ = [
    "cache_api_response",
    "cache_function",
    "no_cache",
    "cache_method_result",
    "use_cached_model",
    "time_view",
    "track_user_activity",
    "redis_cache",
]

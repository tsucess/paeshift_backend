"""
Redis timestamp validation module.

This module provides utilities for validating and invalidating cache entries
based on timestamps, ensuring that cached data is always up-to-date.
"""

import functools
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union

from django.db import models
from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from core.redis.client import redis_client, with_redis_retry
from core.redis.settings import CACHE_ENABLED, CACHE_TIMEOUTS
from core.redis.utils import (
    get_cached_data,
    set_cached_data,
    delete_cached_data,
)

# Set up logging
logger = logging.getLogger(__name__)


def get_model_timestamp(instance: models.Model) -> Optional[str]:
    """
    Get the timestamp for a model instance.

    This function returns a timestamp that can be used to validate cache entries.
    It uses the model's updated_at field if available, or falls back to other fields.

    Args:
        instance: Model instance

    Returns:
        Timestamp string or None if not available
    """
    # Try updated_at field
    if hasattr(instance, "updated_at"):
        timestamp = getattr(instance, "updated_at")
        if timestamp:
            return timestamp.isoformat()

    # Try modified_at field
    if hasattr(instance, "modified_at"):
        timestamp = getattr(instance, "modified_at")
        if timestamp:
            return timestamp.isoformat()

    # Try last_modified field
    if hasattr(instance, "last_modified"):
        timestamp = getattr(instance, "last_modified")
        if timestamp:
            return timestamp.isoformat()

    # Try version field
    if hasattr(instance, "version"):
        version = getattr(instance, "version")
        if version:
            return str(version)

    # Fallback to current time
    return timezone.now().isoformat()


def get_cache_timestamp(data: Dict[str, Any]) -> Optional[str]:
    """
    Get the timestamp from cached data.

    Args:
        data: Cached data

    Returns:
        Timestamp string or None if not available
    """
    # Try _timestamp field
    if "_timestamp" in data:
        return data["_timestamp"]

    # Try updated_at field
    if "updated_at" in data:
        return data["updated_at"]

    # Try modified_at field
    if "modified_at" in data:
        return data["modified_at"]

    # Try last_modified field
    if "last_modified" in data:
        return data["last_modified"]

    # Try version field
    if "version" in data:
        return str(data["version"])

    # Try _cached_at field
    if "_cached_at" in data:
        return data["_cached_at"]

    return None


def is_cache_valid(instance: models.Model, data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Check if cached data is valid for a model instance.

    Args:
        instance: Model instance
        data: Cached data

    Returns:
        Tuple of (is_valid, reason)
    """
    # Get timestamps
    model_timestamp = get_model_timestamp(instance)
    cache_timestamp = get_cache_timestamp(data)

    # If either timestamp is missing, consider the cache invalid
    if not model_timestamp:
        return False, "Model timestamp not available"
    if not cache_timestamp:
        return False, "Cache timestamp not available"

    # Parse timestamps
    try:
        model_dt = datetime.fromisoformat(model_timestamp)
        cache_dt = datetime.fromisoformat(cache_timestamp)
    except (ValueError, TypeError):
        # If timestamps can't be parsed as datetimes, compare as strings
        return model_timestamp == cache_timestamp, "Timestamp comparison as strings"

    # Compare timestamps
    if model_dt > cache_dt:
        return False, f"Model timestamp ({model_dt}) is newer than cache timestamp ({cache_dt})"
    return True, f"Cache is valid (model: {model_dt}, cache: {cache_dt})"


def ensure_timestamp_in_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure that data has a timestamp field.

    Args:
        data: Data to check

    Returns:
        Data with timestamp field
    """
    # Check if data already has a timestamp
    if get_cache_timestamp(data) is not None:
        return data

    # Add timestamp
    data["_timestamp"] = timezone.now().isoformat()
    return data


def get_with_timestamp_validation(
    key: str,
    getter: Callable[[str], Optional[Dict[str, Any]]],
    id: Any,
    timeout: Optional[int] = None,
) -> Tuple[Optional[Dict[str, Any]], bool]:
    """
    Get data with timestamp validation.

    Args:
        key: Cache key
        getter: Function to get the data if not in cache
        id: ID to pass to getter
        timeout: Cache timeout in seconds

    Returns:
        Tuple of (data, from_cache)
    """
    if not CACHE_ENABLED or not redis_client:
        # Cache disabled, get from source
        data = getter(id)
        return data, False

    # Try to get from cache
    cached_data = get_cached_data(key)
    if cached_data is not None:
        # Got from cache, return
        return cached_data, True

    # Cache miss, get from source
    data = getter(id)
    if data is not None:
        # Add timestamp if not present
        data = ensure_timestamp_in_data(data)
        # Cache the data
        set_cached_data(key, data, timeout)

    return data, False


def validate_with_timestamp(
    cache_key_prefix: str,
    timestamp_key_suffix: str = "timestamp",
    timeout: int = 3600,
    version: Optional[str] = None
) -> Callable:
    """
    Decorator to validate cached data using a timestamp.

    This decorator caches the result of a function and validates it against a timestamp.
    If the timestamp has changed, the cache is invalidated and the function is called again.

    Args:
        cache_key_prefix: Prefix for the cache key
        timestamp_key_suffix: Suffix for the timestamp key
        timeout: Cache timeout in seconds
        version: Cache version

    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not CACHE_ENABLED or not redis_client:
                return func(*args, **kwargs)

            # Generate cache key
            cache_key = f"{cache_key_prefix}:{args[0] if args else ''}:{kwargs}"
            if version:
                cache_key = f"{cache_key}:v{version}"

            # Generate timestamp key
            timestamp_key = f"{cache_key}:{timestamp_key_suffix}"

            # Try to get from cache
            cached_data = get_cached_data(cache_key)
            cached_timestamp = get_cached_data(timestamp_key)

            if cached_data is not None and cached_timestamp is not None:
                # Check if timestamp has changed
                current_timestamp = timezone.now().isoformat()
                if cached_timestamp == current_timestamp:
                    # Timestamp hasn't changed, return cached data
                    return cached_data

            # Cache miss or timestamp changed, call the function
            result = func(*args, **kwargs)

            # Cache the result
            set_cached_data(cache_key, result, timeout)

            # Cache the timestamp
            current_timestamp = timezone.now().isoformat()
            set_cached_data(timestamp_key, current_timestamp, timeout)

            return result

        return wrapper

    return decorator


def invalidate_on_timestamp_change(
    model_class: Type[models.Model],
    cache_key_prefix: str,
    timeout: int = 3600,
    version: Optional[str] = None
) -> Callable:
    """
    Decorator to invalidate cache when a model's timestamp changes.

    This decorator caches the result of a function and invalidates it
    when the timestamp of a model instance changes.

    Args:
        model_class: Model class to check for timestamp changes
        cache_key_prefix: Prefix for the cache key
        timeout: Cache timeout in seconds
        version: Cache version

    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not CACHE_ENABLED or not redis_client:
                return func(*args, **kwargs)

            # Get instance ID from args or kwargs
            instance_id = None
            if len(args) > 1:
                instance_id = args[1]
            elif "id" in kwargs:
                instance_id = kwargs["id"]
            elif "pk" in kwargs:
                instance_id = kwargs["pk"]
            elif "instance_id" in kwargs:
                instance_id = kwargs["instance_id"]

            if instance_id is None:
                # Can't get instance ID, call the function
                return func(*args, **kwargs)

            # Generate cache key
            cache_key = f"{cache_key_prefix}:{instance_id}"
            if version:
                cache_key = f"{cache_key}:v{version}"

            # Try to get from cache
            cached_data = get_cached_data(cache_key)
            if cached_data is not None:
                # Check if model has changed
                try:
                    instance = model_class.objects.get(pk=instance_id)
                    is_valid, reason = is_cache_valid(instance, cached_data)
                    if is_valid:
                        # Cache is valid, return cached data
                        return cached_data
                except model_class.DoesNotExist:
                    # Model doesn't exist, invalidate cache
                    delete_cached_data(cache_key)
                    return func(*args, **kwargs)

            # Cache miss or model changed, call the function
            result = func(*args, **kwargs)

            # Cache the result
            set_cached_data(cache_key, result, timeout)

            return result

        return wrapper

    return decorator

"""
Timestamp-based cache validation utilities.

This module provides utilities for validating and invalidating cache entries
based on timestamps, ensuring that cached data is always up-to-date.

This is a consolidated module that combines functionality from redis_timestamp_validation.py
and redis_timestamp_decorators.py to eliminate redundancy.
"""

import functools
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union

from django.db import models
from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from core.cache import get_cached_data, set_cached_data, delete_cached_data, redis_client
from core.redis_settings import CACHE_ENABLED

logger = logging.getLogger(__name__)

# Constants
TIMESTAMP_FIELDS = ["last_updated", "updated_at", "timestamp", "modified_at", "created_at"]
VERSION_FIELD = "version"
TIMESTAMP_TOLERANCE_SECONDS = 1  # Allow 1 second tolerance for timestamp comparison


def get_model_timestamp(instance: models.Model) -> Optional[datetime]:
    """
    Get the timestamp from a model instance.

    Args:
        instance: Model instance

    Returns:
        Timestamp or None if not found
    """
    for field_name in TIMESTAMP_FIELDS:
        if hasattr(instance, field_name):
            timestamp = getattr(instance, field_name)
            if isinstance(timestamp, datetime):
                return timestamp
    return None


def get_cache_timestamp(data: Dict[str, Any]) -> Optional[datetime]:
    """
    Get the timestamp from cached data.

    Args:
        data: Cached data

    Returns:
        Timestamp or None if not found
    """
    for field_name in TIMESTAMP_FIELDS:
        if field_name in data:
            try:
                if isinstance(data[field_name], str):
                    return datetime.fromisoformat(data[field_name])
                elif isinstance(data[field_name], (int, float)):
                    return datetime.fromtimestamp(data[field_name])
            except (ValueError, TypeError):
                continue
    return None


def get_model_version(instance: models.Model) -> Optional[int]:
    """
    Get the version from a model instance.

    Args:
        instance: Model instance

    Returns:
        Version or None if not found
    """
    if hasattr(instance, VERSION_FIELD):
        return getattr(instance, VERSION_FIELD)
    return None


def get_cache_version(data: Dict[str, Any]) -> Optional[int]:
    """
    Get the version from cached data.

    Args:
        data: Cached data

    Returns:
        Version or None if not found
    """
    if VERSION_FIELD in data:
        try:
            return int(data[VERSION_FIELD])
        except (ValueError, TypeError):
            return None
    return None


def is_cache_valid(instance: models.Model, cached_data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Check if cached data is valid compared to a model instance.

    Args:
        instance: Model instance
        cached_data: Cached data

    Returns:
        Tuple of (is_valid, reason)
    """
    # Check version if available
    instance_version = get_model_version(instance)
    cache_version = get_cache_version(cached_data)

    if instance_version is not None and cache_version is not None:
        if instance_version > cache_version:
            return False, f"Version mismatch: DB={instance_version}, Cache={cache_version}"

    # Check timestamp if available
    instance_timestamp = get_model_timestamp(instance)
    cache_timestamp = get_cache_timestamp(cached_data)

    if instance_timestamp is not None and cache_timestamp is not None:
        # Allow a small tolerance for timestamp comparison
        if abs((instance_timestamp - cache_timestamp).total_seconds()) > TIMESTAMP_TOLERANCE_SECONDS:
            if instance_timestamp > cache_timestamp:
                return False, f"Timestamp mismatch: DB={instance_timestamp.isoformat()}, Cache={cache_timestamp.isoformat()}"

    return True, "Cache is valid"


def ensure_timestamp_in_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure that data has a timestamp field.

    Args:
        data: Data dictionary

    Returns:
        Data dictionary with timestamp
    """
    # Check if data already has a timestamp
    has_timestamp = False
    for field_name in TIMESTAMP_FIELDS:
        if field_name in data:
            has_timestamp = True
            break

    # If no timestamp, add one
    if not has_timestamp:
        data["timestamp"] = timezone.now().isoformat()

    return data


def validate_cache_key(key: str, instance: models.Model) -> bool:
    """
    Validate a cache key against a model instance.

    Args:
        key: Cache key
        instance: Model instance

    Returns:
        True if cache is valid, False otherwise
    """
    if not CACHE_ENABLED or not redis_client:
        return False

    try:
        # Get cached data
        cached_data = get_cached_data(key)
        if not cached_data:
            return False

        # Check if cache is valid
        is_valid, _ = is_cache_valid(instance, cached_data)
        return is_valid
    except Exception as e:
        logger.error(f"Error validating cache key {key}: {str(e)}")
        return False


def invalidate_if_stale(key: str, instance: models.Model) -> bool:
    """
    Invalidate a cache key if it's stale compared to a model instance.

    Args:
        key: Cache key
        instance: Model instance

    Returns:
        True if cache was invalidated, False otherwise
    """
    if not CACHE_ENABLED or not redis_client:
        return False

    try:
        # Get cached data
        cached_data = get_cached_data(key)
        if not cached_data:
            return False

        # Check if cache is valid
        is_valid, reason = is_cache_valid(instance, cached_data)
        if not is_valid:
            # Invalidate cache
            delete_cached_data(key)
            logger.info(f"Invalidated stale cache for {key}: {reason}")
            return True

        return False
    except Exception as e:
        logger.error(f"Error checking cache staleness for {key}: {str(e)}")
        return False


def update_cache_with_timestamp(key: str, data: Dict[str, Any], timeout: Optional[int] = None) -> bool:
    """
    Update cache with data, ensuring it has a timestamp.

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
        # Ensure data has a timestamp
        data = ensure_timestamp_in_data(data)

        # Cache the data
        return set_cached_data(key, data, timeout)
    except Exception as e:
        logger.error(f"Error updating cache with timestamp for {key}: {str(e)}")
        return False


def get_with_timestamp_validation(
    key: str,
    instance_getter,
    instance_id: Any,
    timeout: Optional[int] = None
) -> Tuple[Dict[str, Any], bool]:
    """
    Get cached data with timestamp validation.

    Args:
        key: Cache key
        instance_getter: Function to get the model instance
        instance_id: ID to pass to the instance getter
        timeout: Cache timeout in seconds

    Returns:
        Tuple of (data, from_cache)
    """
    if not CACHE_ENABLED or not redis_client:
        # Cache disabled, get from source
        instance = instance_getter(instance_id)
        if not instance:
            return None, False

        # Convert instance to data
        if hasattr(instance, "to_dict") and callable(getattr(instance, "to_dict")):
            return instance.to_dict(), False

        # Basic conversion
        data = {"id": instance.pk}
        for field in instance._meta.fields:
            field_name = field.name
            value = getattr(instance, field_name)

            # Handle special field types
            if isinstance(value, models.Model):
                data[field_name] = value.pk
            elif hasattr(value, 'isoformat'):
                data[field_name] = value.isoformat()
            else:
                data[field_name] = value

        return data, False

    try:
        # Try to get from cache
        cached_data = get_cached_data(key)

        if cached_data:
            # Got from cache, validate
            instance = instance_getter(instance_id)
            if not instance:
                # Instance doesn't exist anymore, invalidate cache
                delete_cached_data(key)
                return None, False

            # Check if cache is valid
            is_valid, _ = is_cache_valid(instance, cached_data)
            if is_valid:
                # Cache is valid
                return cached_data, True

            # Cache is invalid, update it
            if hasattr(instance, "to_dict") and callable(getattr(instance, "to_dict")):
                data = instance.to_dict()
            else:
                # Basic conversion
                data = {"id": instance.pk}
                for field in instance._meta.fields:
                    field_name = field.name
                    value = getattr(instance, field_name)

                    # Handle special field types
                    if isinstance(value, models.Model):
                        data[field_name] = value.pk
                    elif hasattr(value, 'isoformat'):
                        data[field_name] = value.isoformat()
                    else:
                        data[field_name] = value

            # Update cache
            update_cache_with_timestamp(key, data, timeout)
            return data, False

        # Not in cache, get from source
        instance = instance_getter(instance_id)
        if not instance:
            return None, False

        # Convert instance to data
        if hasattr(instance, "to_dict") and callable(getattr(instance, "to_dict")):
            data = instance.to_dict()
        else:
            # Basic conversion
            data = {"id": instance.pk}
            for field in instance._meta.fields:
                field_name = field.name
                value = getattr(instance, field_name)

                # Handle special field types
                if isinstance(value, models.Model):
                    data[field_name] = value.pk
                elif hasattr(value, 'isoformat'):
                    data[field_name] = value.isoformat()
                else:
                    data[field_name] = value

        # Cache the data
        update_cache_with_timestamp(key, data, timeout)
        return data, False
    except Exception as e:
        logger.error(f"Error getting with timestamp validation for {key}: {str(e)}")

        # Try to get from source as fallback
        try:
            instance = instance_getter(instance_id)
            if not instance:
                return None, False

            # Convert instance to data
            if hasattr(instance, "to_dict") and callable(getattr(instance, "to_dict")):
                return instance.to_dict(), False

            # Basic conversion
            data = {"id": instance.pk}
            for field in instance._meta.fields:
                field_name = field.name
                value = getattr(instance, field_name)

                # Handle special field types
                if isinstance(value, models.Model):
                    data[field_name] = value.pk
                elif hasattr(value, 'isoformat'):
                    data[field_name] = value.isoformat()
                else:
                    data[field_name] = value

            return data, False
        except Exception as e2:
            logger.error(f"Error getting from source as fallback: {str(e2)}")
            return None, False


# Timestamp-based decorators
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
            if not CACHE_ENABLED:
                return func(*args, **kwargs)

            # Generate cache keys
            base_key = f"{cache_key_prefix}:{func.__name__}"
            if version:
                base_key = f"{base_key}:v{version}"

            # Add args and kwargs to the key
            arg_parts = []
            for arg in args:
                if isinstance(arg, (str, int, float, bool)):
                    arg_parts.append(str(arg))
                elif hasattr(arg, 'pk'):
                    arg_parts.append(f"{arg.__class__.__name__}:{arg.pk}")

            for k, v in sorted(kwargs.items()):
                if isinstance(v, (str, int, float, bool)):
                    arg_parts.append(f"{k}:{v}")
                elif hasattr(v, 'pk'):
                    arg_parts.append(f"{k}:{v.__class__.__name__}:{v.pk}")

            if arg_parts:
                arg_key = ":".join(arg_parts)
                cache_key = f"{base_key}:{arg_key}"
            else:
                cache_key = base_key

            timestamp_key = f"{cache_key}:{timestamp_key_suffix}"

            # Try to get cached data and timestamp
            cached_data = get_cached_data(cache_key)
            cached_timestamp = get_cached_data(timestamp_key)

            # Get current timestamp
            current_timestamp = timezone.now()

            # Check if we need to refresh the cache
            refresh_cache = (
                cached_data is None or
                cached_timestamp is None or
                (isinstance(cached_timestamp, datetime) and current_timestamp - cached_timestamp > timedelta(seconds=timeout))
            )

            if refresh_cache:
                # Call the function
                result = func(*args, **kwargs)

                # Cache the result and timestamp
                set_cached_data(cache_key, result, timeout)
                set_cached_data(timestamp_key, current_timestamp, timeout)

                return result
            else:
                # Use cached data
                return cached_data

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
            if not CACHE_ENABLED:
                return func(*args, **kwargs)

            # Find model instance in args or kwargs
            model_instance = None
            for arg in args:
                if isinstance(arg, model_class):
                    model_instance = arg
                    break

            if model_instance is None:
                for _, v in kwargs.items():
                    if isinstance(v, model_class):
                        model_instance = v
                        break

            if model_instance is None:
                # No model instance found, just call the function
                return func(*args, **kwargs)

            # Generate cache keys
            base_key = f"{cache_key_prefix}:{func.__name__}"
            if version:
                base_key = f"{base_key}:v{version}"

            cache_key = f"{base_key}:{model_instance.__class__.__name__}:{model_instance.pk}"
            timestamp_key = f"{cache_key}:timestamp"

            # Get model timestamp
            model_timestamp = get_model_timestamp(model_instance)
            if model_timestamp is None:
                # No timestamp field found, just call the function
                return func(*args, **kwargs)

            # Try to get cached data and timestamp
            cached_data = get_cached_data(cache_key)
            cached_timestamp = get_cached_data(timestamp_key)

            # Check if we need to refresh the cache
            refresh_cache = (
                cached_data is None or
                cached_timestamp is None or
                (isinstance(cached_timestamp, datetime) and model_timestamp > cached_timestamp)
            )

            if refresh_cache:
                # Call the function
                result = func(*args, **kwargs)

                # Cache the result and timestamp
                set_cached_data(cache_key, result, timeout)
                set_cached_data(timestamp_key, model_timestamp, timeout)

                return result
            else:
                # Use cached data
                return cached_data

        return wrapper

    return decorator

"""
Timestamp-based cache validation decorators.

This module provides decorators for timestamp-based cache validation,
ensuring that cached data is always up-to-date.
"""

import functools
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Type, Union

from django.db import models
from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from core.cache import get_cached_data, set_cached_data, delete_cached_data
from core.redis_timestamp_validation import (
    get_model_timestamp, get_cache_timestamp, 
    is_cache_valid, ensure_timestamp_in_data,
    get_with_timestamp_validation
)

logger = logging.getLogger(__name__)


def cache_with_timestamp(key_prefix: str, timeout: int = 3600):
    """
    Decorator to cache a function result with timestamp validation.
    
    This decorator caches the result of a function and validates it using timestamps.
    
    Args:
        key_prefix: Prefix for the cache key
        timeout: Cache timeout in seconds
        
    Returns:
        Decorated function
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{key_prefix}:{func.__name__}"
            
            # Add args and kwargs to cache key
            if args:
                cache_key += f":{':'.join(str(arg) for arg in args)}"
            if kwargs:
                cache_key += f":{':'.join(f'{k}={v}' for k, v in kwargs.items())}"
                
            # Try to get from cache
            cached_data = get_cached_data(cache_key)
            
            if cached_data:
                # Check if cache has a timestamp
                cache_timestamp = None
                for field_name in ["timestamp", "last_updated", "updated_at", "created_at"]:
                    if field_name in cached_data:
                        try:
                            if isinstance(cached_data[field_name], str):
                                cache_timestamp = cached_data[field_name]
                            break
                        except (ValueError, TypeError):
                            continue
                
                # If cache has a timestamp, check if it's recent enough
                if cache_timestamp:
                    # Return cached data
                    return cached_data["result"]
            
            # Call the original function
            result = func(*args, **kwargs)
            
            # Cache the result with timestamp
            data = {
                "result": result,
                "timestamp": timezone.now().isoformat(),
            }
            set_cached_data(cache_key, data, timeout)
            
            return result
            
        return wrapper
    return decorator


def cache_model_with_timestamp(model_class: Type[models.Model], id_param: str = "pk", timeout: int = 3600):
    """
    Decorator to cache a model instance with timestamp validation.
    
    This decorator caches a model instance and validates it using timestamps.
    
    Args:
        model_class: Model class to cache
        id_param: Name of the parameter containing the model ID
        timeout: Cache timeout in seconds
        
    Returns:
        Decorated function
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get the model ID from kwargs
            model_id = kwargs.get(id_param)
            
            if not model_id:
                # No model ID, call the original function
                return func(*args, **kwargs)
                
            # Generate cache key
            model_name = model_class.__name__.lower()
            cache_key = f"model:{model_name}:{model_id}"
            
            # Define a function to get the model instance from the database
            def get_from_db(id):
                try:
                    return model_class.objects.get(pk=id)
                except model_class.DoesNotExist:
                    return None
            
            # Try to get with timestamp validation
            data, from_cache = get_with_timestamp_validation(
                cache_key, 
                get_from_db, 
                model_id, 
                timeout
            )
            
            if data:
                # Replace the model ID with the instance in kwargs
                if from_cache:
                    # Create a model instance from cached data
                    instance = model_class()
                    for field_name, field_value in data.items():
                        if field_name not in ["model", "_django_model", "_cached_at"]:
                            setattr(instance, field_name, field_value)
                    
                    # Mark as from cache
                    instance._from_cache = True
                    instance._cached_data = data
                    
                    # Replace the model ID with the instance
                    kwargs[id_param] = instance
                else:
                    # Get fresh instance from database
                    instance = get_from_db(model_id)
                    if instance:
                        # Replace the model ID with the instance
                        kwargs[id_param] = instance
            
            # Call the original function
            return func(*args, **kwargs)
            
        return wrapper
    return decorator


def invalidate_on_change(model_class: Type[models.Model], cache_key_func: Callable):
    """
    Decorator to invalidate cache when a model changes.
    
    This decorator invalidates cache entries when a model instance changes.
    
    Args:
        model_class: Model class to watch for changes
        cache_key_func: Function to generate cache keys from model instance
        
    Returns:
        Decorated function
    """
    def decorator(func):
        # Register signal handlers
        from django.db.models.signals import post_save, post_delete
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Call the original function
            return func(*args, **kwargs)
        
        # Define signal handlers
        def invalidate_cache(sender, instance, **kwargs):
            # Generate cache keys
            cache_keys = cache_key_func(instance)
            
            if isinstance(cache_keys, str):
                cache_keys = [cache_keys]
                
            # Invalidate cache
            for cache_key in cache_keys:
                delete_cached_data(cache_key)
                logger.debug(f"Invalidated cache for {cache_key}")
        
        # Register signal handlers
        post_save.connect(invalidate_cache, sender=model_class, weak=False)
        post_delete.connect(invalidate_cache, sender=model_class, weak=False)
        
        return wrapper
    return decorator


def auto_refresh_cache(model_class: Type[models.Model], cache_key_func: Callable, refresh_func: Callable):
    """
    Decorator to automatically refresh cache when a model changes.
    
    This decorator refreshes cache entries when a model instance changes.
    
    Args:
        model_class: Model class to watch for changes
        cache_key_func: Function to generate cache keys from model instance
        refresh_func: Function to refresh cache entries
        
    Returns:
        Decorated function
    """
    def decorator(func):
        # Register signal handlers
        from django.db.models.signals import post_save, post_delete
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Call the original function
            return func(*args, **kwargs)
        
        # Define signal handlers
        def refresh_cache(sender, instance, **kwargs):
            # Generate cache keys
            cache_keys = cache_key_func(instance)
            
            if isinstance(cache_keys, str):
                cache_keys = [cache_keys]
                
            # Refresh cache
            for cache_key in cache_keys:
                refresh_func(cache_key, instance)
                logger.debug(f"Refreshed cache for {cache_key}")
        
        # Register signal handlers
        post_save.connect(refresh_cache, sender=model_class, weak=False)
        
        return wrapper
    return decorator

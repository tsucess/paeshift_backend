"""
Atomic update utilities for cache consistency.

This module provides utilities for performing atomic updates to both
database and cache, ensuring consistency between the two.
"""

import logging
import time
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type, Union

from django.db import models, transaction
from django.utils import timezone

from core.cache import get_cached_data, set_cached_data, delete_cached_data
from core.redis_lock import redis_lock
from core.redis_permanent import cache_permanently, get_permanent_cache

logger = logging.getLogger(__name__)


def atomic_cache_update(model_instance, update_func, force_sync=True):
    """
    Perform an atomic update to both database and cache.
    
    This function ensures that both the database and cache are updated
    atomically, preventing race conditions and inconsistencies.
    
    Args:
        model_instance: Model instance to update
        update_func: Function that updates the model instance
        force_sync: Whether to force cache sync even if update fails
        
    Returns:
        Updated model instance
    """
    model_class = model_instance.__class__
    model_name = model_class.__name__
    model_id = model_instance.pk
    
    # Generate lock name
    lock_name = f"lock:{model_name}:{model_id}"
    
    # Generate cache key
    cache_key = None
    if hasattr(model_class, 'get_cache_key'):
        cache_key = model_class.get_cache_key(model_id)
    else:
        cache_key = f"{model_name.lower()}:{model_id}"
    
    # Acquire lock
    with redis_lock(lock_name, timeout=60) as acquired:
        if not acquired:
            logger.warning(f"Could not acquire lock for {model_name}:{model_id}, another process may be updating it")
            return model_instance
        
        try:
            # Start transaction
            with transaction.atomic():
                # Get fresh instance with select_for_update
                fresh_instance = model_class.objects.select_for_update().get(pk=model_id)
                
                # Apply update function
                update_func(fresh_instance)
                
                # Save the instance
                fresh_instance.save()
                
                # Update cache
                if cache_key:
                    # Get cache data
                    if hasattr(fresh_instance, 'get_cache_data'):
                        cache_data = fresh_instance.get_cache_data()
                    else:
                        # Create dictionary from model fields
                        cache_data = {}
                        for field in fresh_instance._meta.fields:
                            field_name = field.name
                            value = getattr(fresh_instance, field_name)
                            
                            # Handle special field types
                            if isinstance(value, models.Model):
                                cache_data[field_name] = value.pk
                            elif hasattr(value, 'isoformat'):
                                cache_data[field_name] = value.isoformat()
                            else:
                                cache_data[field_name] = value
                    
                    # Cache the data
                    if hasattr(model_class, 'redis_cache_permanent') and model_class.redis_cache_permanent:
                        cache_permanently(cache_data, cache_key)
                    else:
                        # Get timeout from model if available
                        timeout = None
                        if hasattr(model_class, 'redis_cache_timeout'):
                            timeout = model_class.redis_cache_timeout
                        
                        set_cached_data(cache_key, cache_data, timeout)
                    
                    logger.debug(f"Updated cache for {model_name}:{model_id}")
                
                return fresh_instance
                
        except Exception as e:
            logger.exception(f"Error performing atomic update for {model_name}:{model_id}: {str(e)}")
            
            # If force_sync is True, try to update cache anyway
            if force_sync and cache_key:
                try:
                    # Get fresh instance
                    fresh_instance = model_class.objects.get(pk=model_id)
                    
                    # Get cache data
                    if hasattr(fresh_instance, 'get_cache_data'):
                        cache_data = fresh_instance.get_cache_data()
                    else:
                        # Create dictionary from model fields
                        cache_data = {}
                        for field in fresh_instance._meta.fields:
                            field_name = field.name
                            value = getattr(fresh_instance, field_name)
                            
                            # Handle special field types
                            if isinstance(value, models.Model):
                                cache_data[field_name] = value.pk
                            elif hasattr(value, 'isoformat'):
                                cache_data[field_name] = value.isoformat()
                            else:
                                cache_data[field_name] = value
                    
                    # Cache the data
                    if hasattr(model_class, 'redis_cache_permanent') and model_class.redis_cache_permanent:
                        cache_permanently(cache_data, cache_key)
                    else:
                        # Get timeout from model if available
                        timeout = None
                        if hasattr(model_class, 'redis_cache_timeout'):
                            timeout = model_class.redis_cache_timeout
                        
                        set_cached_data(cache_key, cache_data, timeout)
                    
                    logger.debug(f"Force-updated cache for {model_name}:{model_id} after update error")
                    
                except Exception as cache_error:
                    logger.exception(f"Error force-updating cache for {model_name}:{model_id}: {str(cache_error)}")
            
            # Re-raise the original exception
            raise


def atomic_cache_update_decorator(func):
    """
    Decorator for methods that update a model instance.
    
    This decorator wraps a method that updates a model instance,
    ensuring that both the database and cache are updated atomically.
    
    Example:
        @atomic_cache_update_decorator
        def update_status(self, new_status):
            self.status = new_status
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        # Define update function
        def update_func(instance):
            return func(instance, *args, **kwargs)
        
        # Perform atomic update
        return atomic_cache_update(self, update_func)
    
    return wrapper


def bulk_atomic_cache_update(model_class, ids, update_func):
    """
    Perform atomic updates on multiple model instances.
    
    This function updates multiple model instances atomically,
    ensuring that both the database and cache are updated consistently.
    
    Args:
        model_class: Model class
        ids: List of primary keys
        update_func: Function that updates a model instance
        
    Returns:
        List of updated model instances
    """
    model_name = model_class.__name__
    updated_instances = []
    
    for model_id in ids:
        try:
            # Get the instance
            instance = model_class.objects.get(pk=model_id)
            
            # Perform atomic update
            updated_instance = atomic_cache_update(instance, update_func)
            updated_instances.append(updated_instance)
            
        except Exception as e:
            logger.exception(f"Error performing bulk atomic update for {model_name}:{model_id}: {str(e)}")
    
    return updated_instances

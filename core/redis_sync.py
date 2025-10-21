"""
Redis synchronization utilities.

This module provides utilities for keeping Redis cache in sync with the database.
"""

import logging
from typing import Any, Dict, List, Optional, Type, Union

from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from core.cache import (
    get_cached_data,
    set_cached_data,
    delete_cached_data,
    invalidate_cache_pattern,
)
from core.redis_permanent import (
    cache_permanently,
    get_permanent_cache,
    delete_permanent_cache,
)

logger = logging.getLogger(__name__)

# Registry of models that should be synced with Redis
# Format: {model_class: {cache_prefix, timeout, permanent}}
_SYNC_REGISTRY = {}


def register_model_for_sync(
    model_class: Type[models.Model],
    cache_prefix: str,
    timeout: Optional[int] = None,
    permanent: bool = False,
) -> None:
    """
    Register a model for automatic synchronization with Redis.
    
    Args:
        model_class: The model class to sync
        cache_prefix: The prefix for cache keys
        timeout: Cache timeout in seconds (None for permanent)
        permanent: Whether to cache permanently
    """
    _SYNC_REGISTRY[model_class] = {
        "cache_prefix": cache_prefix,
        "timeout": timeout,
        "permanent": permanent,
    }
    logger.info(f"Registered model for sync: {model_class.__name__} with prefix {cache_prefix}")


def sync_model_to_redis(
    instance: models.Model,
    cache_prefix: Optional[str] = None,
    timeout: Optional[int] = None,
    permanent: bool = False,
) -> bool:
    """
    Synchronize a model instance to Redis.
    
    Args:
        instance: The model instance to sync
        cache_prefix: The prefix for cache keys (defaults to model name)
        timeout: Cache timeout in seconds (None for permanent)
        permanent: Whether to cache permanently
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get model class and name
        model_class = instance.__class__
        model_name = model_class.__name__.lower()
        
        # Use provided prefix or default to model name
        prefix = cache_prefix or model_name
        
        # Generate cache key
        cache_key = f"{prefix}:{instance.pk}"
        
        # Convert instance to dict
        if hasattr(instance, "to_dict"):
            # Use custom to_dict method if available
            data = instance.to_dict()
        elif hasattr(instance, "to_json"):
            # Use custom to_json method if available
            data = instance.to_json()
        else:
            # Default serialization
            data = {
                "id": instance.pk,
                "model": model_name,
            }
            
            # Add common fields if they exist
            for field in instance._meta.fields:
                field_name = field.name
                if field_name != "id":
                    value = getattr(instance, field_name)
                    
                    # Handle special field types
                    if isinstance(value, models.Model):
                        # For foreign keys, just store the ID
                        data[field_name] = value.pk
                    elif hasattr(value, "isoformat"):
                        # For dates and times, convert to ISO format
                        data[field_name] = value.isoformat()
                    else:
                        # For other fields, store as is
                        data[field_name] = value
        
        # Cache the data
        if permanent:
            success = cache_permanently(data, cache_key)
        else:
            success = set_cached_data(cache_key, data, timeout)
        
        if success:
            logger.debug(f"Synced {model_name} {instance.pk} to Redis")
        else:
            logger.warning(f"Failed to sync {model_name} {instance.pk} to Redis")
        
        return success
    except Exception as e:
        logger.error(f"Error syncing model to Redis: {str(e)}")
        return False


def invalidate_model_cache(
    instance: models.Model,
    cache_prefix: Optional[str] = None,
) -> bool:
    """
    Invalidate cache for a model instance.
    
    Args:
        instance: The model instance
        cache_prefix: The prefix for cache keys (defaults to model name)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get model name
        model_name = instance.__class__.__name__.lower()
        
        # Use provided prefix or default to model name
        prefix = cache_prefix or model_name
        
        # Generate cache key
        cache_key = f"{prefix}:{instance.pk}"
        
        # Delete from both regular and permanent cache
        regular_success = delete_cached_data(cache_key)
        permanent_success = delete_permanent_cache(cache_key)
        
        if regular_success or permanent_success:
            logger.debug(f"Invalidated cache for {model_name} {instance.pk}")
        
        return regular_success or permanent_success
    except Exception as e:
        logger.error(f"Error invalidating model cache: {str(e)}")
        return False


@receiver(post_save)
def sync_on_save(sender, instance, created, **kwargs):
    """
    Signal handler to sync model to Redis when saved.
    
    Args:
        sender: The model class
        instance: The model instance
        created: Whether the instance was created
    """
    # Check if the model is registered for sync
    if sender not in _SYNC_REGISTRY:
        return
    
    # Get sync settings
    sync_settings = _SYNC_REGISTRY[sender]
    
    # Sync to Redis
    sync_model_to_redis(
        instance,
        cache_prefix=sync_settings["cache_prefix"],
        timeout=sync_settings["timeout"],
        permanent=sync_settings["permanent"],
    )


@receiver(post_delete)
def invalidate_on_delete(sender, instance, **kwargs):
    """
    Signal handler to invalidate cache when a model instance is deleted.
    
    Args:
        sender: The model class
        instance: The model instance
    """
    # Check if the model is registered for sync
    if sender not in _SYNC_REGISTRY:
        return
    
    # Get sync settings
    sync_settings = _SYNC_REGISTRY[sender]
    
    # Invalidate cache
    invalidate_model_cache(
        instance,
        cache_prefix=sync_settings["cache_prefix"],
    )


class RedisSyncMixin:
    """
    Mixin for models to automatically sync with Redis.
    
    This mixin adds methods to sync the model with Redis when it is saved or deleted.
    """
    
    # Cache settings
    redis_cache_prefix = None  # Override in subclass
    redis_cache_timeout = None  # Override in subclass
    redis_cache_permanent = False  # Override in subclass
    
    def sync_to_redis(self):
        """
        Sync this model instance to Redis.
        
        Returns:
            True if successful, False otherwise
        """
        return sync_model_to_redis(
            self,
            cache_prefix=self.redis_cache_prefix or self.__class__.__name__.lower(),
            timeout=self.redis_cache_timeout,
            permanent=self.redis_cache_permanent,
        )
    
    def invalidate_redis_cache(self):
        """
        Invalidate Redis cache for this model instance.
        
        Returns:
            True if successful, False otherwise
        """
        return invalidate_model_cache(
            self,
            cache_prefix=self.redis_cache_prefix or self.__class__.__name__.lower(),
        )
    
    def save(self, *args, **kwargs):
        """
        Override save method to sync with Redis.
        
        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
        """
        # Call the original save method
        result = super().save(*args, **kwargs)
        
        # Sync to Redis
        self.sync_to_redis()
        
        return result
    
    def delete(self, *args, **kwargs):
        """
        Override delete method to invalidate Redis cache.
        
        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
        """
        # Invalidate Redis cache
        self.invalidate_redis_cache()
        
        # Call the original delete method
        return super().delete(*args, **kwargs)

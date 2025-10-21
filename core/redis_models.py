"""
Redis-based model caching utilities.

This module provides utilities for caching Django model instances in Redis
and keeping the cache in sync with database changes.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Type, Union, Tuple

from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from core.cache import (
    delete_cached_data,
    get_cached_data,
    set_cached_data,
)

# Import timestamp validation utilities
try:
    from core.redis_timestamp_validation import (
        get_model_timestamp, get_cache_timestamp,
        is_cache_valid, ensure_timestamp_in_data,
        get_with_timestamp_validation
    )
except ImportError:
    # Fallback if the module is not available
    def get_model_timestamp(instance): return None
    def get_cache_timestamp(data): return None
    def is_cache_valid(instance, data): return True, "Validation not available"
    def ensure_timestamp_in_data(data): return data
    def get_with_timestamp_validation(key, getter, id, timeout): return None, False

logger = logging.getLogger(__name__)

# Constants
MODEL_CACHE_EXPIRATION = 60 * 60 * 24  # 24 hours
MODEL_CACHE_PREFIX = "model:"


class ModelCache:
    """
    Redis-based model cache.

    This class provides methods for caching Django model instances in Redis
    and keeping the cache in sync with database changes.
    """

    def __init__(self, model_class: Type[models.Model], expiration: int = MODEL_CACHE_EXPIRATION):
        """
        Initialize a model cache.

        Args:
            model_class: Django model class
            expiration: Cache expiration time in seconds
        """
        self.model_class = model_class
        self.model_name = model_class.__name__.lower()
        self.expiration = expiration

    def get(self, instance_id: Union[int, str], use_cache: bool = True) -> Optional[models.Model]:
        """
        Get a model instance.

        Args:
            instance_id: Instance ID
            use_cache: Whether to use the cache

        Returns:
            Model instance or None if not found
        """
        try:
            # If not using cache, get from database
            if not use_cache:
                return self.model_class.objects.get(pk=instance_id)

            # Generate cache key
            cache_key = self._get_cache_key(instance_id)

            # Define a function to get the instance from the database
            def get_from_db(id):
                try:
                    return self.model_class.objects.get(pk=id)
                except ObjectDoesNotExist:
                    return None

            # Try to get with timestamp validation
            data, from_cache = get_with_timestamp_validation(
                cache_key,
                get_from_db,
                instance_id,
                self.expiration
            )

            if data:
                if from_cache:
                    # Data is from cache and valid
                    instance = self._data_to_instance(data)
                    instance._from_cache = True
                    instance._cached_data = data
                    return instance
                else:
                    # Data is fresh from database
                    instance = get_from_db(instance_id)
                    if instance:
                        # Cache the instance
                        self.cache(instance)
                    return instance

            # Not found or error
            return None
        except Exception as e:
            logger.error(f"Error getting {self.model_name} with ID {instance_id}: {str(e)}")

            # Try to get from database as fallback
            try:
                return self.model_class.objects.get(pk=instance_id)
            except ObjectDoesNotExist:
                return None
            except Exception as e2:
                logger.error(f"Error getting {self.model_name} from database: {str(e2)}")
                return None

    def cache(self, instance: models.Model) -> bool:
        """
        Cache a model instance.

        Args:
            instance: Model instance

        Returns:
            True if successful, False otherwise
        """
        try:
            # Generate cache key
            cache_key = self._get_cache_key(instance.pk)

            # Convert instance to data
            instance_data = self._instance_to_data(instance)

            # Ensure data has a timestamp for validation
            instance_data = ensure_timestamp_in_data(instance_data)

            # Add cache metadata
            instance_data["_cached_at"] = timezone.now().isoformat()

            # Cache data
            return set_cached_data(cache_key, instance_data, self.expiration)
        except Exception as e:
            logger.error(f"Error caching {self.model_name} with ID {instance.pk}: {str(e)}")
            return False

    def invalidate(self, instance_id: Union[int, str]) -> bool:
        """
        Invalidate a cached model instance.

        Args:
            instance_id: Instance ID

        Returns:
            True if successful, False otherwise
        """
        try:
            # Generate cache key
            cache_key = self._get_cache_key(instance_id)

            # Delete from cache
            return delete_cached_data(cache_key)
        except Exception as e:
            logger.error(f"Error invalidating {self.model_name} with ID {instance_id}: {str(e)}")
            return False

    def _get_cache_key(self, instance_id: Union[int, str]) -> str:
        """
        Generate a cache key for a model instance.

        Args:
            instance_id: Instance ID

        Returns:
            Cache key
        """
        return f"{MODEL_CACHE_PREFIX}{self.model_name}:{instance_id}"

    def _instance_to_data(self, instance: models.Model) -> Dict[str, Any]:
        """
        Convert a model instance to a dictionary.

        Args:
            instance: Model instance

        Returns:
            Dictionary representation of the instance
        """
        # If instance has a to_dict method, use it
        if hasattr(instance, "to_dict") and callable(getattr(instance, "to_dict")):
            data = instance.to_dict()
            # Ensure data has timestamps for validation
            return ensure_timestamp_in_data(data)

        # If instance has a to_json method, use it
        if hasattr(instance, "to_json") and callable(getattr(instance, "to_json")):
            data = json.loads(instance.to_json())
            # Ensure data has timestamps for validation
            return ensure_timestamp_in_data(data)

        # Otherwise, create a basic dictionary
        data = {
            "id": instance.pk,
            "model": self.model_name,
            "_django_model": f"{instance.__class__.__module__}.{instance.__class__.__name__}",
            "_cached_at": timezone.now().isoformat(),  # Add cache timestamp
        }

        # Add fields
        for field in instance._meta.fields:
            field_name = field.name
            field_value = getattr(instance, field_name)

            # Handle special field types
            if isinstance(field, models.DateTimeField) and field_value is not None:
                field_value = field_value.isoformat()
            elif isinstance(field, models.DateField) and field_value is not None:
                field_value = field_value.isoformat()
            elif isinstance(field, models.FileField) and field_value:
                field_value = field_value.url if field_value else None
            elif isinstance(field, models.ForeignKey) and field_value is not None:
                # For foreign keys, just store the ID
                field_value = field_value.pk

            data[field_name] = field_value

        # Ensure data has timestamps for validation
        return ensure_timestamp_in_data(data)

    def _data_to_instance(self, data: Dict[str, Any]) -> models.Model:
        """
        Convert a dictionary to a model instance.

        Args:
            data: Dictionary representation of the instance

        Returns:
            Model instance
        """
        # Get model class
        model_class = self.model_class

        # Create a new instance
        instance = model_class()

        # Set fields
        for field_name, field_value in data.items():
            # Skip special fields
            if field_name in ["model", "_django_model"]:
                continue

            # Set field value
            setattr(instance, field_name, field_value)

        # Mark as from cache
        instance._from_cache = True

        return instance


# Dictionary to store model cache instances
_model_caches = {}


def get_model_cache(model_class: Type[models.Model]) -> ModelCache:
    """
    Get a model cache for a model class.

    Args:
        model_class: Django model class

    Returns:
        ModelCache instance
    """
    model_name = model_class.__name__

    if model_name not in _model_caches:
        _model_caches[model_name] = ModelCache(model_class)

    return _model_caches[model_name]


def cache_model(instance: models.Model) -> bool:
    """
    Cache a model instance.

    Args:
        instance: Model instance

    Returns:
        True if successful, False otherwise
    """
    model_cache = get_model_cache(instance.__class__)
    return model_cache.cache(instance)


def invalidate_model_cache(instance: models.Model) -> bool:
    """
    Invalidate a cached model instance.

    Args:
        instance: Model instance

    Returns:
        True if successful, False otherwise
    """
    model_cache = get_model_cache(instance.__class__)
    return model_cache.invalidate(instance.pk)


def get_cached_model(model_class: Type[models.Model], instance_id: Union[int, str], use_cache: bool = True) -> Optional[models.Model]:
    """
    Get a cached model instance.

    Args:
        model_class: Django model class
        instance_id: Instance ID
        use_cache: Whether to use the cache

    Returns:
        Model instance or None if not found
    """
    model_cache = get_model_cache(model_class)
    return model_cache.get(instance_id, use_cache)


# Signal handlers to keep cache in sync with database

@receiver(post_save)
def model_post_save_handler(sender, instance, created, **kwargs):
    """
    Handle post_save signal to update the cache.

    Args:
        sender: Model class
        instance: Model instance
        created: Whether the instance was created
        **kwargs: Additional arguments
    """
    try:
        # Skip if this is a built-in model
        if sender._meta.app_label in ["auth", "contenttypes", "sessions", "admin"]:
            return

        # Skip Profile models to avoid conflicts between accounts.Profile and chatapp.Profile
        if sender.__name__ == "Profile":
            logger.debug(f"Skipping automatic caching for Profile model with ID {instance.pk}")
            return

        # Cache the instance
        cache_model(instance)

        logger.debug(f"Cached {sender.__name__} with ID {instance.pk} after save")
    except Exception as e:
        logger.error(f"Error caching {sender.__name__} with ID {instance.pk} after save: {str(e)}")


@receiver(post_delete)
def model_post_delete_handler(sender, instance, **kwargs):
    """
    Handle post_delete signal to invalidate the cache.

    Args:
        sender: Model class
        instance: Model instance
        **kwargs: Additional arguments
    """
    try:
        # Skip if this is a built-in model
        if sender._meta.app_label in ["auth", "contenttypes", "sessions", "admin"]:
            return

        # Skip Profile models to avoid conflicts between accounts.Profile and chatapp.Profile
        if sender.__name__ == "Profile":
            logger.debug(f"Skipping automatic cache invalidation for Profile model with ID {instance.pk}")
            return

        # Invalidate the cache
        invalidate_model_cache(instance)

        logger.debug(f"Invalidated {sender.__name__} with ID {instance.pk} after delete")
    except Exception as e:
        logger.error(f"Error invalidating {sender.__name__} with ID {instance.pk} after delete: {str(e)}")

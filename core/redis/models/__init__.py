"""
Redis models module.

This module provides utilities for caching Django model instances in Redis.
"""

import logging
from typing import Any, Dict, Optional, Type, Union

# Import Django utilities
from django.utils import timezone

# Import Redis utilities
from core.redis.client import redis_client
from core.redis.settings import (
    CACHE_ENABLED,
    CACHE_PREFIXES,
    CACHE_TIMEOUTS,
    CACHE_VERSION,
    MODEL_CACHE_EXPIRATION,
    MODEL_CACHE_PREFIX,
)
from core.redis.utils import (
    generate_cache_key,
    get_cached_data,
    set_cached_data,
    delete_cached_data,
)

# Set up logging
logger = logging.getLogger(__name__)

# We'll import Django models lazily in each function to avoid AppRegistryNotReady error

# Define RedisCachedModel as a function that returns the class
# This delays the class creation until it's actually used
def get_redis_cached_model():
    """
    Returns the RedisCachedModel class.

    This function delays the creation of the RedisCachedModel class until
    it's actually used, avoiding AppRegistryNotReady errors during Django startup.
    """
    # Import Django models here to avoid circular imports
    from django.db import models as django_models

    class RedisCachedModel(django_models.Model):
        """
        Abstract model mixin that provides Redis caching functionality.

        This mixin combines the best features of RedisCachedModelMixin, RedisSyncMixin,
        and CacheableModelMixin to provide a standardized approach to model caching.

        Features:
        - Automatic cache invalidation on save/delete
        - Customizable cache key generation
        - Configurable cache timeout
        - Selective field caching
        - Cache versioning

        Usage:
            class MyModel(models.Model, RedisCachedModel):
                # Model fields...

                # Redis caching configuration
                redis_cache_enabled = True
                redis_cache_prefix = "my_model"
                redis_cache_timeout = 3600  # 1 hour
                redis_cache_related = ["related_field"]
                redis_cache_exclude = ["excluded_field"]
        """

        # Cache configuration
        redis_cache_enabled = True
        redis_cache_prefix = None
        redis_cache_timeout = None
        redis_cache_related = []
        redis_cache_exclude = []
        redis_cache_permanent = False
        redis_cache_version = CACHE_VERSION

        class Meta:
            abstract = True

        def get_cache_key(self, suffix: Optional[str] = None) -> str:
            """
            Get the cache key for this instance.

            Args:
                suffix: Optional suffix to add to the key

            Returns:
                Cache key string
            """
            # Get prefix
            prefix = self.redis_cache_prefix
            if prefix is None:
                prefix = self.__class__.__name__.lower()

            # Generate key
            key = f"{prefix}:{self.pk}"

            # Add suffix if provided
            if suffix:
                key = f"{key}:{suffix}"

            # Add version
            key = f"{key}:v{self.redis_cache_version}"

            return key

        def get_cache_data(self) -> Dict[str, Any]:
            """
            Get the data to cache for this instance.

            Returns:
                Dictionary of data to cache
            """
            # Get all fields
            data = {}
            for field in self._meta.fields:
                # Skip excluded fields
                if field.name in self.redis_cache_exclude:
                    continue

                # Get field value
                value = getattr(self, field.name)

                # Add to data
                data[field.name] = value

            # Add related fields
            for related_field in self.redis_cache_related:
                # Get related object
                related_obj = getattr(self, related_field)

                # Skip if None
                if related_obj is None:
                    continue

                # Add to data
                if hasattr(related_obj, "get_cache_data"):
                    # Use get_cache_data if available
                    data[related_field] = related_obj.get_cache_data()
                else:
                    # Otherwise, use a simple representation
                    data[related_field] = {
                        "id": related_obj.pk,
                        "model": related_obj.__class__.__name__,
                    }

            # Add metadata
            data["_cached_at"] = timezone.now().isoformat()
            data["_model"] = self.__class__.__name__
            data["_app"] = self._meta.app_label

            return data

        def cache_instance(self) -> bool:
            """
            Cache this instance in Redis.

            Returns:
                True if successful, False otherwise
            """
            if not CACHE_ENABLED or not redis_client or not self.redis_cache_enabled:
                return False

            try:
                # Generate cache key
                cache_key = self.get_cache_key()

                # Get data to cache
                cache_data = self.get_cache_data()

                # Determine timeout
                timeout = self.redis_cache_timeout
                if timeout is None:
                    # Use default timeout based on model name or global default
                    model_name = self.__class__.__name__.lower()
                    timeout = CACHE_TIMEOUTS.get(model_name, CACHE_TIMEOUTS["default"])

                # Use permanent caching if specified
                if self.redis_cache_permanent:
                    from core.redis.utils import cache_permanently
                    cache_permanently(cache_data, cache_key)
                    logger.debug(f"Permanently cached {self.__class__.__name__}:{self.pk}")
                else:
                    # Set in cache with timeout
                    set_cached_data(cache_key, cache_data, timeout)
                    logger.debug(f"Cached {self.__class__.__name__}:{self.pk} with timeout {timeout}s")

                return True
            except Exception as e:
                logger.error(f"Error caching {self.__class__.__name__}:{self.pk}: {str(e)}")
                return False

        def invalidate_cache(self) -> bool:
            """
            Invalidate the cache for this instance.

            Returns:
                True if successful, False otherwise
            """
            if not CACHE_ENABLED or not redis_client:
                return False

            try:
                # Generate cache key
                cache_key = self.get_cache_key()

                # Delete from cache
                delete_cached_data(cache_key)
                logger.debug(f"Invalidated cache for {self.__class__.__name__}:{self.pk}")

                return True
            except Exception as e:
                logger.error(f"Error invalidating cache for {self.__class__.__name__}:{self.pk}: {str(e)}")
                return False

        def save(self, *args, **kwargs):
            """Override save to update cache."""
            # Call the original save method
            super().save(*args, **kwargs)

            # Update cache if enabled
            if CACHE_ENABLED and self.redis_cache_enabled:
                self.cache_instance()

        def delete(self, *args, **kwargs):
            """Override delete to invalidate cache."""
            # Invalidate cache if enabled
            if CACHE_ENABLED and self.redis_cache_enabled:
                self.invalidate_cache()

            # Call the original delete method
            super().delete(*args, **kwargs)

    return RedisCachedModel


# Create a proxy for RedisCachedModel that will be resolved when used
class RedisCachedModelProxy:
    """
    Proxy class for RedisCachedModel.

    This class acts as a proxy for the RedisCachedModel class, resolving it
    only when it's actually used, avoiding AppRegistryNotReady errors.
    """
    _model_class = None

    @classmethod
    def get_model_class(cls):
        """Get the actual model class, initializing it if needed."""
        if cls._model_class is None:
            cls._model_class = get_redis_cached_model()
        return cls._model_class

    def __new__(cls, *args, **kwargs):
        model_class = cls.get_model_class()
        return model_class(*args, **kwargs)


# Replace RedisCachedModel with the proxy
RedisCachedModel = RedisCachedModelProxy

# For backwards compatibility
RedisCachedModelMixin = RedisCachedModelProxy


def cache_model(instance, timeout: Optional[int] = None) -> bool:
    """
    Cache a model instance.

    Args:
        instance: Django model instance to cache
        timeout: Cache timeout in seconds

    Returns:
        True if successful, False otherwise
    """
    # Import Django models here to avoid circular imports
    from django.db import models
    if not CACHE_ENABLED or not redis_client:
        return False

    try:
        # Check if instance has cache_instance method
        if hasattr(instance, "cache_instance") and callable(instance.cache_instance):
            return instance.cache_instance()

        # Otherwise, use generic caching
        model_name = instance.__class__.__name__.lower()
        prefix = CACHE_PREFIXES.get(model_name, MODEL_CACHE_PREFIX)
        cache_key = generate_cache_key(prefix, instance.pk)

        # Convert instance to dictionary
        data = {}
        for field in instance._meta.fields:
            value = getattr(instance, field.name)
            data[field.name] = value

        # Add metadata
        data["_cached_at"] = timezone.now().isoformat()
        data["_model"] = instance.__class__.__name__
        data["_app"] = instance._meta.app_label

        # Determine timeout
        if timeout is None:
            timeout = CACHE_TIMEOUTS.get(model_name, MODEL_CACHE_EXPIRATION)

        # Cache the data
        set_cached_data(cache_key, data, timeout)
        logger.debug(f"Cached {instance.__class__.__name__}:{instance.pk}")

        return True
    except Exception as e:
        logger.error(f"Error caching {instance.__class__.__name__}:{instance.pk}: {str(e)}")
        return False


def get_cached_model(model_class, instance_id: Any):
    """
    Get a cached model instance.

    Args:
        model_class: Django model class
        instance_id: Instance ID

    Returns:
        Model instance or None if not found
    """
    # Import Django models here to avoid circular imports
    from django.db import models
    if not CACHE_ENABLED or not redis_client:
        return None

    try:
        # Generate cache key
        model_name = model_class.__name__.lower()
        prefix = CACHE_PREFIXES.get(model_name, MODEL_CACHE_PREFIX)
        cache_key = generate_cache_key(prefix, instance_id)

        # Get from cache
        cached_data = get_cached_data(cache_key)
        if cached_data is None:
            return None

        # Create instance
        instance = model_class()

        # Set fields
        for field_name, value in cached_data.items():
            # Skip metadata fields
            if field_name.startswith("_"):
                continue

            # Set field value
            setattr(instance, field_name, value)

        return instance
    except Exception as e:
        logger.error(f"Error getting cached {model_class.__name__}:{instance_id}: {str(e)}")
        return None


def invalidate_model_cache(instance) -> bool:
    """
    Invalidate the cache for a model instance.

    Args:
        instance: Django model instance

    Returns:
        True if successful, False otherwise
    """
    # Import Django models here to avoid circular imports
    from django.db import models
    if not CACHE_ENABLED or not redis_client:
        return False

    try:
        # Check if instance has invalidate_cache method
        if hasattr(instance, "invalidate_cache") and callable(instance.invalidate_cache):
            return instance.invalidate_cache()

        # Otherwise, use generic invalidation
        model_name = instance.__class__.__name__.lower()
        prefix = CACHE_PREFIXES.get(model_name, MODEL_CACHE_PREFIX)
        cache_key = generate_cache_key(prefix, instance.pk)

        # Delete from cache
        delete_cached_data(cache_key)
        logger.debug(f"Invalidated cache for {instance.__class__.__name__}:{instance.pk}")

        return True
    except Exception as e:
        logger.error(f"Error invalidating cache for {instance.__class__.__name__}:{instance.pk}: {str(e)}")
        return False

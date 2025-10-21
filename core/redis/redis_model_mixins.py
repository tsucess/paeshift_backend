"""
Redis model caching mixins.

This module provides mixins for Django models to integrate with Redis caching.
It consolidates functionality from multiple existing mixins to provide a standardized
approach to model caching.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Set, Type, Union

from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete, post_save

from core.cache import delete_cached_data, get_cached_data, set_cached_data
from core.redis_settings import CACHE_ENABLED, CACHE_TIMEOUTS, CACHE_DEFAULT_TIMEOUT

logger = logging.getLogger(__name__)


class RedisCachedModel(models.Model):
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
        class MyModel(RedisCachedModel):
            # Define cache settings
            redis_cache_enabled = True
            redis_cache_timeout = 3600  # 1 hour
            redis_cache_prefix = 'my_model'
            redis_cache_version = '1'
            redis_cache_fields = ['id', 'name', 'description']  # Fields to cache
            redis_cache_exclude = ['password', 'secret_key']  # Fields to exclude
            
            # Model fields
            name = models.CharField(max_length=100)
            description = models.TextField()
            # ...
    """
    
    # Cache settings with defaults
    redis_cache_enabled = True
    redis_cache_timeout = None  # Use default timeout
    redis_cache_prefix = None  # Use model name as prefix
    redis_cache_version = '1'
    redis_cache_fields = None  # Cache all fields
    redis_cache_exclude = None  # Don't exclude any fields
    redis_cache_related = False  # Don't cache related objects by default
    redis_cache_permanent = False  # Use timeout by default
    
    class Meta:
        abstract = True
    
    @classmethod
    def get_cache_key(cls, instance_id: Union[int, str]) -> str:
        """
        Generate a cache key for a model instance.
        
        Args:
            instance_id: Primary key of the instance
            
        Returns:
            Cache key string
        """
        prefix = cls.redis_cache_prefix or cls.__name__.lower()
        version = cls.redis_cache_version
        
        if version:
            return f"{prefix}:{instance_id}:v{version}"
        else:
            return f"{prefix}:{instance_id}"
    
    def get_cache_data(self) -> Dict[str, Any]:
        """
        Get the data to cache for this instance.
        
        Returns:
            Dictionary of field values to cache
        """
        cache_data = {}
        
        # Get all fields or specified fields
        fields_to_cache = self.redis_cache_fields or [f.name for f in self._meta.fields]
        
        # Apply exclusions
        if self.redis_cache_exclude:
            fields_to_cache = [f for f in fields_to_cache if f not in self.redis_cache_exclude]
        
        # Add fields to cache data
        for field_name in fields_to_cache:
            try:
                value = getattr(self, field_name)
                
                # Handle special field types
                if isinstance(value, models.Model):
                    # For foreign keys, store the ID
                    cache_data[field_name] = value.pk
                elif hasattr(value, 'isoformat'):
                    # For dates/datetimes, store ISO format
                    cache_data[field_name] = value.isoformat()
                else:
                    # For other types, store as is
                    cache_data[field_name] = value
            except Exception as e:
                logger.warning(f"Error caching field {field_name} for {self.__class__.__name__}: {str(e)}")
        
        # Add related objects if enabled
        if self.redis_cache_related:
            for related_obj in self._meta.related_objects:
                related_name = related_obj.get_accessor_name()
                
                try:
                    related_manager = getattr(self, related_name)
                    
                    if hasattr(related_manager, 'all'):
                        # For many-to-many and reverse foreign keys
                        related_ids = list(related_manager.all().values_list('id', flat=True))
                        cache_data[f"{related_name}_ids"] = related_ids
                except Exception as e:
                    logger.warning(
                        f"Error caching related field {related_name} for {self.__class__.__name__}: {str(e)}"
                    )
        
        return cache_data
    
    def cache_instance(self) -> bool:
        """
        Cache this instance in Redis.
        
        Returns:
            True if successful, False otherwise
        """
        if not CACHE_ENABLED or not self.redis_cache_enabled:
            return False
        
        try:
            # Generate cache key
            cache_key = self.get_cache_key(self.pk)
            
            # Get data to cache
            cache_data = self.get_cache_data()
            
            # Determine timeout
            timeout = self.redis_cache_timeout
            if timeout is None:
                # Use default timeout based on model name or global default
                model_name = self.__class__.__name__.lower()
                timeout = CACHE_TIMEOUTS.get(model_name, CACHE_DEFAULT_TIMEOUT)
            
            # Use permanent caching if specified
            if self.redis_cache_permanent:
                from core.redis_permanent import cache_permanently
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
        if not CACHE_ENABLED or not self.redis_cache_enabled:
            return False
        
        try:
            # Generate cache key
            cache_key = self.get_cache_key(self.pk)
            
            # Delete from cache
            deleted = delete_cached_data(cache_key)
            
            if deleted:
                logger.debug(f"Invalidated cache for {self.__class__.__name__}:{self.pk}")
            
            return deleted
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


# For backwards compatibility
RedisCachedModelMixin = RedisCachedModel

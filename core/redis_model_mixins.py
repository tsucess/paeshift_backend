"""
Redis model mixins.

This module provides mixins for caching Django model instances in Redis.
It consolidates the best practices from various approaches to model caching.
"""

import json
import logging
from typing import Any, Dict, Optional, Type

from django.conf import settings
from django.db import models

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
    redis_cache_version = "1.0"
    
    class Meta:
        abstract = True
    
    def get_cache_key(self, suffix=None):
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
    
    def get_cache_data(self):
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
        
        return data
    
    def cache_instance(self):
        """
        Cache this instance in Redis.
        
        Returns:
            True if successful, False otherwise
        """
        if not CACHE_ENABLED or not self.redis_cache_enabled:
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
                timeout = CACHE_TIMEOUTS.get(model_name, CACHE_DEFAULT_TIMEOUT)
            
            # Set in cache with timeout
            if self.redis_cache_permanent:
                # Use permanent caching
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
    
    def invalidate_cache(self):
        """
        Invalidate the cache for this instance.
        
        Returns:
            True if successful, False otherwise
        """
        if not CACHE_ENABLED:
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

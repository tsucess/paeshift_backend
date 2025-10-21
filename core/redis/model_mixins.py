"""
Model mixins for enhanced caching and consistency.

This module provides mixins that can be added to models to enhance
cache consistency through timestamps, versioning, and other features.
"""

from django.db import models
from django.utils import timezone


class TimestampedModelMixin(models.Model):
    """
    Mixin that adds standard timestamp fields to a model.
    
    This mixin adds created_at and last_updated fields to ensure
    models have consistent timestamp fields for cache synchronization.
    """
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    last_updated = models.DateTimeField(auto_now=True, db_index=True)
    
    class Meta:
        abstract = True


class VersionedModelMixin(TimestampedModelMixin):
    """
    Mixin that adds versioning to a model for strong consistency.
    
    This mixin adds a version field that is incremented on each save,
    allowing for version-based consistency checking between cache and database.
    """
    version = models.IntegerField(default=1, db_index=True)
    
    def save(self, *args, **kwargs):
        """
        Override save to increment version on each save.
        
        If this is an update (not a new instance), increment the version.
        """
        if self.pk is not None:  # This is an update, not a new instance
            self.version += 1
        super().save(*args, **kwargs)
    
    class Meta:
        abstract = True


class CacheableModelMixin(models.Model):
    """
    Mixin that marks a model as cacheable and provides cache-related utilities.
    
    This mixin adds fields and methods to help with cache management,
    including cache flags, prefixes, and timeouts.
    """
    cache_enabled = True
    redis_cache_prefix = None
    redis_cache_timeout = 3600  # 1 hour default
    redis_cache_permanent = False
    
    class Meta:
        abstract = True
    
    @classmethod
    def get_cache_key(cls, pk):
        """
        Get the cache key for an instance of this model.
        
        Args:
            pk: Primary key of the instance
            
        Returns:
            Cache key string
        """
        prefix = cls.redis_cache_prefix or cls.__name__.lower()
        return f"{prefix}:{pk}"
    
    def get_cache_data(self):
        """
        Get the data to cache for this instance.
        
        Override this method to customize what gets cached.
        
        Returns:
            Dictionary of data to cache
        """
        data = {}
        for field in self._meta.fields:
            field_name = field.name
            value = getattr(self, field_name)
            
            # Handle special field types
            if isinstance(value, models.Model):
                data[field_name] = value.pk
            elif hasattr(value, 'isoformat'):
                data[field_name] = value.isoformat()
            else:
                data[field_name] = value
        
        return data


class ComprehensiveCacheableModelMixin(VersionedModelMixin, CacheableModelMixin):
    """
    Comprehensive mixin for models that need strong cache consistency.
    
    This mixin combines versioning, timestamps, and cache utilities
    for models that require the highest level of cache consistency.
    """
    
    class Meta:
        abstract = True

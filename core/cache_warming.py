"""
Cache warming utilities.

This module provides utilities for warming the cache with frequently accessed data,
ensuring that cache hits are maximized and database load is minimized.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Union, Any

from django.apps import apps
from django.conf import settings
from django.db import models
from django.db.models import Count, Q
from django.utils import timezone

from core.cache import get_cached_data, set_cached_data
from core.redis_permanent import cache_permanently, get_permanent_cache

logger = logging.getLogger(__name__)

# Constants
WARM_CACHE_BATCH_SIZE = getattr(settings, 'WARM_CACHE_BATCH_SIZE', 100)
WARM_CACHE_MAX_INSTANCES = getattr(settings, 'WARM_CACHE_MAX_INSTANCES', 1000)
WARM_CACHE_RECENT_THRESHOLD = getattr(settings, 'WARM_CACHE_RECENT_THRESHOLD', 24)  # hours


def get_cacheable_models():
    """
    Get all models that use Redis caching.
    
    Returns:
        List of model classes
    """
    cacheable_models = []
    
    # Check for models with caching attributes
    for app_config in apps.get_app_configs():
        for model in app_config.get_models():
            # Check if model has Redis caching mixins
            if (hasattr(model, 'cache_enabled') or 
                hasattr(model, 'redis_cache_prefix') or
                hasattr(model, 'redis_cache_timeout')):
                cacheable_models.append(model)
    
    return cacheable_models


def warm_cache_for_model(model_class, strategy='recent', limit=WARM_CACHE_MAX_INSTANCES):
    """
    Warm the cache for a specific model.
    
    Args:
        model_class: Model class to warm cache for
        strategy: Caching strategy ('recent', 'popular', 'all')
        limit: Maximum number of instances to cache
        
    Returns:
        Dictionary with warming statistics
    """
    model_name = model_class.__name__
    
    stats = {
        'model': model_name,
        'strategy': strategy,
        'instances_cached': 0,
        'instances_skipped': 0,
        'errors': 0,
        'elapsed_time': 0,
    }
    
    start_time = time.time()
    
    try:
        # Get instances based on strategy
        if strategy == 'recent':
            # Get recently updated instances
            recent_threshold = timezone.now() - timedelta(hours=WARM_CACHE_RECENT_THRESHOLD)
            
            # Check if model has last_updated field
            if hasattr(model_class, 'last_updated'):
                instances = model_class.objects.filter(
                    last_updated__gte=recent_threshold
                ).order_by('-last_updated')[:limit]
            elif hasattr(model_class, 'updated_at'):
                instances = model_class.objects.filter(
                    updated_at__gte=recent_threshold
                ).order_by('-updated_at')[:limit]
            elif hasattr(model_class, 'created_at'):
                instances = model_class.objects.filter(
                    created_at__gte=recent_threshold
                ).order_by('-created_at')[:limit]
            else:
                # No timestamp field, fall back to all instances
                instances = model_class.objects.all()[:limit]
                
        elif strategy == 'popular':
            # This strategy requires application-specific logic
            # Here's a generic implementation that assumes a 'views' or 'hits' field
            if hasattr(model_class, 'views'):
                instances = model_class.objects.order_by('-views')[:limit]
            elif hasattr(model_class, 'hits'):
                instances = model_class.objects.order_by('-hits')[:limit]
            else:
                # No popularity field, fall back to all instances
                instances = model_class.objects.all()[:limit]
                
        else:  # 'all' strategy
            instances = model_class.objects.all()[:limit]
        
        # Cache instances in batches
        total_instances = len(instances)
        
        for i in range(0, total_instances, WARM_CACHE_BATCH_SIZE):
            batch = instances[i:i+WARM_CACHE_BATCH_SIZE]
            
            for instance in batch:
                try:
                    # Generate cache key
                    cache_key = None
                    if hasattr(model_class, 'get_cache_key'):
                        cache_key = model_class.get_cache_key(instance.pk)
                    else:
                        cache_key = f"{model_name.lower()}:{instance.pk}"
                    
                    # Check if already in cache
                    cached_data = get_cached_data(cache_key)
                    if cached_data is None:
                        # Try permanent cache
                        cached_data = get_permanent_cache(cache_key)
                    
                    if cached_data is not None:
                        stats['instances_skipped'] += 1
                        continue
                    
                    # Get cache data
                    if hasattr(instance, 'get_cache_data'):
                        cache_data = instance.get_cache_data()
                    else:
                        # Create dictionary from model fields
                        cache_data = {}
                        for field in instance._meta.fields:
                            field_name = field.name
                            value = getattr(instance, field_name)
                            
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
                    
                    stats['instances_cached'] += 1
                    
                except Exception as e:
                    logger.exception(f"Error warming cache for {model_name}:{instance.pk}: {str(e)}")
                    stats['errors'] += 1
            
            # Sleep between batches to reduce load
            if i + WARM_CACHE_BATCH_SIZE < total_instances:
                time.sleep(0.1)
        
    except Exception as e:
        logger.exception(f"Error warming cache for {model_name}: {str(e)}")
        stats['errors'] += 1
    
    # Calculate elapsed time
    stats['elapsed_time'] = time.time() - start_time
    
    logger.info(
        f"Completed cache warming for {model_name} ({strategy}): "
        f"{stats['instances_cached']} cached, {stats['instances_skipped']} skipped, "
        f"{stats['errors']} errors in {stats['elapsed_time']:.2f} seconds"
    )
    
    return stats


def warm_all_caches(strategy='recent', limit=WARM_CACHE_MAX_INSTANCES):
    """
    Warm the cache for all cacheable models.
    
    Args:
        strategy: Caching strategy ('recent', 'popular', 'all')
        limit: Maximum number of instances to cache per model
        
    Returns:
        Dictionary with warming statistics
    """
    logger.info(f"Starting cache warming for all models ({strategy})")
    
    stats = {
        'models': {},
        'total_models': 0,
        'total_instances_cached': 0,
        'total_instances_skipped': 0,
        'total_errors': 0,
        'elapsed_time': 0,
    }
    
    start_time = time.time()
    
    # Get all cacheable models
    cacheable_models = get_cacheable_models()
    
    stats['total_models'] = len(cacheable_models)
    
    # Warm cache for each model
    for model in cacheable_models:
        model_stats = warm_cache_for_model(model, strategy=strategy, limit=limit)
        
        # Add to overall stats
        stats['models'][model.__name__] = model_stats
        stats['total_instances_cached'] += model_stats['instances_cached']
        stats['total_instances_skipped'] += model_stats['instances_skipped']
        stats['total_errors'] += model_stats['errors']
    
    # Calculate elapsed time
    stats['elapsed_time'] = time.time() - start_time
    
    logger.info(
        f"Completed cache warming for all models ({strategy}): "
        f"{stats['total_models']} models, {stats['total_instances_cached']} instances cached, "
        f"{stats['total_instances_skipped']} instances skipped, "
        f"{stats['total_errors']} errors in {stats['elapsed_time']:.2f} seconds"
    )
    
    return stats


def intelligent_cache_warming():
    """
    Intelligently warm the cache based on access patterns.
    
    This function analyzes cache access patterns and warms the cache
    for frequently accessed models and instances.
    
    Returns:
        Dictionary with warming statistics
    """
    # This would require tracking cache access patterns
    # For now, we'll use a simple implementation that warms recent items
    return warm_all_caches(strategy='recent')


# For Django Q
def scheduled_cache_warming():
    """Scheduled task to warm the cache."""
    return intelligent_cache_warming()


# For Celery
try:
    from celery import shared_task
    
    @shared_task(name="warm_cache")
    def celery_cache_warming():
        """Celery task to warm the cache."""
        return intelligent_cache_warming()
        
except ImportError:
    pass

"""
Scheduled tasks for cache consistency.

This module provides scheduled tasks for checking and maintaining cache consistency.
"""

import logging
import random
from typing import Dict, List, Optional

from django.apps import apps
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from godmode.cache_sync import check_cache_consistency, reconcile_cache_for_model

logger = logging.getLogger(__name__)

# Constants
CONSISTENCY_THRESHOLD = getattr(settings, 'CACHE_CONSISTENCY_THRESHOLD', 0.9)  # 90% consistency required
AUTO_RECONCILE_THRESHOLD = getattr(settings, 'CACHE_AUTO_RECONCILE_THRESHOLD', 0.9)  # Auto-reconcile if below 70%
SAMPLE_SIZE = getattr(settings, 'CACHE_CONSISTENCY_SAMPLE_SIZE', 100)  # Check 100 instances
CACHE_MODELS_KEY = 'cache_consistency:models'
CONSISTENCY_STATS_KEY_PREFIX = 'cache_consistency:stats:'


def get_cacheable_models() -> List:
    """Get all models that use Redis caching."""
    # Try to get from cache
    cached_models = cache.get(CACHE_MODELS_KEY)
    if cached_models:
        return cached_models
        
    # Not in cache, find cacheable models
    cacheable_models = []
    
    # Check for models with Redis caching mixins
    for app_config in apps.get_app_configs():
        for model in app_config.get_models():
            # Check if model has Redis caching mixins
            if (hasattr(model, 'cache_enabled') or 
                hasattr(model, 'redis_cache_prefix') or
                hasattr(model, 'redis_cache_timeout')):
                cacheable_models.append(model)
    
    # Cache the result
    cache.set(CACHE_MODELS_KEY, cacheable_models, 3600)  # Cache for 1 hour
    
    return cacheable_models


def check_model_consistency(model) -> Dict:
    """
    Check cache consistency for a model.
    
    Args:
        model: Django model class
        
    Returns:
        Dictionary with consistency statistics
    """
    model_name = model.__name__
    
    try:
        logger.info(f"Checking cache consistency for {model_name}")
        stats = check_cache_consistency(model, sample_size=SAMPLE_SIZE)
        
        # Calculate consistency ratio
        total = stats['total']
        if total > 0:
            consistency_ratio = stats['consistent'] / total
        else:
            consistency_ratio = 1.0
            
        # Store stats
        stats_key = f"{CONSISTENCY_STATS_KEY_PREFIX}{model_name}"
        cache.set(stats_key, {
            'timestamp': timezone.now().isoformat(),
            'stats': stats,
            'consistency_ratio': consistency_ratio,
        }, 86400)  # Cache for 24 hours
        
        logger.info(f"Cache consistency for {model_name}: {consistency_ratio:.2%}")
        
        # Check if we need to reconcile
        if consistency_ratio < AUTO_RECONCILE_THRESHOLD:
            logger.warning(
                f"Cache consistency for {model_name} is below threshold "
                f"({consistency_ratio:.2%} < {AUTO_RECONCILE_THRESHOLD:.2%}). "
                f"Triggering automatic reconciliation."
            )
            
            # Trigger reconciliation
            reconcile_cache_for_model(model, force=False, batch_size=100, max_instances=1000)
            
        elif consistency_ratio < CONSISTENCY_THRESHOLD:
            logger.warning(
                f"Cache consistency for {model_name} is below threshold "
                f"({consistency_ratio:.2%} < {CONSISTENCY_THRESHOLD:.2%})."
            )
            
        return {
            'model': model_name,
            'stats': stats,
            'consistency_ratio': consistency_ratio,
            'reconciled': consistency_ratio < AUTO_RECONCILE_THRESHOLD,
        }
            
    except Exception as e:
        logger.exception(f"Error checking cache consistency for {model_name}: {str(e)}")
        return {
            'model': model_name,
            'error': str(e),
        }


def check_all_models_consistency() -> Dict:
    """
    Check cache consistency for all cacheable models.
    
    Returns:
        Dictionary with consistency statistics for all models
    """
    models = get_cacheable_models()
    
    results = {
        'models': {},
        'total_models': len(models),
        'models_checked': 0,
        'models_reconciled': 0,
        'average_consistency': 0,
    }
    
    total_consistency = 0
    
    for model in models:
        model_result = check_model_consistency(model)
        
        if 'consistency_ratio' in model_result:
            total_consistency += model_result['consistency_ratio']
            
            if model_result.get('reconciled', False):
                results['models_reconciled'] += 1
                
        results['models'][model.__name__] = model_result
        results['models_checked'] += 1
    
    if results['models_checked'] > 0:
        results['average_consistency'] = total_consistency / results['models_checked']
    
    logger.info(
        f"Completed consistency check for {results['models_checked']} models. "
        f"Average consistency: {results['average_consistency']:.2%}. "
        f"Models reconciled: {results['models_reconciled']}."
    )
    
    return results


# For Django Q
def scheduled_consistency_check():
    """Scheduled task to check cache consistency for all models."""
    return check_all_models_consistency()


# For Celery
try:
    from celery import shared_task
    
    @shared_task(name="check_cache_consistency")
    def celery_consistency_check():
        """Celery task to check cache consistency for all models."""
        return check_all_models_consistency()
        
except ImportError:
    pass

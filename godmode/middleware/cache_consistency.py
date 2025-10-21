"""
Cache consistency middleware.

This middleware automatically detects cache inconsistencies during normal application
operation and triggers reconciliation when needed.
"""

import logging
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Union, Any

from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from core.cache import get_cached_data
from core.redis_permanent import get_permanent_cache
from godmode.cache_sync import check_cache_consistency, reconcile_cache_for_model

logger = logging.getLogger(__name__)

# Constants
CONSISTENCY_CHECK_PROBABILITY = getattr(settings, 'CACHE_CONSISTENCY_CHECK_PROBABILITY', 0.01)  # 1% chance
CONSISTENCY_CHECK_INTERVAL = getattr(settings, 'CACHE_CONSISTENCY_CHECK_INTERVAL', 3600)  # 1 hour
CONSISTENCY_THRESHOLD = getattr(settings, 'CACHE_CONSISTENCY_THRESHOLD', 0.9)  # 90% consistency required
AUTO_RECONCILE_THRESHOLD = getattr(settings, 'CACHE_AUTO_RECONCILE_THRESHOLD', 0.7)  # Auto-reconcile if below 70%
SAMPLE_SIZE = getattr(settings, 'CACHE_CONSISTENCY_SAMPLE_SIZE', 50)  # Check 50 instances
CACHE_MODELS_KEY = 'cache_consistency:models'
LAST_CHECK_KEY_PREFIX = 'cache_consistency:last_check:'
CONSISTENCY_STATS_KEY_PREFIX = 'cache_consistency:stats:'


class CacheConsistencyMiddleware:
    """
    Middleware that automatically detects cache inconsistencies and triggers reconciliation.
    
    This middleware randomly samples cached models during normal application operation
    to detect inconsistencies. When inconsistencies exceed a threshold, it automatically
    triggers reconciliation.
    """
    
    def __init__(self, get_response):
        """Initialize the middleware."""
        self.get_response = get_response
        self.cacheable_models = self._get_cacheable_models()
        
    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Process the request and check cache consistency."""
        # Process the request first
        response = self.get_response(request)
        
        # Only check for authenticated users to avoid performance impact on public pages
        if not request.user.is_authenticated:
            return response
            
        # Randomly decide whether to check consistency
        if random.random() < CONSISTENCY_CHECK_PROBABILITY:
            self._check_consistency(request)
            
        return response
    
    def _get_cacheable_models(self) -> List:
        """Get all models that use Redis caching."""
        # Try to get from cache
        cached_models = cache.get(CACHE_MODELS_KEY)
        if cached_models:
            return cached_models
            
        # Not in cache, find cacheable models
        from django.apps import apps
        
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
    
    def _should_check_model(self, model) -> bool:
        """Determine if a model should be checked for consistency."""
        model_name = model.__name__
        
        # Check when the model was last checked
        last_check_key = f"{LAST_CHECK_KEY_PREFIX}{model_name}"
        last_check = cache.get(last_check_key)
        
        if last_check:
            # Don't check if it was checked recently
            last_check_time = datetime.fromisoformat(last_check)
            if timezone.now() - last_check_time < timedelta(seconds=CONSISTENCY_CHECK_INTERVAL):
                return False
        
        return True
    
    def _check_consistency(self, request: HttpRequest) -> None:
        """Check cache consistency for a random model."""
        if not self.cacheable_models:
            return
            
        # Select a random model
        model = random.choice(self.cacheable_models)
        model_name = model.__name__
        
        # Check if we should check this model
        if not self._should_check_model(model):
            return
            
        # Update last check time
        last_check_key = f"{LAST_CHECK_KEY_PREFIX}{model_name}"
        cache.set(last_check_key, timezone.now().isoformat(), CONSISTENCY_CHECK_INTERVAL * 2)
        
        # Check consistency
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
            }, CONSISTENCY_CHECK_INTERVAL * 2)
            
            logger.info(f"Cache consistency for {model_name}: {consistency_ratio:.2%}")
            
            # Check if we need to reconcile
            if consistency_ratio < AUTO_RECONCILE_THRESHOLD:
                logger.warning(
                    f"Cache consistency for {model_name} is below threshold "
                    f"({consistency_ratio:.2%} < {AUTO_RECONCILE_THRESHOLD:.2%}). "
                    f"Triggering automatic reconciliation."
                )
                
                # Trigger reconciliation in a background task
                self._trigger_reconciliation(model)
            elif consistency_ratio < CONSISTENCY_THRESHOLD:
                logger.warning(
                    f"Cache consistency for {model_name} is below threshold "
                    f"({consistency_ratio:.2%} < {CONSISTENCY_THRESHOLD:.2%})."
                )
                
        except Exception as e:
            logger.exception(f"Error checking cache consistency for {model_name}: {str(e)}")
    
    def _trigger_reconciliation(self, model) -> None:
        """Trigger cache reconciliation for a model."""
        try:
            # Use Django Q for background processing if available
            try:
                from django_q.tasks import async_task
                async_task(
                    'godmode.cache_sync.reconcile_cache_for_model',
                    model,
                    force=False,
                    batch_size=100,
                    max_instances=1000,
                    task_name=f"reconcile_cache_{model.__name__}",
                    group='cache_reconciliation'
                )
                logger.info(f"Queued cache reconciliation for {model.__name__} using Django Q")
                return
            except ImportError:
                pass
                
            # Use Celery if available
            try:
                from celery import shared_task
                
                @shared_task(name=f"reconcile_cache_{model.__name__}")
                def reconcile_task():
                    reconcile_cache_for_model(model, force=False, batch_size=100, max_instances=1000)
                
                reconcile_task.delay()
                logger.info(f"Queued cache reconciliation for {model.__name__} using Celery")
                return
            except ImportError:
                pass
                
            # Fall back to direct execution (not recommended for production)
            logger.warning(
                f"No task queue available. Running cache reconciliation for {model.__name__} directly. "
                f"This may impact performance."
            )
            reconcile_cache_for_model(model, force=False, batch_size=100, max_instances=1000)
            
        except Exception as e:
            logger.exception(f"Error triggering cache reconciliation for {model.__name__}: {str(e)}")

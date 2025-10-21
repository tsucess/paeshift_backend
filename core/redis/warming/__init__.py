"""
Redis cache warming module.

This module provides utilities for warming the Redis cache with frequently
accessed data, improving application performance.
"""

import concurrent.futures
import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Type, Union

from django.apps import apps
from django.db import models
from django.utils import timezone

from core.redis.client import redis_client
from core.redis.models import cache_model
from core.redis.settings import CACHE_ENABLED
from core.redis.utils import set_cached_data

# Set up logging
logger = logging.getLogger(__name__)

# Constants
WARM_BATCH_SIZE = 100
WARM_SLEEP_BETWEEN_BATCHES = 0.1
WARM_MAX_WORKERS = 4
WARM_TIMEOUT = 3600  # 1 hour


def warm_model_cache(
    model_class: Type[models.Model],
    batch_size: int = WARM_BATCH_SIZE,
    sleep_between_batches: float = WARM_SLEEP_BETWEEN_BATCHES,
    filter_kwargs: Optional[Dict] = None,
    order_by: Optional[List[str]] = None,
    limit: Optional[int] = None,
    permanent: bool = False,
) -> Tuple[int, int]:
    """
    Warm the cache for a model by caching all instances.
    Args:
        model_class: The model class to warm
        batch_size: Number of instances to cache in each batch
        sleep_between_batches: Sleep time between batches to reduce load
        filter_kwargs: Optional filter criteria
        order_by: Optional ordering
        limit: Optional limit on number of instances to cache
        permanent: Whether to cache permanently
    Returns:
        Tuple of (total_instances, cached_instances)
    """
    if not CACHE_ENABLED:
        logger.warning("Cache is disabled, skipping cache warming")
        return 0, 0

    start_time = time.time()
    logger.info(f"Starting cache warming for {model_class.__name__}")

    # Build queryset
    queryset = model_class.objects.all()

    # Apply filters
    if filter_kwargs:
        queryset = queryset.filter(**filter_kwargs)

    # Apply ordering
    if order_by:
        queryset = queryset.order_by(*order_by)

    # Apply limit
    if limit:
        queryset = queryset[:limit]

    # Get total count
    total_instances = queryset.count()
    logger.info(f"Found {total_instances} instances of {model_class.__name__} to cache")

    # Cache in batches
    cached_instances = 0
    for i in range(0, total_instances, batch_size):
        batch = queryset[i:i + batch_size]
        batch_start_time = time.time()

        for instance in batch:
            try:
                # Cache the instance
                cache_model(instance)
                cached_instances += 1
            except Exception as e:
                logger.error(f"Error caching {model_class.__name__} instance {instance.pk}: {str(e)}")

        # Log progress
        batch_end_time = time.time()
        batch_duration = batch_end_time - batch_start_time
        logger.info(
            f"Cached {len(batch)} instances of {model_class.__name__} "
            f"in {batch_duration:.2f}s ({cached_instances}/{total_instances})"
        )

        # Sleep between batches to reduce load
        if sleep_between_batches > 0 and i + batch_size < total_instances:
            time.sleep(sleep_between_batches)

    # Log completion
    end_time = time.time()
    duration = end_time - start_time
    logger.info(
        f"Completed cache warming for {model_class.__name__}: "
        f"{cached_instances}/{total_instances} instances cached in {duration:.2f}s"
    )

    return total_instances, cached_instances


def warm_critical_models() -> Dict[str, Tuple[int, int]]:
    """
    Warm the cache for critical models.
    Returns:
        Dictionary mapping model names to (total_instances, cached_instances)
    """
    if not CACHE_ENABLED:
        logger.warning("Cache is disabled, skipping cache warming")
        return {}

    start_time = time.time()
    logger.info("Starting cache warming for critical models")

    # Define critical models
    critical_models = [
        # User model - cache active users first
        {
            "model": "auth.User",
            "filter_kwargs": {"is_active": True},
            "order_by": ["-last_login"],
            "limit": 1000,
        },
        # Profile model - if it exists
        {
            "model": "accounts.Profile",
            "order_by": ["-updated_at"],
            "limit": 1000,
        },
        # Job model - active jobs first
        {
            "model": "jobs.Job",
            "filter_kwargs": {"is_active": True},
            "order_by": ["-created_at"],
            "limit": 500,
        },
        # JobIndustry model - all industries
        {
            "model": "jobs.JobIndustry",
            "permanent": True,
        },
        # JobSubCategory model - all subcategories
        {
            "model": "jobs.JobSubCategory",
            "permanent": True,
        },
    ]

    results = {}

    # Warm each model
    for model_config in critical_models:
        model_name = model_config.pop("model")
        try:
            # Get model class
            model_class = apps.get_model(model_name)

            # Warm the model cache
            total, cached = warm_model_cache(model_class, **model_config)
            results[model_name] = (total, cached)
        except Exception as e:
            logger.error(f"Error warming cache for model {model_name}: {str(e)}")
            results[model_name] = (0, 0)

    # Log completion
    end_time = time.time()
    duration = end_time - start_time
    logger.info(f"Completed cache warming for critical models in {duration:.2f}s")

    return results


def warm_api_endpoints() -> Dict[str, bool]:
    """
    Warm the cache for frequently accessed API endpoints.
    Returns:
        Dictionary mapping endpoint names to success status
    """
    if not CACHE_ENABLED:
        logger.warning("Cache is disabled, skipping cache warming")
        return {}

    start_time = time.time()
    logger.info("Starting cache warming for API endpoints")

    # Define endpoints to warm
    endpoints = [
        {
            "name": "job_categories",
            "url": "/api/v1/jobs/categories/",
            "params": {},
            "timeout": 86400,  # 24 hours
        },
        {
            "name": "job_industries",
            "url": "/api/v1/jobs/industries/",
            "params": {},
            "timeout": 86400,  # 24 hours
        },
        {
            "name": "job_subcategories",
            "url": "/api/v1/jobs/subcategories/",
            "params": {},
            "timeout": 86400,  # 24 hours
        },
        {
            "name": "featured_jobs",
            "url": "/api/v1/jobs/featured/",
            "params": {},
            "timeout": 3600,  # 1 hour
        },
    ]

    results = {}

    # Warm each endpoint
    for endpoint in endpoints:
        try:
            # Generate cache key
            cache_key = f"api:{endpoint['url']}"
            if endpoint.get("params"):
                cache_key = f"{cache_key}:{endpoint['params']}"

            # TODO: Implement actual API call to get data
            # For now, just log that we would warm this endpoint
            logger.info(f"Would warm endpoint {endpoint['name']} at {endpoint['url']}")
            results[endpoint["name"]] = True
        except Exception as e:
            logger.error(f"Error warming cache for endpoint {endpoint['name']}: {str(e)}")
            results[endpoint["name"]] = False

    # Log completion
    end_time = time.time()
    duration = end_time - start_time
    logger.info(f"Completed cache warming for API endpoints in {duration:.2f}s")

    return results


def warm_cache() -> Dict:
    """
    Warm the entire cache.
    Returns:
        Dictionary with warming results
    """
    start_time = time.time()
    logger.info("Starting cache warming")

    # Warm models
    model_results = warm_frequently_accessed_models()

    # Warm API endpoints
    endpoint_results = warm_api_endpoints()

    elapsed = time.time() - start_time
    logger.info(f"Completed cache warming in {elapsed:.2f} seconds")

    return {
        "models": model_results,
        "endpoints": endpoint_results,
        "elapsed_seconds": elapsed,
        "timestamp": timezone.now().isoformat(),
    }


def warm_frequently_accessed_models() -> Dict[str, Tuple[int, int]]:
    """
    Warm the cache for frequently accessed models.
    Returns:
        Dictionary mapping model names to (total_instances, cached_instances)
    """
    if not CACHE_ENABLED:
        logger.warning("Cache is disabled, skipping cache warming")
        return {}

    start_time = time.time()
    logger.info("Starting cache warming for frequently accessed models")

    # Define models to warm
    models_to_warm = [
        # User model
        {
            "model": "auth.User",
            "filter_kwargs": {"is_active": True},
            "limit": 1000,
        },
        # Profile model
        {
            "model": "accounts.Profile",
            "limit": 1000,
        },
        # Job model
        {
            "model": "jobs.Job",
            "filter_kwargs": {"is_active": True},
            "limit": 500,
        },
        # Application model
        {
            "model": "jobs.JobApplication",
            "limit": 500,
        },
        # Review model
        {
            "model": "reviews.Review",
            "limit": 500,
        },
        # Notification model
        {
            "model": "notifications.Notification",
            "limit": 500,
        },
    ]

    results = {}

    # Use ThreadPoolExecutor for parallel warming
    with concurrent.futures.ThreadPoolExecutor(max_workers=WARM_MAX_WORKERS) as executor:
        # Submit warming tasks
        future_to_model = {}
        for model_config in models_to_warm:
            model_name = model_config.pop("model")
            try:
                # Get model class
                model_class = apps.get_model(model_name)

                # Submit warming task
                future = executor.submit(warm_model_cache, model_class, **model_config)
                future_to_model[future] = model_name
            except Exception as e:
                logger.error(f"Error submitting warming task for model {model_name}: {str(e)}")
                results[model_name] = (0, 0)

        # Get results
        for future in concurrent.futures.as_completed(future_to_model):
            model_name = future_to_model[future]
            try:
                total, cached = future.result()
                results[model_name] = (total, cached)
            except Exception as e:
                logger.error(f"Error warming cache for model {model_name}: {str(e)}")
                results[model_name] = (0, 0)

    # Log completion
    end_time = time.time()
    duration = end_time - start_time
    logger.info(f"Completed cache warming for frequently accessed models in {duration:.2f}s")

    return results


def setup_cache_warming_schedule():
    """
    Set up scheduled cache warming.
    """
    if not CACHE_ENABLED:
        logger.warning("Cache is disabled, skipping cache warming schedule setup")
        return

    logger.info("Setting up cache warming schedule")

    # Schedule with Django Q if available
    try:
        from django_q.tasks import schedule
        from django_q.models import Schedule

        # Schedule full warming
        schedule(
            "core.redis.warming.warm_cache",
            name="Warm Redis Cache (Full)",
            schedule_type=Schedule.CRON,
            cron="0 */6 * * *",  # Every 6 hours
        )

        # Schedule critical warming
        schedule(
            "core.redis.warming.warm_critical_models",
            name="Warm Redis Cache (Critical)",
            schedule_type=Schedule.CRON,
            cron="0 */2 * * *",  # Every 2 hours
        )

        logger.info("Cache warming schedule set up successfully")
    except ImportError:
        logger.warning("Django Q not available, skipping cache warming schedule setup")
    except Exception as e:
        logger.error(f"Error setting up cache warming schedule: {str(e)}")

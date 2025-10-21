"""
Redis cache warming module.

This module provides comprehensive tools for warming the Redis cache with frequently accessed data,
scheduling regular warming, and handling cold starts.

This is a consolidated module that combines functionality from redis_warming.py and cache_warming.py
to eliminate redundancy.
"""

import importlib
import inspect
import logging
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Set, Tuple, Type, Union

from django.apps import apps
from django.conf import settings
from django.db import models
from django.db.models import Count, Q
from django.urls import URLPattern, URLResolver, get_resolver
from django.utils import timezone

from core.cache import (
    cache_model_instance,
    get_cached_model_instance,
    CACHE_PREFIXES,
    CACHE_TIMEOUTS,
    redis_client,
)
from core.redis_model_mixin import RedisCachedModelMixin
from core.redis_permanent import cache_permanently
from core.redis_settings import CACHE_ENABLED
from core.redis_sync import RedisSyncMixin
from core.redis_warming_settings import (
    CACHE_WARM_BATCH_SIZE,
    CACHE_WARM_SLEEP_BETWEEN_BATCHES,
    CACHE_WARM_PRIORITY_MODELS,
    CACHE_WARM_PRIORITY_ENDPOINTS,
    CACHE_WARM_MAX_WORKERS,
    CACHE_WARM_TIMEOUT,
    CACHE_WARM_CRITICAL_MODELS,
    CACHE_WARM_STATIC_MODELS,
    CACHE_WARM_SCHEDULES,
    CACHE_WARM_ON_STARTUP,
    CACHE_WARM_ON_IMPORT,
)

logger = logging.getLogger(__name__)

# Constants
WARM_BATCH_SIZE = CACHE_WARM_BATCH_SIZE
WARM_SLEEP_BETWEEN_BATCHES = CACHE_WARM_SLEEP_BETWEEN_BATCHES
WARM_PRIORITY_MODELS = CACHE_WARM_PRIORITY_MODELS
WARM_PRIORITY_ENDPOINTS = CACHE_WARM_PRIORITY_ENDPOINTS
WARM_MAX_WORKERS = CACHE_WARM_MAX_WORKERS
WARM_TIMEOUT = CACHE_WARM_TIMEOUT


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
        logger.warning(f"Cache warming skipped for {model_class.__name__}: Cache is disabled")
        return 0, 0

    start_time = time.time()
    logger.info(f"Starting cache warming for {model_class.__name__}")

    # Check if model uses RedisCachedModelMixin or RedisSyncMixin
    uses_cache_mixin = issubclass(model_class, RedisCachedModelMixin)
    uses_sync_mixin = issubclass(model_class, RedisSyncMixin)

    if not (uses_cache_mixin or uses_sync_mixin):
        logger.warning(
            f"Model {model_class.__name__} does not use RedisCachedModelMixin or RedisSyncMixin"
        )

    # Build queryset
    queryset = model_class.objects.all()

    # Apply filters if provided
    if filter_kwargs:
        queryset = queryset.filter(**filter_kwargs)

    # Apply ordering if provided
    if order_by:
        queryset = queryset.order_by(*order_by)

    # Apply limit if provided
    if limit:
        queryset = queryset[:limit]

    # Get total count
    total_instances = queryset.count()

    # Cache in batches
    cached_instances = 0
    for i in range(0, total_instances, batch_size):
        batch = queryset[i:i + batch_size]
        for instance in batch:
            try:
                if uses_cache_mixin:
                    # Use the model's cache method
                    instance.cache()
                    cached_instances += 1
                elif uses_sync_mixin:
                    # Use the model's sync_to_redis method
                    instance.sync_to_redis()
                    cached_instances += 1
                else:
                    # Use generic caching
                    model_type = model_class.__name__.lower()
                    # Convert instance to dict
                    if hasattr(instance, "to_dict"):
                        data = instance.to_dict()
                    else:
                        # Basic serialization
                        data = {
                            "id": instance.pk,
                            "model": model_type,
                        }
                        # Add common fields
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
                    # Cache the instance
                    if permanent:
                        cache_permanently(data, f"{model_type}:{instance.pk}")
                    else:
                        timeout = CACHE_TIMEOUTS.get(model_type, CACHE_TIMEOUTS["default"])
                        cache_model_instance(model_type, instance.pk, data, timeout)

                    cached_instances += 1

            except Exception as e:
                logger.error(
                    f"Error caching {model_class.__name__} instance {instance.pk}: {str(e)}"
                )

        # Sleep between batches to reduce load
        if sleep_between_batches > 0 and i + batch_size < total_instances:
            time.sleep(sleep_between_batches)

    elapsed = time.time() - start_time
    logger.info(
        f"Completed cache warming for {model_class.__name__}: "
        f"{cached_instances}/{total_instances} instances cached in {elapsed:.2f} seconds"
    )
    return total_instances, cached_instances


def warm_frequently_accessed_models() -> Dict[str, Tuple[int, int]]:
    """
    Warm the cache for frequently accessed models.
    Returns:
        Dictionary mapping model names to (total_instances, cached_instances)
    """
    results = {}

    # Import models
    from django.apps import apps
    from django.contrib.auth import get_user_model

    User = get_user_model()

    # Define models to warm with their parameters
    models_to_warm = [
        # User model - cache active users first
        {
            "model": User,
            "filter_kwargs": {"is_active": True},
            "order_by": ["-last_login"],
            "limit": 1000,
        },
        # Profile model - if it exists
        {
            "model": apps.get_model("accounts", "Profile"),
            "order_by": ["-updated_at"],
            "limit": 1000,
        },
        # Job model - active jobs first
        {
            "model": apps.get_model("jobs", "Job"),
            "filter_kwargs": {"is_active": True},
            "order_by": ["-created_at"],
            "limit": 500,
        },
        # JobIndustry model - all industries
        {
            "model": apps.get_model("jobs", "JobIndustry"),
            "permanent": True,
        },
        # JobSubCategory model - all subcategories
        {
            "model": apps.get_model("jobs", "JobSubCategory"),
            "permanent": True,
        },
        # Application model - recent applications
        {
            "model": apps.get_model("jobs", "Application"),
            "order_by": ["-created_at"],
            "limit": 500,
        },
        # SavedJob model - recent saved jobs
        {
            "model": apps.get_model("jobs", "SavedJob"),
            "order_by": ["-saved_at"],
            "limit": 500,
        },
        # UserLocation model - recent locations
        {
            "model": apps.get_model("userlocation", "UserLocation"),
            "order_by": ["-last_updated"],
            "limit": 500,
        },
    ]
    # Add priority models from settings
    for model_path in WARM_PRIORITY_MODELS:
        try:
            app_label, model_name = model_path.split(".")
            model_class = apps.get_model(app_label, model_name)

            # Check if model is already in the list
            if not any(m["model"] == model_class for m in models_to_warm):
                models_to_warm.append({"model": model_class})

        except Exception as e:
            logger.error(f"Error loading priority model {model_path}: {str(e)}")

    # Warm each model
    for model_config in models_to_warm:
        model_class = model_config.pop("model")
        try:
            total, cached = warm_model_cache(model_class, **model_config)
            results[model_class.__name__] = (total, cached)
        except Exception as e:
            logger.error(f"Error warming cache for {model_class.__name__}: {str(e)}")
            results[model_class.__name__] = (0, 0)
    return results


def warm_api_endpoints() -> Dict[str, bool]:
    """
    Warm the cache for frequently accessed API endpoints.
    Returns:
        Dictionary mapping endpoint names to success status
    """
    results = {}

    # Import Django's test client
    from django.test import Client

    # Create a client
    client = Client()

    # Define endpoints to warm
    endpoints = [
        # Jobs endpoints
        {"name": "all_jobs", "path": "/api/jobs/alljobs/", "method": "get"},
        {"name": "job_industries", "path": "/api/jobs/job-industries/", "method": "get"},
        {"name": "job_subcategories", "path": "/api/jobs/job-subcategories/", "method": "get"},
        {"name": "saved_jobs", "path": "/api/jobs/saved-jobs/1", "method": "get"},  # Example user ID

        # User endpoints
        {"name": "active_users", "path": "/api/accounts/active-users/15/", "method": "put"},
        {"name": "last_seen", "path": "/api/accounts/users/1/last-seen/", "method": "get"},  # Example user ID
        {"name": "whoami", "path": "/api/accounts/whoami/1", "method": "get"},  # Example user ID

        # Rating endpoints
        {"name": "user_ratings", "path": "/api/rating/ratings/1", "method": "get"},  # Example user ID

        # Payment endpoints
        {"name": "user_payments", "path": "/api/payments/users/1/payments", "method": "get"},  # Example user ID
    ]

    # Add priority endpoints from settings
    for endpoint_config in WARM_PRIORITY_ENDPOINTS:
        if isinstance(endpoint_config, dict) and "name" in endpoint_config and "path" in endpoint_config:
            # Check if endpoint is already in the list
            if not any(e["name"] == endpoint_config["name"] for e in endpoints):
                endpoints.append(endpoint_config)

    # Warm each endpoint
    for endpoint in endpoints:
        try:
            name = endpoint["name"]
            path = endpoint["path"]
            method = endpoint["method"]

            logger.info(f"Warming cache for endpoint: {name} ({path})")

            # Make the request
            if method == "get":
                response = client.get(path)
            elif method == "post":
                response = client.post(path, {})
            elif method == "put":
                response = client.put(path, {})
            else:
                logger.error(f"Unsupported method: {method}")
                results[name] = False
                continue
            # Check if the request was successful
            if response.status_code == 200:
                logger.info(f"Successfully warmed cache for endpoint: {name}")
                results[name] = True
            else:
                logger.warning(
                    f"Failed to warm cache for endpoint: {name} "
                    f"(status code: {response.status_code})"
                )
                results[name] = False

        except Exception as e:
            logger.error(f"Error warming cache for endpoint {endpoint['name']}: {str(e)}")
            results[endpoint["name"]] = False

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


def warm_critical_models():
    """
    Warm only the most critical models that change frequently.

    This is a lightweight version of warm_cache() for more frequent execution.
    Uses the CACHE_WARM_CRITICAL_MODELS setting to determine which models to warm.
    """
    if not CACHE_ENABLED:
        logger.warning("Critical cache warming skipped: Cache is disabled")
        return

    start_time = time.time()
    logger.info("Starting critical cache warming")

    results = {}

    # Import models
    from django.apps import apps
    from django.contrib.auth import get_user_model

    User = get_user_model()

    # Get critical models from settings
    critical_models = []
    for model_config in CACHE_WARM_CRITICAL_MODELS:
        try:
            model_name = model_config["model"]
            app_label, model_name = model_name.split(".")

            # Get model class
            if model_name.lower() == "customuser":
                model_class = User
            else:
                model_class = apps.get_model(app_label, model_name)

            # Create config with model class
            config = model_config.copy()
            config["model"] = model_class

            critical_models.append(config)
        except Exception as e:
            logger.error(f"Error loading critical model {model_config.get('model', 'unknown')}: {str(e)}")

    # Warm each critical model
    for model_config in critical_models:
        model_class = model_config.pop("model")
        try:
            total, cached = warm_model_cache(model_class, **model_config)
            results[model_class.__name__] = (total, cached)
        except Exception as e:
            logger.error(f"Error warming cache for critical model {model_class.__name__}: {str(e)}")
            results[model_class.__name__] = (0, 0)

    elapsed = time.time() - start_time
    logger.info(f"Completed critical cache warming in {elapsed:.2f} seconds")

    return {
        "models": results,
        "elapsed_seconds": elapsed,
        "timestamp": timezone.now().isoformat(),
    }


def warm_static_models():
    """
    Warm static models that rarely change.

    This function warms the cache for static data like industries, categories, etc.
    Uses the CACHE_WARM_STATIC_MODELS setting to determine which models to warm.
    """
    if not CACHE_ENABLED:
        logger.warning("Static cache warming skipped: Cache is disabled")
        return

    start_time = time.time()
    logger.info("Starting static cache warming")

    results = {}

    # Import models
    from django.apps import apps
    from django.contrib.auth import get_user_model

    User = get_user_model()

    # Get static models from settings
    static_models = []
    for model_config in CACHE_WARM_STATIC_MODELS:
        try:
            model_name = model_config["model"]
            app_label, model_name = model_name.split(".")

            # Get model class
            if model_name.lower() == "customuser":
                model_class = User
            else:
                model_class = apps.get_model(app_label, model_name)

            # Create config with model class
            config = model_config.copy()
            config["model"] = model_class

            static_models.append(config)
        except Exception as e:
            logger.error(f"Error loading static model {model_config.get('model', 'unknown')}: {str(e)}")

    # Warm each static model
    for model_config in static_models:
        model_class = model_config.pop("model")
        try:
            total, cached = warm_model_cache(model_class, **model_config)
            results[model_class.__name__] = (total, cached)
        except Exception as e:
            logger.error(f"Error warming cache for static model {model_class.__name__}: {str(e)}")
            results[model_class.__name__] = (0, 0)

    elapsed = time.time() - start_time
    logger.info(f"Completed static cache warming in {elapsed:.2f} seconds")

    return {
        "models": results,
        "elapsed_seconds": elapsed,
        "timestamp": timezone.now().isoformat(),
    }


def schedule_cache_warming():
    """
    Schedule cache warming tasks based on configured schedules.

    Uses the CACHE_WARM_SCHEDULES setting to determine the schedule for each type of warming.
    """
    if not CACHE_ENABLED:
        logger.warning("Cache warming scheduling skipped: Cache is disabled")
        return

    try:
        # Schedule with Celery if available
        try:
            from celery import current_app

            # Define tasks
            @current_app.task(name="core.redis_warming.warm_cache_task")
            def warm_cache_task():
                warm_cache()

            @current_app.task(name="core.redis_warming.warm_critical_models_task")
            def warm_critical_models_task():
                warm_critical_models()

            @current_app.task(name="core.redis_warming.warm_static_models_task")
            def warm_static_models_task():
                warm_static_models()

            @current_app.task(name="core.redis_warming.check_consistency_task")
            def check_consistency_task():
                from core.redis_consistency import check_frequently_accessed_models_consistency
                check_frequently_accessed_models_consistency()

            # Schedule tasks based on configured schedules
            beat_schedule = {
                # Full cache warming
                "warm-cache-full": {
                    "task": "core.redis_warming.warm_cache_task",
                    "schedule": CACHE_WARM_SCHEDULES["full"],
                    "options": {"expires": CACHE_WARM_SCHEDULES["full"] * 1.5},
                },
                # Critical models warming
                "warm-cache-critical": {
                    "task": "core.redis_warming.warm_critical_models_task",
                    "schedule": CACHE_WARM_SCHEDULES["critical"],
                    "options": {"expires": CACHE_WARM_SCHEDULES["critical"] * 1.5},
                },
                # Static models warming
                "warm-cache-static": {
                    "task": "core.redis_warming.warm_static_models_task",
                    "schedule": CACHE_WARM_SCHEDULES["static"],
                    "options": {"expires": CACHE_WARM_SCHEDULES["static"] * 1.5},
                },
                # Consistency check
                "check-cache-consistency": {
                    "task": "core.redis_warming.check_consistency_task",
                    "schedule": CACHE_WARM_SCHEDULES["consistency"],
                    "options": {"expires": CACHE_WARM_SCHEDULES["consistency"] * 1.5},
                },
            }

            # Update Celery beat schedule
            current_app.conf.beat_schedule.update(beat_schedule)

            logger.info("Scheduled cache warming with Celery")
            return
        except ImportError:
            logger.debug("Celery not available, trying Django Q")

        # Schedule with Django Q if available
        try:
            from django_q.tasks import schedule
            from django_q.models import Schedule

            # Schedule full warming
            schedule(
                "core.redis_warming.warm_cache",
                name="Warm Redis Cache (Full)",
                schedule_type=Schedule.CRON,
                cron=f"*/{int(CACHE_WARM_SCHEDULES['full'] / 60)} * * * *",  # Convert seconds to minutes
            )

            # Schedule critical warming
            schedule(
                "core.redis_warming.warm_critical_models",
                name="Warm Redis Cache (Critical)",
                schedule_type=Schedule.CRON,
                cron=f"*/{int(CACHE_WARM_SCHEDULES['critical'] / 60)} * * * *",  # Convert seconds to minutes
            )

            # Schedule static warming
            schedule(
                "core.redis_warming.warm_static_models",
                name="Warm Redis Cache (Static)",
                schedule_type=Schedule.CRON,
                cron=f"0 */{int(CACHE_WARM_SCHEDULES['static'] / 3600)} * * *",  # Convert seconds to hours
            )

            # Schedule consistency check
            schedule(
                "core.redis_consistency.check_frequently_accessed_models_consistency",
                name="Check Redis Cache Consistency",
                schedule_type=Schedule.CRON,
                cron=f"0 */{int(CACHE_WARM_SCHEDULES['consistency'] / 3600)} * * *",  # Convert seconds to hours
            )

            logger.info("Scheduled cache warming with Django Q")
            return
        except ImportError:
            logger.debug("Django Q not available")

        logger.warning("No task scheduler available for cache warming")
    except Exception as e:
        logger.error(f"Error scheduling cache warming: {str(e)}")


def warm_cache_on_startup():
    """
    Warm the cache on application startup.
    """
    if not CACHE_ENABLED:
        logger.warning("Startup cache warming skipped: Cache is disabled")
        return

    # Check if startup warming is enabled
    if not getattr(settings, "CACHE_WARM_ON_STARTUP", True):
        logger.info("Startup cache warming is disabled in settings")
        return

    logger.info("Starting cache warming on startup")

    try:
        # Warm the cache in a separate thread to avoid blocking startup
        def warm_thread():
            try:
                warm_cache()
            except Exception as e:
                logger.error(f"Error in startup cache warming thread: {str(e)}")

        thread = threading.Thread(target=warm_thread)
        thread.daemon = True
        thread.start()

        logger.info("Started cache warming thread")
    except Exception as e:
        logger.error(f"Error starting cache warming thread: {str(e)}")


def schedule_monitoring_alerts():
    """
    Schedule cache monitoring alerts.

    This function schedules periodic checks of cache health and sends alerts
    when issues are detected.
    """
    if not CACHE_ENABLED:
        logger.warning("Cache monitoring scheduling skipped: Cache is disabled")
        return

    try:
        # Schedule with Celery if available
        try:
            from celery import current_app

            # Import monitoring function
            from core.redis_alerts import monitor_cache_health

            @current_app.task(name="core.redis_alerts.monitor_cache_health_task")
            def monitor_cache_health_task():
                monitor_cache_health()

            # Schedule monitoring every 15 minutes
            current_app.conf.beat_schedule.update({
                "monitor-cache-health": {
                    "task": "core.redis_alerts.monitor_cache_health_task",
                    "schedule": 60 * 15,  # 15 minutes
                    "options": {"expires": 60 * 20},
                },
            })

            logger.info("Scheduled cache monitoring with Celery")
            return
        except ImportError:
            logger.debug("Celery not available, trying Django Q")

        # Schedule with Django Q if available
        try:
            from django_q.tasks import schedule
            from django_q.models import Schedule

            # Schedule monitoring every 15 minutes
            schedule(
                "core.redis_alerts.scheduled_cache_monitoring",
                name="Monitor Redis Cache Health",
                schedule_type=Schedule.MINUTES,
                minutes=15,
            )

            logger.info("Scheduled cache monitoring with Django Q")
            return
        except ImportError:
            logger.debug("Django Q not available")

        logger.warning("No task scheduler available for cache monitoring")
    except Exception as e:
        logger.error(f"Error scheduling cache monitoring: {str(e)}")


# Warm cache on module import if enabled
if CACHE_WARM_ON_IMPORT:
    warm_cache_on_startup()

# Schedule monitoring alerts
schedule_monitoring_alerts()

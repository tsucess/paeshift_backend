"""
Redis scheduled tasks module.

This module provides scheduled tasks for Redis cache warming,
monitoring, memory optimization, and telemetry.
"""

import logging
from datetime import timedelta

from django.utils import timezone

from core.redis_monitoring import record_stats
from core.redis_optimization import optimize_memory_usage
from core.redis_settings import CACHE_ENABLED
from core.redis_warming import warm_cache, warm_frequently_accessed_models, warm_api_endpoints

logger = logging.getLogger(__name__)


def warm_cache_task():
    """
    Scheduled task to warm the Redis cache.
    
    This task warms the cache for frequently accessed models and API endpoints.
    It should be scheduled to run periodically, e.g., every hour.
    """
    if not CACHE_ENABLED:
        logger.info("Cache warming task skipped: Redis cache is disabled")
        return
        
    logger.info("Starting scheduled cache warming task")
    
    try:
        # Warm models
        model_results = warm_frequently_accessed_models()
        
        # Warm API endpoints
        endpoint_results = warm_api_endpoints()
        
        logger.info(
            f"Completed scheduled cache warming task: "
            f"{sum(count for _, count in model_results.values())} model instances cached, "
            f"{sum(1 for success in endpoint_results.values() if success)} endpoints warmed"
        )
    except Exception as e:
        logger.error(f"Error in scheduled cache warming task: {str(e)}")


def record_stats_task():
    """
    Scheduled task to record Redis cache statistics.
    
    This task records cache statistics for historical tracking.
    It should be scheduled to run periodically, e.g., every 15 minutes.
    """
    if not CACHE_ENABLED:
        logger.info("Stats recording task skipped: Redis cache is disabled")
        return
        
    logger.info("Starting scheduled stats recording task")
    
    try:
        # Record stats
        success = record_stats()
        
        if success:
            logger.info("Completed scheduled stats recording task")
        else:
            logger.warning("Failed to record cache statistics")
    except Exception as e:
        logger.error(f"Error in scheduled stats recording task: {str(e)}")


def optimize_memory_task():
    """
    Scheduled task to optimize Redis memory usage.
    
    This task applies various memory optimization techniques.
    It should be scheduled to run periodically, e.g., every day during off-peak hours.
    """
    if not CACHE_ENABLED:
        logger.info("Memory optimization task skipped: Redis cache is disabled")
        return
        
    logger.info("Starting scheduled memory optimization task")
    
    try:
        # Optimize memory
        results = optimize_memory_usage()
        
        # Check for errors
        if "error" in results:
            logger.error(f"Memory optimization failed: {results['error']}")
        else:
            memory_saved = results.get("memory_saved_human", "0 KB")
            keys_removed = results.get("keys_removed", 0)
            
            logger.info(
                f"Completed scheduled memory optimization task: "
                f"{memory_saved} saved, {keys_removed} keys removed"
            )
    except Exception as e:
        logger.error(f"Error in scheduled memory optimization task: {str(e)}")


def register_celery_tasks(app):
    """
    Register Redis tasks with Celery.
    
    Args:
        app: Celery app instance
    """
    @app.task(name="core.redis_tasks.warm_cache_task")
    def celery_warm_cache_task():
        warm_cache_task()
        
    @app.task(name="core.redis_tasks.record_stats_task")
    def celery_record_stats_task():
        record_stats_task()
        
    @app.task(name="core.redis_tasks.optimize_memory_task")
    def celery_optimize_memory_task():
        optimize_memory_task()
        
    # Schedule tasks
    app.conf.beat_schedule.update({
        "warm-cache-hourly": {
            "task": "core.redis_tasks.warm_cache_task",
            "schedule": timedelta(hours=1),
            "options": {"expires": 3600},
        },
        "record-stats-every-15-minutes": {
            "task": "core.redis_tasks.record_stats_task",
            "schedule": timedelta(minutes=15),
            "options": {"expires": 900},
        },
        "optimize-memory-daily": {
            "task": "core.redis_tasks.optimize_memory_task",
            "schedule": timedelta(days=1),
            "options": {"expires": 86400},
        },
    })
    
    logger.info("Registered Redis tasks with Celery")


def register_django_q_tasks():
    """
    Register Redis tasks with Django Q.
    """
    try:
        from django_q.tasks import schedule
        from django_q.models import Schedule
        
        # Schedule cache warming task (hourly)
        schedule(
            "core.redis_tasks.warm_cache_task",
            name="Warm Redis Cache",
            schedule_type=Schedule.HOURLY,
        )
        
        # Schedule stats recording task (every 15 minutes)
        schedule(
            "core.redis_tasks.record_stats_task",
            name="Record Redis Stats",
            minutes=15,
        )
        
        # Schedule memory optimization task (daily at 3 AM)
        schedule(
            "core.redis_tasks.optimize_memory_task",
            name="Optimize Redis Memory",
            schedule_type=Schedule.DAILY,
            next_run=timezone.now().replace(hour=3, minute=0, second=0),
        )
        
        logger.info("Registered Redis tasks with Django Q")
    except ImportError:
        logger.warning("Django Q not installed, skipping task registration")
    except Exception as e:
        logger.error(f"Error registering Redis tasks with Django Q: {str(e)}")


# Register tasks with the appropriate task queue
try:
    # Try to register with Celery if available
    from celery import current_app
    register_celery_tasks(current_app)
except ImportError:
    # Fall back to Django Q
    register_django_q_tasks()

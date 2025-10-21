"""
Redis API module.

This module provides API endpoints for Redis monitoring, cache warming,
memory optimization, and telemetry.
"""

import json
import logging
from typing import Dict, List, Optional

from django.apps import apps
from django.http import JsonResponse
from django.utils import timezone
from ninja import Router

from core.redis_monitoring import (
    get_cache_stats,
    get_historical_stats,
    get_hit_rate,
    get_key_count_by_prefix,
    get_memory_usage,
    analyze_key_size,
)
from core.redis.redis_optimization import (
    optimize_memory_usage,
    compress_large_values,
    delete_unused_keys,
    extend_ttl_for_popular_keys,
)
from core.redis.redis_settings import CACHE_ENABLED
from core.redis.redis_telemetry import get_slow_operations, get_telemetry_stats
from core.redis.redis_warming import warm_cache, warm_frequently_accessed_models, warm_api_endpoints, warm_critical_models
from core.redis.redis_consistency import (
    check_model_consistency,
    check_frequently_accessed_models_consistency,
    verify_cache_entry,
    repair_cache_entry,
)
from core.redis.redis_analytics import (
    analyze_hit_rate_by_prefix,
    analyze_key_size_distribution,
    analyze_ttl_distribution,
    analyze_cache_churn,
    analyze_cache_misses,
    analyze_cache_efficiency,
    analyze_cache_performance,
    generate_optimization_recommendations,
    get_analytics_dashboard,
)

logger = logging.getLogger(__name__)

redis_router = Router(tags=["Redis"])


@redis_router.get("/stats")
def cache_stats(request):
    """
    Get Redis cache statistics.
    Returns:
        Cache statistics
    """
    if not CACHE_ENABLED:
        return JsonResponse({"error": "Redis cache is disabled"}, status=400)
    return get_cache_stats()


@redis_router.get("/memory")
def memory_usage(request):
    """
    Get Redis memory usage statistics.
    Returns:
        Memory usage statistics
    """
    if not CACHE_ENABLED:
        return JsonResponse({"error": "Redis cache is disabled"}, status=400)
    return get_memory_usage()


@redis_router.get("/keys")
def key_counts(request):
    """
    Get Redis key counts by prefix.
    Returns:
        Key counts by prefix
    """
    if not CACHE_ENABLED:
        return JsonResponse({"error": "Redis cache is disabled"}, status=400)
    return get_key_count_by_prefix()


@redis_router.get("/hit-rate")
def hit_rate(request):
    """
    Get Redis cache hit rate.
    Returns:
        Cache hit rate statistics
    """
    if not CACHE_ENABLED:
        return JsonResponse({"error": "Redis cache is disabled"}, status=400)
    return get_hit_rate()


@redis_router.get("/historical-stats")
def historical_stats(request, period: str = "hourly", days: int = 1):
    """
    Get historical Redis cache statistics.

    Args:
        period: "hourly", "daily", or "weekly"
        days: Number of days to look back

    Returns:
        Historical cache statistics
    """
    if not CACHE_ENABLED:
        return JsonResponse({"error": "Redis cache is disabled"}, status=400)
    return get_historical_stats(period, days)


@redis_router.get("/analyze-keys")
def analyze_keys(request, pattern: str = "*", sample_size: int = 100):
    """
    Analyze Redis keys by size.

    Args:
        pattern: Key pattern to match
        sample_size: Number of keys to sample

    Returns:
        Key size statistics
    """
    if not CACHE_ENABLED:
        return JsonResponse({"error": "Redis cache is disabled"}, status=400)
    return analyze_key_size(pattern, sample_size)


@redis_router.post("/warm-cache")
def warm_cache_endpoint(request):
    """
    Warm the Redis cache.
    Returns:
        Cache warming results
    """
    if not CACHE_ENABLED:
        return JsonResponse({"error": "Redis cache is disabled"}, status=400)
    return warm_cache()


@redis_router.post("/warm-models")
def warm_models_endpoint(request):
    """
    Warm the Redis cache for frequently accessed models.
    Returns:
        Model warming results
    """
    if not CACHE_ENABLED:
        return JsonResponse({"error": "Redis cache is disabled"}, status=400)
    return warm_frequently_accessed_models()


@redis_router.post("/warm-endpoints")
def warm_endpoints_endpoint(request):
    """
    Warm the Redis cache for frequently accessed API endpoints.
    Returns:
        Endpoint warming results
    """
    if not CACHE_ENABLED:
        return JsonResponse({"error": "Redis cache is disabled"}, status=400)
    return warm_api_endpoints()


@redis_router.post("/optimize-memory")
def optimize_memory_endpoint(request):
    """
    Optimize Redis memory usage.
    Returns:
        Memory optimization results
    """
    if not CACHE_ENABLED:
        return JsonResponse({"error": "Redis cache is disabled"}, status=400)
    return optimize_memory_usage()


@redis_router.post("/compress-values")
def compress_values_endpoint(request, pattern: str = "*", sample_size: int = 100, min_size: int = 1024):
    """
    Compress large values in Redis.
    Args:
        pattern: Key pattern to match
        sample_size: Number of keys to sample
        min_size: Minimum size to compress
    Returns:
        Compression results
    """
    if not CACHE_ENABLED:
        return JsonResponse({"error": "Redis cache is disabled"}, status=400)
    return compress_large_values(pattern, sample_size, min_size)


@redis_router.post("/delete-unused")
def delete_unused_endpoint(request, pattern: str = "*", days: int = 7, sample_size: int = 1000, dry_run: bool = True):
    """
    Delete unused keys in Redis.
    Args:
        pattern: Key pattern to match
        days: Number of days to consider a key unused
        sample_size: Number of keys to sample
        dry_run: If True, only report keys that would be deleted
    Returns:
        Deletion results
    """
    if not CACHE_ENABLED:
        return JsonResponse({"error": "Redis cache is disabled"}, status=400)
    return delete_unused_keys(pattern, days, sample_size, dry_run)


@redis_router.post("/extend-ttl")
def extend_ttl_endpoint(request, pattern: str = "*", min_hits: int = 10, extension_factor: float = 2.0, sample_size: int = 1000):
    """
    Extend TTL for frequently accessed keys in Redis.
    Args:
        pattern: Key pattern to match
        min_hits: Minimum number of hits to consider a key popular
        extension_factor: Factor to multiply TTL by
        sample_size: Number of keys to sample
    Returns:
        TTL extension results
    """
    if not CACHE_ENABLED:
        return JsonResponse({"error": "Redis cache is disabled"}, status=400)
    return extend_ttl_for_popular_keys(pattern, min_hits, extension_factor, sample_size)


@redis_router.get("/slow-operations")
def slow_operations_endpoint(request, operation_type: Optional[str] = None, min_duration_ms: float = 100, limit: int = 100):
    """
    Get slow Redis operations.
    Args:
        operation_type: Optional operation type filter
        min_duration_ms: Minimum duration in milliseconds
        limit: Maximum number of operations to return
    Returns:
        List of slow operations
    """
    if not CACHE_ENABLED:
        return JsonResponse({"error": "Redis cache is disabled"}, status=400)
    return get_slow_operations(operation_type, min_duration_ms, limit)


@redis_router.get("/telemetry-stats")
def telemetry_stats_endpoint(request):
    """
    Get Redis telemetry statistics.
    Returns:
        Telemetry statistics
    """
    if not CACHE_ENABLED:
        return JsonResponse({"error": "Redis cache is disabled"}, status=400)

    return get_telemetry_stats()


@redis_router.post("/warm-critical")
def warm_critical_endpoint(request):
    """
    Warm the Redis cache for critical models that change frequently.

    This is a lightweight version of warm_cache() for more frequent execution.

    Returns:
        Critical model warming results
    """
    if not CACHE_ENABLED:
        return JsonResponse({"error": "Redis cache is disabled"}, status=400)

    return warm_critical_models()


@redis_router.post("/check-consistency")
def check_consistency_endpoint(request, model_name: Optional[str] = None, model_id: Optional[int] = None, auto_repair: bool = True):
    """
    Check consistency between database and cache.

    Args:
        model_name: Optional model name to check (e.g., "User", "Job")
        model_id: Optional model instance ID to check
        auto_repair: Whether to automatically repair inconsistencies

    Returns:
        Consistency check results
    """
    if not CACHE_ENABLED:
        return JsonResponse({"error": "Redis cache is disabled"}, status=400)

    # If model name and ID are provided, check specific instance
    if model_name and model_id:
        # Get model class
        try:
            if model_name.lower() == "user":
                from django.contrib.auth import get_user_model
                model_class = get_user_model()
            else:
                # Try to find the model class
                for app_config in apps.get_app_configs():
                    try:
                        model_class = app_config.get_model(model_name)
                        break
                    except LookupError:
                        continue
                else:
                    return JsonResponse({"error": f"Model {model_name} not found"}, status=400)

            # Check consistency
            return check_model_consistency(model_class, model_id, auto_repair)
        except Exception as e:
            logger.error(f"Error checking consistency for {model_name} instance {model_id}: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)

    # If only model name is provided, check all instances of that model
    elif model_name:
        # Get model class
        try:
            if model_name.lower() == "user":
                from django.contrib.auth import get_user_model
                model_class = get_user_model()
            else:
                # Try to find the model class
                for app_config in apps.get_app_configs():
                    try:
                        model_class = app_config.get_model(model_name)
                        break
                    except LookupError:
                        continue
                else:
                    return JsonResponse({"error": f"Model {model_name} not found"}, status=400)

            # Check consistency
            return check_model_consistency(model_class, auto_repair=auto_repair)
        except Exception as e:
            logger.error(f"Error checking consistency for {model_name}: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)

    # If no model name is provided, check all frequently accessed models
    else:
        return check_frequently_accessed_models_consistency(auto_repair)


@redis_router.post("/run-consistency-check")
def run_consistency_check_endpoint(request, sample_size: int = 100, auto_repair: bool = True):
    """
    Run a comprehensive consistency check as a background task.

    This endpoint triggers a background task to check consistency between
    the database and cache for all models. The task runs asynchronously
    and logs the results.

    Args:
        sample_size: Number of instances to check per model
        auto_repair: Whether to automatically repair inconsistencies

    Returns:
        Task information
    """
    if not CACHE_ENABLED:
        return JsonResponse({"error": "Redis cache is disabled"}, status=400)

    try:
        # Try to run with Celery
        try:
            from celery import current_app

            @current_app.task(name="core.redis_consistency.run_full_consistency_check")
            def run_full_consistency_check(sample_size, auto_repair):
                from core.redis.redis_consistency import check_frequently_accessed_models_consistency
                return check_frequently_accessed_models_consistency(auto_repair)

            # Run the task
            task = run_full_consistency_check.delay(sample_size, auto_repair)

            return {
                "message": "Consistency check started",
                "task_id": task.id,
                "status": "PENDING",
            }
        except ImportError:
            logger.debug("Celery not available, trying Django Q")

        # Try to run with Django Q
        try:
            from django_q.tasks import async_task

            # Run the task
            task_id = async_task(
                "core.redis_consistency.check_frequently_accessed_models_consistency",
                auto_repair,
                hook="core.redis_api.log_consistency_check_results",
            )

            return {
                "message": "Consistency check started",
                "task_id": str(task_id),
                "status": "PENDING",
            }
        except ImportError:
            logger.debug("Django Q not available")

        # Run synchronously as fallback
        logger.warning("No task queue available, running consistency check synchronously")
        results = check_frequently_accessed_models_consistency(auto_repair)

        return {
            "message": "Consistency check completed synchronously",
            "results": results,
        }
    except Exception as e:
        logger.error(f"Error starting consistency check: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


def log_consistency_check_results(task):
    """
    Log the results of a consistency check task.

    This function is used as a hook for Django Q tasks.

    Args:
        task: Django Q task object
    """
    try:
        results = task.result

        if not results:
            logger.warning("Consistency check task returned no results")
            return

        # Log summary
        total_checked = results.get("total_checked", 0)
        total_consistent = results.get("total_consistent", 0)
        total_inconsistent = results.get("total_inconsistent", 0)
        total_missing = results.get("total_missing", 0)
        total_repaired = results.get("total_repaired", 0)

        logger.info(
            f"Consistency check completed: "
            f"{total_consistent}/{total_checked} consistent, "
            f"{total_inconsistent} inconsistent, "
            f"{total_missing} missing, "
            f"{total_repaired} repaired"
        )

        # Log details for each model
        models = results.get("models", {})
        for model_name, model_results in models.items():
            if isinstance(model_results, dict):
                checked = model_results.get("checked_instances", 0)
                consistent = model_results.get("consistent_instances", 0)
                inconsistent = model_results.get("inconsistent_instances", 0)
                missing = model_results.get("missing_from_cache", 0)
                repaired = model_results.get("repaired_instances", 0)

                if inconsistent > 0 or missing > 0:
                    logger.warning(
                        f"Model {model_name}: "
                        f"{consistent}/{checked} consistent, "
                        f"{inconsistent} inconsistent, "
                        f"{missing} missing, "
                        f"{repaired} repaired"
                    )
    except Exception as e:
        logger.error(f"Error logging consistency check results: {str(e)}")


@redis_router.get("/verify-cache")
def verify_cache_endpoint(request, model_type: str, instance_id: int):
    """
    Verify a specific cache entry against the database.

    Args:
        model_type: Model type (e.g., "user", "job")
        instance_id: Instance ID

    Returns:
        Verification results
    """
    if not CACHE_ENABLED:
        return JsonResponse({"error": "Redis cache is disabled"}, status=400)

    return verify_cache_entry(model_type, instance_id)


@redis_router.post("/repair-cache")
def repair_cache_endpoint(request, model_type: str, instance_id: int):
    """
    Repair a specific cache entry.

    Args:
        model_type: Model type (e.g., "user", "job")
        instance_id: Instance ID

    Returns:
        Repair results
    """
    if not CACHE_ENABLED:
        return JsonResponse({"error": "Redis cache is disabled"}, status=400)

    return repair_cache_entry(model_type, instance_id)


@redis_router.get("/analytics/hit-rate-by-prefix")
def hit_rate_by_prefix_endpoint(request):
    """
    Analyze hit rate by key prefix.

    Returns:
        Hit rate analysis by prefix
    """
    if not CACHE_ENABLED:
        return JsonResponse({"error": "Redis cache is disabled"}, status=400)

    return analyze_hit_rate_by_prefix()


@redis_router.get("/analytics/key-size-distribution")
def key_size_distribution_endpoint(request):
    """
    Analyze key size distribution.

    Returns:
        Key size distribution
    """
    if not CACHE_ENABLED:
        return JsonResponse({"error": "Redis cache is disabled"}, status=400)

    return analyze_key_size_distribution()


@redis_router.get("/analytics/ttl-distribution")
def ttl_distribution_endpoint(request):
    """
    Analyze TTL distribution.

    Returns:
        TTL distribution
    """
    if not CACHE_ENABLED:
        return JsonResponse({"error": "Redis cache is disabled"}, status=400)

    return analyze_ttl_distribution()


@redis_router.get("/analytics/cache-churn")
def cache_churn_endpoint(request):
    """
    Analyze cache churn (keys that are frequently evicted).

    Returns:
        Cache churn analysis
    """
    if not CACHE_ENABLED:
        return JsonResponse({"error": "Redis cache is disabled"}, status=400)

    return analyze_cache_churn()


@redis_router.get("/analytics/cache-misses")
def cache_misses_endpoint(request):
    """
    Analyze cache misses to identify opportunities for improvement.

    Returns:
        Cache miss analysis
    """
    if not CACHE_ENABLED:
        return JsonResponse({"error": "Redis cache is disabled"}, status=400)

    return analyze_cache_misses()


@redis_router.get("/analytics/cache-efficiency")
def cache_efficiency_endpoint(request):
    """
    Analyze cache efficiency (hit rate vs memory usage).

    Returns:
        Cache efficiency analysis
    """
    if not CACHE_ENABLED:
        return JsonResponse({"error": "Redis cache is disabled"}, status=400)

    return analyze_cache_efficiency()


@redis_router.get("/analytics/cache-performance")
def cache_performance_endpoint(request):
    """
    Analyze cache performance (response times).

    Returns:
        Cache performance analysis
    """
    if not CACHE_ENABLED:
        return JsonResponse({"error": "Redis cache is disabled"}, status=400)

    return analyze_cache_performance()


@redis_router.get("/analytics/recommendations")
def recommendations_endpoint(request):
    """
    Generate optimization recommendations based on analytics.

    Returns:
        Optimization recommendations
    """
    if not CACHE_ENABLED:
        return JsonResponse({"error": "Redis cache is disabled"}, status=400)

    return generate_optimization_recommendations()


@redis_router.get("/analytics/dashboard")
def analytics_dashboard_endpoint(request):
    """
    Get a comprehensive analytics dashboard.

    Returns:
        Analytics dashboard data
    """
    if not CACHE_ENABLED:
        return JsonResponse({"error": "Redis cache is disabled"}, status=400)

    return get_analytics_dashboard()


@redis_router.get("/dashboard")
def dashboard_endpoint(request):
    """
    Get Redis dashboard data.
    Returns:
        Dashboard data
    """
    if not CACHE_ENABLED:
        return JsonResponse({"error": "Redis cache is disabled"}, status=400)
    # Get various statistics
    stats = get_cache_stats()
    memory = get_memory_usage()
    keys = get_key_count_by_prefix()
    hit_rate_stats = get_hit_rate()
    telemetry = get_telemetry_stats()
    slow_ops = get_slow_operations(limit=5)

    # Get consistency check results (lightweight check)
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        consistency = check_model_consistency(User, auto_repair=False)
    except Exception as e:
        logger.error(f"Error checking consistency for dashboard: {str(e)}")
        consistency = {"error": str(e)}

    # Get optimization recommendations
    try:
        recommendations = generate_optimization_recommendations()
    except Exception as e:
        logger.error(f"Error generating recommendations for dashboard: {str(e)}")
        recommendations = {"error": str(e)}

    # Combine into dashboard data
    dashboard = {
        "stats": stats,
        "memory": memory,
        "keys": keys,
        "hit_rate": hit_rate_stats,
        "telemetry": telemetry,
        "slow_operations": slow_ops,
        "consistency": consistency,
        "recommendations": recommendations,
        "timestamp": timezone.now().isoformat(),
    }

    return dashboard

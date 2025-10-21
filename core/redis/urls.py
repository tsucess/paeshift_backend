"""
Redis URLs.
"""

from django.urls import path
from django.contrib.admin.views.decorators import staff_member_required

from core.redis.admin import (
    redis_dashboard_view,
    redis_dashboard_api,
    redis_stats_api,
    redis_slow_operations_api,
    redis_warm_cache_api,
    redis_clear_cache_api,
    redis_optimize_memory_api,
)

urlpatterns = [
    # Redis dashboard
    path(
        "dashboard/",
        staff_member_required(redis_dashboard_view),
        name="redis_dashboard",
    ),
    path(
        "dashboard/api/",
        staff_member_required(redis_dashboard_api),
        name="redis_dashboard_api",
    ),
    path(
        "stats/api/",
        staff_member_required(redis_stats_api),
        name="redis_stats_api",
    ),
    path(
        "slow-operations/api/",
        staff_member_required(redis_slow_operations_api),
        name="redis_slow_operations_api",
    ),
    path(
        "warm-cache/api/",
        staff_member_required(redis_warm_cache_api),
        name="redis_warm_cache_api",
    ),
    path(
        "clear-cache/api/",
        staff_member_required(redis_clear_cache_api),
        name="redis_clear_cache_api",
    ),
    path(
        "optimize-memory/api/",
        staff_member_required(redis_optimize_memory_api),
        name="redis_optimize_memory_api",
    ),
]

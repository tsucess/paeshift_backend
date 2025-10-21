"""
Core URLs for monitoring and system health.
"""

from django.urls import path, include
from ninja import NinjaAPI

from .monitoring import cache_stats_view, clear_cache_view, system_health_view
from .redis_api import redis_router
from .views import redis_dashboard_view

# Create a Ninja API instance for Redis monitoring
redis_api = NinjaAPI(
    title="Redis Monitoring API",
    version="10.0.0",  # Sequential version number
    description="API for Redis monitoring, cache warming, and optimization",
    urls_namespace="redis_api",  # Added namespace
)

# Add the Redis router to the API
redis_api.add_router("", redis_router)

urlpatterns = [
    # Legacy monitoring endpoints
    path("monitoring/cache-stats/", cache_stats_view, name="cache_stats"),
    path("monitoring/clear-cache/", clear_cache_view, name="clear_cache"),
    path("monitoring/system-health/", system_health_view, name="system_health"),

    # Redis monitoring API
    path("redis/", redis_api.urls),

    # Redis dashboard
    path("redis-dashboard/", redis_dashboard_view, name="redis_dashboard"),

    # New consolidated Redis module
    path("redis/", include("core.redis.urls")),
]

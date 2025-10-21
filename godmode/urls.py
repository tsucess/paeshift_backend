from django.urls import path, include
from ninja import NinjaAPI

from . import views
# Removed import for signup_view as it doesn't exist
from .views.mfa_views import (
    mfa_setup_view, mfa_setup_confirm_view, mfa_verify_view,
    mfa_verify_confirm_view, mfa_disable_view, mfa_qr_code_view,
    mfa_api_verify_view
)
from .views.redis_monitor import (
    redis_monitor_view, redis_stats_api, warm_cache_api, clear_cache_api, delete_key_api
)
from .views.cache_consistency import (
    cache_consistency_dashboard, check_model_consistency_view,
    reconcile_model_view, check_all_consistency_view
)
from .views.monitoring_views import (
    geocoding_dashboard, geocoding_metrics_api, test_geocoding_api, cache_stats_api
)
# Import the router but don't use it directly
# from .api import godmode_router

# Create a Ninja API instance for God Mode
godmode_api = NinjaAPI(
    version="1.0.22",  # Sequential version number
    urls_namespace="godmode_api",
)

app_name = "godmode"

urlpatterns = [
    # Dashboard
    path("", views.godmode_dashboard, name="dashboard"),

    # Redis Monitor
    path("redis-monitor/", redis_monitor_view, name="redis_monitor"),
    path("api/redis-stats/", redis_stats_api, name="redis_stats_api"),
    path("api/warm-cache/", warm_cache_api, name="warm_cache_api"),
    path("api/clear-cache/", clear_cache_api, name="clear_cache_api"),
    path("api/delete-key/", delete_key_api, name="delete_key_api"),
    # User Management
    path("user-activity/", views.user_activity, name="user_activity"),
    path("user/<int:user_id>/", views.user_detail, name="user_detail"),
    path("user/<int:user_id>/delete/", views.delete_user, name="delete_user"),
    # Location Verification
    path(
        "location-verification/",
        views.location_verification,
        name="location_verification",
    ),
    path(
        "verify-location/<int:verification_id>/",
        views.verify_location,
        name="verify_location",
    ),
    # Simulations
    path("run-simulation/", views.run_simulation, name="run_simulation"),
    path("simulations/", views.simulations, name="simulations"),
    path(
        "simulation/<int:simulation_id>/",
        views.simulation_detail,
        name="simulation_detail",
    ),
    # Webhook Logs
    path("webhook-logs/", views.webhook_logs, name="webhook_logs"),
    path(
        "webhook-log/<int:log_id>/", views.webhook_log_detail, name="webhook_log_detail"
    ),
    # Work Assignments
    path("work-assignments/", views.work_assignments, name="work_assignments"),
    path(
        "work-assignment/<int:assignment_id>/",
        views.work_assignment_detail,
        name="work_assignment_detail",
    ),
    path(
        "create-work-assignment/",
        views.create_work_assignment,
        name="create_work_assignment",
    ),
    # Data Exports
    path("data-exports/", views.data_exports, name="data_exports"),
    path(
        "create-export-config/", views.create_export_config, name="create_export_config"
    ),
    path("run-export/<int:config_id>/", views.run_export, name="run_export"),
    # User Rankings
    path("user-rankings/", views.user_rankings, name="user_rankings"),
    path("generate-rankings/", views.generate_rankings, name="generate_rankings"),
    path(
        "generate-rankings/<str:ranking_type>/",
        views.generate_rankings,
        name="generate_rankings_type",
    ),
    # Security Dashboard
    path("security/", views.security_dashboard, name="security_dashboard"),

    # API endpoints
    path("api/", godmode_api.urls),

    # Cache Sync
    path("cache-sync/", views.cache_sync_view, name="cache_sync"),

    # MFA
    path("mfa/setup/", mfa_setup_view, name="mfa_setup"),
    path("mfa/setup/confirm/", mfa_setup_confirm_view, name="mfa_setup_confirm"),
    path("mfa/verify/", mfa_verify_view, name="mfa_verify"),
    path("mfa/verify/confirm/", mfa_verify_confirm_view, name="mfa_verify_confirm"),
    path("mfa/disable/", mfa_disable_view, name="mfa_disable"),
    path("mfa/qr-code/", mfa_qr_code_view, name="mfa_qr_code"),
    path("api/mfa/verify/", mfa_api_verify_view, name="mfa_api_verify"),

    # IP Whitelist
    path("ip-whitelist/", views.ip_whitelist_view, name="ip_whitelist"),
    path("ip-whitelist/add/", views.ip_whitelist_add_view, name="ip_whitelist_add"),
    path("ip-whitelist/delete/<int:whitelist_id>/", views.ip_whitelist_delete_view, name="ip_whitelist_delete"),

    # Audit Logs
    path("audit-logs/", views.audit_logs_view, name="audit_logs"),
    path("audit-logs/<int:log_id>/", views.audit_log_detail_view, name="audit_log_detail"),

    # Cache Consistency
    path("cache-consistency/", cache_consistency_dashboard, name="cache_consistency"),
    path("cache-consistency/check/<str:app_label>/<str:model_name>/",
         check_model_consistency_view, name="check_model_consistency"),
    path("cache-consistency/reconcile/<str:app_label>/<str:model_name>/",
         reconcile_model_view, name="reconcile_model"),
    path("cache-consistency/check-all/",
         check_all_consistency_view, name="check_all_consistency"),

    # Geocoding Monitoring
    path("geocoding/", geocoding_dashboard, name="geocoding_dashboard"),
    path("api/geocoding/metrics/", geocoding_metrics_api, name="geocoding_metrics_api"),
    path("api/geocoding/test/", test_geocoding_api, name="test_geocoding_api"),
    path("api/geocoding/cache-stats/", cache_stats_api, name="geocoding_cache_stats_api"),
]

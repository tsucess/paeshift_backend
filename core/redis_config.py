"""
Redis cache configuration.

This module provides centralized configuration for Redis cache TTLs,
invalidation rules, memory limits, and other optimization settings.
"""

import logging
from enum import Enum
from typing import Dict, List, Set, Type, Any

from django.apps import apps
from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)


class CacheNamespace(str, Enum):
    """Enum of cache namespaces for consistent key prefixes."""

    # Model-related caches
    MODEL = "model"
    USER = "user"
    JOB = "job"
    APPLICATION = "app"
    PROFILE = "profile"
    INDUSTRY = "industry"
    SUBCATEGORY = "subcat"

    # API-related caches
    API = "api"
    WHOAMI = "whoami"
    QUERY = "query"

    # Advanced features
    RANKING = "rank"
    ACTIVITY = "activity"
    PRESENCE = "presence"
    NOTIFICATION = "notif"
    LEADERBOARD = "leaderboard"
    LOCK = "lock"
    RATE_LIMIT = "ratelimit"

    # System caches
    GEOCODE = "geocode"
    CONFIG = "config"
    SESSION = "session"
    TELEMETRY = "telemetry"

    # Default namespace
    DEFAULT = "cache"

    def __str__(self) -> str:
        """Return the namespace with a colon suffix."""
        return f"{self.value}:"


class CacheTTL:
    """Standard TTL values for different types of cached data."""

    # Short-lived caches (seconds)
    MICRO = 5  # 5 seconds
    TINY = 30  # 30 seconds
    SMALL = 60  # 1 minute
    MEDIUM = 60 * 5  # 5 minutes

    # Medium-lived caches (minutes)
    STANDARD = 60 * 15  # 15 minutes
    EXTENDED = 60 * 30  # 30 minutes
    LONG = 60 * 60  # 1 hour

    # Long-lived caches (hours)
    VERY_LONG = 60 * 60 * 3  # 3 hours
    DAILY = 60 * 60 * 24  # 24 hours
    WEEKLY = 60 * 60 * 24 * 7  # 7 days

    # Special cases
    PERMANENT = 60 * 60 * 24 * 30  # 30 days
    LOCK_TIMEOUT = 60  # 1 minute for locks

    # Default TTL
    DEFAULT = 60 * 15  # 15 minutes


# TTL mapping by namespace
NAMESPACE_TTL_MAP = {
    CacheNamespace.MODEL: CacheTTL.DAILY,
    CacheNamespace.USER: CacheTTL.STANDARD,
    CacheNamespace.JOB: CacheTTL.DAILY,
    CacheNamespace.APPLICATION: CacheTTL.DAILY,
    CacheNamespace.PROFILE: CacheTTL.DAILY,
    CacheNamespace.INDUSTRY: CacheTTL.WEEKLY,
    CacheNamespace.SUBCATEGORY: CacheTTL.WEEKLY,
    CacheNamespace.API: CacheTTL.STANDARD,
    CacheNamespace.WHOAMI: CacheTTL.STANDARD,
    CacheNamespace.QUERY: CacheTTL.MEDIUM,
    CacheNamespace.RANKING: CacheTTL.DAILY,
    CacheNamespace.ACTIVITY: CacheTTL.DAILY,
    CacheNamespace.PRESENCE: CacheTTL.SMALL,
    CacheNamespace.NOTIFICATION: CacheTTL.STANDARD,
    CacheNamespace.LEADERBOARD: CacheTTL.DAILY,
    CacheNamespace.LOCK: CacheTTL.LOCK_TIMEOUT,
    CacheNamespace.RATE_LIMIT: CacheTTL.DAILY,
    CacheNamespace.GEOCODE: CacheTTL.PERMANENT,
    CacheNamespace.CONFIG: CacheTTL.DAILY,
    CacheNamespace.SESSION: CacheTTL.DAILY,
    CacheNamespace.TELEMETRY: CacheTTL.DAILY,
    CacheNamespace.DEFAULT: CacheTTL.DEFAULT,
}

# Override TTLs from settings if provided
NAMESPACE_TTL_OVERRIDES = getattr(settings, "CACHE_NAMESPACE_TTL_OVERRIDES", {})
NAMESPACE_TTL_MAP.update(NAMESPACE_TTL_OVERRIDES)


# Model-specific TTLs
MODEL_TTL_MAP = {
    # Format: "app_label.model_name": ttl_in_seconds
    "accounts.User": CacheTTL.STANDARD,
    "accounts.Profile": CacheTTL.STANDARD,
    "jobs.Job": CacheTTL.DAILY,
    "jobs.JobIndustry": CacheTTL.WEEKLY,
    "jobs.JobSubCategory": CacheTTL.WEEKLY,
    "jobs.Application": CacheTTL.DAILY,
    "jobs.SavedJob": CacheTTL.DAILY,
    "userlocation.UserLocation": CacheTTL.STANDARD,
}

# Override model TTLs from settings if provided
MODEL_TTL_OVERRIDES = getattr(settings, "CACHE_MODEL_TTL_OVERRIDES", {})
MODEL_TTL_MAP.update(MODEL_TTL_OVERRIDES)


# Model dependencies for invalidation
MODEL_DEPENDENCIES = {
    # Format: "app_label.model_name": ["dependent_app_label.dependent_model_name", ...]
    "accounts.User": ["accounts.Profile", "jobs.Application", "jobs.SavedJob"],
    "accounts.Profile": ["accounts.User"],
    "jobs.Job": ["jobs.Application", "jobs.SavedJob"],
    "jobs.JobIndustry": ["jobs.Job"],
    "jobs.JobSubCategory": ["jobs.Job"],
    "jobs.Application": ["jobs.Job"],
    "jobs.SavedJob": ["jobs.Job"],
    "userlocation.UserLocation": ["accounts.User"],
}

# Override model dependencies from settings if provided
MODEL_DEPENDENCY_OVERRIDES = getattr(settings, "CACHE_MODEL_DEPENDENCY_OVERRIDES", {})
for model_name, dependencies in MODEL_DEPENDENCY_OVERRIDES.items():
    if model_name in MODEL_DEPENDENCIES:
        MODEL_DEPENDENCIES[model_name].extend(dependencies)
    else:
        MODEL_DEPENDENCIES[model_name] = dependencies


def get_ttl_for_namespace(namespace: str) -> int:
    """
    Get the TTL for a namespace.

    Args:
        namespace: Cache namespace

    Returns:
        TTL in seconds
    """
    if namespace in NAMESPACE_TTL_MAP:
        return NAMESPACE_TTL_MAP[namespace]

    # Try to match with enum value
    try:
        enum_namespace = CacheNamespace(namespace.rstrip(':'))
        return NAMESPACE_TTL_MAP[enum_namespace]
    except (ValueError, KeyError):
        pass

    return CacheTTL.DEFAULT


def get_ttl_for_model(model_class: Type[models.Model]) -> int:
    """
    Get the TTL for a model.

    Args:
        model_class: Model class

    Returns:
        TTL in seconds
    """
    model_name = f"{model_class._meta.app_label}.{model_class.__name__}"

    if model_name in MODEL_TTL_MAP:
        return MODEL_TTL_MAP[model_name]

    # Try to match with namespace
    namespace = model_class.__name__.lower()
    return get_ttl_for_namespace(namespace)


def get_dependencies_for_model(model_class: Type[models.Model]) -> List[Type[models.Model]]:
    """
    Get the dependencies for a model.

    Args:
        model_class: Model class

    Returns:
        List of dependent model classes
    """
    model_name = f"{model_class._meta.app_label}.{model_class.__name__}"

    if model_name not in MODEL_DEPENDENCIES:
        return []

    dependencies = []

    for dependent_name in MODEL_DEPENDENCIES[model_name]:
        try:
            app_label, model_name = dependent_name.split(".")
            dependent_model = apps.get_model(app_label, model_name)
            dependencies.append(dependent_model)
        except Exception as e:
            logger.error(f"Error loading dependent model {dependent_name}: {str(e)}")

    return dependencies


def register_model_dependencies():
    """
    Register model dependencies for invalidation.
    """
    try:
        from core.redis_invalidation import register_model_dependency

        for model_name, dependencies in MODEL_DEPENDENCIES.items():
            try:
                app_label, model_name = model_name.split(".")
                model_class = apps.get_model(app_label, model_name)

                for dependent_name in dependencies:
                    try:
                        dep_app_label, dep_model_name = dependent_name.split(".")
                        dependent_model = apps.get_model(dep_app_label, dep_model_name)
                        register_model_dependency(model_class, dependent_model)
                    except Exception as e:
                        logger.error(
                            f"Error registering dependency {dependent_name} "
                            f"for model {model_name}: {str(e)}"
                        )
            except Exception as e:
                logger.error(f"Error loading model {model_name}: {str(e)}")
    except ImportError:
        logger.warning("redis_invalidation module not available, skipping dependency registration")


# Cache optimization settings
CACHE_OPTIMIZATION = {
    # Model-specific optimization settings
    "model_settings": {
        # User-related models
        "accounts.User": {
            "max_memory_mb": 50,
            "max_entries": 10000,
            "eviction_policy": "lru",  # Least Recently Used
            "cache_related": ["profile"],
            "cache_exclude": ["password", "last_login"],
        },
        "accounts.Profile": {
            "max_memory_mb": 50,
            "max_entries": 10000,
            "eviction_policy": "lru",
            "cache_related": ["user"],
            "cache_exclude": ["user_files"],  # Exclude ImageField to avoid serialization issues
        },

        # Job-related models
        "jobs.Job": {
            "max_memory_mb": 100,
            "max_entries": 20000,
            "eviction_policy": "lru",
            "cache_related": ["client", "industry", "subcategory"],
            "cache_exclude": [],
        },
        "jobs.Application": {
            "max_memory_mb": 50,
            "max_entries": 50000,
            "eviction_policy": "lru",
            "cache_related": ["job", "applicant"],
            "cache_exclude": [],
        },
        "jobs.SavedJob": {
            "max_memory_mb": 20,
            "max_entries": 50000,
            "eviction_policy": "lru",
            "cache_related": ["job", "user"],
            "cache_exclude": [],
        },

        # Location-related models
        "userlocation.UserLocation": {
            "max_memory_mb": 50,
            "max_entries": 100000,
            "eviction_policy": "lru",
            "cache_related": ["user"],
            "cache_exclude": [],
        },
    },

    # Geocoding cache settings
    "geocoding": {
        "max_memory_mb": 100,
        "max_entries": 100000,
        "eviction_policy": "lru",
    },

    # Global settings
    "global": {
        "max_total_memory_mb": 500,  # 500 MB maximum total memory usage
        "stats_interval": 1000,  # Log stats every 1000 operations
        "monitoring_enabled": True,
        "auto_reconciliation": True,
        "reconciliation_interval": 60 * 60 * 24,  # 24 hours
    },
}

# Override optimization settings from settings if provided
CACHE_OPTIMIZATION_OVERRIDES = getattr(settings, "CACHE_OPTIMIZATION_OVERRIDES", {})
if CACHE_OPTIMIZATION_OVERRIDES:
    # Update global settings
    if "global" in CACHE_OPTIMIZATION_OVERRIDES:
        CACHE_OPTIMIZATION["global"].update(CACHE_OPTIMIZATION_OVERRIDES["global"])

    # Update model settings
    if "model_settings" in CACHE_OPTIMIZATION_OVERRIDES:
        for model_name, settings_dict in CACHE_OPTIMIZATION_OVERRIDES["model_settings"].items():
            if model_name in CACHE_OPTIMIZATION["model_settings"]:
                CACHE_OPTIMIZATION["model_settings"][model_name].update(settings_dict)
            else:
                CACHE_OPTIMIZATION["model_settings"][model_name] = settings_dict

    # Update geocoding settings
    if "geocoding" in CACHE_OPTIMIZATION_OVERRIDES:
        CACHE_OPTIMIZATION["geocoding"].update(CACHE_OPTIMIZATION_OVERRIDES["geocoding"])


def get_optimization_settings_for_model(model_class: Type[models.Model]) -> Dict[str, Any]:
    """
    Get optimization settings for a model.

    Args:
        model_class: Model class

    Returns:
        Dictionary with optimization settings
    """
    model_name = f"{model_class._meta.app_label}.{model_class.__name__}"

    if model_name in CACHE_OPTIMIZATION["model_settings"]:
        return CACHE_OPTIMIZATION["model_settings"][model_name]

    # Return default settings
    return {
        "max_memory_mb": 10,
        "max_entries": 1000,
        "eviction_policy": "lru",
        "cache_related": [],
        "cache_exclude": [],
    }


def log_optimization_settings():
    """Log the current cache optimization settings."""
    logger.info("Redis cache optimization settings:")

    # Log global settings
    global_settings = CACHE_OPTIMIZATION["global"]
    logger.info(f"  - Max total memory: {global_settings['max_total_memory_mb']} MB")
    logger.info(f"  - Stats interval: {global_settings['stats_interval']} operations")
    logger.info(f"  - Monitoring enabled: {global_settings['monitoring_enabled']}")
    logger.info(f"  - Auto reconciliation: {global_settings['auto_reconciliation']}")

    # Log geocoding settings
    geo_settings = CACHE_OPTIMIZATION["geocoding"]
    logger.info(f"  - Geocoding cache: {geo_settings['max_memory_mb']} MB max memory, "
               f"{geo_settings['max_entries']} max entries")

    # Log model-specific settings (sample)
    logger.info("  - Model-specific optimization settings configured for:")
    for model_name in CACHE_OPTIMIZATION["model_settings"].keys():
        logger.info(f"    - {model_name}")


# Register model dependencies when the module is imported
register_model_dependencies()

# Log optimization settings
log_optimization_settings()

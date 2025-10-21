"""
Redis settings and configuration.

This module centralizes all Redis-related settings and provides a consistent
configuration interface for all Redis-based features.
"""

import logging
from enum import Enum
from typing import Dict, Any, Optional, Type, Union

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

# Redis connection settings
REDIS_HOST = getattr(settings, "REDIS_HOST", "localhost")
REDIS_PORT = getattr(settings, "REDIS_PORT", 6379)
REDIS_PASSWORD = getattr(settings, "REDIS_PASSWORD", None)
REDIS_SSL = getattr(settings, "REDIS_SSL", False)

# Redis database indexes
REDIS_DB_CELERY = getattr(settings, "REDIS_DB_CELERY", 0)  # For Celery broker/backend
REDIS_DB_CACHE = getattr(settings, "REDIS_DB_CACHE", 1)    # For Django cache
REDIS_DB_SESSIONS = getattr(settings, "REDIS_DB_SESSIONS", 2)  # For Django sessions
REDIS_DB_CHANNELS = getattr(settings, "REDIS_DB_CHANNELS", 3)  # For Django Channels
REDIS_DB_GEOCODE = getattr(settings, "REDIS_DB_GEOCODE", 4)    # For geocoding cache

# Cache settings
# Default to False if Redis is not available
CACHE_ENABLED = getattr(settings, "CACHE_ENABLED", True)
CACHE_VERSION = getattr(settings, "CACHE_VERSION", "1.0")  # Increment when data schema changes
CACHE_DEFAULT_TIMEOUT = getattr(settings, "CACHE_DEFAULT_TIMEOUT", 60 * 60 * 24)  # 24 hours
CACHE_STATS_INTERVAL = getattr(settings, "CACHE_STATS_INTERVAL", 100)  # Log stats every N operations
CACHE_FALLBACK_TO_DB = getattr(settings, "CACHE_FALLBACK_TO_DB", True)  # Fallback to database if Redis is unavailable

# Cache timeouts by data type (in seconds)
CACHE_TIMEOUTS = {
    "user": getattr(settings, "CACHE_TIMEOUT_USER", 60 * 60 * 24),  # 24 hours
    "job": getattr(settings, "CACHE_TIMEOUT_JOB", 60 * 60 * 2),  # 2 hours
    "application": getattr(settings, "CACHE_TIMEOUT_APPLICATION", 60 * 30),  # 30 minutes
    "profile": getattr(settings, "CACHE_TIMEOUT_PROFILE", 60 * 60 * 12),  # 12 hours
    "industry": getattr(settings, "CACHE_TIMEOUT_INDUSTRY", 60 * 60 * 24 * 7),  # 7 days
    "subcategory": getattr(settings, "CACHE_TIMEOUT_SUBCATEGORY", 60 * 60 * 24 * 7),  # 7 days
    "whoami": getattr(settings, "CACHE_TIMEOUT_WHOAMI", 60 * 15),  # 15 minutes
    "api": getattr(settings, "CACHE_TIMEOUT_API", 60 * 5),  # 5 minutes
    "query": getattr(settings, "CACHE_TIMEOUT_QUERY", 60 * 10),  # 10 minutes
    "model": getattr(settings, "CACHE_TIMEOUT_MODEL", 60 * 60 * 24),  # 24 hours
    "default": CACHE_DEFAULT_TIMEOUT,
}

# TTL mapping by namespace enum
NAMESPACE_ENUM_TTL_MAP = {
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


def get_ttl_for_namespace(namespace: Union[str, CacheNamespace]) -> int:
    """
    Get the TTL for a namespace.

    Args:
        namespace: Cache namespace

    Returns:
        TTL in seconds
    """
    # If namespace is an enum, convert to string
    if isinstance(namespace, CacheNamespace):
        if namespace in NAMESPACE_ENUM_TTL_MAP:
            return NAMESPACE_ENUM_TTL_MAP[namespace]
        namespace_str = namespace.value
    else:
        namespace_str = namespace

    # Remove trailing colon if present
    if namespace_str.endswith(':'):
        namespace_str = namespace_str[:-1]

    # Check if namespace is in the string map
    if namespace_str in CACHE_TIMEOUTS:
        return CACHE_TIMEOUTS[namespace_str]

    # Try to match with enum value
    try:
        enum_namespace = CacheNamespace(namespace_str)
        if enum_namespace in NAMESPACE_ENUM_TTL_MAP:
            return NAMESPACE_ENUM_TTL_MAP[enum_namespace]
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

    # Check model-specific TTL in settings
    model_ttl_map = getattr(settings, "CACHE_MODEL_TTL_MAP", {})
    if model_name in model_ttl_map:
        return model_ttl_map[model_name]

    # Try to match with namespace
    namespace = model_class.__name__.lower()
    return get_ttl_for_namespace(namespace)

# Model cache settings
MODEL_CACHE_ENABLED = getattr(settings, "MODEL_CACHE_ENABLED", True)
MODEL_CACHE_EXPIRATION = getattr(settings, "MODEL_CACHE_EXPIRATION", 60 * 60 * 24)  # 24 hours
MODEL_CACHE_PREFIX = getattr(settings, "MODEL_CACHE_PREFIX", "model:")

# Geocoding cache settings
GEOCODE_CACHE_ENABLED = getattr(settings, "GEOCODE_CACHE_ENABLED", True)
GEOCODE_CACHE_EXPIRATION = getattr(settings, "GEOCODE_CACHE_EXPIRATION", 60 * 60 * 24 * 30)  # 30 days
GEOCODE_CACHE_PREFIX = getattr(settings, "GEOCODE_CACHE_PREFIX", "geocode:")

# Rate limiting settings
RATE_LIMIT_ENABLED = getattr(settings, "RATE_LIMIT_ENABLED", True)
RATE_LIMIT_DEFAULT = getattr(settings, "RATE_LIMIT_DEFAULT", 100)  # Requests per minute
RATE_LIMIT_PREFIX = getattr(settings, "RATE_LIMIT_PREFIX", "ratelimit:")

# Pub/Sub settings
PUBSUB_ENABLED = getattr(settings, "PUBSUB_ENABLED", True)

# Feature flags settings
FEATURE_FLAGS_NAMESPACE = getattr(settings, "FEATURE_FLAGS_NAMESPACE", "feature_flags")

# Redis URL helpers
def get_redis_url(db: int = REDIS_DB_CACHE) -> str:
    """
    Get a Redis URL for the specified database.

    Args:
        db: Redis database index

    Returns:
        Redis URL string
    """
    protocol = "rediss" if REDIS_SSL else "redis"
    auth = f":{REDIS_PASSWORD}@" if REDIS_PASSWORD else ""
    return f"{protocol}://{auth}{REDIS_HOST}:{REDIS_PORT}/{db}"

def get_redis_connection_params(db: int = REDIS_DB_CACHE) -> Dict[str, Any]:
    """
    Get Redis connection parameters for the specified database.

    Args:
        db: Redis database index

    Returns:
        Dictionary of connection parameters
    """
    return {
        "host": REDIS_HOST,
        "port": REDIS_PORT,
        "db": db,
        "password": REDIS_PASSWORD,
        "ssl": REDIS_SSL,
        "decode_responses": True,
        "socket_timeout": 5,
        "health_check_interval": 30,
    }

# Redis connection URLs for different services
REDIS_URL_CELERY = get_redis_url(REDIS_DB_CELERY)
REDIS_URL_CACHE = get_redis_url(REDIS_DB_CACHE)
REDIS_URL_SESSIONS = get_redis_url(REDIS_DB_SESSIONS)
REDIS_URL_CHANNELS = get_redis_url(REDIS_DB_CHANNELS)
REDIS_URL_GEOCODE = get_redis_url(REDIS_DB_GEOCODE)

# Log Redis configuration
logger.info(f"Redis configuration:")
logger.info(f"  - Host: {REDIS_HOST}")
logger.info(f"  - Port: {REDIS_PORT}")
logger.info(f"  - SSL: {REDIS_SSL}")
logger.info(f"  - Celery DB: {REDIS_DB_CELERY}")
logger.info(f"  - Cache DB: {REDIS_DB_CACHE}")
logger.info(f"  - Sessions DB: {REDIS_DB_SESSIONS}")
logger.info(f"  - Channels DB: {REDIS_DB_CHANNELS}")
logger.info(f"  - Geocode DB: {REDIS_DB_GEOCODE}")
logger.info(f"  - Cache enabled: {CACHE_ENABLED}")
logger.info(f"  - Cache version: {CACHE_VERSION}")
logger.info(f"  - Model cache enabled: {MODEL_CACHE_ENABLED}")
logger.info(f"  - Geocode cache enabled: {GEOCODE_CACHE_ENABLED}")
logger.info(f"  - Rate limiting enabled: {RATE_LIMIT_ENABLED}")
logger.info(f"  - Pub/Sub enabled: {PUBSUB_ENABLED}")

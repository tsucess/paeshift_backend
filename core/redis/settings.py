"""
Redis settings module.

This module provides all Redis-related settings for the application,
consolidating settings from various files into a single location.
"""

import logging
from typing import Any, Dict, Optional

from django.conf import settings

# Set up logging
logger = logging.getLogger(__name__)

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
CACHE_ENABLED = getattr(settings, "CACHE_ENABLED", True)
CACHE_VERSION = getattr(settings, "CACHE_VERSION", "1.0")  # Increment when data schema changes
CACHE_DEFAULT_TIMEOUT = getattr(settings, "CACHE_DEFAULT_TIMEOUT", 60 * 60 * 24)  # 24 hours
CACHE_STATS_INTERVAL = getattr(settings, "CACHE_STATS_INTERVAL", 100)  # Log stats every N operations
CACHE_FALLBACK_TO_DB = getattr(settings, "CACHE_FALLBACK_TO_DB", True)  # Fallback to database if Redis is unavailable

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
RATE_LIMIT_PREFIX = getattr(settings, "RATE_LIMIT_PREFIX", "ratelimit:")

# Cache timeouts by data type (in seconds)
CACHE_TIMEOUTS = {
    "user": getattr(settings, "CACHE_TIMEOUT_USER", 60 * 60 * 24),  # 24 hours
    "job": getattr(settings, "CACHE_TIMEOUT_JOB", 60 * 60 * 12),  # 12 hours
    "application": getattr(settings, "CACHE_TIMEOUT_APPLICATION", 60 * 60 * 6),  # 6 hours
    "profile": getattr(settings, "CACHE_TIMEOUT_PROFILE", 60 * 60 * 24),  # 24 hours
    "industry": getattr(settings, "CACHE_TIMEOUT_INDUSTRY", 60 * 60 * 24 * 7),  # 7 days
    "subcategory": getattr(settings, "CACHE_TIMEOUT_SUBCATEGORY", 60 * 60 * 24 * 7),  # 7 days
    "whoami": getattr(settings, "CACHE_TIMEOUT_WHOAMI", 60 * 60),  # 1 hour
    "api": getattr(settings, "CACHE_TIMEOUT_API", 60 * 15),  # 15 minutes
    "query": getattr(settings, "CACHE_TIMEOUT_QUERY", 60 * 5),  # 5 minutes
    "default": CACHE_DEFAULT_TIMEOUT,
}

# Cache prefixes by data type
CACHE_PREFIXES = {
    "user": "user:",
    "job": "job:",
    "application": "app:",
    "profile": "profile:",
    "industry": "industry:",
    "subcategory": "subcat:",
    "whoami": "whoami:",
    "api": "api:",
    "query": "query:",
    "default": "cache:",
    # Advanced features
    "ranking": "rank:",
    "activity": "activity:",
    "presence": "presence:",
    "notification": "notif:",
    "leaderboard": "leaderboard:",
    "lock": "lock:",
    "rate_limit": "ratelimit:",
}

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

"""
Redis cache settings.

This module provides settings for the Redis cache.
"""

import logging
from enum import Enum
from typing import Dict, Any, Optional

from django.conf import settings

# Set up logging
logger = logging.getLogger(__name__)

# Redis connection settings
REDIS_HOST = getattr(settings, "REDIS_HOST", "localhost")
REDIS_PORT = getattr(settings, "REDIS_PORT", 6379)
REDIS_PASSWORD = getattr(settings, "REDIS_PASSWORD", None)
REDIS_DB_CACHE = getattr(settings, "REDIS_DB_CACHE", 0)
REDIS_DB_SESSIONS = getattr(settings, "REDIS_DB_SESSIONS", 1)
REDIS_DB_CELERY = getattr(settings, "REDIS_DB_CELERY", 2)
REDIS_DB_CHANNELS = getattr(settings, "REDIS_DB_CHANNELS", 3)


def get_redis_connection_params(db=None):
    """
    Get Redis connection parameters.

    Args:
        db: Redis database number

    Returns:
        Dictionary with Redis connection parameters
    """
    params = {
        "host": REDIS_HOST,
        "port": REDIS_PORT,
        "db": db if db is not None else REDIS_DB_CACHE,
    }

    if REDIS_PASSWORD:
        params["password"] = REDIS_PASSWORD

    return params

# Cache settings
CACHE_ENABLED = True
CACHE_VERSION = "1.0"
CACHE_DEFAULT_TIMEOUT = 3600  # 1 hour
CACHE_STATS_INTERVAL = 1000  # Log stats every 1000 operations

# Cache prefixes
CACHE_PREFIXES = {
    "api": "api",
    "function": "func",
    "model": "model",
    "user": "user",
    "job": "job",
    "application": "app",
    "notification": "notif",
    "location": "loc",
    "payment": "pay",
    "review": "review",
    "default": "cache",
}

# Cache timeouts (in seconds)
CACHE_TIMEOUTS = {
    "api": 300,  # 5 minutes
    "function": 600,  # 10 minutes
    "model": 1800,  # 30 minutes
    "user": 3600,  # 1 hour
    "job": 1800,  # 30 minutes
    "application": 1800,  # 30 minutes
    "notification": 300,  # 5 minutes
    "location": 86400,  # 24 hours
    "payment": 3600,  # 1 hour
    "review": 3600,  # 1 hour
    "default": 3600,  # 1 hour
}

# Model cache settings
MODEL_CACHE_ENABLED = True
MODEL_CACHE_PREFIX = "model"
MODEL_CACHE_EXPIRATION = 3600  # 1 hour

# Cache namespaces
class CacheNamespace(str, Enum):
    """Cache namespace enum."""
    API = "api"
    FUNCTION = "function"
    MODEL = "model"
    USER = "user"
    JOB = "job"
    APPLICATION = "application"
    NOTIFICATION = "notification"
    LOCATION = "location"
    PAYMENT = "payment"
    REVIEW = "review"
    DEFAULT = "default"

# Cache TTL enum
class CacheTTL(int, Enum):
    """Cache TTL enum."""
    VERY_SHORT = 60  # 1 minute
    SHORT = 300  # 5 minutes
    MEDIUM = 1800  # 30 minutes
    LONG = 3600  # 1 hour
    VERY_LONG = 86400  # 24 hours
    PERMANENT = -1  # No expiration

def get_ttl_for_namespace(namespace: str) -> int:
    """
    Get the TTL for a namespace.

    Args:
        namespace: Cache namespace

    Returns:
        TTL in seconds
    """
    return CACHE_TIMEOUTS.get(namespace, CACHE_DEFAULT_TIMEOUT)

def get_prefix_for_namespace(namespace: str) -> str:
    """
    Get the prefix for a namespace.

    Args:
        namespace: Cache namespace

    Returns:
        Cache prefix
    """
    return CACHE_PREFIXES.get(namespace, CACHE_PREFIXES["default"])

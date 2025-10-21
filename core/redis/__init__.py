"""
Redis caching module for the Payshift application.

This module provides a comprehensive Redis caching system that can be used
across all applications to cache API responses, database queries, and other
expensive operations.

The module is organized into the following submodules:
- decorators: Decorators for caching function results and API responses
- models: Utilities for caching Django model instances
- monitoring: Tools for monitoring Redis cache health and performance
- warming: Utilities for warming the cache
- utils: Utility functions for working with Redis

Usage:
    from core.redis import cache_api_response, RedisCachedModel, warm_cache
"""

import logging

# Set up logging
logger = logging.getLogger(__name__)

# Import core functionality
from core.redis.settings import CACHE_ENABLED, CACHE_VERSION
from core.redis.client import redis_client, get_redis_client

# Import decorators
from core.redis.decorators import (
    cache_api_response,
    cache_function,
    no_cache,
    cache_method_result,
    use_cached_model,
)

# Import model caching
from core.redis.models import (
    RedisCachedModel,
    cache_model,
    get_cached_model,
    invalidate_model_cache,
)

# Import timestamp validation
from core.redis.timestamp import (
    validate_with_timestamp,
    invalidate_on_timestamp_change,
)

# Import cache warming
from core.redis.warming import (
    warm_cache,
    warm_model_cache,
    warm_critical_models,
)

# Import monitoring
from core.redis.monitoring import (
    get_cache_stats,
    record_stats,
    get_dashboard_data,
)

# Log module initialization
logger.info(f"Redis caching module initialized (enabled={CACHE_ENABLED}, version={CACHE_VERSION})")

__all__ = [
    # Core
    "CACHE_ENABLED",
    "CACHE_VERSION",
    "redis_client",
    "get_redis_client",
    
    # Decorators
    "cache_api_response",
    "cache_function",
    "no_cache",
    "cache_method_result",
    "use_cached_model",
    
    # Model caching
    "RedisCachedModel",
    "cache_model",
    "get_cached_model",
    "invalidate_model_cache",
    
    # Timestamp validation
    "validate_with_timestamp",
    "invalidate_on_timestamp_change",
    
    # Cache warming
    "warm_cache",
    "warm_model_cache",
    "warm_critical_models",
    
    # Monitoring
    "get_cache_stats",
    "record_stats",
    "get_dashboard_data",
]

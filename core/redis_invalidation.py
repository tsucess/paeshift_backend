"""
Compatibility module for core.redis_invalidation.

This module provides backward compatibility with the old Redis invalidation system.
It imports and re-exports the invalidation functions from the new standardized Redis caching module.
"""

import logging
from typing import Any, Optional, Type, Union

# Import Django models
from django.db import models

# Import invalidation functions from the new module
from core.redis.redis_invalidation import (
    invalidate_model_cache,
    invalidate_function_cache,
    invalidate_api_cache,
)

# Set up logging
logger = logging.getLogger(__name__)

# Re-export all functions
__all__ = [
    "invalidate_model_cache",
    "invalidate_function_cache",
    "invalidate_api_cache",
]

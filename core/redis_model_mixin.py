"""
Compatibility module for Redis model mixin.

This module provides backward compatibility for code that imports RedisCachedModelMixin
from core.redis_model_mixin.
"""

# Import the RedisCachedModelMixin from the new location
from core.redis.models import RedisCachedModelMixin

# Re-export the class
__all__ = ['RedisCachedModelMixin']

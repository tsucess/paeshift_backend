"""
Redis model mixin for Django models.

This module provides a mixin for Django models to easily integrate with Redis caching.

DEPRECATED: This module is maintained for backward compatibility.
Please use core.redis_model_mixins instead.
"""

# Import from the consolidated module for backward compatibility
from core.redis_model_mixins import RedisCachedModel as _RedisCachedModel
import logging

logger = logging.getLogger(__name__)


class RedisCachedModelMixin(_RedisCachedModel):
    """
    Mixin for Django models to easily integrate with Redis caching.

    This mixin provides methods for caching model instances in Redis
    and keeping the cache in sync with database changes.

    DEPRECATED: This class is maintained for backward compatibility.
    Please use RedisCachedModel from core.redis_model_mixins instead.
    """
    class Meta:
        abstract = True

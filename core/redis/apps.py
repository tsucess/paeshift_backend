"""
Redis app configuration.
"""

import logging

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

# Set up logging
logger = logging.getLogger(__name__)


class RedisConfig(AppConfig):
    """
    Redis app configuration.
    """

    name = "core.redis"
    verbose_name = _("Redis Cache")
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        """
        Initialize the Redis app.
        """
        logger.info("Initializing Redis app")

        # Import settings to initialize Redis client
        from core.redis.settings import CACHE_ENABLED, CACHE_VERSION
        from core.redis.client import redis_client

        # Log Redis status
        if redis_client:
            logger.info(f"Redis cache initialized (enabled={CACHE_ENABLED}, version={CACHE_VERSION})")
        else:
            logger.warning("Redis client not available, caching will be disabled")

        # Set up cache warming on startup if enabled
        try:
            from django.conf import settings
            if getattr(settings, "REDIS_WARM_CACHE_ON_STARTUP", False):
                logger.info("Setting up cache warming on startup")
                from core.redis.warming import warm_critical_models
                import threading
                threading.Thread(target=warm_critical_models).start()
        except Exception as e:
            logger.error(f"Error setting up cache warming on startup: {str(e)}")

        # Set up scheduled cache warming if enabled
        try:
            from django.conf import settings
            if getattr(settings, "REDIS_WARM_CACHE_SCHEDULED", False):
                logger.info("Setting up scheduled cache warming")
                from core.redis.warming import setup_cache_warming_schedule
                setup_cache_warming_schedule()
        except Exception as e:
            logger.error(f"Error setting up scheduled cache warming: {str(e)}")

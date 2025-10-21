from django.apps import AppConfig
import logging
import threading
import time

logger = logging.getLogger(__name__)


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Core"

    def ready(self):
        """
        Initialize the core app.
        """
        # Import signals
        import core.signals

        # Import cache signals for Phase 2.2c
        try:
            import core.cache_signals
            core.cache_signals.register_cache_signals()
        except Exception as e:
            logger.warning(f"Failed to register cache signals: {str(e)}")

        # Only run in the main thread to avoid running twice in development
        if threading.current_thread() == threading.main_thread():
            # Delay database operations to avoid accessing the database during initialization
            self._setup_delayed_tasks()

    def _setup_delayed_tasks(self):
        """
        Set up tasks with a delay to avoid database access during initialization.
        """
        import threading

        def delayed_setup():
            # Wait for Django to fully initialize
            time.sleep(5)

            # Now it's safe to access the database
            try:
                # Set up scheduled tasks
                from core.scheduler import setup_scheduled_tasks
                setup_scheduled_tasks()

                # Set up Redis cache warming if enabled
                try:
                    from django.conf import settings
                    if getattr(settings, "REDIS_WARM_CACHE_ON_STARTUP", False):
                        logger.info("Setting up Redis cache warming on startup")
                        from core.redis.warming import warm_critical_models
                        warm_critical_models()

                    if getattr(settings, "REDIS_WARM_CACHE_SCHEDULED", False):
                        logger.info("Setting up scheduled Redis cache warming")
                        from core.redis.warming import setup_cache_warming_schedule
                        setup_cache_warming_schedule()
                except Exception as e:
                    logger.error(f"Failed to set up Redis cache warming: {str(e)}")
            except Exception as e:
                logger.error(f"Failed to set up scheduled tasks: {str(e)}")

        # Start a thread to set up tasks after initialization
        thread = threading.Thread(target=delayed_setup)
        thread.daemon = True
        thread.start()

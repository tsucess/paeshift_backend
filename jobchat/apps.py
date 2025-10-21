from django.apps import AppConfig


class JobchatConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "jobchat"
    verbose_name = "Job Chat"  # Added human-readable name

    def ready(self):
        # Import signals or other startup code here if needed
        pass


class JobsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "jobs"
    verbose_name = "Job Listings"  # Added human-readable name

    def ready(self):
        # Removed unnecessary get_user_model() call
        # Import signals here instead if needed
        from . import signals  # Example if you have signals

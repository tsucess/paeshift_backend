from django.apps import AppConfig
from django.conf import settings

class RatingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "rating"

    def ready(self):
        # Import signals from the rating app instead of reviews
        import rating.signals

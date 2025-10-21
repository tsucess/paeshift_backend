"""
URL configuration for gamification app.
"""
from django.urls import path
from ninja import NinjaAPI

# Create a simple API instance for gamification
gamification_api = NinjaAPI(title="Gamification API", version="1.0.0")

# For now, just create empty URL patterns
urlpatterns = [
    path("", gamification_api.urls),
]

from django.urls import path
from ninja import NinjaAPI

from .api import location_router  # Import your router

# Create API instance with proper naming
location_api = NinjaAPI(
    version="1.0.15",  # Sequential version number
    docs_url="/docs",
    openapi_url="/openapi.json",
    # csrf=True,  # Not supported in this version of django-ninja
    urls_namespace="location_api",  # Added namespace
)

# Mount the router with clear path prefix
location_api.add_router("/", location_router, tags=["location"])

urlpatterns = [
    path("", location_api.urls),
]

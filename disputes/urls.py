# disputes/urls.py

from django.urls import path
from ninja import NinjaAPI

from .api import \
    disputes_router  # your Router() with @disputes_router.get/post

# Create a mini-API for disputes
disputes_api = NinjaAPI(
    title="Disputes API",
    version="7.0.0",  # Sequential version number
    docs_url="/docs",  # → /disputes/docs
    openapi_url="/openapi.json",  # → /disputes/openapi.json
    urls_namespace="disputes_api",  # Added namespace
)

# Mount the disputes router to the mini-API
disputes_api.add_router("/disputes", disputes_router)

urlpatterns = [
    path("", disputes_api.urls),  # Ensure the namespace and prefix match
]

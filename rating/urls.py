from django.urls import path
from ninja import NinjaAPI

from .api import rating_router  # Corrected import, use rating_router

# Create a NinjaAPI instance for this app
api = NinjaAPI(
    title="Rating API",
    version="1.0.19",
    docs_url="/docs",  # Swagger UI at /rating/docs
    openapi_url="/openapi.json",  # OpenAPI schema at /rating/openapi.json
    urls_namespace="rating_api",
)

# Mount the Rating router
api.add_router("", rating_router)

urlpatterns = [
    # Exposes all routes under the /rating path
    path("", api.urls),
]

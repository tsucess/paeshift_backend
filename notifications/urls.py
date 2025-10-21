from django.urls import path
from ninja import NinjaAPI

from .api import notifications_router  # this should be a Router()

# Create a dedicated NinjaAPI instance
api = NinjaAPI(
    version="1.0.5",  # Sequential version number
    docs_url="/docs",
    openapi_url="/openapi.json",
    urls_namespace="notifications_api",  # Added namespace
)

# Mount your Router to the API
api.add_router("", notifications_router)

urlpatterns = [
    path("", api.urls),
]

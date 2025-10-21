# jobchat/urls.py
from django.urls import path
from ninja import NinjaAPI

from .views import *

# from .api import router  # your router with the update-location endpoint

api = NinjaAPI(
    title="Chat API",
    version="4.0.0",  # Sequential version number
    docs_url="/docs",  # Swagger UI at /rating/docs
    openapi_url="/openapi.json",  # OpenAPI schema at /rating/openapi.json
    urls_namespace="chat_api",  # Added namespace
)

urlpatterns = [
# urls.py
    path("profile/<int:user_id>/", profile, name="profile"),

    
    path("chat/<int:job_id>/", chat_room, name="chat_room"),
    path("api/messages/<int:job_id>/", get_messages, name="get_messages"),
    path("api/locations/<int:job_id>/", get_job_locations, name="get_job_locations"),
    path("api/", api.urls),  # all Ninja routes are now under /api/
]

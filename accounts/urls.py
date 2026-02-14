from django.urls import path
from ninja import NinjaAPI

from .api import accounts_router
from .social_api import social_router
from .otp_api import otp_router
from . import views

accounts_api = NinjaAPI(
    title="Accounts API",
    version="1.0.0",  # Sequential version number
    description="Account management functionality",
    urls_namespace="accounts_api",  # Added namespace
    # csrf=False,  # Not supported in this version of django-ninja
    auth=None,  # Make authentication optional - CONFIGURE IN PRODUCTION!
)

# Add the routers to the API
accounts_api.add_router("/", accounts_router)
accounts_api.add_router("/social/", social_router)
accounts_api.add_router("/otp/", otp_router)
urlpatterns = [
    path("", accounts_api.urls),
    # path("send-otp/", views.send_otp_view, name="send_otp"),
    # path("verify-otp/", views.verify_otp_view, name="verify_otp"),
]


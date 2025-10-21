from django.urls import path
from ninja import NinjaAPI

# from godmode.monitoring import clear_cache_view, geocoding_stats_view, test_geocoding_view  # Temporarily commented out

from .api import core_router
from .applicant import applicant_router
from .client import client_router
from .shift import shift_router

jobs_api = NinjaAPI(
    version="1.0.21",
    urls_namespace="jobs_api_v1",
)

jobs_api.add_router("", core_router)
jobs_api.add_router("clients/", client_router)
jobs_api.add_router("applicants/", applicant_router)
jobs_api.add_router("shifts/", shift_router)


urlpatterns = [
    path("", jobs_api.urls),
    # Temporarily commented out - depends on godmode app
    # path("monitoring/geocoding-stats/", geocoding_stats_view, name="geocoding_stats"),
    # path("monitoring/clear-cache/", clear_cache_view, name="clear_cache"),
    # path("monitoring/test-geocoding/", test_geocoding_view, name="test_geocoding"),
]

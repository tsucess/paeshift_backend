# payment/urls.py
from django.urls import path
from django.contrib.admin.views.decorators import staff_member_required
from ninja import NinjaAPI

from .admin_views import (
    webhook_dashboard,
    webhook_stats,
    process_batch,
    cleanup_queue,
    retry_failed,
    retry_webhook,
)
from .api import payments_router  # Import the payments_router from api.py
from .webhooks import flutterwave_webhook, paystack_webhook

# Create a NinjaAPI instance for this app
api = NinjaAPI(
    version="1.0.18",  # Sequential version number
    docs_url="/docs",  # Swagger UI at /payment/docs
    openapi_url="/openapi.json",  # OpenAPI schema at /payment/openapi.json
    urls_namespace="payment_api",  # Added namespace
)

# Mount the Payment router
api.add_router("", payments_router)


from .views import paystack_webhook, verify_payment_view


urlpatterns = [
    # Exposes all routes under the /payment path
    path("", api.urls),

    # Webhook endpoints
    path("webhooks/flutterwave/", flutterwave_webhook, name="flutterwave_webhook"),
    path('paystack/webhook/', paystack_webhook, name='paystack_webhook'),
    # path("verify-payment/", verify_payment_view, name="verify_payment"),
    
    path("verify/", verify_payment_view, name="verify_payment"),

    
    # Admin views
    path("admin/webhook-dashboard/", staff_member_required(webhook_dashboard), name="webhook_dashboard"),
    path("admin/webhook-stats/", staff_member_required(webhook_stats), name="webhook_stats"),
    path("admin/process-batch/", staff_member_required(process_batch), name="process_batch"),
    path("admin/cleanup-queue/", staff_member_required(cleanup_queue), name="cleanup_queue"),
    path("admin/retry-failed/", staff_member_required(retry_failed), name="retry_failed"),
    path("admin/retry-webhook/<str:webhook_id>/", staff_member_required(retry_webhook), name="retry_webhook"),
]





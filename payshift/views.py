"""
Root views for the payshift project.
"""
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods


@require_http_methods(["GET"])
def health_check(request):
    """
    Health check endpoint for the API.
    Returns a simple JSON response indicating the API is running.
    """
    return JsonResponse({
        "status": "ok",
        "message": "Payshift API is running",
        "service": "payshift-backend"
    })


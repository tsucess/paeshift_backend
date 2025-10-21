"""
Webhook-related views for God Mode.

This module provides views for managing webhooks in God Mode.
"""

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render


@staff_member_required
def webhook_logs(request):
    """
    View for listing webhook logs.
    
    Args:
        request: HTTP request
        
    Returns:
        Rendered webhook logs template
    """
    context = {
        "title": "Webhook Logs",
    }
    return render(request, "godmode/webhook_logs.html", context)


@staff_member_required
def webhook_log_detail(request, log_id):
    """
    View for webhook log details.
    
    Args:
        request: HTTP request
        log_id: Log ID
        
    Returns:
        Rendered webhook log detail template
    """
    context = {
        "title": "Webhook Log Detail",
        "log_id": log_id,
    }
    return render(request, "godmode/webhook_log_detail.html", context)

"""
Security-related views for God Mode.

This module provides views for security features in God Mode.
"""

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render


@staff_member_required
def security_dashboard(request):
    """
    View for security dashboard.
    
    Args:
        request: HTTP request
        
    Returns:
        Rendered security dashboard template
    """
    context = {
        "title": "Security Dashboard",
    }
    return render(request, "godmode/security_dashboard.html", context)


@staff_member_required
def ip_whitelist_view(request):
    """
    View for IP whitelist.
    
    Args:
        request: HTTP request
        
    Returns:
        Rendered IP whitelist template
    """
    context = {
        "title": "IP Whitelist",
    }
    return render(request, "godmode/ip_whitelist.html", context)


@staff_member_required
def ip_whitelist_add_view(request):
    """
    View for adding to IP whitelist.
    
    Args:
        request: HTTP request
        
    Returns:
        Rendered add to IP whitelist template
    """
    context = {
        "title": "Add to IP Whitelist",
    }
    return render(request, "godmode/ip_whitelist_add.html", context)


@staff_member_required
def ip_whitelist_delete_view(request, whitelist_id):
    """
    View for deleting from IP whitelist.
    
    Args:
        request: HTTP request
        whitelist_id: Whitelist ID
        
    Returns:
        Rendered delete from IP whitelist template
    """
    context = {
        "title": "Delete from IP Whitelist",
        "whitelist_id": whitelist_id,
    }
    return render(request, "godmode/ip_whitelist_delete.html", context)


@staff_member_required
def audit_logs_view(request):
    """
    View for audit logs.
    
    Args:
        request: HTTP request
        
    Returns:
        Rendered audit logs template
    """
    context = {
        "title": "Audit Logs",
    }
    return render(request, "godmode/audit_logs.html", context)


@staff_member_required
def audit_log_detail_view(request, log_id):
    """
    View for audit log details.
    
    Args:
        request: HTTP request
        log_id: Log ID
        
    Returns:
        Rendered audit log detail template
    """
    context = {
        "title": "Audit Log Detail",
        "log_id": log_id,
    }
    return render(request, "godmode/audit_log_detail.html", context)

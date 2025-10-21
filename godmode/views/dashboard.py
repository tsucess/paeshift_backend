"""
Dashboard views for God Mode.

This module provides views for the God Mode dashboard.
"""

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render


@staff_member_required
def godmode_dashboard(request):
    """
    Main dashboard view for God Mode.
    
    Args:
        request: HTTP request
        
    Returns:
        Rendered dashboard template
    """
    context = {
        "title": "God Mode Dashboard",
    }
    return render(request, "godmode/dashboard.html", context)

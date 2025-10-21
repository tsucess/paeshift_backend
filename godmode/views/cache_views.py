"""
Cache-related views for God Mode.

This module provides views for cache management in God Mode.
"""

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render


@staff_member_required
def cache_sync_view(request):
    """
    View for cache synchronization.
    
    Args:
        request: HTTP request
        
    Returns:
        Rendered cache sync template
    """
    context = {
        "title": "Cache Synchronization",
    }
    return render(request, "godmode/cache_sync.html", context)

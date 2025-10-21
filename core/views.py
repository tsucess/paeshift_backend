"""
Core views module.

This module provides views for the Redis dashboard and other core functionality.
"""

import logging

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.utils import timezone

from core.redis_monitoring import get_cache_stats
from core.redis_settings import CACHE_ENABLED

logger = logging.getLogger(__name__)


@staff_member_required
def redis_dashboard_view(request):
    """
    Redis dashboard view.
    
    This view renders the Redis dashboard template with initial data.
    The dashboard then uses AJAX to fetch real-time data.
    
    Args:
        request: HTTP request
        
    Returns:
        Rendered dashboard template
    """
    if not CACHE_ENABLED:
        return render(
            request,
            "admin/error.html",
            {"title": "Redis Error", "error": "Redis cache is disabled"},
        )
        
    # Get initial stats
    try:
        stats = get_cache_stats()
    except Exception as e:
        logger.error(f"Error getting Redis stats: {str(e)}")
        stats = {"error": str(e)}
        
    context = {
        "title": "Redis Dashboard",
        "stats": stats,
        "timestamp": timezone.now().isoformat(),
    }
    
    return render(request, "admin/redis_dashboard.html", context)

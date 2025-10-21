"""
Monitoring views for the godmode application.

This module provides views for monitoring various aspects of the application,
including geocoding performance, cache statistics, and system health.
"""

import json
import logging
from datetime import datetime, timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from jobs.geocoding import geocode_address
from jobs.geocoding_cache import get_cache_stats
from jobs.geocoding_monitor import GeocodingMetrics

logger = logging.getLogger(__name__)


@staff_member_required
@never_cache
@require_GET
def geocoding_dashboard(request):
    """
    View function for the geocoding monitoring dashboard.
    
    This view renders a dashboard with detailed geocoding metrics and statistics.
    """
    return render(request, 'godmode/geocoding_dashboard.html', {
        'title': 'Geocoding Monitoring Dashboard',
        'refresh_interval': 30,  # seconds
    })


@staff_member_required
@never_cache
@require_GET
def geocoding_metrics_api(request):
    """
    API endpoint for geocoding metrics.
    
    This endpoint returns detailed metrics about the geocoding system,
    including performance, cache hit rates, and error statistics.
    """
    metrics = GeocodingMetrics.get_metrics()
    return JsonResponse(metrics)


@staff_member_required
@never_cache
@require_GET
def test_geocoding_api(request):
    """
    API endpoint to test geocoding for a specific address.
    
    This endpoint allows testing the geocoding system with a specific address
    and provider, and returns detailed results.
    """
    address = request.GET.get('address', '')
    provider = request.GET.get('provider', None)
    
    if not address:
        return JsonResponse({
            'success': False,
            'error': 'Address parameter is required',
        }, status=400)
    
    # Perform geocoding
    start_time = timezone.now()
    result = geocode_address(address, provider)
    elapsed_time = (timezone.now() - start_time).total_seconds()
    
    # Add timing information if not already present
    if 'total_time' not in result:
        result['total_time'] = elapsed_time
    
    # Add timestamp
    result['timestamp'] = timezone.now().isoformat()
    
    return JsonResponse(result)


@staff_member_required
@never_cache
@require_GET
def cache_stats_api(request):
    """
    API endpoint for cache statistics.
    
    This endpoint returns detailed statistics about the Redis cache,
    including memory usage, hit rates, and key distribution.
    """
    stats = get_cache_stats()
    
    # Add timestamp
    stats['timestamp'] = timezone.now().isoformat()
    
    return JsonResponse(stats)

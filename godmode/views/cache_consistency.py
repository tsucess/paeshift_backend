"""
Views for cache consistency monitoring and management.

This module provides views for monitoring cache consistency and triggering
reconciliation when needed.
"""

import json
import logging
from datetime import datetime

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from godmode.cache_sync import check_cache_consistency, reconcile_cache_for_model
from godmode.tasks.cache_tasks import get_cacheable_models, check_all_models_consistency

logger = logging.getLogger(__name__)

# Constants
CONSISTENCY_STATS_KEY_PREFIX = 'cache_consistency:stats:'


@staff_member_required
def cache_consistency_dashboard(request: HttpRequest) -> HttpResponse:
    """
    Display cache consistency dashboard.
    
    Args:
        request: HTTP request
        
    Returns:
        HTTP response
    """
    # Get all cacheable models
    models = get_cacheable_models()
    
    # Get consistency stats for each model
    model_stats = []
    
    for model in models:
        model_name = model.__name__
        
        # Try to get stats from cache
        stats_key = f"{CONSISTENCY_STATS_KEY_PREFIX}{model_name}"
        cached_stats = cache.get(stats_key)
        
        if cached_stats:
            # Convert timestamp to datetime
            timestamp = datetime.fromisoformat(cached_stats['timestamp'])
            age = timezone.now() - timestamp
            
            model_stats.append({
                'model': model_name,
                'app': model._meta.app_label,
                'stats': cached_stats['stats'],
                'consistency_ratio': cached_stats['consistency_ratio'],
                'timestamp': timestamp,
                'age_hours': age.total_seconds() / 3600,
                'status': _get_consistency_status(cached_stats['consistency_ratio']),
            })
        else:
            model_stats.append({
                'model': model_name,
                'app': model._meta.app_label,
                'stats': None,
                'consistency_ratio': None,
                'timestamp': None,
                'age_hours': None,
                'status': 'unknown',
            })
    
    # Sort by consistency ratio (ascending)
    model_stats.sort(key=lambda x: x['consistency_ratio'] if x['consistency_ratio'] is not None else 1.0)
    
    # Calculate overall stats
    total_models = len(model_stats)
    models_with_stats = sum(1 for m in model_stats if m['stats'] is not None)
    
    if models_with_stats > 0:
        average_consistency = sum(
            m['consistency_ratio'] for m in model_stats if m['consistency_ratio'] is not None
        ) / models_with_stats
    else:
        average_consistency = None
    
    # Count models by status
    status_counts = {
        'critical': sum(1 for m in model_stats if m['status'] == 'critical'),
        'warning': sum(1 for m in model_stats if m['status'] == 'warning'),
        'good': sum(1 for m in model_stats if m['status'] == 'good'),
        'unknown': sum(1 for m in model_stats if m['status'] == 'unknown'),
    }
    
    context = {
        'model_stats': model_stats,
        'total_models': total_models,
        'models_with_stats': models_with_stats,
        'average_consistency': average_consistency,
        'status_counts': status_counts,
        'page_title': 'Cache Consistency',
        'section': 'cache_consistency',
    }
    
    return render(request, 'godmode/cache_consistency/dashboard.html', context)


@staff_member_required
def check_model_consistency_view(request: HttpRequest, app_label: str, model_name: str) -> JsonResponse:
    """
    Check cache consistency for a model.
    
    Args:
        request: HTTP request
        app_label: App label
        model_name: Model name
        
    Returns:
        JSON response with consistency statistics
    """
    from django.apps import apps
    
    try:
        # Get model
        model = apps.get_model(app_label, model_name)
        
        # Check consistency
        stats = check_cache_consistency(model, sample_size=100)
        
        # Calculate consistency ratio
        total = stats['total']
        if total > 0:
            consistency_ratio = stats['consistent'] / total
        else:
            consistency_ratio = 1.0
            
        # Store stats
        stats_key = f"{CONSISTENCY_STATS_KEY_PREFIX}{model.__name__}"
        cache.set(stats_key, {
            'timestamp': timezone.now().isoformat(),
            'stats': stats,
            'consistency_ratio': consistency_ratio,
        }, 86400)  # Cache for 24 hours
        
        return JsonResponse({
            'success': True,
            'model': model.__name__,
            'app': app_label,
            'stats': stats,
            'consistency_ratio': consistency_ratio,
            'status': _get_consistency_status(consistency_ratio),
            'timestamp': timezone.now().isoformat(),
        })
        
    except Exception as e:
        logger.exception(f"Error checking consistency for {app_label}.{model_name}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)


@staff_member_required
@require_POST
def reconcile_model_view(request: HttpRequest, app_label: str, model_name: str) -> JsonResponse:
    """
    Reconcile cache for a model.
    
    Args:
        request: HTTP request
        app_label: App label
        model_name: Model name
        
    Returns:
        JSON response with reconciliation status
    """
    from django.apps import apps
    
    try:
        # Get model
        model = apps.get_model(app_label, model_name)
        
        # Get parameters
        data = json.loads(request.body)
        force = data.get('force', False)
        batch_size = data.get('batch_size', 100)
        max_instances = data.get('max_instances', 1000)
        
        # Use Django Q for background processing if available
        try:
            from django_q.tasks import async_task
            task_id = async_task(
                'godmode.cache_sync.reconcile_cache_for_model',
                model,
                force=force,
                batch_size=batch_size,
                max_instances=max_instances,
                task_name=f"reconcile_cache_{model.__name__}",
                group='cache_reconciliation'
            )
            
            return JsonResponse({
                'success': True,
                'model': model.__name__,
                'app': app_label,
                'task_id': task_id,
                'message': f"Reconciliation task queued for {app_label}.{model_name}",
            })
            
        except ImportError:
            # Use Celery if available
            try:
                from celery import shared_task
                
                @shared_task(name=f"reconcile_cache_{model.__name__}")
                def reconcile_task():
                    return reconcile_cache_for_model(
                        model, force=force, batch_size=batch_size, max_instances=max_instances
                    )
                
                task = reconcile_task.delay()
                
                return JsonResponse({
                    'success': True,
                    'model': model.__name__,
                    'app': app_label,
                    'task_id': task.id,
                    'message': f"Reconciliation task queued for {app_label}.{model_name}",
                })
                
            except ImportError:
                # Fall back to direct execution
                stats = reconcile_cache_for_model(
                    model, force=force, batch_size=batch_size, max_instances=max_instances
                )
                
                return JsonResponse({
                    'success': True,
                    'model': model.__name__,
                    'app': app_label,
                    'stats': stats,
                    'message': f"Reconciliation completed for {app_label}.{model_name}",
                })
        
    except Exception as e:
        logger.exception(f"Error reconciling {app_label}.{model_name}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)


@staff_member_required
@require_POST
def check_all_consistency_view(request: HttpRequest) -> JsonResponse:
    """
    Check cache consistency for all models.
    
    Args:
        request: HTTP request
        
    Returns:
        JSON response with consistency statistics
    """
    try:
        # Use Django Q for background processing if available
        try:
            from django_q.tasks import async_task
            task_id = async_task(
                'godmode.tasks.cache_tasks.scheduled_consistency_check',
                task_name="check_all_cache_consistency",
                group='cache_consistency'
            )
            
            return JsonResponse({
                'success': True,
                'task_id': task_id,
                'message': "Consistency check task queued for all models",
            })
            
        except ImportError:
            # Use Celery if available
            try:
                from godmode.tasks.cache_tasks import celery_consistency_check
                
                task = celery_consistency_check.delay()
                
                return JsonResponse({
                    'success': True,
                    'task_id': task.id,
                    'message': "Consistency check task queued for all models",
                })
                
            except (ImportError, AttributeError):
                # Fall back to direct execution
                results = check_all_models_consistency()
                
                return JsonResponse({
                    'success': True,
                    'results': results,
                    'message': "Consistency check completed for all models",
                })
        
    except Exception as e:
        logger.exception(f"Error checking consistency for all models: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)


def _get_consistency_status(ratio: float) -> str:
    """
    Get consistency status based on ratio.
    
    Args:
        ratio: Consistency ratio
        
    Returns:
        Status string: 'critical', 'warning', or 'good'
    """
    if ratio is None:
        return 'unknown'
        
    auto_reconcile_threshold = getattr(settings, 'CACHE_AUTO_RECONCILE_THRESHOLD', 0.7)
    consistency_threshold = getattr(settings, 'CACHE_CONSISTENCY_THRESHOLD', 0.9)
    
    if ratio < auto_reconcile_threshold:
        return 'critical'
    elif ratio < consistency_threshold:
        return 'warning'
    else:
        return 'good'

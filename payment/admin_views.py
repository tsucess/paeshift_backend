"""
Admin views for payment webhook monitoring and management.

This module provides admin views for:
1. Webhook queue dashboard
2. Webhook queue statistics
3. Webhook batch processing
4. Webhook queue cleanup
5. Retrying failed webhooks
"""

import json
import logging
from datetime import datetime

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .batch_processor import process_webhook_batch
from .webhook_queue import (
    cleanup_stale_processing,
    get_queue_stats,
    retry_failed_webhooks,
)

logger = logging.getLogger(__name__)


@staff_member_required
def webhook_dashboard(request):
    """
    Render the webhook dashboard.
    
    Args:
        request: HTTP request
        
    Returns:
        Rendered dashboard template
    """
    # Get queue stats
    stats = get_queue_stats()
    
    context = {
        "title": "Webhook Queue Dashboard",
        "stats": stats,
        "timestamp": timezone.now().isoformat(),
    }
    
    return render(request, "admin/webhook_dashboard.html", context)


@staff_member_required
def webhook_stats(request):
    """
    Get webhook queue statistics.
    
    Args:
        request: HTTP request
        
    Returns:
        JSON response with queue statistics
    """
    try:
        # Get queue stats
        stats = get_queue_stats()
        
        # Get failed webhooks
        failed_webhooks = []
        try:
            from django.core.cache import cache
            failed_data = cache.lrange("payment:webhook_failed", 0, 9)  # Get last 10
            
            if failed_data:
                for item in failed_data:
                    try:
                        webhook = json.loads(item)
                        failed_webhooks.append(webhook)
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            logger.exception(f"Error getting failed webhooks: {str(e)}")
        
        # Get completed webhooks
        completed_webhooks = []
        try:
            from django.core.cache import cache
            completed_data = cache.lrange("payment:webhook_completed", 0, 9)  # Get last 10
            
            if completed_data:
                for item in completed_data:
                    try:
                        webhook = json.loads(item)
                        completed_webhooks.append(webhook)
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            logger.exception(f"Error getting completed webhooks: {str(e)}")
        
        return JsonResponse({
            "stats": stats,
            "failed_webhooks": failed_webhooks,
            "completed_webhooks": completed_webhooks,
            "timestamp": timezone.now().isoformat(),
        })
    except Exception as e:
        logger.exception(f"Error getting webhook stats: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


@staff_member_required
@require_POST
@csrf_exempt
def process_batch(request):
    """
    Process a batch of webhooks.
    
    Args:
        request: HTTP request
        
    Returns:
        JSON response with processing results
    """
    try:
        # Get batch size from request or use default
        batch_size = int(request.POST.get("batch_size", 20))
        
        # Process batch
        success_count, failure_count = process_webhook_batch(batch_size)
        
        return JsonResponse({
            "status": "success",
            "success_count": success_count,
            "failure_count": failure_count,
            "timestamp": timezone.now().isoformat(),
        })
    except Exception as e:
        logger.exception(f"Error processing webhook batch: {str(e)}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@staff_member_required
@require_POST
@csrf_exempt
def cleanup_queue(request):
    """
    Clean up the webhook queue.
    
    Args:
        request: HTTP request
        
    Returns:
        JSON response with cleanup results
    """
    try:
        # Requeue stale processing webhooks
        requeued_stale = cleanup_stale_processing()
        
        # Retry failed webhooks (up to 50 at a time)
        requeued_failed = retry_failed_webhooks(max_count=50)
        
        return JsonResponse({
            "status": "success",
            "requeued_stale": requeued_stale,
            "requeued_failed": requeued_failed,
            "timestamp": timezone.now().isoformat(),
        })
    except Exception as e:
        logger.exception(f"Error cleaning up webhook queue: {str(e)}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@staff_member_required
@require_POST
@csrf_exempt
def retry_failed(request):
    """
    Retry failed webhooks.
    
    Args:
        request: HTTP request
        
    Returns:
        JSON response with retry results
    """
    try:
        # Get max count from request or use default
        max_count = int(request.POST.get("max_count", 100))
        
        # Retry failed webhooks
        requeued_count = retry_failed_webhooks(max_count=max_count)
        
        return JsonResponse({
            "status": "success",
            "requeued_count": requeued_count,
            "timestamp": timezone.now().isoformat(),
        })
    except Exception as e:
        logger.exception(f"Error retrying failed webhooks: {str(e)}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@staff_member_required
@require_POST
@csrf_exempt
def retry_webhook(request, webhook_id):
    """
    Retry a specific webhook.
    
    Args:
        request: HTTP request
        webhook_id: Webhook ID
        
    Returns:
        JSON response with retry result
    """
    try:
        # Get webhook data
        from django.core.cache import cache
        data_key = f"payment:webhook_data:{webhook_id}"
        webhook_data_json = cache.get(data_key)
        
        if not webhook_data_json:
            return JsonResponse({
                "status": "error",
                "message": f"Webhook {webhook_id} not found",
            }, status=404)
        
        webhook_data = json.loads(webhook_data_json)
        
        # Reset attempt count and error
        webhook_data["attempts"] = 0
        webhook_data["error"] = None
        webhook_data["status"] = "retrying"
        
        # Store updated data
        cache.set(data_key, json.dumps(webhook_data), 60 * 60 * 24 * 7)  # 7 days
        
        # Requeue with high priority
        from .webhook_queue import PRIORITY_HIGH
        score = PRIORITY_HIGH * 1000 + int(datetime.now().timestamp())
        cache.zadd("payment:webhook_queue", {webhook_id: score})
        
        # Remove from failed list
        failed_webhooks = cache.lrange("payment:webhook_failed", 0, -1)
        
        for webhook_json in failed_webhooks:
            try:
                webhook = json.loads(webhook_json)
                if webhook.get("webhook_id") == webhook_id:
                    cache.lrem("payment:webhook_failed", 1, webhook_json)
                    break
            except json.JSONDecodeError:
                pass
        
        return JsonResponse({
            "status": "success",
            "message": f"Webhook {webhook_id} requeued",
            "timestamp": timezone.now().isoformat(),
        })
    except Exception as e:
        logger.exception(f"Error retrying webhook {webhook_id}: {str(e)}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

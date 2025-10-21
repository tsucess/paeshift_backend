"""
Webhook utilities for God Mode.

This module provides utilities for capturing, logging, and reprocessing payment webhooks.
"""

import json
import logging
import uuid
from datetime import datetime

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from godmode.models import WebhookLog
from payment.models import Payment

logger = logging.getLogger(__name__)


def capture_webhook(
    reference,
    gateway,
    request_data,
    response_data=None,
    status="pending",
    ip_address=None,
    error_message=None,
):
    """
    Capture a payment webhook and log it.
    
    Args:
        reference: Payment reference/transaction ID
        gateway: Payment gateway (paystack, flutterwave, etc.)
        request_data: Request data from the webhook
        response_data: Response data (if any)
        status: Status of the webhook (success, failed, pending, error)
        ip_address: IP address of the webhook sender
        error_message: Error message (if any)
        
    Returns:
        WebhookLog instance
    """
    # Generate a unique ID for this webhook capture
    unique_id = str(uuid.uuid4())
    
    # Ensure request_data is a dictionary
    if isinstance(request_data, str):
        try:
            request_data = json.loads(request_data)
        except json.JSONDecodeError:
            request_data = {"raw_data": request_data}
    
    # Ensure response_data is a dictionary
    if response_data is None:
        response_data = {}
    elif isinstance(response_data, str):
        try:
            response_data = json.loads(response_data)
        except json.JSONDecodeError:
            response_data = {"raw_data": response_data}
    
    # Add unique ID and timestamp to request data
    request_data["webhook_id"] = unique_id
    request_data["captured_at"] = timezone.now().isoformat()
    
    # Create webhook log
    webhook_log = WebhookLog.objects.create(
        reference=reference,
        gateway=gateway,
        status=status,
        request_data=request_data,
        response_data=response_data or {},
        error_message=error_message,
        ip_address=ip_address,
    )
    
    logger.info(
        f"Webhook captured: {webhook_log.id} - {reference} - {gateway} - {status}"
    )
    
    return webhook_log


def reprocess_webhook(webhook_id):
    """
    Reprocess a failed webhook.
    
    Args:
        webhook_id: ID of the webhook to reprocess
        
    Returns:
        Tuple of (success, message, updated_webhook)
    """
    try:
        webhook = WebhookLog.objects.get(id=webhook_id)
        
        # Only reprocess failed or error webhooks
        if webhook.status not in ["failed", "error"]:
            return False, f"Cannot reprocess webhook with status: {webhook.status}", webhook
        
        # Get the payment reference
        reference = webhook.reference
        
        # Find the payment
        try:
            payment = Payment.objects.get(pay_code=reference)
        except Payment.DoesNotExist:
            return False, f"Payment with reference {reference} not found", webhook
        
        # Determine the gateway and call the appropriate verification function
        gateway = webhook.gateway
        
        if gateway == "paystack":
            from payment.api import _verify_paystack
            verification_func = _verify_paystack
        elif gateway == "flutterwave":
            from payment.api import _verify_flutterwave
            verification_func = _verify_flutterwave
        else:
            return False, f"Unsupported gateway: {gateway}", webhook
        
        # Verify the payment
        try:
            verification_result = verification_func(reference)
            
            # Update payment status based on verification result
            with transaction.atomic():
                if verification_result.get("status") == "success":
                    payment.status = "Completed"
                    payment.save()
                    
                    # Update webhook status
                    webhook.status = "success"
                    webhook.response_data = verification_result
                    webhook.error_message = None
                    webhook.save()
                    
                    return True, "Payment verified successfully", webhook
                else:
                    return False, "Payment verification failed", webhook
                    
        except Exception as e:
            # Update webhook with error
            webhook.status = "error"
            webhook.error_message = str(e)
            webhook.save()
            
            return False, f"Error reprocessing webhook: {str(e)}", webhook
            
    except WebhookLog.DoesNotExist:
        return False, f"Webhook with ID {webhook_id} not found", None
    except Exception as e:
        logger.exception(f"Error reprocessing webhook {webhook_id}: {str(e)}")
        return False, f"Error: {str(e)}", None


def get_webhook_stats():
    """
    Get statistics about webhooks.
    
    Returns:
        Dictionary with webhook statistics
    """
    total = WebhookLog.objects.count()
    success = WebhookLog.objects.filter(status="success").count()
    failed = WebhookLog.objects.filter(status="failed").count()
    pending = WebhookLog.objects.filter(status="pending").count()
    error = WebhookLog.objects.filter(status="error").count()
    
    # Calculate success rate
    success_rate = (success / total * 100) if total > 0 else 0
    
    # Get gateway breakdown
    paystack = WebhookLog.objects.filter(gateway="paystack").count()
    flutterwave = WebhookLog.objects.filter(gateway="flutterwave").count()
    other = total - paystack - flutterwave
    
    # Get recent activity
    recent = WebhookLog.objects.order_by("-created_at")[:10]
    
    return {
        "total": total,
        "success": success,
        "failed": failed,
        "pending": pending,
        "error": error,
        "success_rate": success_rate,
        "gateways": {
            "paystack": paystack,
            "flutterwave": flutterwave,
            "other": other,
        },
        "recent": [
            {
                "id": log.id,
                "reference": log.reference,
                "gateway": log.gateway,
                "status": log.status,
                "created_at": log.created_at.isoformat(),
            }
            for log in recent
        ],
    }

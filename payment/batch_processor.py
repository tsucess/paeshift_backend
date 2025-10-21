"""
Batch processor for payment webhooks.

This module provides utilities for processing payment webhooks in batches,
improving performance and reducing database load.
"""

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from django.db import transaction
from django.utils import timezone

from .models import Payment
from .services import FlutterwaveService, PaystackService
from .tasks import process_payment_webhook_q
from .webhook_queue import (
    get_webhook_batch,
    mark_webhook_completed,
    mark_webhook_failed,
)

logger = logging.getLogger(__name__)

# Constants
DEFAULT_BATCH_SIZE = 20
MAX_BATCH_SIZE = 100
MIN_BATCH_SIZE = 5


def process_webhook_batch(batch_size: int = DEFAULT_BATCH_SIZE) -> Tuple[int, int]:
    """
    Process a batch of webhooks from the queue.
    
    Args:
        batch_size: Number of webhooks to process
        
    Returns:
        Tuple of (success_count, failure_count)
    """
    # Get batch of webhooks
    webhooks = get_webhook_batch(batch_size)
    
    if not webhooks:
        logger.debug("No webhooks to process")
        return 0, 0
    
    logger.info(f"Processing batch of {len(webhooks)} webhooks")
    
    # Group webhooks by payment method for batch processing
    paystack_webhooks = []
    flutterwave_webhooks = []
    other_webhooks = []
    
    for webhook in webhooks:
        payment_method = webhook.get("payment_method", "").lower()
        if payment_method == "paystack":
            paystack_webhooks.append(webhook)
        elif payment_method == "flutterwave":
            flutterwave_webhooks.append(webhook)
        else:
            other_webhooks.append(webhook)
    
    # Process each group
    success_count = 0
    failure_count = 0
    
    # Process Paystack webhooks
    if paystack_webhooks:
        s, f = process_paystack_batch(paystack_webhooks)
        success_count += s
        failure_count += f
    
    # Process Flutterwave webhooks
    if flutterwave_webhooks:
        s, f = process_flutterwave_batch(flutterwave_webhooks)
        success_count += s
        failure_count += f
    
    # Process other webhooks individually
    for webhook in other_webhooks:
        try:
            result = process_single_webhook(webhook)
            if result.get("status") in ["success", "skipped"]:
                success_count += 1
            else:
                failure_count += 1
        except Exception as e:
            logger.exception(f"Error processing webhook: {str(e)}")
            failure_count += 1
    
    logger.info(f"Batch processing completed: {success_count} succeeded, {failure_count} failed")
    return success_count, failure_count


def process_paystack_batch(webhooks: List[Dict[str, Any]]) -> Tuple[int, int]:
    """
    Process a batch of Paystack webhooks.
    
    Args:
        webhooks: List of webhook data dictionaries
        
    Returns:
        Tuple of (success_count, failure_count)
    """
    if not webhooks:
        return 0, 0
    
    logger.info(f"Processing batch of {len(webhooks)} Paystack webhooks")
    
    # Extract references for batch verification
    references = [webhook.get("reference") for webhook in webhooks if webhook.get("reference")]
    
    # Create service
    service = PaystackService()
    
    # Batch verify payments
    verification_results = {}
    for reference in references:
        try:
            result = service.verify_payment(reference)
            verification_results[reference] = result
        except Exception as e:
            logger.exception(f"Error verifying Paystack payment {reference}: {str(e)}")
            verification_results[reference] = {"status": "error", "message": str(e)}
    
    # Get payment records in a single query
    payment_map = {}
    try:
        payments = Payment.objects.filter(pay_code__in=references)
        for payment in payments:
            payment_map[payment.pay_code] = payment
    except Exception as e:
        logger.exception(f"Error fetching payment records: {str(e)}")
    
    # Process each webhook
    success_count = 0
    failure_count = 0
    
    for webhook in webhooks:
        webhook_id = webhook.get("id")
        reference = webhook.get("reference")
        
        try:
            # Skip if no reference
            if not reference:
                mark_webhook_failed(webhook_id, "Missing reference", retry=False)
                failure_count += 1
                continue
            
            # Get verification result
            verification_result = verification_results.get(reference, {"status": "error", "message": "Verification failed"})
            
            # Get payment record
            payment = payment_map.get(reference)
            
            if not payment:
                mark_webhook_failed(webhook_id, f"Payment with reference {reference} not found", retry=False)
                failure_count += 1
                continue
            
            # Skip if payment is already in a final state
            if payment.status in ["Completed", "Failed", "Refunded"]:
                mark_webhook_completed(webhook_id, {
                    "status": "skipped",
                    "message": f"Payment {reference} already in state {payment.status}",
                })
                success_count += 1
                continue
            
            # Update payment status based on verification
            if verification_result.get("status") == "success":
                # Update payment in database
                with transaction.atomic():
                    payment.status = "Completed"
                    payment.save()
                    
                    # Update job payment status if this payment is for a job
                    if payment.job:
                        job = payment.job
                        job.payment_status = "paid"
                        job.save()
                
                # Mark webhook as completed
                mark_webhook_completed(webhook_id, {
                    "status": "success",
                    "message": "Payment completed",
                    "payment_id": payment.id,
                    "amount": str(payment.original_amount),
                })
                
                success_count += 1
            else:
                # Mark payment as failed
                with transaction.atomic():
                    payment.status = "Failed"
                    payment.save()
                
                # Mark webhook as completed
                mark_webhook_completed(webhook_id, {
                    "status": "failed",
                    "message": "Payment failed",
                    "payment_id": payment.id,
                    "amount": str(payment.original_amount),
                })
                
                success_count += 1
        except Exception as e:
            logger.exception(f"Error processing Paystack webhook {webhook_id}: {str(e)}")
            mark_webhook_failed(webhook_id, str(e))
            failure_count += 1
    
    return success_count, failure_count


def process_flutterwave_batch(webhooks: List[Dict[str, Any]]) -> Tuple[int, int]:
    """
    Process a batch of Flutterwave webhooks.
    
    Args:
        webhooks: List of webhook data dictionaries
        
    Returns:
        Tuple of (success_count, failure_count)
    """
    if not webhooks:
        return 0, 0
    
    logger.info(f"Processing batch of {len(webhooks)} Flutterwave webhooks")
    
    # Extract references for batch verification
    references = [webhook.get("reference") for webhook in webhooks if webhook.get("reference")]
    
    # Create service
    service = FlutterwaveService()
    
    # Batch verify payments
    verification_results = {}
    for reference in references:
        try:
            result = service.verify_payment(reference)
            verification_results[reference] = result
        except Exception as e:
            logger.exception(f"Error verifying Flutterwave payment {reference}: {str(e)}")
            verification_results[reference] = {"status": "error", "message": str(e)}
    
    # Get payment records in a single query
    payment_map = {}
    try:
        payments = Payment.objects.filter(pay_code__in=references)
        for payment in payments:
            payment_map[payment.pay_code] = payment
    except Exception as e:
        logger.exception(f"Error fetching payment records: {str(e)}")
    
    # Process each webhook
    success_count = 0
    failure_count = 0
    
    for webhook in webhooks:
        webhook_id = webhook.get("id")
        reference = webhook.get("reference")
        
        try:
            # Skip if no reference
            if not reference:
                mark_webhook_failed(webhook_id, "Missing reference", retry=False)
                failure_count += 1
                continue
            
            # Get verification result
            verification_result = verification_results.get(reference, {"status": "error", "message": "Verification failed"})
            
            # Get payment record
            payment = payment_map.get(reference)
            
            if not payment:
                mark_webhook_failed(webhook_id, f"Payment with reference {reference} not found", retry=False)
                failure_count += 1
                continue
            
            # Skip if payment is already in a final state
            if payment.status in ["Completed", "Failed", "Refunded"]:
                mark_webhook_completed(webhook_id, {
                    "status": "skipped",
                    "message": f"Payment {reference} already in state {payment.status}",
                })
                success_count += 1
                continue
            
            # Update payment status based on verification
            if verification_result.get("status") == "success":
                # Update payment in database
                with transaction.atomic():
                    payment.status = "Completed"
                    payment.save()
                    
                    # Update job payment status if this payment is for a job
                    if payment.job:
                        job = payment.job
                        job.payment_status = "paid"
                        job.save()
                
                # Mark webhook as completed
                mark_webhook_completed(webhook_id, {
                    "status": "success",
                    "message": "Payment completed",
                    "payment_id": payment.id,
                    "amount": str(payment.original_amount),
                })
                
                success_count += 1
            else:
                # Mark payment as failed
                with transaction.atomic():
                    payment.status = "Failed"
                    payment.save()
                
                # Mark webhook as completed
                mark_webhook_completed(webhook_id, {
                    "status": "failed",
                    "message": "Payment failed",
                    "payment_id": payment.id,
                    "amount": str(payment.original_amount),
                })
                
                success_count += 1
        except Exception as e:
            logger.exception(f"Error processing Flutterwave webhook {webhook_id}: {str(e)}")
            mark_webhook_failed(webhook_id, str(e))
            failure_count += 1
    
    return success_count, failure_count


def process_single_webhook(webhook: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a single webhook.
    
    Args:
        webhook: Webhook data dictionary
        
    Returns:
        Processing result
    """
    webhook_id = webhook.get("id")
    reference = webhook.get("reference")
    payment_method = webhook.get("payment_method")
    status = webhook.get("status")
    raw_data = webhook.get("raw_data")
    
    try:
        # Use existing task for processing
        result = process_payment_webhook_q(
            reference=reference,
            payment_method=payment_method,
            status=status,
            raw_data=raw_data,
        )
        
        # Mark webhook as completed
        mark_webhook_completed(webhook_id, result)
        
        return result
    except Exception as e:
        logger.exception(f"Error processing webhook {webhook_id}: {str(e)}")
        mark_webhook_failed(webhook_id, str(e))
        return {"status": "error", "message": str(e)}

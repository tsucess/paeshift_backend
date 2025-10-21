"""
Webhook queue implementation for payment processing.

This module provides a dedicated queue system for processing payment webhooks,
with support for:
1. Batching similar webhooks
2. Prioritizing webhooks based on type and age
3. Handling retries with exponential backoff
4. Monitoring queue health and performance
"""

import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union  

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from core.redis_lock import redis_lock

logger = logging.getLogger(__name__)

# Constants
WEBHOOK_QUEUE_KEY = "payment:webhook_queue"
WEBHOOK_PROCESSING_KEY = "payment:webhook_processing"
WEBHOOK_FAILED_KEY = "payment:webhook_failed"
WEBHOOK_COMPLETED_KEY = "payment:webhook_completed"
WEBHOOK_DATA_PREFIX = "payment:webhook_data:"
WEBHOOK_STATS_KEY = "payment:webhook_stats"

# Expiration times
QUEUE_EXPIRATION = 60 * 60 * 24 * 7  # 7 days
PROCESSING_EXPIRATION = 60 * 10  # 10 minutes
DATA_EXPIRATION = 60 * 60 * 24 * 7  # 7 days
STATS_EXPIRATION = 60 * 60 * 24 * 30  # 30 days

# Batch settings
DEFAULT_BATCH_SIZE = 20
MAX_BATCH_SIZE = 100
MIN_BATCH_SIZE = 5

# Priority settings
PRIORITY_HIGH = 0
PRIORITY_NORMAL = 1
PRIORITY_LOW = 2


def enqueue_webhook(
    payment_method: str,
    reference: str,
    status: str,
    raw_data: Dict[str, Any],
    priority: int = PRIORITY_NORMAL,
) -> str:
    """
    Add a webhook to the processing queue.
    
    Args:
        payment_method: Payment gateway (paystack, flutterwave)
        reference: Payment reference/code
        status: Payment status from webhook
        raw_data: Complete webhook payload
        priority: Priority level (0=high, 1=normal, 2=low)
        
    Returns:
        Webhook ID
    """
    # Generate webhook ID
    webhook_id = str(uuid.uuid4())
    
    # Create webhook data
    webhook_data = {
        "id": webhook_id,
        "payment_method": payment_method,
        "reference": reference,
        "status": status,
        "raw_data": raw_data,
        "priority": priority,
        "enqueued_at": timezone.now().isoformat(),
        "attempts": 0,
        "last_attempt": None,
        "error": None,
    }
    
    # Store webhook data
    data_key = f"{WEBHOOK_DATA_PREFIX}{webhook_id}"
    cache.set(data_key, json.dumps(webhook_data), DATA_EXPIRATION)
    
    # Add to queue with priority score
    # Lower score = higher priority
    score = priority * 1000 + int(time.time())
    cache.zadd(WEBHOOK_QUEUE_KEY, {webhook_id: score})
    
    # Set expiration on queue if not already set
    if not cache.ttl(WEBHOOK_QUEUE_KEY):
        cache.expire(WEBHOOK_QUEUE_KEY, QUEUE_EXPIRATION)
    
    # Update stats
    update_webhook_stats("enqueued")
    
    logger.info(f"Webhook {webhook_id} for {payment_method} payment {reference} added to queue")
    return webhook_id


def get_webhook_batch(batch_size: int = DEFAULT_BATCH_SIZE) -> List[Dict[str, Any]]:
    """
    Get a batch of webhooks to process.
    
    Args:
        batch_size: Maximum number of webhooks to retrieve
        
    Returns:
        List of webhook data dictionaries
    """
    # Ensure batch size is within limits
    batch_size = max(MIN_BATCH_SIZE, min(batch_size, MAX_BATCH_SIZE))
    
    # Get lock to prevent multiple workers from processing the same webhooks
    with redis_lock("webhook_batch_lock", timeout=30):
        # Get webhook IDs from queue, ordered by score (priority)
        webhook_ids = cache.zrange(WEBHOOK_QUEUE_KEY, 0, batch_size - 1)
        
        if not webhook_ids:
            return []
        
        # Move webhooks to processing set
        for webhook_id in webhook_ids:
            # Remove from queue
            cache.zrem(WEBHOOK_QUEUE_KEY, webhook_id)
            
            # Add to processing set with expiration time
            processing_data = {
                "webhook_id": webhook_id,
                "started_at": timezone.now().isoformat(),
            }
            cache.set(
                f"{WEBHOOK_PROCESSING_KEY}:{webhook_id}",
                json.dumps(processing_data),
                PROCESSING_EXPIRATION,
            )
        
        # Get webhook data for each ID
        webhooks = []
        for webhook_id in webhook_ids:
            data_key = f"{WEBHOOK_DATA_PREFIX}{webhook_id}"
            webhook_data_json = cache.get(data_key)
            
            if webhook_data_json:
                try:
                    webhook_data = json.loads(webhook_data_json)
                    webhooks.append(webhook_data)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse webhook data for {webhook_id}")
            else:
                logger.error(f"Webhook data not found for {webhook_id}")
        
        # Update stats
        update_webhook_stats("processing", len(webhooks))
        
        return webhooks


def mark_webhook_completed(webhook_id: str, result: Dict[str, Any]) -> bool:
    """
    Mark a webhook as completed.
    
    Args:
        webhook_id: Webhook ID
        result: Processing result
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get webhook data
        data_key = f"{WEBHOOK_DATA_PREFIX}{webhook_id}"
        webhook_data_json = cache.get(data_key)
        
        if not webhook_data_json:
            logger.error(f"Webhook data not found for {webhook_id}")
            return False
        
        webhook_data = json.loads(webhook_data_json)
        
        # Update webhook data
        webhook_data["completed_at"] = timezone.now().isoformat()
        webhook_data["result"] = result
        webhook_data["status"] = "completed"
        
        # Store updated data
        cache.set(data_key, json.dumps(webhook_data), DATA_EXPIRATION)
        
        # Remove from processing
        cache.delete(f"{WEBHOOK_PROCESSING_KEY}:{webhook_id}")
        
        # Add to completed set
        completed_data = {
            "webhook_id": webhook_id,
            "reference": webhook_data.get("reference"),
            "payment_method": webhook_data.get("payment_method"),
            "completed_at": webhook_data["completed_at"],
            "result": result,
        }
        cache.lpush(WEBHOOK_COMPLETED_KEY, json.dumps(completed_data))
        
        # Trim completed list to prevent it from growing too large
        cache.ltrim(WEBHOOK_COMPLETED_KEY, 0, 999)  # Keep last 1000 entries
        
        # Set expiration on completed list if not already set
        if not cache.ttl(WEBHOOK_COMPLETED_KEY):
            cache.expire(WEBHOOK_COMPLETED_KEY, QUEUE_EXPIRATION)
        
        # Update stats
        update_webhook_stats("completed")
        
        logger.info(f"Webhook {webhook_id} marked as completed")
        return True
    except Exception as e:
        logger.exception(f"Error marking webhook {webhook_id} as completed: {str(e)}")
        return False


def mark_webhook_failed(webhook_id: str, error: str, retry: bool = True) -> bool:
    """
    Mark a webhook as failed.
    
    Args:
        webhook_id: Webhook ID
        error: Error message
        retry: Whether to retry the webhook
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get webhook data
        data_key = f"{WEBHOOK_DATA_PREFIX}{webhook_id}"
        webhook_data_json = cache.get(data_key)
        
        if not webhook_data_json:
            logger.error(f"Webhook data not found for {webhook_id}")
            return False
        
        webhook_data = json.loads(webhook_data_json)
        
        # Update webhook data
        webhook_data["attempts"] = webhook_data.get("attempts", 0) + 1
        webhook_data["last_attempt"] = timezone.now().isoformat()
        webhook_data["error"] = error
        
        # Check if max attempts reached
        max_attempts = getattr(settings, "WEBHOOK_MAX_ATTEMPTS", 5)
        
        if webhook_data["attempts"] >= max_attempts or not retry:
            # Mark as permanently failed
            webhook_data["status"] = "failed"
            
            # Add to failed set
            failed_data = {
                "webhook_id": webhook_id,
                "reference": webhook_data.get("reference"),
                "payment_method": webhook_data.get("payment_method"),
                "failed_at": webhook_data["last_attempt"],
                "attempts": webhook_data["attempts"],
                "error": error,
            }
            cache.lpush(WEBHOOK_FAILED_KEY, json.dumps(failed_data))
            
            # Trim failed list to prevent it from growing too large
            cache.ltrim(WEBHOOK_FAILED_KEY, 0, 999)  # Keep last 1000 entries
            
            # Set expiration on failed list if not already set
            if not cache.ttl(WEBHOOK_FAILED_KEY):
                cache.expire(WEBHOOK_FAILED_KEY, QUEUE_EXPIRATION)
            
            # Update stats
            update_webhook_stats("failed")
            
            logger.warning(
                f"Webhook {webhook_id} permanently failed after {webhook_data['attempts']} attempts: {error}"
            )
        else:
            # Requeue with backoff
            webhook_data["status"] = "retrying"
            
            # Calculate backoff delay (exponential)
            delay = min(2 ** (webhook_data["attempts"] - 1) * 60, 3600)  # Max 1 hour
            
            # Requeue with delay
            score = webhook_data.get("priority", PRIORITY_NORMAL) * 1000 + int(time.time() + delay)
            cache.zadd(WEBHOOK_QUEUE_KEY, {webhook_id: score})
            
            # Update stats
            update_webhook_stats("retried")
            
            logger.info(
                f"Webhook {webhook_id} failed, retrying in {delay} seconds (attempt {webhook_data['attempts']}): {error}"
            )
        
        # Store updated data
        cache.set(data_key, json.dumps(webhook_data), DATA_EXPIRATION)
        
        # Remove from processing
        cache.delete(f"{WEBHOOK_PROCESSING_KEY}:{webhook_id}")
        
        return True
    except Exception as e:
        logger.exception(f"Error marking webhook {webhook_id} as failed: {str(e)}")
        return False


def retry_failed_webhooks(max_count: int = 100) -> int:
    """
    Retry failed webhooks.
    
    Args:
        max_count: Maximum number of webhooks to retry
        
    Returns:
        Number of webhooks requeued
    """
    try:
        # Get failed webhooks
        failed_webhooks = cache.lrange(WEBHOOK_FAILED_KEY, 0, max_count - 1)
        
        if not failed_webhooks:
            return 0
        
        requeued_count = 0
        
        for webhook_json in failed_webhooks:
            try:
                webhook = json.loads(webhook_json)
                webhook_id = webhook.get("webhook_id")
                
                if not webhook_id:
                    continue
                
                # Get full webhook data
                data_key = f"{WEBHOOK_DATA_PREFIX}{webhook_id}"
                webhook_data_json = cache.get(data_key)
                
                if not webhook_data_json:
                    continue
                
                webhook_data = json.loads(webhook_data_json)
                
                # Reset attempt count and error
                webhook_data["attempts"] = 0
                webhook_data["error"] = None
                webhook_data["status"] = "retrying"
                
                # Store updated data
                cache.set(data_key, json.dumps(webhook_data), DATA_EXPIRATION)
                
                # Requeue with high priority
                score = PRIORITY_HIGH * 1000 + int(time.time())
                cache.zadd(WEBHOOK_QUEUE_KEY, {webhook_id: score})
                
                # Remove from failed list
                cache.lrem(WEBHOOK_FAILED_KEY, 1, webhook_json)
                
                requeued_count += 1
                
                logger.info(f"Requeued failed webhook {webhook_id}")
            except Exception as e:
                logger.exception(f"Error requeuing failed webhook: {str(e)}")
        
        # Update stats
        update_webhook_stats("requeued", requeued_count)
        
        return requeued_count
    except Exception as e:
        logger.exception(f"Error retrying failed webhooks: {str(e)}")
        return 0


def get_queue_stats() -> Dict[str, Any]:
    """
    Get webhook queue statistics.
    
    Returns:
        Dictionary with queue statistics
    """
    try:
        # Get counts
        queued_count = cache.zcard(WEBHOOK_QUEUE_KEY) or 0
        processing_keys = cache.keys(f"{WEBHOOK_PROCESSING_KEY}:*")
        processing_count = len(processing_keys) if processing_keys else 0
        failed_count = cache.llen(WEBHOOK_FAILED_KEY) or 0
        completed_count = cache.llen(WEBHOOK_COMPLETED_KEY) or 0
        
        # Get stats from Redis
        stats_json = cache.get(WEBHOOK_STATS_KEY)
        stats = json.loads(stats_json) if stats_json else {
            "enqueued_total": 0,
            "completed_total": 0,
            "failed_total": 0,
            "retried_total": 0,
            "requeued_total": 0,
            "processing_total": 0,
            "last_updated": timezone.now().isoformat(),
        }
        
        # Combine current counts with total stats
        return {
            "queued": queued_count,
            "processing": processing_count,
            "failed": failed_count,
            "completed": completed_count,
            "enqueued_total": stats.get("enqueued_total", 0),
            "completed_total": stats.get("completed_total", 0),
            "failed_total": stats.get("failed_total", 0),
            "retried_total": stats.get("retried_total", 0),
            "requeued_total": stats.get("requeued_total", 0),
            "processing_total": stats.get("processing_total", 0),
            "last_updated": stats.get("last_updated", timezone.now().isoformat()),
            "current_time": timezone.now().isoformat(),
        }
    except Exception as e:
        logger.exception(f"Error getting queue stats: {str(e)}")
        return {"error": str(e)}


def update_webhook_stats(action: str, count: int = 1) -> bool:
    """
    Update webhook statistics.
    
    Args:
        action: Action type (enqueued, completed, failed, retried, requeued, processing)
        count: Number of webhooks affected
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get current stats
        stats_json = cache.get(WEBHOOK_STATS_KEY)
        stats = json.loads(stats_json) if stats_json else {
            "enqueued_total": 0,
            "completed_total": 0,
            "failed_total": 0,
            "retried_total": 0,
            "requeued_total": 0,
            "processing_total": 0,
            "last_updated": timezone.now().isoformat(),
        }
        
        # Update stats based on action
        if action == "enqueued":
            stats["enqueued_total"] = stats.get("enqueued_total", 0) + count
        elif action == "completed":
            stats["completed_total"] = stats.get("completed_total", 0) + count
        elif action == "failed":
            stats["failed_total"] = stats.get("failed_total", 0) + count
        elif action == "retried":
            stats["retried_total"] = stats.get("retried_total", 0) + count
        elif action == "requeued":
            stats["requeued_total"] = stats.get("requeued_total", 0) + count
        elif action == "processing":
            stats["processing_total"] = stats.get("processing_total", 0) + count
        
        # Update timestamp
        stats["last_updated"] = timezone.now().isoformat()
        
        # Store updated stats
        cache.set(WEBHOOK_STATS_KEY, json.dumps(stats), STATS_EXPIRATION)
        
        return True
    except Exception as e:
        logger.exception(f"Error updating webhook stats: {str(e)}")
        return False


def cleanup_stale_processing() -> int:
    """
    Clean up stale processing webhooks.
    
    Returns:
        Number of webhooks requeued
    """
    try:
        # Get processing keys
        processing_keys = cache.keys(f"{WEBHOOK_PROCESSING_KEY}:*")
        
        if not processing_keys:
            return 0
        
        requeued_count = 0
        
        for key in processing_keys:
            try:
                # Extract webhook ID from key
                webhook_id = key.split(":")[-1]
                
                # Get processing data
                processing_data_json = cache.get(key)
                
                if not processing_data_json:
                    continue
                
                processing_data = json.loads(processing_data_json)
                started_at = datetime.fromisoformat(processing_data.get("started_at", ""))
                
                # Check if processing for too long (more than 10 minutes)
                if timezone.now() - started_at > timedelta(minutes=10):
                    # Get webhook data
                    data_key = f"{WEBHOOK_DATA_PREFIX}{webhook_id}"
                    webhook_data_json = cache.get(data_key)
                    
                    if not webhook_data_json:
                        # Remove stale processing key
                        cache.delete(key)
                        continue
                    
                    webhook_data = json.loads(webhook_data_json)
                    
                    # Mark as failed and retry
                    mark_webhook_failed(
                        webhook_id,
                        "Processing timed out",
                        retry=True,
                    )
                    
                    requeued_count += 1
                    
                    logger.warning(f"Requeued stale processing webhook {webhook_id}")
            except Exception as e:
                logger.exception(f"Error processing stale webhook: {str(e)}")
        
        return requeued_count
    except Exception as e:
        logger.exception(f"Error cleaning up stale processing: {str(e)}")
        return 0

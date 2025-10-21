"""
Redis caching utilities for payment data.

This module provides utilities for caching payment data with short timeouts
and comprehensive logging.
"""

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from django.core.cache import cache

from core.cache import (
    get_cached_data,
    set_cached_data,
    delete_cached_data,
    invalidate_cache_pattern,
)
from core.redis_permanent import (
    cache_permanently,
    get_permanent_cache,
    delete_permanent_cache,
)

logger = logging.getLogger(__name__)

# Constants
PAYMENT_CACHE_PREFIX = "payment:"
PAYMENT_LOG_PREFIX = "payment_log:"
PAYMENT_CACHE_TIMEOUT = 60 * 15  # 15 minutes
PAYMENT_LOG_TIMEOUT = 60 * 60 * 24 * 30  # 30 days


def get_payment_cache_key(payment_id: Union[int, str]) -> str:
    """
    Get a payment cache key.

    Args:
        payment_id: Payment ID

    Returns:
        Cache key
    """
    return f"{PAYMENT_CACHE_PREFIX}{payment_id}"


def get_payment_log_key(payment_id: Union[int, str]) -> str:
    """
    Get a payment log key.

    Args:
        payment_id: Payment ID

    Returns:
        Log key
    """
    return f"{PAYMENT_LOG_PREFIX}{payment_id}"


def cache_payment(payment_data: Dict[str, Any], timeout: int = PAYMENT_CACHE_TIMEOUT) -> bool:
    """
    Cache payment data.

    Args:
        payment_data: Payment data
        timeout: Cache timeout in seconds

    Returns:
        True if successful, False otherwise
    """
    try:
        # Get payment ID
        payment_id = payment_data.get("id")
        if not payment_id:
            logger.error("Payment data missing ID")
            return False

        # Generate cache key
        cache_key = get_payment_cache_key(payment_id)

        # Cache payment data
        success = set_cached_data(cache_key, payment_data, timeout)

        # Log payment data
        log_payment(payment_data)

        return success
    except Exception as e:
        logger.error(f"Error caching payment data: {str(e)}")
        return False


def cache_payment_permanently(payment_data: Dict[str, Any]) -> bool:
    """
    Cache payment data permanently (no timeout).

    Args:
        payment_data: Payment data

    Returns:
        True if successful, False otherwise
    """
    try:
        # Get payment ID and reference code
        payment_id = payment_data.get("id")
        pay_code = payment_data.get("pay_code")

        if not payment_id:
            logger.error("Payment data missing ID")
            return False

        # Generate cache keys
        id_cache_key = get_payment_cache_key(payment_id)

        # Cache payment data permanently
        success = cache_permanently(payment_data, id_cache_key)

        # Also cache by reference code if available
        if pay_code:
            ref_cache_key = get_payment_cache_key(pay_code)
            ref_success = cache_permanently(payment_data, ref_cache_key)
            success = success and ref_success

        if success:
            logger.info(f"Payment {payment_id} cached permanently")

        return success
    except Exception as e:
        logger.error(f"Error caching payment data permanently: {str(e)}")
        return False


def get_cached_payment(payment_id: Union[int, str]) -> Optional[Dict[str, Any]]:
    """
    Get cached payment data.

    Args:
        payment_id: Payment ID or reference code

    Returns:
        Payment data or None
    """
    try:
        # Generate cache key
        cache_key = get_payment_cache_key(payment_id)

        # First try to get from permanent cache
        permanent_data = get_permanent_cache(cache_key)
        if permanent_data:
            logger.debug(f"Retrieved permanently cached payment data for {payment_id}")
            return permanent_data

        # Then try regular cache
        return get_cached_data(cache_key)
    except Exception as e:
        logger.error(f"Error getting cached payment data: {str(e)}")
        return None


def invalidate_payment_cache(payment_id: Union[int, str]) -> bool:
    """
    Invalidate payment cache.

    Args:
        payment_id: Payment ID or reference code

    Returns:
        True if successful, False otherwise
    """
    try:
        # Generate cache key
        cache_key = get_payment_cache_key(payment_id)

        # Delete from both regular and permanent cache
        regular_success = delete_cached_data(cache_key)
        permanent_success = delete_permanent_cache(cache_key)

        if regular_success or permanent_success:
            logger.info(f"Payment cache invalidated for {payment_id}")

        return regular_success or permanent_success
    except Exception as e:
        logger.error(f"Error invalidating payment cache: {str(e)}")
        return False


def invalidate_user_payment_cache(user_id: Union[int, str]) -> int:
    """
    Invalidate all payment cache for a user.

    Args:
        user_id: User ID

    Returns:
        Number of invalidated keys
    """
    try:
        # Generate cache pattern
        cache_pattern = f"{PAYMENT_CACHE_PREFIX}*:user:{user_id}:*"

        # Invalidate cache pattern
        return invalidate_cache_pattern(cache_pattern)
    except Exception as e:
        logger.error(f"Error invalidating user payment cache: {str(e)}")
        return 0


def log_payment(payment_data: Dict[str, Any]) -> bool:
    """
    Log payment data.

    Args:
        payment_data: Payment data

    Returns:
        True if successful, False otherwise
    """
    try:
        # Get payment ID
        payment_id = payment_data.get("id")
        if not payment_id:
            logger.error("Payment data missing ID")
            return False

        # Generate log key
        log_key = get_payment_log_key(payment_id)

        # Get existing log or create new one
        log_data = get_cached_data(log_key) or []

        # Add timestamp to payment data
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "data": payment_data,
        }

        # Add to log
        log_data.append(log_entry)

        # Cache log data
        return set_cached_data(log_key, log_data, PAYMENT_LOG_TIMEOUT)
    except Exception as e:
        logger.error(f"Error logging payment data: {str(e)}")
        return False


def get_payment_log(payment_id: Union[int, str]) -> List[Dict[str, Any]]:
    """
    Get payment log.

    Args:
        payment_id: Payment ID

    Returns:
        Payment log
    """
    try:
        # Generate log key
        log_key = get_payment_log_key(payment_id)

        # Get log data
        return get_cached_data(log_key) or []
    except Exception as e:
        logger.error(f"Error getting payment log: {str(e)}")
        return []


def log_payment_status_change(payment_id: Union[int, str], old_status: str, new_status: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
    """
    Log payment status change.

    Args:
        payment_id: Payment ID
        old_status: Old status
        new_status: New status
        metadata: Optional metadata

    Returns:
        True if successful, False otherwise
    """
    try:
        # Generate log key
        log_key = get_payment_log_key(payment_id)

        # Get existing log or create new one
        log_data = get_cached_data(log_key) or []

        # Create log entry
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "status_change",
            "old_status": old_status,
            "new_status": new_status,
        }

        # Add metadata if provided
        if metadata:
            log_entry["metadata"] = metadata

        # Add to log
        log_data.append(log_entry)

        # Cache log data
        success = set_cached_data(log_key, log_data, PAYMENT_LOG_TIMEOUT)

        # Log to logger
        logger.info(f"Payment {payment_id} status changed: {old_status} -> {new_status}")

        return success
    except Exception as e:
        logger.error(f"Error logging payment status change: {str(e)}")
        return False

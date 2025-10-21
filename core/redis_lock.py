"""
Redis locking module for distributed locks.

This module provides functions for acquiring and releasing distributed locks
using Redis. This is useful for ensuring that only one process can perform
a certain operation at a time, even in a distributed environment.
"""

import logging
import time
import uuid
from functools import wraps
from typing import Any, Callable, Optional

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Constants
LOCK_PREFIX = "lock:"
DEFAULT_TIMEOUT = 60  # 1 minute
DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_DELAY = 0.2  # 200ms


def redis_lock(
    key: str,
    timeout: int = DEFAULT_TIMEOUT,
    retry_count: int = DEFAULT_RETRY_COUNT,
    retry_delay: float = DEFAULT_RETRY_DELAY,
):
    """
    Decorator for acquiring a Redis lock before executing a function.

    Args:
        key: The key to use for the lock
        timeout: The timeout in seconds for the lock
        retry_count: Number of times to retry acquiring the lock
        retry_delay: Delay in seconds between retries

    Returns:
        Decorator function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate a unique lock value
            lock_value = str(uuid.uuid4())
            
            # Add prefix to key
            prefixed_key = f"{LOCK_PREFIX}{key}"
            
            # Try to acquire the lock
            acquired = False
            for i in range(retry_count + 1):
                acquired = cache.add(prefixed_key, lock_value, timeout)
                if acquired:
                    break
                if i < retry_count:
                    logger.debug(f"Failed to acquire lock {key}, retrying in {retry_delay}s")
                    time.sleep(retry_delay)
            
            if not acquired:
                logger.warning(f"Failed to acquire lock {key} after {retry_count} retries")
                raise LockError(f"Failed to acquire lock {key}")
            
            try:
                # Execute the function
                return func(*args, **kwargs)
            finally:
                # Release the lock
                # Only release if we still own the lock
                current_value = cache.get(prefixed_key)
                if current_value == lock_value:
                    cache.delete(prefixed_key)
                    logger.debug(f"Released lock {key}")
                else:
                    logger.warning(f"Lock {key} was already released or expired")
        
        return wrapper
    
    return decorator


class LockError(Exception):
    """Exception raised when a lock cannot be acquired."""
    pass


def acquire_lock(
    key: str,
    timeout: int = DEFAULT_TIMEOUT,
    retry_count: int = DEFAULT_RETRY_COUNT,
    retry_delay: float = DEFAULT_RETRY_DELAY,
) -> Optional[str]:
    """
    Acquire a Redis lock.

    Args:
        key: The key to use for the lock
        timeout: The timeout in seconds for the lock
        retry_count: Number of times to retry acquiring the lock
        retry_delay: Delay in seconds between retries

    Returns:
        Lock value if acquired, None otherwise
    """
    # Generate a unique lock value
    lock_value = str(uuid.uuid4())
    
    # Add prefix to key
    prefixed_key = f"{LOCK_PREFIX}{key}"
    
    # Try to acquire the lock
    for i in range(retry_count + 1):
        acquired = cache.add(prefixed_key, lock_value, timeout)
        if acquired:
            logger.debug(f"Acquired lock {key}")
            return lock_value
        if i < retry_count:
            logger.debug(f"Failed to acquire lock {key}, retrying in {retry_delay}s")
            time.sleep(retry_delay)
    
    logger.warning(f"Failed to acquire lock {key} after {retry_count} retries")
    return None


def release_lock(key: str, lock_value: str) -> bool:
    """
    Release a Redis lock.

    Args:
        key: The key used for the lock
        lock_value: The value returned by acquire_lock

    Returns:
        True if the lock was released, False otherwise
    """
    # Add prefix to key
    prefixed_key = f"{LOCK_PREFIX}{key}"
    
    # Only release if we still own the lock
    current_value = cache.get(prefixed_key)
    if current_value == lock_value:
        cache.delete(prefixed_key)
        logger.debug(f"Released lock {key}")
        return True
    else:
        logger.warning(f"Lock {key} was already released or expired")
        return False

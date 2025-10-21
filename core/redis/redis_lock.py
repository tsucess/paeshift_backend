"""
Redis-based distributed locking.

This module provides utilities for distributed locking using Redis.
"""

import logging
import time
from contextlib import contextmanager
from typing import Optional

from django.core.cache import cache

logger = logging.getLogger(__name__)

# Constants
LOCK_PREFIX = "lock:"
DEFAULT_TIMEOUT = 30  # seconds
DEFAULT_WAIT_TIMEOUT = 0  # seconds
DEFAULT_SLEEP_INTERVAL = 0.1  # seconds


def get_lock_key(name: str) -> str:
    """
    Get a lock key.
    
    Args:
        name: Lock name
        
    Returns:
        Lock key
    """
    return f"{LOCK_PREFIX}{name}"


def acquire_lock(name: str, timeout: int = DEFAULT_TIMEOUT) -> bool:
    """
    Acquire a lock.
    
    Args:
        name: Lock name
        timeout: Lock timeout in seconds
        
    Returns:
        True if lock acquired, False otherwise
    """
    lock_key = get_lock_key(name)
    
    # Try to acquire lock using add (which fails if the key already exists)
    acquired = cache.add(lock_key, "1", timeout)
    
    if acquired:
        logger.debug(f"Acquired lock: {name}")
    else:
        logger.debug(f"Failed to acquire lock: {name}")
    
    return acquired


def release_lock(name: str) -> bool:
    """
    Release a lock.
    
    Args:
        name: Lock name
        
    Returns:
        True if lock released, False otherwise
    """
    lock_key = get_lock_key(name)
    
    # Delete the lock key
    cache.delete(lock_key)
    
    logger.debug(f"Released lock: {name}")
    
    return True


@contextmanager
def redis_lock(name: str, timeout: int = DEFAULT_TIMEOUT, wait_timeout: int = DEFAULT_WAIT_TIMEOUT):
    """
    Context manager for Redis locks.
    
    Args:
        name: Lock name
        timeout: Lock timeout in seconds
        wait_timeout: Time to wait for the lock in seconds
        
    Yields:
        True if lock acquired, False otherwise
    """
    acquired = False
    
    # Try to acquire lock
    start_time = time.time()
    while not acquired and (time.time() - start_time) < wait_timeout:
        acquired = acquire_lock(name, timeout)
        
        if not acquired and wait_timeout > 0:
            # Wait and try again
            time.sleep(DEFAULT_SLEEP_INTERVAL)
    
    try:
        # Yield the result
        yield acquired
    finally:
        # Release lock if acquired
        if acquired:
            release_lock(name)

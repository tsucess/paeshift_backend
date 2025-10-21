"""
Distributed locking utilities.

This module provides utilities for distributed locking using Redis,
ensuring that critical operations are performed atomically across multiple processes.
"""

import logging
import time
import uuid
from contextlib import contextmanager
from typing import Optional

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Constants
DEFAULT_LOCK_TIMEOUT = getattr(settings, 'DISTRIBUTED_LOCK_TIMEOUT', 60)  # 60 seconds
DEFAULT_RETRY_COUNT = getattr(settings, 'DISTRIBUTED_LOCK_RETRY_COUNT', 3)
DEFAULT_RETRY_DELAY = getattr(settings, 'DISTRIBUTED_LOCK_RETRY_DELAY', 0.2)  # 200ms


class DistributedLock:
    """
    Distributed lock implementation using Redis.
    
    This class provides a distributed lock that can be used to ensure
    that critical operations are performed atomically across multiple processes.
    """
    
    def __init__(self, name, timeout=DEFAULT_LOCK_TIMEOUT, retry_count=DEFAULT_RETRY_COUNT, 
                 retry_delay=DEFAULT_RETRY_DELAY):
        """
        Initialize the distributed lock.
        
        Args:
            name: Lock name
            timeout: Lock timeout in seconds
            retry_count: Number of times to retry acquiring the lock
            retry_delay: Delay between retries in seconds
        """
        self.name = f"lock:{name}"
        self.timeout = timeout
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.token = str(uuid.uuid4())
        self.acquired = False
    
    def acquire(self) -> bool:
        """
        Acquire the lock.
        
        Returns:
            True if the lock was acquired, False otherwise
        """
        for attempt in range(self.retry_count + 1):
            # Try to acquire the lock
            acquired = cache.add(self.name, self.token, self.timeout)
            
            if acquired:
                self.acquired = True
                logger.debug(f"Acquired lock {self.name} (token: {self.token})")
                return True
            
            # If this is not the last attempt, wait and retry
            if attempt < self.retry_count:
                time.sleep(self.retry_delay)
        
        logger.warning(f"Failed to acquire lock {self.name} after {self.retry_count + 1} attempts")
        return False
    
    def release(self) -> bool:
        """
        Release the lock.
        
        Returns:
            True if the lock was released, False otherwise
        """
        if not self.acquired:
            logger.warning(f"Attempted to release unacquired lock {self.name}")
            return False
        
        # Get the current token
        current_token = cache.get(self.name)
        
        # Only release the lock if the token matches
        if current_token == self.token:
            cache.delete(self.name)
            self.acquired = False
            logger.debug(f"Released lock {self.name} (token: {self.token})")
            return True
        else:
            logger.warning(
                f"Failed to release lock {self.name}: token mismatch "
                f"(expected: {self.token}, actual: {current_token})"
            )
            return False
    
    def extend(self, additional_timeout: Optional[int] = None) -> bool:
        """
        Extend the lock timeout.
        
        Args:
            additional_timeout: Additional timeout in seconds (if None, uses the original timeout)
            
        Returns:
            True if the lock was extended, False otherwise
        """
        if not self.acquired:
            logger.warning(f"Attempted to extend unacquired lock {self.name}")
            return False
        
        # Get the current token
        current_token = cache.get(self.name)
        
        # Only extend the lock if the token matches
        if current_token == self.token:
            timeout = additional_timeout if additional_timeout is not None else self.timeout
            cache.set(self.name, self.token, timeout)
            logger.debug(f"Extended lock {self.name} (token: {self.token}) for {timeout} seconds")
            return True
        else:
            logger.warning(
                f"Failed to extend lock {self.name}: token mismatch "
                f"(expected: {self.token}, actual: {current_token})"
            )
            return False
    
    def is_locked(self) -> bool:
        """
        Check if the lock is currently held.
        
        Returns:
            True if the lock is held, False otherwise
        """
        return cache.get(self.name) is not None
    
    def is_owner(self) -> bool:
        """
        Check if the current instance owns the lock.
        
        Returns:
            True if the current instance owns the lock, False otherwise
        """
        return cache.get(self.name) == self.token


@contextmanager
def distributed_lock(name, timeout=DEFAULT_LOCK_TIMEOUT, retry_count=DEFAULT_RETRY_COUNT, 
                    retry_delay=DEFAULT_RETRY_DELAY):
    """
    Context manager for distributed locking.
    
    This context manager acquires a distributed lock, executes the code block,
    and releases the lock when the block completes.
    
    Args:
        name: Lock name
        timeout: Lock timeout in seconds
        retry_count: Number of times to retry acquiring the lock
        retry_delay: Delay between retries in seconds
        
    Yields:
        True if the lock was acquired, False otherwise
    """
    lock = DistributedLock(name, timeout, retry_count, retry_delay)
    acquired = lock.acquire()
    
    try:
        yield acquired
    finally:
        if acquired:
            lock.release()


def with_distributed_lock(name, timeout=DEFAULT_LOCK_TIMEOUT, retry_count=DEFAULT_RETRY_COUNT, 
                         retry_delay=DEFAULT_RETRY_DELAY):
    """
    Decorator for distributed locking.
    
    This decorator acquires a distributed lock before executing the function,
    and releases the lock when the function completes.
    
    Args:
        name: Lock name or function that returns a lock name
        timeout: Lock timeout in seconds
        retry_count: Number of times to retry acquiring the lock
        retry_delay: Delay between retries in seconds
        
    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get lock name
            lock_name = name
            if callable(name):
                lock_name = name(*args, **kwargs)
            
            # Acquire lock
            with distributed_lock(lock_name, timeout, retry_count, retry_delay) as acquired:
                if not acquired:
                    logger.warning(f"Failed to acquire lock {lock_name} for {func.__name__}")
                    raise RuntimeError(f"Failed to acquire lock {lock_name}")
                
                # Execute function
                return func(*args, **kwargs)
        
        return wrapper
    
    return decorator

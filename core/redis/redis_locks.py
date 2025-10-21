"""
Redis-based distributed locking and cache stampede protection.

This module provides utilities for distributed locking and cache stampede protection
using Redis, ensuring that concurrent processes don't interfere with each other.
"""

import logging
import random
import time
import uuid
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Optional, Union

import redis
from django.conf import settings

from core.cache import get_cached_data, redis_client, set_cached_data
from core.redis_keys import CacheNamespace, CacheTTL, generate_key
from core.redis_settings import CACHE_ENABLED

logger = logging.getLogger(__name__)

# Constants
DEFAULT_LOCK_TIMEOUT = CacheTTL.LOCK_TIMEOUT  # 60 seconds
DEFAULT_LOCK_SLEEP = 0.1  # 100ms
DEFAULT_LOCK_RETRIES = 50  # 5 seconds total
STAMPEDE_WINDOW_RATIO = 0.1  # 10% of TTL
MIN_STAMPEDE_WINDOW = 5  # 5 seconds minimum
MAX_STAMPEDE_WINDOW = 300  # 5 minutes maximum


class LockAcquisitionError(Exception):
    """Exception raised when a lock cannot be acquired."""
    pass


class DistributedLock:
    """
    Redis-based distributed lock implementation.
    
    This class provides a distributed lock using Redis, ensuring that
    only one process can execute a critical section at a time.
    """
    
    def __init__(
        self,
        lock_name: str,
        timeout: int = DEFAULT_LOCK_TIMEOUT,
        sleep_time: float = DEFAULT_LOCK_SLEEP,
        max_retries: int = DEFAULT_LOCK_RETRIES,
        namespace: Union[str, CacheNamespace] = CacheNamespace.LOCK,
    ):
        """
        Initialize a distributed lock.
        
        Args:
            lock_name: Name of the lock
            timeout: Lock timeout in seconds
            sleep_time: Time to sleep between retries
            max_retries: Maximum number of retries
            namespace: Cache namespace for the lock
        """
        self.lock_name = lock_name
        self.timeout = timeout
        self.sleep_time = sleep_time
        self.max_retries = max_retries
        self.namespace = namespace
        self.lock_id = str(uuid.uuid4())
        self.lock_key = generate_key(namespace, lock_name)
        self.acquired = False
    
    def acquire(self, blocking: bool = True) -> bool:
        """
        Acquire the lock.
        
        Args:
            blocking: Whether to block until the lock is acquired
            
        Returns:
            True if the lock was acquired, False otherwise
            
        Raises:
            LockAcquisitionError: If the lock cannot be acquired and blocking is True
        """
        if not CACHE_ENABLED or not redis_client:
            logger.warning(f"Redis not available, lock {self.lock_name} not acquired")
            return True
        
        start_time = time.time()
        retries = 0
        
        while True:
            # Try to acquire the lock using SET NX
            acquired = redis_client.set(
                self.lock_key, self.lock_id, ex=self.timeout, nx=True
            )
            
            if acquired:
                self.acquired = True
                duration_ms = round((time.time() - start_time) * 1000, 2)
                logger.debug(
                    f"Lock acquired: {self.lock_name} "
                    f"[id={self.lock_id}, retries={retries}, duration={duration_ms}ms]"
                )
                return True
            
            # If not blocking, return False immediately
            if not blocking:
                logger.debug(f"Lock not acquired (non-blocking): {self.lock_name}")
                return False
            
            # If we've reached the maximum number of retries, raise an exception
            if retries >= self.max_retries:
                duration_ms = round((time.time() - start_time) * 1000, 2)
                error_msg = (
                    f"Failed to acquire lock {self.lock_name} after {retries} retries "
                    f"({duration_ms}ms)"
                )
                logger.error(error_msg)
                raise LockAcquisitionError(error_msg)
            
            # Sleep and retry
            retries += 1
            time.sleep(self.sleep_time)
    
    def release(self) -> bool:
        """
        Release the lock.
        
        Returns:
            True if the lock was released, False otherwise
        """
        if not CACHE_ENABLED or not redis_client or not self.acquired:
            return False
        
        try:
            # Only release the lock if it's still owned by us
            # This prevents releasing a lock that has expired and been acquired by another process
            script = """
            if redis.call('get', KEYS[1]) == ARGV[1] then
                return redis.call('del', KEYS[1])
            else
                return 0
            end
            """
            result = redis_client.eval(script, 1, self.lock_key, self.lock_id)
            
            if result:
                logger.debug(f"Lock released: {self.lock_name} [id={self.lock_id}]")
                self.acquired = False
                return True
            else:
                logger.warning(
                    f"Lock not released (not owner): {self.lock_name} [id={self.lock_id}]"
                )
                return False
        except Exception as e:
            logger.error(f"Error releasing lock {self.lock_name}: {str(e)}")
            return False
    
    def __enter__(self):
        """Context manager entry."""
        self.acquire()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()


@contextmanager
def distributed_lock(
    lock_name: str,
    timeout: int = DEFAULT_LOCK_TIMEOUT,
    sleep_time: float = DEFAULT_LOCK_SLEEP,
    max_retries: int = DEFAULT_LOCK_RETRIES,
    namespace: Union[str, CacheNamespace] = CacheNamespace.LOCK,
):
    """
    Context manager for distributed locking.
    
    Args:
        lock_name: Name of the lock
        timeout: Lock timeout in seconds
        sleep_time: Time to sleep between retries
        max_retries: Maximum number of retries
        namespace: Cache namespace for the lock
        
    Yields:
        The lock object
        
    Raises:
        LockAcquisitionError: If the lock cannot be acquired
    """
    lock = DistributedLock(
        lock_name, timeout, sleep_time, max_retries, namespace
    )
    lock.acquire()
    try:
        yield lock
    finally:
        lock.release()


def with_distributed_lock(
    lock_name_or_func: Union[str, Callable],
    timeout: int = DEFAULT_LOCK_TIMEOUT,
    sleep_time: float = DEFAULT_LOCK_SLEEP,
    max_retries: int = DEFAULT_LOCK_RETRIES,
    namespace: Union[str, CacheNamespace] = CacheNamespace.LOCK,
):
    """
    Decorator for distributed locking.
    
    Args:
        lock_name_or_func: Name of the lock or the function to decorate
        timeout: Lock timeout in seconds
        sleep_time: Time to sleep between retries
        max_retries: Maximum number of retries
        namespace: Cache namespace for the lock
        
    Returns:
        Decorated function
        
    Raises:
        LockAcquisitionError: If the lock cannot be acquired
    """
    # Handle case where decorator is used without arguments
    if callable(lock_name_or_func):
        func = lock_name_or_func
        lock_name = f"{func.__module__}.{func.__name__}"
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            with distributed_lock(
                lock_name, timeout, sleep_time, max_retries, namespace
            ):
                return func(*args, **kwargs)
        
        return wrapper
    
    # Handle case where decorator is used with arguments
    lock_name = lock_name_or_func
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # If lock_name is a format string, format it with args and kwargs
            actual_lock_name = lock_name
            if "{" in lock_name and "}" in lock_name:
                try:
                    # Create a dict with positional args as arg0, arg1, etc.
                    format_args = {f"arg{i}": arg for i, arg in enumerate(args)}
                    # Add kwargs
                    format_args.update(kwargs)
                    # Add function name
                    format_args["func"] = func.__name__
                    # Format the lock name
                    actual_lock_name = lock_name.format(**format_args)
                except Exception as e:
                    logger.warning(
                        f"Error formatting lock name {lock_name}: {str(e)}. "
                        f"Using original lock name."
                    )
            
            with distributed_lock(
                actual_lock_name, timeout, sleep_time, max_retries, namespace
            ):
                return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def get_with_stampede_protection(
    key: str,
    getter_func: Callable,
    ttl: int,
    *args,
    **kwargs,
) -> Any:
    """
    Get a value from cache with stampede protection.
    
    This function implements the probabilistic early expiration algorithm
    to prevent cache stampedes.
    
    Args:
        key: Cache key
        getter_func: Function to get the value if not in cache
        ttl: Cache TTL in seconds
        *args: Arguments to pass to getter_func
        **kwargs: Keyword arguments to pass to getter_func
        
    Returns:
        The cached value or the result of getter_func
    """
    if not CACHE_ENABLED or not redis_client:
        return getter_func(*args, **kwargs)
    
    # Try to get from cache
    cached_value = get_cached_data(key)
    
    # If found in cache, check if we should refresh it
    if cached_value is not None:
        # Calculate the stampede window (10% of TTL, min 5s, max 5min)
        window = max(min(ttl * STAMPEDE_WINDOW_RATIO, MAX_STAMPEDE_WINDOW), MIN_STAMPEDE_WINDOW)
        
        # Get the remaining TTL
        try:
            remaining_ttl = redis_client.ttl(key)
            
            # If the remaining TTL is within the window, refresh with probability
            # proportional to how close we are to expiration
            if 0 < remaining_ttl < window:
                # Calculate probability (higher as we get closer to expiration)
                probability = 1 - (remaining_ttl / window)
                
                # Refresh with calculated probability
                if random.random() < probability:
                    logger.debug(
                        f"Early refresh for key {key} "
                        f"[ttl={remaining_ttl}s, window={window}s, prob={probability:.2f}]"
                    )
                    
                    # Use a lock to ensure only one process refreshes the cache
                    lock_name = f"refresh:{key}"
                    lock = DistributedLock(lock_name, timeout=10)
                    
                    if lock.acquire(blocking=False):
                        try:
                            # Get fresh value
                            fresh_value = getter_func(*args, **kwargs)
                            
                            # Update cache
                            set_cached_data(key, fresh_value, ttl)
                            
                            # Return fresh value
                            return fresh_value
                        finally:
                            lock.release()
        except Exception as e:
            logger.warning(f"Error checking TTL for key {key}: {str(e)}")
        
        # Return cached value
        return cached_value
    
    # Not in cache, get fresh value with lock to prevent multiple processes
    # from generating the same value simultaneously
    lock_name = f"generate:{key}"
    
    try:
        with distributed_lock(lock_name, timeout=30):
            # Check cache again in case another process has already generated the value
            cached_value = get_cached_data(key)
            if cached_value is not None:
                return cached_value
            
            # Generate fresh value
            fresh_value = getter_func(*args, **kwargs)
            
            # Cache the value
            set_cached_data(key, fresh_value, ttl)
            
            return fresh_value
    except LockAcquisitionError:
        # If we couldn't acquire the lock, someone else is generating the value
        # Wait a bit and check the cache again
        time.sleep(1)
        cached_value = get_cached_data(key)
        
        if cached_value is not None:
            return cached_value
        
        # If still not in cache, generate without caching to avoid overload
        logger.warning(
            f"Lock acquisition failed for key {key}, generating value without caching"
        )
        return getter_func(*args, **kwargs)


def cache_with_stampede_protection(
    ttl: int,
    key_func: Optional[Callable] = None,
    namespace: Union[str, CacheNamespace] = CacheNamespace.DEFAULT,
):
    """
    Decorator for caching with stampede protection.
    
    Args:
        ttl: Cache TTL in seconds
        key_func: Function to generate the cache key
        namespace: Cache namespace
        
    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not CACHE_ENABLED or not redis_client:
                return func(*args, **kwargs)
            
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Generate a key based on function name and arguments
                from core.redis_keys import function_cache_key
                cache_key = function_cache_key(func, *args, **kwargs, namespace=namespace)
            
            # Get with stampede protection
            return get_with_stampede_protection(
                cache_key, func, ttl, *args, **kwargs
            )
        
        return wrapper
    
    return decorator

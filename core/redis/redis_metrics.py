"""
Redis-based metrics collection and monitoring.

This module provides utilities for collecting and monitoring metrics using Redis.
"""

import logging
import time
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Union

from django.core.cache import cache

logger = logging.getLogger(__name__)

# Constants
METRICS_PREFIX = "metrics:"
COUNTER_PREFIX = "counter:"
GAUGE_PREFIX = "gauge:"
TIMER_PREFIX = "timer:"
HISTOGRAM_PREFIX = "histogram:"
METRICS_EXPIRATION = 60 * 60 * 24 * 7  # 7 days


def get_hash_key(prefix: str, name: str) -> str:
    """
    Get a hash key.
    
    Args:
        prefix: Key prefix
        name: Metric name
        
    Returns:
        Hash key
    """
    return f"{prefix}{name}"


def increment_counter(namespace: str, name: str, value: int = 1) -> bool:
    """
    Increment a counter.
    
    Args:
        namespace: Metrics namespace
        name: Counter name
        value: Value to increment by
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Generate counter key
        counter_key = f"{METRICS_PREFIX}{namespace}:{COUNTER_PREFIX}"
        
        # Increment counter
        pipe = cache.client.pipeline()
        pipe.hincrby(counter_key, name, value)
        pipe.expire(counter_key, METRICS_EXPIRATION)
        pipe.execute()
        
        return True
    except Exception as e:
        logger.error(f"Error incrementing counter {namespace}.{name}: {str(e)}")
        return False


def get_counter(namespace: str, name: str) -> int:
    """
    Get a counter value.
    
    Args:
        namespace: Metrics namespace
        name: Counter name
        
    Returns:
        Counter value
    """
    try:
        # Generate counter key
        counter_key = f"{METRICS_PREFIX}{namespace}:{COUNTER_PREFIX}"
        
        # Get counter
        value = cache.client.hget(counter_key, name)
        
        return int(value) if value else 0
    except Exception as e:
        logger.error(f"Error getting counter {namespace}.{name}: {str(e)}")
        return 0


def set_gauge(namespace: str, name: str, value: float) -> bool:
    """
    Set a gauge value.
    
    Args:
        namespace: Metrics namespace
        name: Gauge name
        value: Gauge value
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Generate gauge key
        gauge_key = f"{METRICS_PREFIX}{namespace}:{GAUGE_PREFIX}"
        
        # Set gauge
        pipe = cache.client.pipeline()
        pipe.hset(gauge_key, name, value)
        pipe.expire(gauge_key, METRICS_EXPIRATION)
        pipe.execute()
        
        return True
    except Exception as e:
        logger.error(f"Error setting gauge {namespace}.{name}: {str(e)}")
        return False


def get_gauge(namespace: str, name: str) -> float:
    """
    Get a gauge value.
    
    Args:
        namespace: Metrics namespace
        name: Gauge name
        
    Returns:
        Gauge value
    """
    try:
        # Generate gauge key
        gauge_key = f"{METRICS_PREFIX}{namespace}:{GAUGE_PREFIX}"
        
        # Get gauge
        value = cache.client.hget(gauge_key, name)
        
        return float(value) if value else 0.0
    except Exception as e:
        logger.error(f"Error getting gauge {namespace}.{name}: {str(e)}")
        return 0.0


def record_timer(namespace: str, name: str, value: float) -> bool:
    """
    Record a timer value.
    
    Args:
        namespace: Metrics namespace
        name: Timer name
        value: Timer value in milliseconds
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Generate timer key
        timer_key = f"{METRICS_PREFIX}{namespace}:{TIMER_PREFIX}{name}"
        
        # Record timer
        pipe = cache.client.pipeline()
        pipe.lpush(timer_key, value)
        pipe.ltrim(timer_key, 0, 999)  # Keep only the last 1000 values
        pipe.expire(timer_key, METRICS_EXPIRATION)
        pipe.execute()
        
        return True
    except Exception as e:
        logger.error(f"Error recording timer {namespace}.{name}: {str(e)}")
        return False


def get_timer_stats(namespace: str, name: str) -> Dict[str, float]:
    """
    Get timer statistics.
    
    Args:
        namespace: Metrics namespace
        name: Timer name
        
    Returns:
        Timer statistics
    """
    try:
        # Generate timer key
        timer_key = f"{METRICS_PREFIX}{namespace}:{TIMER_PREFIX}{name}"
        
        # Get timer values
        values = cache.client.lrange(timer_key, 0, -1)
        
        # Convert to float
        values = [float(value) for value in values]
        
        # Calculate statistics
        if values:
            return {
                "count": len(values),
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
                "p50": sorted(values)[len(values) // 2],
                "p90": sorted(values)[int(len(values) * 0.9)],
                "p95": sorted(values)[int(len(values) * 0.95)],
                "p99": sorted(values)[int(len(values) * 0.99)],
            }
        else:
            return {
                "count": 0,
                "min": 0,
                "max": 0,
                "avg": 0,
                "p50": 0,
                "p90": 0,
                "p95": 0,
                "p99": 0,
            }
    except Exception as e:
        logger.error(f"Error getting timer stats {namespace}.{name}: {str(e)}")
        return {
            "count": 0,
            "min": 0,
            "max": 0,
            "avg": 0,
            "p50": 0,
            "p90": 0,
            "p95": 0,
            "p99": 0,
            "error": str(e),
        }


def time_function(namespace: str, name: str):
    """
    Decorator for timing functions.
    
    Args:
        namespace: Metrics namespace
        name: Timer name
        
    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Start timer
            start_time = time.time()
            
            try:
                # Call function
                result = func(*args, **kwargs)
                
                # Record time
                elapsed_ms = (time.time() - start_time) * 1000
                record_timer(namespace, name, elapsed_ms)
                
                return result
            except Exception as e:
                # Record time even on exception
                elapsed_ms = (time.time() - start_time) * 1000
                record_timer(namespace, name, elapsed_ms)
                
                # Record error counter
                increment_counter(namespace, f"{name}.error", 1)
                
                # Re-raise exception
                raise
                
        return wrapper
    return decorator

"""
Cache telemetry and monitoring utilities.

This module provides utilities for monitoring cache performance and health,
including hit rates, latency, and consistency metrics.
"""

import json
import logging
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Dict, List, Optional, Set, Tuple, Union, Any

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

# Constants
TELEMETRY_ENABLED = getattr(settings, 'CACHE_TELEMETRY_ENABLED', True)
TELEMETRY_SAMPLE_RATE = getattr(settings, 'CACHE_TELEMETRY_SAMPLE_RATE', 0.1)  # 10% of operations
TELEMETRY_RETENTION_DAYS = getattr(settings, 'CACHE_TELEMETRY_RETENTION_DAYS', 7)
TELEMETRY_AGGREGATION_INTERVAL = getattr(settings, 'CACHE_TELEMETRY_AGGREGATION_INTERVAL', 300)  # 5 minutes

# Redis keys
TELEMETRY_HIT_RATE_KEY = 'cache:telemetry:hit_rate'
TELEMETRY_LATENCY_KEY = 'cache:telemetry:latency'
TELEMETRY_ERRORS_KEY = 'cache:telemetry:errors'
TELEMETRY_CONSISTENCY_KEY = 'cache:telemetry:consistency'
TELEMETRY_OPERATIONS_KEY = 'cache:telemetry:operations'


def record_cache_operation(operation, key, success, latency_ms, data_size=None):
    """
    Record a cache operation for telemetry.
    
    Args:
        operation: Operation type ('get', 'set', 'delete')
        key: Cache key
        success: Whether the operation was successful
        latency_ms: Operation latency in milliseconds
        data_size: Size of data in bytes (for 'set' operations)
    """
    if not TELEMETRY_ENABLED:
        return
    
    # Only sample a percentage of operations to reduce overhead
    import random
    if random.random() > TELEMETRY_SAMPLE_RATE:
        return
    
    try:
        # Get current timestamp
        now = timezone.now()
        timestamp = int(now.timestamp())
        
        # Round timestamp to aggregation interval
        interval_timestamp = timestamp - (timestamp % TELEMETRY_AGGREGATION_INTERVAL)
        
        # Extract model name from key if possible
        model_name = 'unknown'
        if ':' in key:
            parts = key.split(':')
            if len(parts) >= 2:
                model_name = parts[0]
        
        # Create telemetry data
        telemetry_data = {
            'operation': operation,
            'key': key,
            'model': model_name,
            'success': success,
            'latency_ms': latency_ms,
            'timestamp': timestamp,
        }
        
        if data_size is not None:
            telemetry_data['data_size'] = data_size
        
        # Record operation
        operations_key = f"{TELEMETRY_OPERATIONS_KEY}:{interval_timestamp}"
        cache.lpush(operations_key, json.dumps(telemetry_data))
        cache.expire(operations_key, TELEMETRY_RETENTION_DAYS * 86400)
        
        # Update hit rate
        if operation == 'get':
            hit_rate_key = f"{TELEMETRY_HIT_RATE_KEY}:{model_name}:{interval_timestamp}"
            if success:
                cache.hincrby(hit_rate_key, 'hits', 1)
            else:
                cache.hincrby(hit_rate_key, 'misses', 1)
            cache.expire(hit_rate_key, TELEMETRY_RETENTION_DAYS * 86400)
        
        # Update latency
        latency_key = f"{TELEMETRY_LATENCY_KEY}:{model_name}:{operation}:{interval_timestamp}"
        cache.lpush(latency_key, latency_ms)
        cache.ltrim(latency_key, 0, 999)  # Keep only the last 1000 latency measurements
        cache.expire(latency_key, TELEMETRY_RETENTION_DAYS * 86400)
        
        # Update errors
        if not success:
            errors_key = f"{TELEMETRY_ERRORS_KEY}:{model_name}:{interval_timestamp}"
            cache.hincrby(errors_key, operation, 1)
            cache.expire(errors_key, TELEMETRY_RETENTION_DAYS * 86400)
        
    except Exception as e:
        logger.exception(f"Error recording cache telemetry: {str(e)}")


def record_cache_consistency(model_name, consistency_ratio):
    """
    Record cache consistency metrics.
    
    Args:
        model_name: Model name
        consistency_ratio: Consistency ratio (0.0 to 1.0)
    """
    if not TELEMETRY_ENABLED:
        return
    
    try:
        # Get current timestamp
        now = timezone.now()
        timestamp = int(now.timestamp())
        
        # Round timestamp to aggregation interval
        interval_timestamp = timestamp - (timestamp % TELEMETRY_AGGREGATION_INTERVAL)
        
        # Record consistency
        consistency_key = f"{TELEMETRY_CONSISTENCY_KEY}:{model_name}:{interval_timestamp}"
        cache.lpush(consistency_key, consistency_ratio)
        cache.ltrim(consistency_key, 0, 99)  # Keep only the last 100 consistency measurements
        cache.expire(consistency_key, TELEMETRY_RETENTION_DAYS * 86400)
        
    except Exception as e:
        logger.exception(f"Error recording cache consistency: {str(e)}")


def get_cache_telemetry(model_name=None, start_time=None, end_time=None):
    """
    Get cache telemetry metrics.
    
    Args:
        model_name: Model name (optional)
        start_time: Start time (optional)
        end_time: End time (optional)
        
    Returns:
        Dictionary with telemetry metrics
    """
    if not TELEMETRY_ENABLED:
        return {'enabled': False}
    
    try:
        # Set default time range if not provided
        if end_time is None:
            end_time = timezone.now()
        if start_time is None:
            start_time = end_time - timedelta(hours=24)
        
        # Convert to timestamps
        start_timestamp = int(start_time.timestamp())
        end_timestamp = int(end_time.timestamp())
        
        # Round timestamps to aggregation interval
        start_interval = start_timestamp - (start_timestamp % TELEMETRY_AGGREGATION_INTERVAL)
        end_interval = end_timestamp - (end_timestamp % TELEMETRY_AGGREGATION_INTERVAL)
        
        # Initialize metrics
        metrics = {
            'hit_rate': {},
            'latency': {},
            'errors': {},
            'consistency': {},
            'operations': {},
            'time_range': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
            },
        }
        
        # Get all keys in the time range
        interval = start_interval
        while interval <= end_interval:
            # Get hit rate
            if model_name:
                hit_rate_key = f"{TELEMETRY_HIT_RATE_KEY}:{model_name}:{interval}"
                hit_rate_data = cache.hgetall(hit_rate_key)
                if hit_rate_data:
                    hits = int(hit_rate_data.get('hits', 0))
                    misses = int(hit_rate_data.get('misses', 0))
                    total = hits + misses
                    if total > 0:
                        metrics['hit_rate'][interval] = {
                            'hits': hits,
                            'misses': misses,
                            'total': total,
                            'rate': hits / total,
                        }
            else:
                # Get hit rate for all models
                hit_rate_pattern = f"{TELEMETRY_HIT_RATE_KEY}:*:{interval}"
                hit_rate_keys = cache.keys(hit_rate_pattern)
                for key in hit_rate_keys:
                    model = key.split(':')[2]
                    hit_rate_data = cache.hgetall(key)
                    if hit_rate_data:
                        hits = int(hit_rate_data.get('hits', 0))
                        misses = int(hit_rate_data.get('misses', 0))
                        total = hits + misses
                        if total > 0:
                            if model not in metrics['hit_rate']:
                                metrics['hit_rate'][model] = {}
                            metrics['hit_rate'][model][interval] = {
                                'hits': hits,
                                'misses': misses,
                                'total': total,
                                'rate': hits / total,
                            }
            
            # Get latency
            if model_name:
                for operation in ['get', 'set', 'delete']:
                    latency_key = f"{TELEMETRY_LATENCY_KEY}:{model_name}:{operation}:{interval}"
                    latency_data = cache.lrange(latency_key, 0, -1)
                    if latency_data:
                        latencies = [float(x) for x in latency_data]
                        metrics['latency'][interval] = {
                            'operation': operation,
                            'min': min(latencies),
                            'max': max(latencies),
                            'avg': sum(latencies) / len(latencies),
                            'count': len(latencies),
                        }
            else:
                # Get latency for all models
                latency_pattern = f"{TELEMETRY_LATENCY_KEY}:*:{interval}"
                latency_keys = cache.keys(latency_pattern)
                for key in latency_keys:
                    parts = key.split(':')
                    model = parts[2]
                    operation = parts[3]
                    latency_data = cache.lrange(key, 0, -1)
                    if latency_data:
                        latencies = [float(x) for x in latency_data]
                        if model not in metrics['latency']:
                            metrics['latency'][model] = {}
                        if operation not in metrics['latency'][model]:
                            metrics['latency'][model][operation] = {}
                        metrics['latency'][model][operation][interval] = {
                            'min': min(latencies),
                            'max': max(latencies),
                            'avg': sum(latencies) / len(latencies),
                            'count': len(latencies),
                        }
            
            # Get errors
            if model_name:
                errors_key = f"{TELEMETRY_ERRORS_KEY}:{model_name}:{interval}"
                errors_data = cache.hgetall(errors_key)
                if errors_data:
                    metrics['errors'][interval] = {
                        'get': int(errors_data.get('get', 0)),
                        'set': int(errors_data.get('set', 0)),
                        'delete': int(errors_data.get('delete', 0)),
                        'total': sum(int(x) for x in errors_data.values()),
                    }
            else:
                # Get errors for all models
                errors_pattern = f"{TELEMETRY_ERRORS_KEY}:*:{interval}"
                errors_keys = cache.keys(errors_pattern)
                for key in errors_keys:
                    model = key.split(':')[2]
                    errors_data = cache.hgetall(key)
                    if errors_data:
                        if model not in metrics['errors']:
                            metrics['errors'][model] = {}
                        metrics['errors'][model][interval] = {
                            'get': int(errors_data.get('get', 0)),
                            'set': int(errors_data.get('set', 0)),
                            'delete': int(errors_data.get('delete', 0)),
                            'total': sum(int(x) for x in errors_data.values()),
                        }
            
            # Get consistency
            if model_name:
                consistency_key = f"{TELEMETRY_CONSISTENCY_KEY}:{model_name}:{interval}"
                consistency_data = cache.lrange(consistency_key, 0, -1)
                if consistency_data:
                    consistency_values = [float(x) for x in consistency_data]
                    metrics['consistency'][interval] = {
                        'min': min(consistency_values),
                        'max': max(consistency_values),
                        'avg': sum(consistency_values) / len(consistency_values),
                        'count': len(consistency_values),
                    }
            else:
                # Get consistency for all models
                consistency_pattern = f"{TELEMETRY_CONSISTENCY_KEY}:*:{interval}"
                consistency_keys = cache.keys(consistency_pattern)
                for key in consistency_keys:
                    model = key.split(':')[2]
                    consistency_data = cache.lrange(key, 0, -1)
                    if consistency_data:
                        consistency_values = [float(x) for x in consistency_data]
                        if model not in metrics['consistency']:
                            metrics['consistency'][model] = {}
                        metrics['consistency'][model][interval] = {
                            'min': min(consistency_values),
                            'max': max(consistency_values),
                            'avg': sum(consistency_values) / len(consistency_values),
                            'count': len(consistency_values),
                        }
            
            # Get operations
            operations_key = f"{TELEMETRY_OPERATIONS_KEY}:{interval}"
            operations_data = cache.lrange(operations_key, 0, -1)
            if operations_data:
                operations = [json.loads(x) for x in operations_data]
                if model_name:
                    operations = [op for op in operations if op.get('model') == model_name]
                
                # Group operations by model
                by_model = {}
                for op in operations:
                    model = op.get('model', 'unknown')
                    if model not in by_model:
                        by_model[model] = []
                    by_model[model].append(op)
                
                # Calculate metrics for each model
                for model, model_ops in by_model.items():
                    if model not in metrics['operations']:
                        metrics['operations'][model] = {}
                    
                    metrics['operations'][model][interval] = {
                        'count': len(model_ops),
                        'get': len([op for op in model_ops if op.get('operation') == 'get']),
                        'set': len([op for op in model_ops if op.get('operation') == 'set']),
                        'delete': len([op for op in model_ops if op.get('operation') == 'delete']),
                        'success': len([op for op in model_ops if op.get('success')]),
                        'error': len([op for op in model_ops if not op.get('success')]),
                    }
            
            # Move to next interval
            interval += TELEMETRY_AGGREGATION_INTERVAL
        
        return metrics
        
    except Exception as e:
        logger.exception(f"Error getting cache telemetry: {str(e)}")
        return {'error': str(e)}


def telemetry_decorator(func):
    """
    Decorator to add telemetry to cache operations.
    
    This decorator wraps cache operations to record telemetry metrics.
    
    Example:
        @telemetry_decorator
        def get_cached_data(key):
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Get operation type from function name
        operation = 'unknown'
        if 'get' in func.__name__:
            operation = 'get'
        elif 'set' in func.__name__ or 'cache' in func.__name__:
            operation = 'set'
        elif 'delete' in func.__name__ or 'remove' in func.__name__:
            operation = 'delete'
        
        # Get key from args or kwargs
        key = None
        if args and isinstance(args[0], str):
            key = args[0]
        elif 'key' in kwargs:
            key = kwargs['key']
        
        # Get data size for set operations
        data_size = None
        if operation == 'set' and len(args) > 1:
            data = args[1]
            if isinstance(data, (str, bytes)):
                data_size = len(data)
            elif isinstance(data, dict):
                data_size = len(json.dumps(data))
        
        # Record start time
        start_time = time.time()
        
        try:
            # Call the original function
            result = func(*args, **kwargs)
            
            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000
            
            # Determine success
            success = True
            if operation == 'get' and result is None:
                success = False
            
            # Record telemetry
            if key:
                record_cache_operation(operation, key, success, latency_ms, data_size)
            
            return result
            
        except Exception as e:
            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000
            
            # Record telemetry
            if key:
                record_cache_operation(operation, key, False, latency_ms, data_size)
            
            # Re-raise the exception
            raise
    
    return wrapper

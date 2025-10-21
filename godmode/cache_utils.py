"""
Cache utilities for God Mode.

This module provides utilities for working with Redis cache.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from django.utils import timezone

from core.cache import redis_client
from core.redis_settings import CACHE_ENABLED

logger = logging.getLogger(__name__)


def ensure_timestamp_in_cache_data(data: Dict) -> Dict:
    """
    Ensure that cache data has a timestamp.
    
    Args:
        data: Cache data
        
    Returns:
        Cache data with timestamp
    """
    # Check if data already has a timestamp
    timestamp_fields = ["last_updated", "updated_at", "timestamp", "modified_at"]
    has_timestamp = any(field in data for field in timestamp_fields)
    
    # If no timestamp, add one
    if not has_timestamp:
        data["timestamp"] = timezone.now().isoformat()
    
    return data


def get_cache_key_info(key: str) -> Dict:
    """
    Get information about a cache key.
    
    Args:
        key: Redis key
        
    Returns:
        Dictionary with key information
    """
    if not CACHE_ENABLED or not redis_client:
        return {"error": "Redis cache is not enabled"}
    
    try:
        # Get data from Redis
        data = redis_client.get(key)
        
        if not data:
            return {"error": f"No data found for key: {key}"}
        
        # Parse JSON data
        try:
            parsed_data = json.loads(data)
        except json.JSONDecodeError:
            return {
                "key": key,
                "type": "string",
                "size": len(data),
                "value": data.decode('utf-8') if len(data) < 1000 else f"{data.decode('utf-8')[:1000]}...",
            }
        
        # Get TTL
        ttl = redis_client.ttl(key)
        
        # Extract timestamp if available
        timestamp = None
        for field in ["last_updated", "updated_at", "timestamp", "modified_at", "created_at"]:
            if field in parsed_data and isinstance(parsed_data[field], str):
                try:
                    timestamp = datetime.fromisoformat(parsed_data[field])
                    break
                except ValueError:
                    pass
        
        # Return key info
        return {
            "key": key,
            "type": "json",
            "size": len(data),
            "ttl": ttl,
            "timestamp": timestamp.isoformat() if timestamp else None,
            "fields": list(parsed_data.keys()),
            "sample": {k: parsed_data[k] for k in list(parsed_data.keys())[:5]} if parsed_data else {},
        }
    except Exception as e:
        logger.error(f"Error getting cache key info for {key}: {str(e)}")
        return {"error": str(e)}


def get_model_cache_keys(model_name: str) -> List[str]:
    """
    Get all Redis keys for a specific model.
    
    Args:
        model_name: Name of the model (lowercase)
        
    Returns:
        List of Redis keys
    """
    if not CACHE_ENABLED or not redis_client:
        return []
    
    try:
        # Get keys for the model
        pattern = f"{model_name}:*"
        keys = redis_client.keys(pattern)
        
        # Also check for permanent cache
        permanent_pattern = f"permanent:{model_name}:*"
        permanent_keys = redis_client.keys(permanent_pattern)
        
        # Combine and return
        return [k.decode('utf-8') for k in keys + permanent_keys]
    except Exception as e:
        logger.error(f"Error getting keys for model {model_name}: {str(e)}")
        return []


def get_cache_stats() -> Dict:
    """
    Get Redis cache statistics.
    
    Returns:
        Dictionary with cache statistics
    """
    if not CACHE_ENABLED or not redis_client:
        return {"error": "Redis cache is not enabled"}
    
    try:
        # Get Redis info
        info = redis_client.info()
        
        # Get memory usage
        used_memory = info.get("used_memory", 0)
        used_memory_peak = info.get("used_memory_peak", 0)
        maxmemory = info.get("maxmemory", 0)
        
        # Calculate percentages
        memory_usage_percent = (used_memory / maxmemory * 100) if maxmemory > 0 else 0
        
        # Get hit rate
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        total_ops = hits + misses
        hit_rate = (hits / total_ops * 100) if total_ops > 0 else 0
        
        # Get key count
        db = info.get(f"db{redis_client.connection_pool.connection_kwargs.get('db', 0)}", {})
        keys = db.get("keys", 0)
        
        # Get key patterns
        key_patterns = {}
        all_keys = redis_client.keys("*")
        
        for key in all_keys:
            key_str = key.decode('utf-8')
            pattern = key_str.split(":")[0] if ":" in key_str else "other"
            
            if pattern in key_patterns:
                key_patterns[pattern] += 1
            else:
                key_patterns[pattern] = 1
        
        return {
            "memory": {
                "used_memory": used_memory,
                "used_memory_human": f"{used_memory / (1024 * 1024):.2f} MB",
                "used_memory_peak": used_memory_peak,
                "used_memory_peak_human": f"{used_memory_peak / (1024 * 1024):.2f} MB",
                "maxmemory": maxmemory,
                "maxmemory_human": f"{maxmemory / (1024 * 1024):.2f} MB" if maxmemory > 0 else "Unlimited",
                "memory_usage_percent": f"{memory_usage_percent:.2f}%",
            },
            "hit_rate": {
                "hits": hits,
                "misses": misses,
                "total_operations": total_ops,
                "hit_rate": f"{hit_rate:.2f}%",
            },
            "keys": {
                "total": keys,
                "patterns": key_patterns,
            },
            "uptime": {
                "seconds": info.get("uptime_in_seconds", 0),
                "days": f"{info.get('uptime_in_seconds', 0) / (24 * 60 * 60):.2f}",
            },
        }
    except Exception as e:
        logger.exception(f"Error getting cache stats: {str(e)}")
        return {"error": str(e)}

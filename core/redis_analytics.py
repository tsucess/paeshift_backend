"""
Redis cache analytics.

This module provides tools for analyzing Redis cache performance and identifying
opportunities for optimization.
"""

import json
import logging
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from core.redis_monitoring import (
    get_cache_stats,
    get_hit_rate,
    get_key_count_by_prefix,
    get_memory_usage,
    get_slow_operations,
)
from core.redis_settings import CACHE_ENABLED
from core.redis_telemetry import get_telemetry_stats

logger = logging.getLogger(__name__)

# Constants
ANALYTICS_SAMPLE_SIZE = getattr(settings, "CACHE_ANALYTICS_SAMPLE_SIZE", 1000)
ANALYTICS_MIN_HITS = getattr(settings, "CACHE_ANALYTICS_MIN_HITS", 10)
ANALYTICS_MIN_MISSES = getattr(settings, "CACHE_ANALYTICS_MIN_MISSES", 10)
ANALYTICS_MIN_SIZE = getattr(settings, "CACHE_ANALYTICS_MIN_SIZE", 1024)  # 1KB
ANALYTICS_HISTORY_DAYS = getattr(settings, "CACHE_ANALYTICS_HISTORY_DAYS", 7)


def analyze_hit_rate_by_prefix() -> Dict:
    """
    Analyze hit rate by key prefix.
    
    Returns:
        Dictionary with hit rate analysis by prefix
    """
    if not CACHE_ENABLED:
        return {"error": "Cache is disabled"}
        
    try:
        # Get telemetry stats
        telemetry = get_telemetry_stats()
        operations = telemetry.get("operations", {})
        
        # Extract get operations
        get_ops = operations.get("get", {})
        
        # Group by prefix
        prefixes = defaultdict(lambda: {"hits": 0, "misses": 0, "total": 0})
        
        for key, stats in get_ops.items():
            # Extract prefix (first part of the key)
            parts = key.split(":")
            prefix = parts[0] if parts else "unknown"
            
            # Count hits and misses
            hits = stats.get("success_count", 0)
            misses = stats.get("failure_count", 0)
            total = hits + misses
            
            prefixes[prefix]["hits"] += hits
            prefixes[prefix]["misses"] += misses
            prefixes[prefix]["total"] += total
        
        # Calculate hit rate for each prefix
        results = {}
        for prefix, stats in prefixes.items():
            hits = stats["hits"]
            total = stats["total"]
            
            if total > 0:
                hit_rate = hits / total
            else:
                hit_rate = 0
                
            results[prefix] = {
                "hits": hits,
                "misses": stats["misses"],
                "total": total,
                "hit_rate": hit_rate,
            }
        
        # Sort by hit rate (ascending)
        sorted_results = dict(sorted(
            results.items(),
            key=lambda item: item[1]["hit_rate"]
        ))
        
        return {
            "prefixes": sorted_results,
            "timestamp": timezone.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error analyzing hit rate by prefix: {str(e)}")
        return {"error": str(e)}


def analyze_key_size_distribution() -> Dict:
    """
    Analyze key size distribution.
    
    Returns:
        Dictionary with key size distribution
    """
    if not CACHE_ENABLED:
        return {"error": "Cache is disabled"}
        
    try:
        from django_redis import get_redis_connection
        redis_client = get_redis_connection("default")
        
        # Get all keys
        keys = redis_client.keys("*")
        
        if not keys:
            return {
                "total_keys": 0,
                "size_distribution": {},
                "timestamp": timezone.now().isoformat(),
            }
            
        # Sample keys if there are too many
        if len(keys) > ANALYTICS_SAMPLE_SIZE:
            import random
            keys = random.sample(keys, ANALYTICS_SAMPLE_SIZE)
        
        # Get size of each key
        size_distribution = defaultdict(int)
        total_size = 0
        
        for key in keys:
            # Get key type
            key_type = redis_client.type(key)
            
            # Get size based on type
            if key_type == b"string":
                # String value
                size = redis_client.strlen(key)
            elif key_type == b"hash":
                # Hash value
                size = sum(len(k) + len(v) for k, v in redis_client.hgetall(key).items())
            elif key_type == b"list":
                # List value
                size = sum(len(item) for item in redis_client.lrange(key, 0, -1))
            elif key_type == b"set":
                # Set value
                size = sum(len(item) for item in redis_client.smembers(key))
            elif key_type == b"zset":
                # Sorted set value
                size = sum(len(item) for item in redis_client.zrange(key, 0, -1))
            else:
                # Unknown type
                size = 0
            
            # Add key size to distribution
            if size < 1024:  # < 1KB
                size_distribution["< 1KB"] += 1
            elif size < 10 * 1024:  # < 10KB
                size_distribution["1KB - 10KB"] += 1
            elif size < 100 * 1024:  # < 100KB
                size_distribution["10KB - 100KB"] += 1
            elif size < 1024 * 1024:  # < 1MB
                size_distribution["100KB - 1MB"] += 1
            else:  # >= 1MB
                size_distribution[">= 1MB"] += 1
                
            total_size += size
        
        # Calculate average size
        average_size = total_size / len(keys) if keys else 0
        
        return {
            "total_keys": len(keys),
            "total_size": total_size,
            "average_size": average_size,
            "size_distribution": dict(size_distribution),
            "timestamp": timezone.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error analyzing key size distribution: {str(e)}")
        return {"error": str(e)}


def analyze_ttl_distribution() -> Dict:
    """
    Analyze TTL distribution.
    
    Returns:
        Dictionary with TTL distribution
    """
    if not CACHE_ENABLED:
        return {"error": "Cache is disabled"}
        
    try:
        from django_redis import get_redis_connection
        redis_client = get_redis_connection("default")
        
        # Get all keys
        keys = redis_client.keys("*")
        
        if not keys:
            return {
                "total_keys": 0,
                "ttl_distribution": {},
                "timestamp": timezone.now().isoformat(),
            }
            
        # Sample keys if there are too many
        if len(keys) > ANALYTICS_SAMPLE_SIZE:
            import random
            keys = random.sample(keys, ANALYTICS_SAMPLE_SIZE)
        
        # Get TTL of each key
        ttl_distribution = defaultdict(int)
        
        for key in keys:
            # Get TTL
            ttl = redis_client.ttl(key)
            
            # Add TTL to distribution
            if ttl < 0:  # No TTL
                ttl_distribution["No TTL"] += 1
            elif ttl < 60:  # < 1 minute
                ttl_distribution["< 1 minute"] += 1
            elif ttl < 60 * 60:  # < 1 hour
                ttl_distribution["1 minute - 1 hour"] += 1
            elif ttl < 60 * 60 * 24:  # < 1 day
                ttl_distribution["1 hour - 1 day"] += 1
            elif ttl < 60 * 60 * 24 * 7:  # < 1 week
                ttl_distribution["1 day - 1 week"] += 1
            else:  # >= 1 week
                ttl_distribution[">= 1 week"] += 1
        
        return {
            "total_keys": len(keys),
            "ttl_distribution": dict(ttl_distribution),
            "timestamp": timezone.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error analyzing TTL distribution: {str(e)}")
        return {"error": str(e)}


def analyze_cache_churn() -> Dict:
    """
    Analyze cache churn (keys that are frequently evicted).
    
    Returns:
        Dictionary with cache churn analysis
    """
    if not CACHE_ENABLED:
        return {"error": "Cache is disabled"}
        
    try:
        # Get telemetry stats
        telemetry = get_telemetry_stats()
        operations = telemetry.get("operations", {})
        
        # Extract set and delete operations
        set_ops = operations.get("set", {})
        delete_ops = operations.get("delete", {})
        
        # Find keys with high set/delete ratio
        churn_keys = []
        
        for key in set(set_ops.keys()) | set(delete_ops.keys()):
            set_count = set_ops.get(key, {}).get("success_count", 0)
            delete_count = delete_ops.get(key, {}).get("success_count", 0)
            
            if set_count > 0 and delete_count > 0:
                churn_ratio = delete_count / set_count
                
                if churn_ratio > 0.5:  # More than 50% of sets are followed by deletes
                    churn_keys.append({
                        "key": key,
                        "set_count": set_count,
                        "delete_count": delete_count,
                        "churn_ratio": churn_ratio,
                    })
        
        # Sort by churn ratio (descending)
        churn_keys.sort(key=lambda k: k["churn_ratio"], reverse=True)
        
        return {
            "churn_keys": churn_keys[:100],  # Limit to top 100
            "total_keys": len(churn_keys),
            "timestamp": timezone.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error analyzing cache churn: {str(e)}")
        return {"error": str(e)}


def analyze_cache_misses() -> Dict:
    """
    Analyze cache misses to identify opportunities for improvement.
    
    Returns:
        Dictionary with cache miss analysis
    """
    if not CACHE_ENABLED:
        return {"error": "Cache is disabled"}
        
    try:
        # Get telemetry stats
        telemetry = get_telemetry_stats()
        operations = telemetry.get("operations", {})
        
        # Extract get operations
        get_ops = operations.get("get", {})
        
        # Find keys with high miss rate
        miss_keys = []
        
        for key, stats in get_ops.items():
            hits = stats.get("success_count", 0)
            misses = stats.get("failure_count", 0)
            total = hits + misses
            
            if total > ANALYTICS_MIN_HITS + ANALYTICS_MIN_MISSES and misses > ANALYTICS_MIN_MISSES:
                miss_rate = misses / total
                
                if miss_rate > 0.2:  # More than 20% misses
                    miss_keys.append({
                        "key": key,
                        "hits": hits,
                        "misses": misses,
                        "total": total,
                        "miss_rate": miss_rate,
                    })
        
        # Sort by miss rate (descending)
        miss_keys.sort(key=lambda k: k["miss_rate"], reverse=True)
        
        return {
            "miss_keys": miss_keys[:100],  # Limit to top 100
            "total_keys": len(miss_keys),
            "timestamp": timezone.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error analyzing cache misses: {str(e)}")
        return {"error": str(e)}


def analyze_cache_efficiency() -> Dict:
    """
    Analyze cache efficiency (hit rate vs memory usage).
    
    Returns:
        Dictionary with cache efficiency analysis
    """
    if not CACHE_ENABLED:
        return {"error": "Cache is disabled"}
        
    try:
        # Get hit rate
        hit_rate_stats = get_hit_rate()
        hit_rate = hit_rate_stats.get("hit_rate", 0)
        
        # Get memory usage
        memory_stats = get_memory_usage()
        used_memory = memory_stats.get("used_memory", 0)
        used_memory_human = memory_stats.get("used_memory_human", "0B")
        
        # Get key count
        key_count = memory_stats.get("keys", 0)
        
        # Calculate efficiency metrics
        if key_count > 0:
            memory_per_key = used_memory / key_count
        else:
            memory_per_key = 0
            
        # Calculate efficiency score (hit rate / memory usage ratio)
        if used_memory > 0:
            efficiency_score = hit_rate / (used_memory / (1024 * 1024))  # Hit rate per MB
        else:
            efficiency_score = 0
            
        return {
            "hit_rate": hit_rate,
            "used_memory": used_memory,
            "used_memory_human": used_memory_human,
            "key_count": key_count,
            "memory_per_key": memory_per_key,
            "efficiency_score": efficiency_score,
            "timestamp": timezone.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error analyzing cache efficiency: {str(e)}")
        return {"error": str(e)}


def analyze_cache_performance() -> Dict:
    """
    Analyze cache performance (response times).
    
    Returns:
        Dictionary with cache performance analysis
    """
    if not CACHE_ENABLED:
        return {"error": "Cache is disabled"}
        
    try:
        # Get telemetry stats
        telemetry = get_telemetry_stats()
        operations = telemetry.get("operations", {})
        
        # Extract get operations
        get_ops = operations.get("get", {})
        
        # Calculate average response time for hits and misses
        hit_times = []
        miss_times = []
        
        for key, stats in get_ops.items():
            # Get success and failure durations
            success_durations = stats.get("success_durations", [])
            failure_durations = stats.get("failure_durations", [])
            
            # Add to hit and miss times
            hit_times.extend(success_durations)
            miss_times.extend(failure_durations)
        
        # Calculate averages
        avg_hit_time = sum(hit_times) / len(hit_times) if hit_times else 0
        avg_miss_time = sum(miss_times) / len(miss_times) if miss_times else 0
        
        # Calculate percentiles
        hit_times.sort()
        miss_times.sort()
        
        p50_hit = hit_times[len(hit_times) // 2] if hit_times else 0
        p90_hit = hit_times[int(len(hit_times) * 0.9)] if hit_times else 0
        p99_hit = hit_times[int(len(hit_times) * 0.99)] if hit_times else 0
        
        p50_miss = miss_times[len(miss_times) // 2] if miss_times else 0
        p90_miss = miss_times[int(len(miss_times) * 0.9)] if miss_times else 0
        p99_miss = miss_times[int(len(miss_times) * 0.99)] if miss_times else 0
        
        return {
            "hit_times": {
                "count": len(hit_times),
                "avg": avg_hit_time,
                "p50": p50_hit,
                "p90": p90_hit,
                "p99": p99_hit,
            },
            "miss_times": {
                "count": len(miss_times),
                "avg": avg_miss_time,
                "p50": p50_miss,
                "p90": p90_miss,
                "p99": p99_miss,
            },
            "timestamp": timezone.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error analyzing cache performance: {str(e)}")
        return {"error": str(e)}


def generate_optimization_recommendations() -> Dict:
    """
    Generate optimization recommendations based on analytics.
    
    Returns:
        Dictionary with optimization recommendations
    """
    if not CACHE_ENABLED:
        return {"error": "Cache is disabled"}
        
    try:
        recommendations = []
        
        # Analyze hit rate
        hit_rate_stats = get_hit_rate()
        hit_rate = hit_rate_stats.get("hit_rate", 0)
        
        if hit_rate < 0.5:
            recommendations.append({
                "type": "hit_rate",
                "severity": "critical",
                "message": f"Hit rate is critically low ({hit_rate:.2%}). Consider warming the cache and reviewing cache invalidation strategies.",
                "details": hit_rate_stats,
            })
        elif hit_rate < 0.7:
            recommendations.append({
                "type": "hit_rate",
                "severity": "warning",
                "message": f"Hit rate is low ({hit_rate:.2%}). Consider warming the cache more frequently.",
                "details": hit_rate_stats,
            })
        elif hit_rate < 0.9:
            recommendations.append({
                "type": "hit_rate",
                "severity": "info",
                "message": f"Hit rate is below optimal ({hit_rate:.2%}). Consider fine-tuning cache TTLs.",
                "details": hit_rate_stats,
            })
        
        # Analyze memory usage
        memory_stats = get_memory_usage()
        memory_usage = memory_stats.get("used_memory_ratio", 0)
        
        if memory_usage > 0.9:
            recommendations.append({
                "type": "memory_usage",
                "severity": "critical",
                "message": f"Memory usage is critically high ({memory_usage:.2%}). Consider increasing maxmemory or optimizing key sizes.",
                "details": memory_stats,
            })
        elif memory_usage > 0.8:
            recommendations.append({
                "type": "memory_usage",
                "severity": "warning",
                "message": f"Memory usage is high ({memory_usage:.2%}). Consider optimizing key sizes or reducing TTLs.",
                "details": memory_stats,
            })
        elif memory_usage > 0.7:
            recommendations.append({
                "type": "memory_usage",
                "severity": "info",
                "message": f"Memory usage is elevated ({memory_usage:.2%}). Monitor for further increases.",
                "details": memory_stats,
            })
        
        # Analyze cache misses
        miss_analysis = analyze_cache_misses()
        miss_keys = miss_analysis.get("miss_keys", [])
        
        if miss_keys:
            top_misses = miss_keys[:5]
            
            recommendations.append({
                "type": "cache_misses",
                "severity": "warning" if len(miss_keys) > 10 else "info",
                "message": f"Found {len(miss_keys)} keys with high miss rates. Consider warming these keys or adjusting TTLs.",
                "details": {"top_misses": top_misses},
            })
        
        # Analyze cache churn
        churn_analysis = analyze_cache_churn()
        churn_keys = churn_analysis.get("churn_keys", [])
        
        if churn_keys:
            top_churn = churn_keys[:5]
            
            recommendations.append({
                "type": "cache_churn",
                "severity": "warning" if len(churn_keys) > 10 else "info",
                "message": f"Found {len(churn_keys)} keys with high churn rates. Consider adjusting TTLs or caching strategies.",
                "details": {"top_churn": top_churn},
            })
        
        # Analyze key size distribution
        size_analysis = analyze_key_size_distribution()
        size_distribution = size_analysis.get("size_distribution", {})
        
        large_keys = size_distribution.get(">= 1MB", 0) + size_distribution.get("100KB - 1MB", 0)
        
        if large_keys > 0:
            recommendations.append({
                "type": "key_size",
                "severity": "warning" if large_keys > 10 else "info",
                "message": f"Found {large_keys} large keys (>100KB). Consider compressing these values or splitting them into smaller keys.",
                "details": {"size_distribution": size_distribution},
            })
        
        # Analyze TTL distribution
        ttl_analysis = analyze_ttl_distribution()
        ttl_distribution = ttl_analysis.get("ttl_distribution", {})
        
        no_ttl_keys = ttl_distribution.get("No TTL", 0)
        
        if no_ttl_keys > 0:
            recommendations.append({
                "type": "ttl",
                "severity": "warning" if no_ttl_keys > 100 else "info",
                "message": f"Found {no_ttl_keys} keys without TTL. Consider adding TTLs to prevent memory leaks.",
                "details": {"ttl_distribution": ttl_distribution},
            })
        
        # Sort recommendations by severity
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        recommendations.sort(key=lambda r: severity_order.get(r["severity"], 3))
        
        return {
            "recommendations": recommendations,
            "timestamp": timezone.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error generating optimization recommendations: {str(e)}")
        return {"error": str(e)}


def get_analytics_dashboard() -> Dict:
    """
    Get a comprehensive analytics dashboard.
    
    Returns:
        Dictionary with analytics dashboard data
    """
    if not CACHE_ENABLED:
        return {"error": "Cache is disabled"}
        
    try:
        # Get various analytics
        hit_rate_by_prefix = analyze_hit_rate_by_prefix()
        key_size_distribution = analyze_key_size_distribution()
        ttl_distribution = analyze_ttl_distribution()
        cache_churn = analyze_cache_churn()
        cache_misses = analyze_cache_misses()
        cache_efficiency = analyze_cache_efficiency()
        cache_performance = analyze_cache_performance()
        recommendations = generate_optimization_recommendations()
        
        # Combine into dashboard
        dashboard = {
            "hit_rate_by_prefix": hit_rate_by_prefix,
            "key_size_distribution": key_size_distribution,
            "ttl_distribution": ttl_distribution,
            "cache_churn": cache_churn,
            "cache_misses": cache_misses,
            "cache_efficiency": cache_efficiency,
            "cache_performance": cache_performance,
            "recommendations": recommendations,
            "timestamp": timezone.now().isoformat(),
        }
        
        return dashboard
    except Exception as e:
        logger.error(f"Error generating analytics dashboard: {str(e)}")
        return {"error": str(e)}

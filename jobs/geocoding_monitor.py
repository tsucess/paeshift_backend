"""
Enhanced geocoding monitoring module.

This module provides detailed metrics and monitoring for the geocoding system,
including performance tracking, cache hit rates, and error analysis.
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.utils import timezone

from jobs.geocoding_cache import get_cache_stats

logger = logging.getLogger(__name__)

# Constants
MAX_STORED_OPERATIONS = 1000  # Maximum number of operations to store in memory
METRICS_WINDOW_SECONDS = 3600  # 1 hour window for metrics

# In-memory storage for recent operations
_recent_operations = []
_provider_metrics = {}
_hourly_metrics = {}
_daily_metrics = {}

class GeocodingMetrics:
    """Class to track and analyze geocoding metrics."""
    
    @staticmethod
    def record_operation(operation_data: Dict[str, Any]) -> None:
        """
        Record a geocoding operation for monitoring and metrics.
        
        Args:
            operation_data: Data about the geocoding operation
        """
        global _recent_operations, _provider_metrics
        
        # Add timestamp if not present
        if "timestamp" not in operation_data:
            operation_data["timestamp"] = timezone.now().isoformat()
            
        # Add to recent operations
        _recent_operations.insert(0, operation_data)
        
        # Limit the size of the list
        if len(_recent_operations) > MAX_STORED_OPERATIONS:
            _recent_operations = _recent_operations[:MAX_STORED_OPERATIONS]
            
        # Update provider metrics
        provider = operation_data.get("provider", "unknown")
        if provider not in _provider_metrics:
            _provider_metrics[provider] = {
                "total_operations": 0,
                "successful_operations": 0,
                "cache_hits": 0,
                "total_time": 0,
                "error_count": 0,
                "error_types": {},
            }
            
        # Update metrics
        _provider_metrics[provider]["total_operations"] += 1
        
        if operation_data.get("success", False):
            _provider_metrics[provider]["successful_operations"] += 1
            
        if operation_data.get("cache_hit", False):
            _provider_metrics[provider]["cache_hits"] += 1
            
        if "total_time" in operation_data:
            _provider_metrics[provider]["total_time"] += operation_data["total_time"]
            
        if not operation_data.get("success", False) and "error_type" in operation_data:
            error_type = operation_data["error_type"]
            _provider_metrics[provider]["error_count"] += 1
            
            if error_type not in _provider_metrics[provider]["error_types"]:
                _provider_metrics[provider]["error_types"][error_type] = 0
                
            _provider_metrics[provider]["error_types"][error_type] += 1
            
        # Update time-based metrics
        GeocodingMetrics._update_time_metrics(operation_data)
    
    @staticmethod
    def _update_time_metrics(operation_data: Dict[str, Any]) -> None:
        """
        Update time-based metrics (hourly, daily).
        
        Args:
            operation_data: Data about the geocoding operation
        """
        global _hourly_metrics, _daily_metrics
        
        # Get current hour and day
        now = timezone.now()
        hour_key = now.strftime("%Y-%m-%d-%H")
        day_key = now.strftime("%Y-%m-%d")
        
        # Initialize hourly metrics if needed
        if hour_key not in _hourly_metrics:
            _hourly_metrics[hour_key] = {
                "total_operations": 0,
                "successful_operations": 0,
                "cache_hits": 0,
                "total_time": 0,
                "providers": {},
            }
            
        # Initialize daily metrics if needed
        if day_key not in _daily_metrics:
            _daily_metrics[day_key] = {
                "total_operations": 0,
                "successful_operations": 0,
                "cache_hits": 0,
                "total_time": 0,
                "providers": {},
            }
            
        # Update hourly metrics
        _hourly_metrics[hour_key]["total_operations"] += 1
        if operation_data.get("success", False):
            _hourly_metrics[hour_key]["successful_operations"] += 1
        if operation_data.get("cache_hit", False):
            _hourly_metrics[hour_key]["cache_hits"] += 1
        if "total_time" in operation_data:
            _hourly_metrics[hour_key]["total_time"] += operation_data["total_time"]
            
        # Update provider in hourly metrics
        provider = operation_data.get("provider", "unknown")
        if provider not in _hourly_metrics[hour_key]["providers"]:
            _hourly_metrics[hour_key]["providers"][provider] = 0
        _hourly_metrics[hour_key]["providers"][provider] += 1
        
        # Update daily metrics
        _daily_metrics[day_key]["total_operations"] += 1
        if operation_data.get("success", False):
            _daily_metrics[day_key]["successful_operations"] += 1
        if operation_data.get("cache_hit", False):
            _daily_metrics[day_key]["cache_hits"] += 1
        if "total_time" in operation_data:
            _daily_metrics[day_key]["total_time"] += operation_data["total_time"]
            
        # Update provider in daily metrics
        if provider not in _daily_metrics[day_key]["providers"]:
            _daily_metrics[day_key]["providers"][provider] = 0
        _daily_metrics[day_key]["providers"][provider] += 1
        
        # Clean up old metrics
        GeocodingMetrics._cleanup_old_metrics()
    
    @staticmethod
    def _cleanup_old_metrics() -> None:
        """Clean up old metrics to prevent memory growth."""
        global _hourly_metrics, _daily_metrics
        
        now = timezone.now()
        
        # Keep only the last 48 hours of hourly metrics
        cutoff_hour = (now - timedelta(hours=48)).strftime("%Y-%m-%d-%H")
        _hourly_metrics = {k: v for k, v in _hourly_metrics.items() if k >= cutoff_hour}
        
        # Keep only the last 90 days of daily metrics
        cutoff_day = (now - timedelta(days=90)).strftime("%Y-%m-%d")
        _daily_metrics = {k: v for k, v in _daily_metrics.items() if k >= cutoff_day}
    
    @staticmethod
    def get_metrics() -> Dict[str, Any]:
        """
        Get comprehensive geocoding metrics.
        
        Returns:
            Dictionary with detailed metrics
        """
        global _recent_operations, _provider_metrics, _hourly_metrics, _daily_metrics
        
        # Get cache statistics
        cache_stats = get_cache_stats()
        
        # Calculate overall metrics
        total_ops = sum(p["total_operations"] for p in _provider_metrics.values())
        successful_ops = sum(p["successful_operations"] for p in _provider_metrics.values())
        cache_hits = sum(p["cache_hits"] for p in _provider_metrics.values())
        total_time = sum(p["total_time"] for p in _provider_metrics.values())
        
        success_rate = (successful_ops / total_ops * 100) if total_ops > 0 else 0
        cache_hit_rate = (cache_hits / total_ops * 100) if total_ops > 0 else 0
        avg_response_time = (total_time / total_ops) if total_ops > 0 else 0
        
        # Get recent operations (last 100)
        recent_operations = _recent_operations[:100]
        
        # Get hourly metrics for the last 24 hours
        now = timezone.now()
        hourly_data = []
        for hour in range(24):
            hour_time = now - timedelta(hours=hour)
            hour_key = hour_time.strftime("%Y-%m-%d-%H")
            if hour_key in _hourly_metrics:
                hourly_data.append({
                    "hour": hour_key,
                    "operations": _hourly_metrics[hour_key]["total_operations"],
                    "success_rate": (_hourly_metrics[hour_key]["successful_operations"] / 
                                    _hourly_metrics[hour_key]["total_operations"] * 100) 
                                    if _hourly_metrics[hour_key]["total_operations"] > 0 else 0,
                    "cache_hit_rate": (_hourly_metrics[hour_key]["cache_hits"] / 
                                      _hourly_metrics[hour_key]["total_operations"] * 100)
                                      if _hourly_metrics[hour_key]["total_operations"] > 0 else 0,
                    "providers": _hourly_metrics[hour_key]["providers"],
                })
            else:
                hourly_data.append({
                    "hour": hour_key,
                    "operations": 0,
                    "success_rate": 0,
                    "cache_hit_rate": 0,
                    "providers": {},
                })
        
        # Get daily metrics for the last 7 days
        daily_data = []
        for day in range(7):
            day_time = now - timedelta(days=day)
            day_key = day_time.strftime("%Y-%m-%d")
            if day_key in _daily_metrics:
                daily_data.append({
                    "day": day_key,
                    "operations": _daily_metrics[day_key]["total_operations"],
                    "success_rate": (_daily_metrics[day_key]["successful_operations"] / 
                                    _daily_metrics[day_key]["total_operations"] * 100)
                                    if _daily_metrics[day_key]["total_operations"] > 0 else 0,
                    "cache_hit_rate": (_daily_metrics[day_key]["cache_hits"] / 
                                      _daily_metrics[day_key]["total_operations"] * 100)
                                      if _daily_metrics[day_key]["total_operations"] > 0 else 0,
                    "providers": _daily_metrics[day_key]["providers"],
                })
            else:
                daily_data.append({
                    "day": day_key,
                    "operations": 0,
                    "success_rate": 0,
                    "cache_hit_rate": 0,
                    "providers": {},
                })
        
        # Prepare the response
        return {
            "cache_stats": cache_stats,
            "overall_metrics": {
                "total_operations": total_ops,
                "successful_operations": successful_ops,
                "success_rate": round(success_rate, 2),
                "cache_hits": cache_hits,
                "cache_hit_rate": round(cache_hit_rate, 2),
                "average_response_time": round(avg_response_time, 3),
                "provider_metrics": _provider_metrics,
            },
            "time_metrics": {
                "hourly": hourly_data,
                "daily": daily_data,
            },
            "recent_operations": recent_operations,
            "timestamp": timezone.now().isoformat(),
        }
    
    @staticmethod
    def log_metrics_summary() -> None:
        """Log a summary of current geocoding metrics."""
        metrics = GeocodingMetrics.get_metrics()
        overall = metrics["overall_metrics"]
        
        logger.info(
            f"Geocoding metrics summary: {overall['total_operations']} operations, "
            f"{overall['success_rate']}% success rate, {overall['cache_hit_rate']}% cache hit rate, "
            f"{overall['average_response_time']}s avg response time"
        )
        
        # Log provider-specific metrics
        for provider, provider_metrics in overall["provider_metrics"].items():
            if provider_metrics["total_operations"] > 0:
                success_rate = (provider_metrics["successful_operations"] / 
                               provider_metrics["total_operations"] * 100)
                cache_hit_rate = (provider_metrics["cache_hits"] / 
                                 provider_metrics["total_operations"] * 100)
                avg_time = (provider_metrics["total_time"] / 
                           provider_metrics["total_operations"])
                
                logger.info(
                    f"Provider {provider}: {provider_metrics['total_operations']} operations, "
                    f"{success_rate:.1f}% success rate, {cache_hit_rate:.1f}% cache hit rate, "
                    f"{avg_time:.3f}s avg response time"
                )

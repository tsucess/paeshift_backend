"""
Redis cache monitoring alerts.

This module provides tools for monitoring Redis cache performance and sending alerts
when issues are detected.
"""

import json
import logging
import smtplib
import time
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from core.redis_monitoring import (
    get_cache_stats,
    get_hit_rate,
    get_memory_usage,
    get_slow_operations,
)
from core.redis_settings import CACHE_ENABLED
from core.redis_telemetry import get_telemetry_stats

logger = logging.getLogger(__name__)

# Alert thresholds
ALERT_THRESHOLDS = {
    # Hit rate thresholds
    "hit_rate": {
        "critical": 0.5,  # 50% hit rate
        "warning": 0.7,   # 70% hit rate
        "info": 0.9,      # 90% hit rate
    },
    
    # Memory usage thresholds
    "memory_usage": {
        "critical": 0.9,  # 90% memory usage
        "warning": 0.8,   # 80% memory usage
        "info": 0.7,      # 70% memory usage
    },
    
    # Eviction rate thresholds (keys evicted per second)
    "eviction_rate": {
        "critical": 100,  # 100 keys/second
        "warning": 50,    # 50 keys/second
        "info": 10,       # 10 keys/second
    },
    
    # Slow operation thresholds (milliseconds)
    "slow_operation": {
        "critical": 500,  # 500ms
        "warning": 200,   # 200ms
        "info": 100,      # 100ms
    },
    
    # Consistency check thresholds (percentage of inconsistent instances)
    "consistency": {
        "critical": 0.1,  # 10% inconsistent
        "warning": 0.05,  # 5% inconsistent
        "info": 0.01,     # 1% inconsistent
    },
}

# Alert recipients
ALERT_RECIPIENTS = getattr(settings, "CACHE_ALERT_RECIPIENTS", [])

# Alert cooldown (in seconds)
ALERT_COOLDOWN = {
    "critical": 60 * 60,     # 1 hour
    "warning": 60 * 60 * 6,  # 6 hours
    "info": 60 * 60 * 24,    # 24 hours
}

# Last alert timestamps
_last_alerts = {}


def check_hit_rate() -> Optional[Dict]:
    """
    Check cache hit rate and return an alert if it's below thresholds.
    
    Returns:
        Alert dictionary or None if no alert
    """
    if not CACHE_ENABLED:
        return None
        
    try:
        # Get hit rate
        hit_rate_stats = get_hit_rate()
        hit_rate = hit_rate_stats.get("hit_rate", 1.0)
        
        # Check thresholds
        if hit_rate < ALERT_THRESHOLDS["hit_rate"]["critical"]:
            return {
                "type": "hit_rate",
                "level": "critical",
                "message": f"Cache hit rate is critically low: {hit_rate:.2%}",
                "details": hit_rate_stats,
                "timestamp": timezone.now().isoformat(),
            }
        elif hit_rate < ALERT_THRESHOLDS["hit_rate"]["warning"]:
            return {
                "type": "hit_rate",
                "level": "warning",
                "message": f"Cache hit rate is low: {hit_rate:.2%}",
                "details": hit_rate_stats,
                "timestamp": timezone.now().isoformat(),
            }
        elif hit_rate < ALERT_THRESHOLDS["hit_rate"]["info"]:
            return {
                "type": "hit_rate",
                "level": "info",
                "message": f"Cache hit rate is below optimal: {hit_rate:.2%}",
                "details": hit_rate_stats,
                "timestamp": timezone.now().isoformat(),
            }
    except Exception as e:
        logger.error(f"Error checking hit rate: {str(e)}")
    
    return None


def check_memory_usage() -> Optional[Dict]:
    """
    Check memory usage and return an alert if it's above thresholds.
    
    Returns:
        Alert dictionary or None if no alert
    """
    if not CACHE_ENABLED:
        return None
        
    try:
        # Get memory usage
        memory_stats = get_memory_usage()
        memory_usage = memory_stats.get("used_memory_ratio", 0.0)
        
        # Check thresholds
        if memory_usage > ALERT_THRESHOLDS["memory_usage"]["critical"]:
            return {
                "type": "memory_usage",
                "level": "critical",
                "message": f"Memory usage is critically high: {memory_usage:.2%}",
                "details": memory_stats,
                "timestamp": timezone.now().isoformat(),
            }
        elif memory_usage > ALERT_THRESHOLDS["memory_usage"]["warning"]:
            return {
                "type": "memory_usage",
                "level": "warning",
                "message": f"Memory usage is high: {memory_usage:.2%}",
                "details": memory_stats,
                "timestamp": timezone.now().isoformat(),
            }
        elif memory_usage > ALERT_THRESHOLDS["memory_usage"]["info"]:
            return {
                "type": "memory_usage",
                "level": "info",
                "message": f"Memory usage is elevated: {memory_usage:.2%}",
                "details": memory_stats,
                "timestamp": timezone.now().isoformat(),
            }
    except Exception as e:
        logger.error(f"Error checking memory usage: {str(e)}")
    
    return None


def check_eviction_rate() -> Optional[Dict]:
    """
    Check eviction rate and return an alert if it's above thresholds.
    
    Returns:
        Alert dictionary or None if no alert
    """
    if not CACHE_ENABLED:
        return None
        
    try:
        # Get cache stats
        stats = get_cache_stats()
        evicted_keys = stats.get("evicted_keys", 0)
        uptime_in_seconds = stats.get("uptime_in_seconds", 1)
        
        # Calculate eviction rate (keys per second)
        eviction_rate = evicted_keys / uptime_in_seconds if uptime_in_seconds > 0 else 0
        
        # Check thresholds
        if eviction_rate > ALERT_THRESHOLDS["eviction_rate"]["critical"]:
            return {
                "type": "eviction_rate",
                "level": "critical",
                "message": f"Eviction rate is critically high: {eviction_rate:.2f} keys/second",
                "details": {"evicted_keys": evicted_keys, "uptime_in_seconds": uptime_in_seconds, "eviction_rate": eviction_rate},
                "timestamp": timezone.now().isoformat(),
            }
        elif eviction_rate > ALERT_THRESHOLDS["eviction_rate"]["warning"]:
            return {
                "type": "eviction_rate",
                "level": "warning",
                "message": f"Eviction rate is high: {eviction_rate:.2f} keys/second",
                "details": {"evicted_keys": evicted_keys, "uptime_in_seconds": uptime_in_seconds, "eviction_rate": eviction_rate},
                "timestamp": timezone.now().isoformat(),
            }
        elif eviction_rate > ALERT_THRESHOLDS["eviction_rate"]["info"]:
            return {
                "type": "eviction_rate",
                "level": "info",
                "message": f"Eviction rate is elevated: {eviction_rate:.2f} keys/second",
                "details": {"evicted_keys": evicted_keys, "uptime_in_seconds": uptime_in_seconds, "eviction_rate": eviction_rate},
                "timestamp": timezone.now().isoformat(),
            }
    except Exception as e:
        logger.error(f"Error checking eviction rate: {str(e)}")
    
    return None


def check_slow_operations() -> Optional[Dict]:
    """
    Check for slow operations and return an alert if any are found.
    
    Returns:
        Alert dictionary or None if no alert
    """
    if not CACHE_ENABLED:
        return None
        
    try:
        # Get slow operations
        slow_ops = get_slow_operations(min_duration_ms=ALERT_THRESHOLDS["slow_operation"]["info"])
        
        if not slow_ops:
            return None
            
        # Find the slowest operation
        slowest_op = max(slow_ops, key=lambda op: op.get("duration_ms", 0))
        duration_ms = slowest_op.get("duration_ms", 0)
        
        # Check thresholds
        if duration_ms > ALERT_THRESHOLDS["slow_operation"]["critical"]:
            return {
                "type": "slow_operation",
                "level": "critical",
                "message": f"Critically slow operation detected: {duration_ms:.2f}ms",
                "details": {"slowest_operation": slowest_op, "slow_operations_count": len(slow_ops)},
                "timestamp": timezone.now().isoformat(),
            }
        elif duration_ms > ALERT_THRESHOLDS["slow_operation"]["warning"]:
            return {
                "type": "slow_operation",
                "level": "warning",
                "message": f"Slow operation detected: {duration_ms:.2f}ms",
                "details": {"slowest_operation": slowest_op, "slow_operations_count": len(slow_ops)},
                "timestamp": timezone.now().isoformat(),
            }
        elif duration_ms > ALERT_THRESHOLDS["slow_operation"]["info"]:
            return {
                "type": "slow_operation",
                "level": "info",
                "message": f"Operation slower than optimal detected: {duration_ms:.2f}ms",
                "details": {"slowest_operation": slowest_op, "slow_operations_count": len(slow_ops)},
                "timestamp": timezone.now().isoformat(),
            }
    except Exception as e:
        logger.error(f"Error checking slow operations: {str(e)}")
    
    return None


def check_consistency() -> Optional[Dict]:
    """
    Check cache consistency and return an alert if issues are found.
    
    Returns:
        Alert dictionary or None if no alert
    """
    if not CACHE_ENABLED:
        return None
        
    try:
        # Import consistency check function
        from core.redis_consistency import check_frequently_accessed_models_consistency
        
        # Run a lightweight consistency check (no auto-repair)
        results = check_frequently_accessed_models_consistency(auto_repair=False)
        
        # Calculate inconsistency ratio
        total_checked = results.get("total_checked", 0)
        total_inconsistent = results.get("total_inconsistent", 0) + results.get("total_missing", 0)
        
        if total_checked == 0:
            return None
            
        inconsistency_ratio = total_inconsistent / total_checked
        
        # Check thresholds
        if inconsistency_ratio > ALERT_THRESHOLDS["consistency"]["critical"]:
            return {
                "type": "consistency",
                "level": "critical",
                "message": f"Cache consistency is critically low: {inconsistency_ratio:.2%} inconsistent",
                "details": results,
                "timestamp": timezone.now().isoformat(),
            }
        elif inconsistency_ratio > ALERT_THRESHOLDS["consistency"]["warning"]:
            return {
                "type": "consistency",
                "level": "warning",
                "message": f"Cache consistency is low: {inconsistency_ratio:.2%} inconsistent",
                "details": results,
                "timestamp": timezone.now().isoformat(),
            }
        elif inconsistency_ratio > ALERT_THRESHOLDS["consistency"]["info"]:
            return {
                "type": "consistency",
                "level": "info",
                "message": f"Cache consistency is below optimal: {inconsistency_ratio:.2%} inconsistent",
                "details": results,
                "timestamp": timezone.now().isoformat(),
            }
    except Exception as e:
        logger.error(f"Error checking consistency: {str(e)}")
    
    return None


def check_all() -> List[Dict]:
    """
    Run all checks and return a list of alerts.
    
    Returns:
        List of alert dictionaries
    """
    alerts = []
    
    # Run all checks
    hit_rate_alert = check_hit_rate()
    if hit_rate_alert:
        alerts.append(hit_rate_alert)
        
    memory_alert = check_memory_usage()
    if memory_alert:
        alerts.append(memory_alert)
        
    eviction_alert = check_eviction_rate()
    if eviction_alert:
        alerts.append(eviction_alert)
        
    slow_op_alert = check_slow_operations()
    if slow_op_alert:
        alerts.append(slow_op_alert)
        
    consistency_alert = check_consistency()
    if consistency_alert:
        alerts.append(consistency_alert)
    
    return alerts


def send_alert_email(alert: Dict) -> bool:
    """
    Send an alert email.
    
    Args:
        alert: Alert dictionary
        
    Returns:
        True if email was sent, False otherwise
    """
    if not ALERT_RECIPIENTS:
        logger.warning("No alert recipients configured, skipping email")
        return False
        
    try:
        # Get alert details
        alert_type = alert.get("type", "unknown")
        alert_level = alert.get("level", "info")
        alert_message = alert.get("message", "No message")
        alert_timestamp = alert.get("timestamp", timezone.now().isoformat())
        
        # Format subject
        subject = f"[{alert_level.upper()}] Redis Cache Alert: {alert_type}"
        
        # Format message
        message = f"""
Redis Cache Alert

Type: {alert_type}
Level: {alert_level}
Time: {alert_timestamp}
Message: {alert_message}

Details:
{json.dumps(alert.get("details", {}), indent=2)}

This is an automated alert from the Redis cache monitoring system.
"""
        
        # Send email
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=ALERT_RECIPIENTS,
            fail_silently=False,
        )
        
        logger.info(f"Sent alert email: {subject}")
        return True
    except Exception as e:
        logger.error(f"Error sending alert email: {str(e)}")
        return False


def send_alert_slack(alert: Dict) -> bool:
    """
    Send an alert to Slack.
    
    Args:
        alert: Alert dictionary
        
    Returns:
        True if alert was sent, False otherwise
    """
    # Get Slack webhook URL
    webhook_url = getattr(settings, "SLACK_WEBHOOK_URL", None)
    
    if not webhook_url:
        logger.warning("No Slack webhook URL configured, skipping Slack alert")
        return False
        
    try:
        import requests
        
        # Get alert details
        alert_type = alert.get("type", "unknown")
        alert_level = alert.get("level", "info")
        alert_message = alert.get("message", "No message")
        alert_timestamp = alert.get("timestamp", timezone.now().isoformat())
        
        # Set color based on level
        color = {
            "critical": "#FF0000",  # Red
            "warning": "#FFA500",   # Orange
            "info": "#0000FF",      # Blue
        }.get(alert_level, "#808080")  # Gray default
        
        # Format Slack message
        slack_message = {
            "attachments": [
                {
                    "fallback": f"Redis Cache Alert: {alert_message}",
                    "color": color,
                    "title": f"Redis Cache Alert: {alert_type}",
                    "text": alert_message,
                    "fields": [
                        {
                            "title": "Level",
                            "value": alert_level.upper(),
                            "short": True,
                        },
                        {
                            "title": "Time",
                            "value": alert_timestamp,
                            "short": True,
                        },
                    ],
                    "footer": "Redis Cache Monitoring",
                }
            ]
        }
        
        # Add details as fields
        details = alert.get("details", {})
        for key, value in details.items():
            if isinstance(value, (int, float, str, bool)):
                slack_message["attachments"][0]["fields"].append({
                    "title": key,
                    "value": str(value),
                    "short": True,
                })
        
        # Send to Slack
        response = requests.post(
            webhook_url,
            json=slack_message,
            headers={"Content-Type": "application/json"},
        )
        
        if response.status_code == 200:
            logger.info(f"Sent alert to Slack: {alert_type} ({alert_level})")
            return True
        else:
            logger.error(f"Error sending alert to Slack: {response.status_code} {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending alert to Slack: {str(e)}")
        return False


def process_alerts(alerts: List[Dict]) -> Dict:
    """
    Process alerts by sending notifications and logging.
    
    Args:
        alerts: List of alert dictionaries
        
    Returns:
        Dictionary with processing results
    """
    results = {
        "total_alerts": len(alerts),
        "alerts_processed": 0,
        "alerts_sent": 0,
        "alerts_skipped": 0,
    }
    
    for alert in alerts:
        results["alerts_processed"] += 1
        
        # Get alert details
        alert_type = alert.get("type", "unknown")
        alert_level = alert.get("level", "info")
        
        # Check cooldown
        alert_key = f"{alert_type}:{alert_level}"
        last_alert_time = _last_alerts.get(alert_key)
        
        if last_alert_time:
            cooldown = ALERT_COOLDOWN.get(alert_level, 0)
            time_since_last = time.time() - last_alert_time
            
            if time_since_last < cooldown:
                # Skip this alert (in cooldown)
                logger.debug(f"Skipping alert {alert_key} (in cooldown: {time_since_last:.2f}s < {cooldown}s)")
                results["alerts_skipped"] += 1
                continue
        
        # Log alert
        logger.warning(f"Redis cache alert: {alert.get('message')}")
        
        # Send notifications
        email_sent = send_alert_email(alert)
        slack_sent = send_alert_slack(alert)
        
        if email_sent or slack_sent:
            # Update last alert time
            _last_alerts[alert_key] = time.time()
            results["alerts_sent"] += 1
    
    return results


def monitor_cache_health():
    """
    Monitor cache health and send alerts if issues are detected.
    
    This function is designed to be called periodically by a scheduler.
    """
    if not CACHE_ENABLED:
        logger.debug("Cache monitoring skipped: Cache is disabled")
        return
        
    logger.debug("Running cache health monitoring")
    
    # Check for issues
    alerts = check_all()
    
    # Process alerts
    if alerts:
        results = process_alerts(alerts)
        logger.info(f"Cache monitoring results: {results}")
    else:
        logger.debug("No cache health issues detected")
    
    return {
        "alerts": alerts,
        "timestamp": timezone.now().isoformat(),
    }


# For Django Q
def scheduled_cache_monitoring():
    """Scheduled task to monitor cache health."""
    return monitor_cache_health()


# For Celery
try:
    from celery import shared_task
    
    @shared_task(name="monitor_cache_health")
    def celery_cache_monitoring():
        """Celery task to monitor cache health."""
        return monitor_cache_health()
        
except ImportError:
    pass

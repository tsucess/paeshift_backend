"""
Redis cache warming settings.

This module provides comprehensive settings for Redis cache warming,
including schedules, priorities, and strategies.
"""

import logging
from typing import Dict, List, Any, Optional

from django.conf import settings

logger = logging.getLogger(__name__)

# Basic warming settings
CACHE_WARM_ON_STARTUP = getattr(settings, "CACHE_WARM_ON_STARTUP", True)
CACHE_WARM_ON_IMPORT = getattr(settings, "CACHE_WARM_ON_IMPORT", False)
CACHE_WARM_BATCH_SIZE = getattr(settings, "CACHE_WARM_BATCH_SIZE", 100)
CACHE_WARM_SLEEP_BETWEEN_BATCHES = getattr(settings, "CACHE_WARM_SLEEP_BETWEEN_BATCHES", 0.1)
CACHE_WARM_MAX_WORKERS = getattr(settings, "CACHE_WARM_MAX_WORKERS", 4)
CACHE_WARM_TIMEOUT = getattr(settings, "CACHE_WARM_TIMEOUT", 60 * 5)  # 5 minutes

# Warming schedules (in seconds)
CACHE_WARM_SCHEDULES = {
    # Full cache warming (all models and endpoints)
    "full": getattr(settings, "CACHE_WARM_SCHEDULE_FULL", 60 * 60),  # 1 hour
    
    # Critical models that change frequently
    "critical": getattr(settings, "CACHE_WARM_SCHEDULE_CRITICAL", 60 * 5),  # 5 minutes
    
    # Static data that rarely changes
    "static": getattr(settings, "CACHE_WARM_SCHEDULE_STATIC", 60 * 60 * 24),  # 24 hours
    
    # User-specific data
    "user": getattr(settings, "CACHE_WARM_SCHEDULE_USER", 60 * 30),  # 30 minutes
    
    # Job-specific data
    "job": getattr(settings, "CACHE_WARM_SCHEDULE_JOB", 60 * 15),  # 15 minutes
    
    # Consistency checks
    "consistency": getattr(settings, "CACHE_WARM_SCHEDULE_CONSISTENCY", 60 * 60 * 6),  # 6 hours
}

# Priority models to warm
CACHE_WARM_PRIORITY_MODELS = getattr(settings, "CACHE_WARM_PRIORITY_MODELS", [
    # User-related models
    "accounts.CustomUser",
    "accounts.Profile",
    
    # Job-related models
    "jobs.Job",
    "jobs.Application",
    "jobs.SavedJob",
    "jobs.JobIndustry",
    "jobs.JobSubCategory",
    
    # Location-related models
    "userlocation.UserLocation",
    
    # Rating-related models
    "rating.Review",
    
    # Payment-related models
    "payment.Payment",
])

# Critical models that change frequently
CACHE_WARM_CRITICAL_MODELS = getattr(settings, "CACHE_WARM_CRITICAL_MODELS", [
    # Active jobs
    {
        "model": "jobs.Job",
        "filter_kwargs": {"is_active": True},
        "order_by": ["-created_at"],
        "limit": 100,
    },
    # Recent applications
    {
        "model": "jobs.Application",
        "order_by": ["-created_at"],
        "limit": 50,
    },
    # Active users
    {
        "model": "accounts.CustomUser",
        "filter_kwargs": {"is_active": True, "last_login__isnull": False},
        "order_by": ["-last_login"],
        "limit": 50,
    },
])

# Static models that rarely change
CACHE_WARM_STATIC_MODELS = getattr(settings, "CACHE_WARM_STATIC_MODELS", [
    # Job industries
    {
        "model": "jobs.JobIndustry",
        "permanent": True,
    },
    # Job subcategories
    {
        "model": "jobs.JobSubCategory",
        "permanent": True,
    },
])

# Priority endpoints to warm
CACHE_WARM_PRIORITY_ENDPOINTS = getattr(settings, "CACHE_WARM_PRIORITY_ENDPOINTS", [
    # Jobs endpoints
    {"name": "all_jobs", "path": "/api/jobs/alljobs/", "method": "get"},
    {"name": "job_industries", "path": "/api/jobs/job-industries/", "method": "get"},
    {"name": "job_subcategories", "path": "/api/jobs/job-subcategories/", "method": "get"},
    {"name": "saved_jobs", "path": "/api/jobs/saved-jobs/1", "method": "get"},
    
    # User endpoints
    {"name": "active_users", "path": "/api/accounts/active-users/15/", "method": "put"},
    {"name": "last_seen", "path": "/api/accounts/users/1/last-seen/", "method": "get"},
    {"name": "whoami", "path": "/api/accounts/whoami/1", "method": "get"},
    
    # Rating endpoints
    {"name": "user_ratings", "path": "/api/rating/ratings/1", "method": "get"},
    
    # Payment endpoints
    {"name": "user_payments", "path": "/api/payments/users/1/payments", "method": "get"},
])

# Warming strategies
CACHE_WARM_STRATEGIES = {
    # Recent strategy - cache recently updated instances
    "recent": {
        "threshold_hours": getattr(settings, "CACHE_WARM_RECENT_THRESHOLD", 24),
        "limit": getattr(settings, "CACHE_WARM_RECENT_LIMIT", 1000),
    },
    
    # Popular strategy - cache frequently accessed instances
    "popular": {
        "min_hits": getattr(settings, "CACHE_WARM_POPULAR_MIN_HITS", 10),
        "limit": getattr(settings, "CACHE_WARM_POPULAR_LIMIT", 1000),
    },
    
    # All strategy - cache all instances
    "all": {
        "limit": getattr(settings, "CACHE_WARM_ALL_LIMIT", 10000),
    },
}

# Consistency check settings
CACHE_CONSISTENCY_CHECK_BATCH_SIZE = getattr(settings, "CACHE_CONSISTENCY_CHECK_BATCH_SIZE", 100)
CACHE_CONSISTENCY_CHECK_SLEEP = getattr(settings, "CACHE_CONSISTENCY_CHECK_SLEEP", 0.1)
CACHE_CONSISTENCY_AUTO_REPAIR = getattr(settings, "CACHE_CONSISTENCY_AUTO_REPAIR", True)
CACHE_CONSISTENCY_SAMPLE_SIZE = getattr(settings, "CACHE_CONSISTENCY_SAMPLE_SIZE", 100)

# Log warming settings
logger.info("Redis cache warming settings:")
logger.info(f"  - Warm on startup: {CACHE_WARM_ON_STARTUP}")
logger.info(f"  - Warm on import: {CACHE_WARM_ON_IMPORT}")
logger.info(f"  - Batch size: {CACHE_WARM_BATCH_SIZE}")
logger.info(f"  - Sleep between batches: {CACHE_WARM_SLEEP_BETWEEN_BATCHES}")
logger.info(f"  - Max workers: {CACHE_WARM_MAX_WORKERS}")
logger.info(f"  - Timeout: {CACHE_WARM_TIMEOUT}")
logger.info(f"  - Full warming schedule: {CACHE_WARM_SCHEDULES['full']} seconds")
logger.info(f"  - Critical warming schedule: {CACHE_WARM_SCHEDULES['critical']} seconds")
logger.info(f"  - Static warming schedule: {CACHE_WARM_SCHEDULES['static']} seconds")
logger.info(f"  - User warming schedule: {CACHE_WARM_SCHEDULES['user']} seconds")
logger.info(f"  - Job warming schedule: {CACHE_WARM_SCHEDULES['job']} seconds")
logger.info(f"  - Consistency check schedule: {CACHE_WARM_SCHEDULES['consistency']} seconds")
logger.info(f"  - Priority models: {len(CACHE_WARM_PRIORITY_MODELS)}")
logger.info(f"  - Critical models: {len(CACHE_WARM_CRITICAL_MODELS)}")
logger.info(f"  - Static models: {len(CACHE_WARM_STATIC_MODELS)}")
logger.info(f"  - Priority endpoints: {len(CACHE_WARM_PRIORITY_ENDPOINTS)}")

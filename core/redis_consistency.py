"""
Redis cache consistency verification module.

This module provides tools for verifying the consistency between Redis cache and database data,
detecting and resolving inconsistencies, and monitoring cache health.
"""

import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple, Type, Union

from django.apps import apps
from django.conf import settings
from django.core.cache import cache
from django.db import models, transaction
from django.db.models import F, Q
from django.utils import timezone

from core.cache import (
    cache_model_instance,
    get_cached_model_instance,
    invalidate_model_instance,
)
from core.redis_model_mixin import RedisCachedModelMixin
from core.redis_settings import CACHE_ENABLED
from core.redis_telemetry import log_operation

logger = logging.getLogger(__name__)

# Constants
CONSISTENCY_CHECK_BATCH_SIZE = getattr(settings, "CACHE_CONSISTENCY_CHECK_BATCH_SIZE", 100)
CONSISTENCY_CHECK_SLEEP = getattr(settings, "CACHE_CONSISTENCY_CHECK_SLEEP", 0.1)
CONSISTENCY_AUTO_REPAIR = getattr(settings, "CACHE_CONSISTENCY_AUTO_REPAIR", True)


def generate_model_hash(instance: models.Model) -> str:
    """
    Generate a hash of a model instance for consistency checking.
    
    Args:
        instance: Model instance
        
    Returns:
        Hash string
    """
    # Get model fields
    fields = {}
    for field in instance._meta.fields:
        if field.name != "id" and not field.name.endswith("_ptr"):
            value = getattr(instance, field.name)
            
            # Handle special field types
            if isinstance(value, models.Model):
                # For foreign keys, just use the ID
                fields[field.name] = value.pk
            elif hasattr(value, "isoformat"):
                # For dates and times, use ISO format
                fields[field.name] = value.isoformat()
            else:
                # For other fields, use as is
                fields[field.name] = value
    
    # Convert to JSON and hash
    json_str = json.dumps(fields, sort_keys=True, default=str)
    return hashlib.md5(json_str.encode()).hexdigest()


def check_model_consistency(
    model_class: Type[models.Model],
    instance_id: Optional[int] = None,
    auto_repair: bool = CONSISTENCY_AUTO_REPAIR,
) -> Dict:
    """
    Check consistency between database and cache for a model.
    
    Args:
        model_class: Model class
        instance_id: Optional instance ID (None checks all instances)
        auto_repair: Whether to automatically repair inconsistencies
        
    Returns:
        Dictionary with consistency check results
    """
    if not CACHE_ENABLED:
        return {"error": "Cache is disabled"}
    
    start_time = time.time()
    model_name = model_class.__name__
    logger.info(f"Starting consistency check for {model_name}")
    
    # Initialize results
    results = {
        "model": model_name,
        "total_instances": 0,
        "checked_instances": 0,
        "consistent_instances": 0,
        "inconsistent_instances": 0,
        "missing_from_cache": 0,
        "repaired_instances": 0,
        "elapsed_seconds": 0,
        "timestamp": timezone.now().isoformat(),
    }
    
    # Build queryset
    queryset = model_class.objects.all()
    if instance_id is not None:
        queryset = queryset.filter(pk=instance_id)
    
    # Get total count
    total_instances = queryset.count()
    results["total_instances"] = total_instances
    
    # Check in batches
    for i in range(0, total_instances, CONSISTENCY_CHECK_BATCH_SIZE):
        batch = queryset[i:i + CONSISTENCY_CHECK_BATCH_SIZE]
        
        for instance in batch:
            results["checked_instances"] += 1
            
            # Generate hash of database instance
            db_hash = generate_model_hash(instance)
            
            # Get cached instance
            model_type = model_class.__name__.lower()
            cached_data = get_cached_model_instance(model_type, instance.pk)
            
            if cached_data is None:
                # Instance missing from cache
                results["missing_from_cache"] += 1
                
                if auto_repair:
                    # Repair by caching the instance
                    if hasattr(instance, "cache") and callable(instance.cache):
                        instance.cache()
                    else:
                        # Use generic caching
                        if hasattr(instance, "to_dict"):
                            data = instance.to_dict()
                        else:
                            # Basic serialization
                            data = {
                                "id": instance.pk,
                                "model": model_type,
                                "db_hash": db_hash,
                            }
                            
                            # Add common fields
                            for field in instance._meta.fields:
                                field_name = field.name
                                if field_name != "id":
                                    value = getattr(instance, field_name)
                                    
                                    # Handle special field types
                                    if isinstance(value, models.Model):
                                        # For foreign keys, just store the ID
                                        data[field_name] = value.pk
                                    elif hasattr(value, "isoformat"):
                                        # For dates and times, convert to ISO format
                                        data[field_name] = value.isoformat()
                                    else:
                                        # For other fields, store as is
                                        data[field_name] = value
                        
                        # Cache the instance
                        cache_model_instance(model_type, instance.pk, data)
                    
                    results["repaired_instances"] += 1
                    logger.info(f"Repaired missing cache for {model_name} instance {instance.pk}")
            else:
                # Instance exists in cache, check consistency
                if isinstance(cached_data, dict) and "db_hash" in cached_data:
                    # Cache already has a hash, compare directly
                    cache_hash = cached_data["db_hash"]
                else:
                    # Generate hash from cached data
                    try:
                        # Create a temporary instance with cached data
                        temp_instance = model_class()
                        temp_instance.pk = instance.pk
                        
                        # Set fields from cached data
                        for field_name, value in cached_data.items():
                            if field_name != "id" and field_name != "model" and field_name != "db_hash":
                                setattr(temp_instance, field_name, value)
                        
                        # Generate hash
                        cache_hash = generate_model_hash(temp_instance)
                    except Exception as e:
                        logger.error(f"Error generating hash for cached {model_name} instance {instance.pk}: {str(e)}")
                        cache_hash = None
                
                if cache_hash == db_hash:
                    # Consistent
                    results["consistent_instances"] += 1
                else:
                    # Inconsistent
                    results["inconsistent_instances"] += 1
                    
                    if auto_repair:
                        # Repair by updating the cache
                        if hasattr(instance, "cache") and callable(instance.cache):
                            instance.cache()
                        else:
                            # Use generic caching
                            if hasattr(instance, "to_dict"):
                                data = instance.to_dict()
                            else:
                                # Basic serialization
                                data = {
                                    "id": instance.pk,
                                    "model": model_type,
                                    "db_hash": db_hash,
                                }
                                
                                # Add common fields
                                for field in instance._meta.fields:
                                    field_name = field.name
                                    if field_name != "id":
                                        value = getattr(instance, field_name)
                                        
                                        # Handle special field types
                                        if isinstance(value, models.Model):
                                            # For foreign keys, just store the ID
                                            data[field_name] = value.pk
                                        elif hasattr(value, "isoformat"):
                                            # For dates and times, convert to ISO format
                                            data[field_name] = value.isoformat()
                                        else:
                                            # For other fields, store as is
                                            data[field_name] = value
                            
                            # Cache the instance
                            cache_model_instance(model_type, instance.pk, data)
                        
                        results["repaired_instances"] += 1
                        logger.info(f"Repaired inconsistent cache for {model_name} instance {instance.pk}")
        
        # Sleep between batches to reduce load
        if CONSISTENCY_CHECK_SLEEP > 0 and i + CONSISTENCY_CHECK_BATCH_SIZE < total_instances:
            time.sleep(CONSISTENCY_CHECK_SLEEP)
    
    # Calculate elapsed time
    elapsed = time.time() - start_time
    results["elapsed_seconds"] = elapsed
    
    logger.info(
        f"Completed consistency check for {model_name}: "
        f"{results['consistent_instances']}/{results['checked_instances']} consistent, "
        f"{results['inconsistent_instances']} inconsistent, "
        f"{results['missing_from_cache']} missing, "
        f"{results['repaired_instances']} repaired "
        f"in {elapsed:.2f} seconds"
    )
    
    return results


def check_frequently_accessed_models_consistency(
    auto_repair: bool = CONSISTENCY_AUTO_REPAIR,
) -> Dict:
    """
    Check consistency for frequently accessed models.
    
    Args:
        auto_repair: Whether to automatically repair inconsistencies
        
    Returns:
        Dictionary with consistency check results
    """
    if not CACHE_ENABLED:
        return {"error": "Cache is disabled"}
    
    start_time = time.time()
    logger.info("Starting consistency check for frequently accessed models")
    
    # Import models
    from django.apps import apps
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    
    # Define models to check
    models_to_check = [
        # User model - check active users first
        {
            "model": User,
            "filter_kwargs": {"is_active": True},
            "order_by": ["-last_login"],
            "limit": 1000,
        },
        # Profile model - if it exists
        {
            "model": apps.get_model("accounts", "Profile"),
            "order_by": ["-updated_at"],
            "limit": 1000,
        },
        # Job model - active jobs first
        {
            "model": apps.get_model("jobs", "Job"),
            "filter_kwargs": {"is_active": True},
            "order_by": ["-created_at"],
            "limit": 500,
        },
        # JobIndustry model - all industries
        {
            "model": apps.get_model("jobs", "JobIndustry"),
        },
        # JobSubCategory model - all subcategories
        {
            "model": apps.get_model("jobs", "JobSubCategory"),
        },
        # Application model - recent applications
        {
            "model": apps.get_model("jobs", "Application"),
            "order_by": ["-created_at"],
            "limit": 500,
        },
        # SavedJob model - recent saved jobs
        {
            "model": apps.get_model("jobs", "SavedJob"),
            "order_by": ["-saved_at"],
            "limit": 500,
        },
        # UserLocation model - recent locations
        {
            "model": apps.get_model("userlocation", "UserLocation"),
            "order_by": ["-last_updated"],
            "limit": 500,
        },
    ]
    
    # Check each model
    results = {}
    for model_config in models_to_check:
        model_class = model_config.pop("model")
        filter_kwargs = model_config.pop("filter_kwargs", {})
        order_by = model_config.pop("order_by", [])
        limit = model_config.pop("limit", None)
        
        try:
            # Build queryset
            queryset = model_class.objects.filter(**filter_kwargs)
            if order_by:
                queryset = queryset.order_by(*order_by)
            if limit:
                queryset = queryset[:limit]
            
            # Check each instance
            model_results = {
                "model": model_class.__name__,
                "total_instances": queryset.count(),
                "checked_instances": 0,
                "consistent_instances": 0,
                "inconsistent_instances": 0,
                "missing_from_cache": 0,
                "repaired_instances": 0,
            }
            
            for instance in queryset:
                model_results["checked_instances"] += 1
                
                # Generate hash of database instance
                db_hash = generate_model_hash(instance)
                
                # Get cached instance
                model_type = model_class.__name__.lower()
                cached_data = get_cached_model_instance(model_type, instance.pk)
                
                if cached_data is None:
                    # Instance missing from cache
                    model_results["missing_from_cache"] += 1
                    
                    if auto_repair:
                        # Repair by caching the instance
                        if hasattr(instance, "cache") and callable(instance.cache):
                            instance.cache()
                        else:
                            # Use generic caching
                            cache_model_instance(model_type, instance.pk, {
                                "id": instance.pk,
                                "model": model_type,
                                "db_hash": db_hash,
                            })
                        
                        model_results["repaired_instances"] += 1
                else:
                    # Instance exists in cache, check consistency
                    if isinstance(cached_data, dict) and "db_hash" in cached_data:
                        # Cache already has a hash, compare directly
                        cache_hash = cached_data["db_hash"]
                    else:
                        # Generate hash from cached data
                        try:
                            # Create a temporary instance with cached data
                            temp_instance = model_class()
                            temp_instance.pk = instance.pk
                            
                            # Set fields from cached data
                            for field_name, value in cached_data.items():
                                if field_name != "id" and field_name != "model" and field_name != "db_hash":
                                    setattr(temp_instance, field_name, value)
                            
                            # Generate hash
                            cache_hash = generate_model_hash(temp_instance)
                        except Exception as e:
                            logger.error(f"Error generating hash for cached {model_class.__name__} instance {instance.pk}: {str(e)}")
                            cache_hash = None
                    
                    if cache_hash == db_hash:
                        # Consistent
                        model_results["consistent_instances"] += 1
                    else:
                        # Inconsistent
                        model_results["inconsistent_instances"] += 1
                        
                        if auto_repair:
                            # Repair by updating the cache
                            if hasattr(instance, "cache") and callable(instance.cache):
                                instance.cache()
                            else:
                                # Use generic caching
                                cache_model_instance(model_type, instance.pk, {
                                    "id": instance.pk,
                                    "model": model_type,
                                    "db_hash": db_hash,
                                })
                            
                            model_results["repaired_instances"] += 1
            
            results[model_class.__name__] = model_results
        except Exception as e:
            logger.error(f"Error checking consistency for {model_class.__name__}: {str(e)}")
            results[model_class.__name__] = {"error": str(e)}
    
    # Calculate elapsed time
    elapsed = time.time() - start_time
    
    # Aggregate results
    total_checked = sum(r.get("checked_instances", 0) for r in results.values() if isinstance(r, dict))
    total_consistent = sum(r.get("consistent_instances", 0) for r in results.values() if isinstance(r, dict))
    total_inconsistent = sum(r.get("inconsistent_instances", 0) for r in results.values() if isinstance(r, dict))
    total_missing = sum(r.get("missing_from_cache", 0) for r in results.values() if isinstance(r, dict))
    total_repaired = sum(r.get("repaired_instances", 0) for r in results.values() if isinstance(r, dict))
    
    logger.info(
        f"Completed consistency check for frequently accessed models: "
        f"{total_consistent}/{total_checked} consistent, "
        f"{total_inconsistent} inconsistent, "
        f"{total_missing} missing, "
        f"{total_repaired} repaired "
        f"in {elapsed:.2f} seconds"
    )
    
    return {
        "models": results,
        "total_checked": total_checked,
        "total_consistent": total_consistent,
        "total_inconsistent": total_inconsistent,
        "total_missing": total_missing,
        "total_repaired": total_repaired,
        "elapsed_seconds": elapsed,
        "timestamp": timezone.now().isoformat(),
    }


def schedule_consistency_checks():
    """
    Schedule regular consistency checks.
    """
    if not CACHE_ENABLED:
        logger.warning("Consistency check scheduling skipped: Cache is disabled")
        return
    
    try:
        # Schedule with Celery if available
        try:
            from celery import current_app
            
            @current_app.task(name="core.redis_consistency.check_consistency_task")
            def check_consistency_task():
                check_frequently_accessed_models_consistency()
            
            # Schedule daily consistency check
            current_app.conf.beat_schedule.update({
                "check-cache-consistency-daily": {
                    "task": "core.redis_consistency.check_consistency_task",
                    "schedule": 60 * 60 * 24,  # 24 hours
                    "options": {"expires": 60 * 60 * 25},
                },
            })
            
            logger.info("Scheduled consistency checks with Celery")
            return
        except ImportError:
            logger.debug("Celery not available, trying Django Q")
        
        # Schedule with Django Q if available
        try:
            from django_q.tasks import schedule
            from django_q.models import Schedule
            
            # Schedule daily consistency check
            schedule(
                "core.redis_consistency.check_frequently_accessed_models_consistency",
                name="Check Redis Cache Consistency",
                schedule_type=Schedule.DAILY,
            )
            
            logger.info("Scheduled consistency checks with Django Q")
            return
        except ImportError:
            logger.debug("Django Q not available")
        
        logger.warning("No task scheduler available for consistency checks")
    except Exception as e:
        logger.error(f"Error scheduling consistency checks: {str(e)}")


def verify_cache_entry(model_type: str, instance_id: int) -> Dict:
    """
    Verify a specific cache entry against the database.
    
    Args:
        model_type: Model type (e.g., "user", "job")
        instance_id: Instance ID
        
    Returns:
        Dictionary with verification results
    """
    if not CACHE_ENABLED:
        return {"error": "Cache is disabled"}
    
    start_time = time.time()
    
    try:
        # Get model class
        if model_type == "user":
            from django.contrib.auth import get_user_model
            model_class = get_user_model()
        else:
            # Try to find the model class
            for app_config in apps.get_app_configs():
                try:
                    model_class = app_config.get_model(model_type)
                    break
                except LookupError:
                    continue
            else:
                return {"error": f"Model type {model_type} not found"}
        
        # Get instance from database
        try:
            instance = model_class.objects.get(pk=instance_id)
        except model_class.DoesNotExist:
            return {
                "model": model_type,
                "id": instance_id,
                "exists_in_db": False,
                "exists_in_cache": get_cached_model_instance(model_type, instance_id) is not None,
                "consistent": False,
                "elapsed_seconds": time.time() - start_time,
                "timestamp": timezone.now().isoformat(),
            }
        
        # Generate hash of database instance
        db_hash = generate_model_hash(instance)
        
        # Get cached instance
        cached_data = get_cached_model_instance(model_type, instance_id)
        
        if cached_data is None:
            # Instance missing from cache
            return {
                "model": model_type,
                "id": instance_id,
                "exists_in_db": True,
                "exists_in_cache": False,
                "consistent": False,
                "elapsed_seconds": time.time() - start_time,
                "timestamp": timezone.now().isoformat(),
            }
        
        # Instance exists in cache, check consistency
        if isinstance(cached_data, dict) and "db_hash" in cached_data:
            # Cache already has a hash, compare directly
            cache_hash = cached_data["db_hash"]
        else:
            # Generate hash from cached data
            try:
                # Create a temporary instance with cached data
                temp_instance = model_class()
                temp_instance.pk = instance_id
                
                # Set fields from cached data
                for field_name, value in cached_data.items():
                    if field_name != "id" and field_name != "model" and field_name != "db_hash":
                        setattr(temp_instance, field_name, value)
                
                # Generate hash
                cache_hash = generate_model_hash(temp_instance)
            except Exception as e:
                logger.error(f"Error generating hash for cached {model_type} instance {instance_id}: {str(e)}")
                cache_hash = None
        
        # Return results
        return {
            "model": model_type,
            "id": instance_id,
            "exists_in_db": True,
            "exists_in_cache": True,
            "consistent": cache_hash == db_hash,
            "elapsed_seconds": time.time() - start_time,
            "timestamp": timezone.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error verifying cache entry {model_type}:{instance_id}: {str(e)}")
        return {
            "model": model_type,
            "id": instance_id,
            "error": str(e),
            "elapsed_seconds": time.time() - start_time,
            "timestamp": timezone.now().isoformat(),
        }


def repair_cache_entry(model_type: str, instance_id: int) -> Dict:
    """
    Repair a specific cache entry.
    
    Args:
        model_type: Model type (e.g., "user", "job")
        instance_id: Instance ID
        
    Returns:
        Dictionary with repair results
    """
    if not CACHE_ENABLED:
        return {"error": "Cache is disabled"}
    
    start_time = time.time()
    
    try:
        # Get model class
        if model_type == "user":
            from django.contrib.auth import get_user_model
            model_class = get_user_model()
        else:
            # Try to find the model class
            for app_config in apps.get_app_configs():
                try:
                    model_class = app_config.get_model(model_type)
                    break
                except LookupError:
                    continue
            else:
                return {"error": f"Model type {model_type} not found"}
        
        # Get instance from database
        try:
            instance = model_class.objects.get(pk=instance_id)
        except model_class.DoesNotExist:
            # Instance doesn't exist in database, invalidate cache
            invalidate_model_instance(model_type, instance_id)
            return {
                "model": model_type,
                "id": instance_id,
                "exists_in_db": False,
                "action": "invalidated",
                "success": True,
                "elapsed_seconds": time.time() - start_time,
                "timestamp": timezone.now().isoformat(),
            }
        
        # Instance exists in database, update cache
        if hasattr(instance, "cache") and callable(instance.cache):
            # Use the model's cache method
            instance.cache()
            action = "cached_with_method"
        else:
            # Use generic caching
            db_hash = generate_model_hash(instance)
            
            if hasattr(instance, "to_dict"):
                data = instance.to_dict()
                data["db_hash"] = db_hash
            else:
                # Basic serialization
                data = {
                    "id": instance.pk,
                    "model": model_type,
                    "db_hash": db_hash,
                }
                
                # Add common fields
                for field in instance._meta.fields:
                    field_name = field.name
                    if field_name != "id":
                        value = getattr(instance, field_name)
                        
                        # Handle special field types
                        if isinstance(value, models.Model):
                            # For foreign keys, just store the ID
                            data[field_name] = value.pk
                        elif hasattr(value, "isoformat"):
                            # For dates and times, convert to ISO format
                            data[field_name] = value.isoformat()
                        else:
                            # For other fields, store as is
                            data[field_name] = value
            
            # Cache the instance
            cache_model_instance(model_type, instance_id, data)
            action = "cached_with_generic"
        
        # Return results
        return {
            "model": model_type,
            "id": instance_id,
            "exists_in_db": True,
            "action": action,
            "success": True,
            "elapsed_seconds": time.time() - start_time,
            "timestamp": timezone.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error repairing cache entry {model_type}:{instance_id}: {str(e)}")
        return {
            "model": model_type,
            "id": instance_id,
            "error": str(e),
            "success": False,
            "elapsed_seconds": time.time() - start_time,
            "timestamp": timezone.now().isoformat(),
        }

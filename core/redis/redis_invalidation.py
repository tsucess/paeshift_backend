"""
Redis cache invalidation utilities.

This module provides a robust and consistent approach to cache invalidation,
including support for related objects, cascading invalidations, and
transaction-aware operations.
"""

import logging
import time
import traceback
from typing import Any, Dict, List, Optional, Set, Type, Union

from django.db import models, transaction
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from core.cache import (
    delete_cached_data,
    generate_cache_key,
    invalidate_cache_pattern,
    redis_client,
)
from core.redis_settings import CACHE_ENABLED, CACHE_PREFIXES, MODEL_CACHE_PREFIX

logger = logging.getLogger(__name__)

# Registry of model dependencies
# Format: {model_class: [dependent_model_classes]}
_MODEL_DEPENDENCIES = {}

# Registry of model invalidation handlers
# Format: {model_class: [invalidation_handlers]}
_INVALIDATION_HANDLERS = {}

# Set to track models currently being invalidated (to prevent infinite recursion)
_CURRENTLY_INVALIDATING = set()


def register_model_dependency(
    model_class: Type[models.Model], dependent_model_class: Type[models.Model]
) -> None:
    """
    Register a dependency between models for cache invalidation.

    When instances of model_class are modified, caches for dependent_model_class
    should also be invalidated.

    Args:
        model_class: The model class that triggers invalidation
        dependent_model_class: The model class whose cache should be invalidated
    """
    if model_class not in _MODEL_DEPENDENCIES:
        _MODEL_DEPENDENCIES[model_class] = []

    if dependent_model_class not in _MODEL_DEPENDENCIES[model_class]:
        _MODEL_DEPENDENCIES[model_class].append(dependent_model_class)
        logger.debug(
            f"Registered cache dependency: {model_class.__name__} -> {dependent_model_class.__name__}"
        )


def register_invalidation_handler(
    model_class: Type[models.Model], handler_func
) -> None:
    """
    Register a custom invalidation handler for a model.

    Args:
        model_class: The model class
        handler_func: Function that takes a model instance and invalidates related caches
    """
    if model_class not in _INVALIDATION_HANDLERS:
        _INVALIDATION_HANDLERS[model_class] = []

    if handler_func not in _INVALIDATION_HANDLERS[model_class]:
        _INVALIDATION_HANDLERS[model_class].append(handler_func)
        logger.debug(
            f"Registered custom invalidation handler for {model_class.__name__}"
        )


def invalidate_model_cache(
    instance: models.Model, cascade: bool = True, reason: str = "manual"
) -> bool:
    """
    Invalidate cache for a model instance and its dependencies.

    Args:
        instance: The model instance
        cascade: Whether to cascade invalidation to dependent models
        reason: Reason for invalidation (for logging)

    Returns:
        True if successful, False otherwise
    """
    if not CACHE_ENABLED or not redis_client:
        return False

    # Prevent infinite recursion
    instance_key = f"{instance.__class__.__name__}:{instance.pk}"
    if instance_key in _CURRENTLY_INVALIDATING:
        return True

    start_time = time.time()
    model_name = instance.__class__.__name__
    
    try:
        _CURRENTLY_INVALIDATING.add(instance_key)
        
        # Generate cache key
        prefix = CACHE_PREFIXES.get(
            model_name.lower(), MODEL_CACHE_PREFIX
        )
        cache_key = generate_cache_key(prefix, instance.pk)
        
        # Delete from cache
        success = delete_cached_data(cache_key)
        
        # Call custom invalidation handlers
        if instance.__class__ in _INVALIDATION_HANDLERS:
            for handler in _INVALIDATION_HANDLERS[instance.__class__]:
                try:
                    handler(instance)
                except Exception as e:
                    logger.error(
                        f"Error in custom invalidation handler for {model_name}: {str(e)}"
                    )
        
        # Cascade invalidation to dependent models
        if cascade and instance.__class__ in _MODEL_DEPENDENCIES:
            for dependent_class in _MODEL_DEPENDENCIES[instance.__class__]:
                try:
                    # Get related instances
                    related_instances = _get_related_instances(instance, dependent_class)
                    
                    for related_instance in related_instances:
                        invalidate_model_cache(
                            related_instance, 
                            cascade=False,  # Prevent infinite recursion
                            reason=f"cascade from {model_name}"
                        )
                except Exception as e:
                    logger.error(
                        f"Error cascading invalidation from {model_name} to {dependent_class.__name__}: {str(e)}"
                    )
        
        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.debug(
            f"Invalidated cache for {model_name} with ID {instance.pk} "
            f"(reason: {reason}, duration: {duration_ms}ms)"
        )
        
        return success
    except Exception as e:
        logger.error(
            f"Error invalidating cache for {model_name} with ID {instance.pk}: {str(e)}\n"
            f"{traceback.format_exc()}"
        )
        return False
    finally:
        # Remove from currently invalidating set
        _CURRENTLY_INVALIDATING.discard(instance_key)


def invalidate_model_class_cache(
    model_class: Type[models.Model], reason: str = "manual"
) -> int:
    """
    Invalidate all cache entries for a model class.

    Args:
        model_class: The model class
        reason: Reason for invalidation (for logging)

    Returns:
        Number of cache entries invalidated
    """
    if not CACHE_ENABLED or not redis_client:
        return 0

    start_time = time.time()
    model_name = model_class.__name__
    
    try:
        # Generate cache pattern
        prefix = CACHE_PREFIXES.get(
            model_name.lower(), MODEL_CACHE_PREFIX
        )
        pattern = f"{prefix}*"
        
        # Invalidate all matching keys
        count = invalidate_cache_pattern(pattern)
        
        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.info(
            f"Invalidated {count} cache entries for {model_name} "
            f"(reason: {reason}, duration: {duration_ms}ms)"
        )
        
        return count
    except Exception as e:
        logger.error(
            f"Error invalidating cache for {model_name}: {str(e)}\n"
            f"{traceback.format_exc()}"
        )
        return 0


def _get_related_instances(
    instance: models.Model, related_model_class: Type[models.Model]
) -> List[models.Model]:
    """
    Get instances of related_model_class that are related to instance.

    Args:
        instance: The model instance
        related_model_class: The related model class

    Returns:
        List of related model instances
    """
    related_instances = []
    
    # Check for direct foreign keys from related model to this model
    for field in related_model_class._meta.fields:
        if isinstance(field, models.ForeignKey) and field.related_model == instance.__class__:
            # Get instances that reference this instance
            filter_kwargs = {field.name: instance}
            related_instances.extend(
                related_model_class.objects.filter(**filter_kwargs)
            )
    
    # Check for direct foreign keys from this model to related model
    for field in instance.__class__._meta.fields:
        if isinstance(field, models.ForeignKey) and field.related_model == related_model_class:
            # Get the related instance
            related_instance = getattr(instance, field.name)
            if related_instance:
                related_instances.append(related_instance)
    
    # Check for many-to-many relationships
    for field in instance.__class__._meta.many_to_many:
        if field.related_model == related_model_class:
            # Get related instances through m2m
            related_instances.extend(getattr(instance, field.name).all())
    
    # Check for many-to-many relationships from related model
    for field in related_model_class._meta.many_to_many:
        if field.related_model == instance.__class__:
            # Get instances that reference this instance through m2m
            filter_kwargs = {f"{field.name}__id": instance.pk}
            related_instances.extend(
                related_model_class.objects.filter(**filter_kwargs)
            )
    
    return related_instances


class TransactionAwareInvalidator:
    """
    Transaction-aware cache invalidation.
    
    This class collects model instances to be invalidated during a transaction
    and performs the invalidation after the transaction is committed.
    """
    
    def __init__(self):
        self.pending_invalidations = {}
        self.is_active = False
    
    def add(self, instance: models.Model, reason: str = "transaction") -> None:
        """
        Add a model instance to be invalidated after the transaction.
        
        Args:
            instance: The model instance
            reason: Reason for invalidation (for logging)
        """
        if not self.is_active:
            # Not in a transaction, invalidate immediately
            invalidate_model_cache(instance, reason=reason)
            return
            
        # Add to pending invalidations
        key = f"{instance.__class__.__name__}:{instance.pk}"
        self.pending_invalidations[key] = (instance, reason)
    
    def start(self) -> None:
        """Start collecting invalidations."""
        self.is_active = True
        self.pending_invalidations = {}
    
    def commit(self) -> None:
        """Commit all pending invalidations."""
        if not self.is_active:
            return
            
        # Process all pending invalidations
        for key, (instance, reason) in self.pending_invalidations.items():
            try:
                invalidate_model_cache(instance, reason=f"transaction:{reason}")
            except Exception as e:
                logger.error(
                    f"Error processing pending invalidation for {key}: {str(e)}"
                )
        
        # Reset
        self.pending_invalidations = {}
        self.is_active = False
    
    def rollback(self) -> None:
        """Rollback all pending invalidations."""
        self.pending_invalidations = {}
        self.is_active = False


# Create a global transaction-aware invalidator
transaction_invalidator = TransactionAwareInvalidator()


@receiver(post_save)
def invalidate_on_save(sender, instance, created, **kwargs):
    """
    Signal handler to invalidate cache when a model is saved.
    
    Args:
        sender: The model class
        instance: The model instance
        created: Whether the instance was created
        **kwargs: Additional arguments
    """
    # Skip built-in models
    if sender._meta.app_label in ["auth", "contenttypes", "sessions", "admin"]:
        return
        
    # Skip if the model has its own cache handling
    if hasattr(instance, "invalidate_cache") and callable(getattr(instance, "invalidate_cache")):
        return
        
    # Invalidate cache
    reason = "created" if created else "updated"
    
    # Check if we're in a transaction
    if transaction.get_connection().in_atomic_block:
        # Add to transaction invalidator
        transaction_invalidator.add(instance, reason=reason)
    else:
        # Invalidate immediately
        invalidate_model_cache(instance, reason=reason)


@receiver(post_delete)
def invalidate_on_delete(sender, instance, **kwargs):
    """
    Signal handler to invalidate cache when a model is deleted.
    
    Args:
        sender: The model class
        instance: The model instance
        **kwargs: Additional arguments
    """
    # Skip built-in models
    if sender._meta.app_label in ["auth", "contenttypes", "sessions", "admin"]:
        return
        
    # Skip if the model has its own cache handling
    if hasattr(instance, "invalidate_cache") and callable(getattr(instance, "invalidate_cache")):
        return
        
    # Invalidate cache
    reason = "deleted"
    
    # Check if we're in a transaction
    if transaction.get_connection().in_atomic_block:
        # Add to transaction invalidator
        transaction_invalidator.add(instance, reason=reason)
    else:
        # Invalidate immediately
        invalidate_model_cache(instance, reason=reason)


@receiver(m2m_changed)
def invalidate_on_m2m_change(sender, instance, action, **kwargs):
    """
    Signal handler to invalidate cache when a many-to-many relationship changes.
    
    Args:
        sender: The through model class
        instance: The model instance
        action: The action performed
        **kwargs: Additional arguments
    """
    # Only invalidate on post actions
    if not action.startswith("post_"):
        return
        
    # Skip if the model has its own cache handling
    if hasattr(instance, "invalidate_cache") and callable(getattr(instance, "invalidate_cache")):
        return
        
    # Invalidate cache
    reason = f"m2m_{action}"
    
    # Check if we're in a transaction
    if transaction.get_connection().in_atomic_block:
        # Add to transaction invalidator
        transaction_invalidator.add(instance, reason=reason)
    else:
        # Invalidate immediately
        invalidate_model_cache(instance, reason=reason)


# Connect to Django's transaction signals
@receiver(transaction.signals.post_commit)
def on_transaction_commit(**kwargs):
    """Commit pending invalidations when a transaction is committed."""
    transaction_invalidator.commit()


@receiver(transaction.signals.post_rollback)
def on_transaction_rollback(**kwargs):
    """Rollback pending invalidations when a transaction is rolled back."""
    transaction_invalidator.rollback()

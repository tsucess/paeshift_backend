"""
Redis hibernation utilities.

This module provides utilities for "hibernating" functions by permanently caching
their results while maintaining consistency with the database.
"""

import functools
import hashlib
import inspect
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type, Union

from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from core.redis.utils import cache_permanently, get_permanent_cache, delete_permanent_cache

logger = logging.getLogger(__name__)

# Registry of model dependencies for cached functions
# Format: {model_class: {(function_name, cache_key_pattern)}}
_DEPENDENCY_REGISTRY = {}


def register_dependency(model_class: Type[models.Model], function_name: str, cache_key_pattern: str) -> None:
    """
    Register a dependency between a model and a cached function.

    Args:
        model_class: The model class that the function depends on
        function_name: The name of the function
        cache_key_pattern: The pattern for cache keys to invalidate
    """
    if model_class not in _DEPENDENCY_REGISTRY:
        _DEPENDENCY_REGISTRY[model_class] = set()

    _DEPENDENCY_REGISTRY[model_class].add((function_name, cache_key_pattern))
    logger.debug(f"Registered dependency: {model_class.__name__} -> {function_name} ({cache_key_pattern})")


def generate_cache_key(func: Callable, args: Tuple, kwargs: Dict) -> str:
    """
    Generate a cache key for a function call.

    Args:
        func: The function
        args: Positional arguments
        kwargs: Keyword arguments

    Returns:
        Cache key
    """
    # Get function name and module
    func_name = func.__name__
    module_name = func.__module__

    # Convert args and kwargs to strings and hash them
    args_str = str(args)
    kwargs_str = str(sorted(kwargs.items()))

    args_hash = hashlib.md5(args_str.encode()).hexdigest()
    kwargs_hash = hashlib.md5(kwargs_str.encode()).hexdigest()

    # Generate key
    return f"hibernate:{module_name}.{func_name}:{args_hash}:{kwargs_hash}"


def hibernate(
    depends_on: Optional[List[Type[models.Model]]] = None,
    key_prefix: Optional[str] = None,
    include_args: bool = True,
    include_kwargs: bool = True,
) -> Callable:
    """
    Decorator to hibernate a function by permanently caching its results.

    The cache is automatically invalidated when any of the dependent models change.

    Args:
        depends_on: List of model classes that the function depends on
        key_prefix: Optional prefix for the cache key
        include_args: Whether to include positional args in the cache key
        include_kwargs: Whether to include keyword args in the cache key

    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_prefix:
                cache_key = f"{key_prefix}:{func.__module__}.{func.__name__}"

                # Add args to key if requested
                if include_args and args:
                    args_str = str(args)
                    cache_key += f":{hashlib.md5(args_str.encode()).hexdigest()}"

                # Add kwargs to key if requested
                if include_kwargs and kwargs:
                    kwargs_str = str(sorted(kwargs.items()))
                    cache_key += f":{hashlib.md5(kwargs_str.encode()).hexdigest()}"
            else:
                cache_key = generate_cache_key(func, args, kwargs)

            # Try to get from cache
            cached_result = get_permanent_cache(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for hibernated function {func.__name__}")
                return cached_result

            # Cache miss, call the function
            logger.debug(f"Cache miss for hibernated function {func.__name__}")
            result = func(*args, **kwargs)

            # Cache the result
            cache_permanently(result, cache_key)

            # Register dependencies
            if depends_on:
                for model_class in depends_on:
                    register_dependency(model_class, func.__name__, cache_key)

            return result

        # Store the original function and dependencies
        wrapper.original_func = func
        wrapper.dependencies = depends_on or []

        return wrapper

    return decorator


@receiver(post_save)
def invalidate_on_save(sender, instance, **kwargs):
    """
    Signal handler to invalidate cache when a model instance is saved.

    Args:
        sender: The model class
        instance: The model instance
    """
    # Check if the model is in the dependency registry
    if sender not in _DEPENDENCY_REGISTRY:
        return

    # Get dependencies
    dependencies = _DEPENDENCY_REGISTRY[sender]

    # Invalidate cache for each dependency
    for function_name, cache_key_pattern in dependencies:
        # If the cache key pattern contains the instance ID, invalidate only that key
        if "{instance.id}" in cache_key_pattern:
            cache_key = cache_key_pattern.format(instance=instance)
            delete_permanent_cache(cache_key)
            logger.info(f"Invalidated cache for {function_name} with key {cache_key}")
        else:
            # Otherwise, invalidate all keys matching the pattern
            # This is a simplified implementation - in a real system, you would use Redis SCAN
            # to find and delete all matching keys
            delete_permanent_cache(cache_key_pattern)
            logger.info(f"Invalidated cache for {function_name} with pattern {cache_key_pattern}")


@receiver(post_delete)
def invalidate_on_delete(sender, instance, **kwargs):
    """
    Signal handler to invalidate cache when a model instance is deleted.

    Args:
        sender: The model class
        instance: The model instance
    """
    # Use the same logic as invalidate_on_save
    invalidate_on_save(sender, instance, **kwargs)


class HibernateMixin:
    """
    Mixin for models to automatically invalidate hibernated functions.

    This mixin adds methods to invalidate hibernated functions when the model
    instance is saved or deleted.
    """

    def invalidate_hibernated_functions(self):
        """
        Invalidate all hibernated functions that depend on this model.
        """
        model_class = self.__class__

        # Check if the model is in the dependency registry
        if model_class not in _DEPENDENCY_REGISTRY:
            return

        # Get dependencies
        dependencies = _DEPENDENCY_REGISTRY[model_class]

        # Invalidate cache for each dependency
        for function_name, cache_key_pattern in dependencies:
            # If the cache key pattern contains the instance ID, invalidate only that key
            if "{instance.id}" in cache_key_pattern:
                cache_key = cache_key_pattern.format(instance=self)
                delete_permanent_cache(cache_key)
                logger.info(f"Invalidated cache for {function_name} with key {cache_key}")
            else:
                # Otherwise, invalidate all keys matching the pattern
                delete_permanent_cache(cache_key_pattern)
                logger.info(f"Invalidated cache for {function_name} with pattern {cache_key_pattern}")

    def save(self, *args, **kwargs):
        """
        Override save method to invalidate hibernated functions.

        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
        """
        # Call the original save method
        result = super().save(*args, **kwargs)

        # Invalidate hibernated functions
        self.invalidate_hibernated_functions()

        return result

    def delete(self, *args, **kwargs):
        """
        Override delete method to invalidate hibernated functions.

        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
        """
        # Invalidate hibernated functions
        self.invalidate_hibernated_functions()

        # Call the original delete method
        return super().delete(*args, **kwargs)

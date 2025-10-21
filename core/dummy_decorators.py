"""
Dummy decorators to replace Redis decorators when caching is disabled.
These decorators do nothing but allow the code to run without Redis dependencies.
"""

import functools
from typing import Any, Callable


def time_view(func: Callable) -> Callable:
    """Dummy time_view decorator - does nothing."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


def cache_api_response(timeout: int = 300, key_prefix: str = "") -> Callable:
    """Dummy cache_api_response decorator - does nothing."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator


def cache_function(timeout: int = 300, key_prefix: str = "") -> Callable:
    """Dummy cache_function decorator - does nothing."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator


def no_cache(func: Callable) -> Callable:
    """Dummy no_cache decorator - does nothing."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


def cache_method_result(timeout: int = 300) -> Callable:
    """Dummy cache_method_result decorator - does nothing."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator


def use_cached_model(model_param: str, model_class: Any, id_param: str = "pk") -> Callable:
    """Dummy use_cached_model decorator - does nothing."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator


def hibernate(func: Callable) -> Callable:
    """Dummy hibernate decorator - does nothing."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


def log_operation(*args, **kwargs) -> None:
    """Dummy log_operation function - does nothing."""
    pass


# Export all dummy decorators
__all__ = [
    'time_view',
    'cache_api_response', 
    'cache_function',
    'no_cache',
    'cache_method_result',
    'use_cached_model',
    'hibernate',
    'log_operation',
]

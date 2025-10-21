"""
Redis-based rate limiting utilities.

This module provides utilities for rate limiting API requests and other operations
using Redis as a backend.
"""

import logging
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional, Union

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, JsonResponse

logger = logging.getLogger(__name__)

# Constants
RATE_LIMIT_PREFIX = "rate_limit:"
DEFAULT_RATE_LIMIT = 60  # requests per minute
DEFAULT_RATE_WINDOW = 60  # seconds


def get_rate_limit_key(prefix: str, identifier: str) -> str:
    """
    Generate a rate limit key.
    
    Args:
        prefix: Key prefix
        identifier: Unique identifier (e.g., IP address, user ID)
        
    Returns:
        Rate limit key
    """
    return f"{RATE_LIMIT_PREFIX}{prefix}:{identifier}"


def is_rate_limited(
    prefix: str,
    identifier: str,
    limit: int = DEFAULT_RATE_LIMIT,
    window: int = DEFAULT_RATE_WINDOW,
) -> bool:
    """
    Check if a request should be rate limited.
    
    Args:
        prefix: Key prefix
        identifier: Unique identifier (e.g., IP address, user ID)
        limit: Maximum number of requests allowed in the window
        window: Time window in seconds
        
    Returns:
        True if rate limited, False otherwise
    """
    key = get_rate_limit_key(prefix, identifier)
    
    # Get current count
    count = cache.get(key, 0)
    
    # Check if limit exceeded
    if count >= limit:
        return True
    
    # Increment count
    pipe = cache.client.pipeline()
    pipe.incr(key)
    
    # Set expiration if not already set
    if count == 0:
        pipe.expire(key, window)
    
    pipe.execute()
    
    return False


def get_rate_limit_remaining(
    prefix: str,
    identifier: str,
    limit: int = DEFAULT_RATE_LIMIT,
) -> int:
    """
    Get remaining requests allowed.
    
    Args:
        prefix: Key prefix
        identifier: Unique identifier (e.g., IP address, user ID)
        limit: Maximum number of requests allowed in the window
        
    Returns:
        Number of remaining requests allowed
    """
    key = get_rate_limit_key(prefix, identifier)
    
    # Get current count
    count = cache.get(key, 0)
    
    # Calculate remaining
    remaining = max(0, limit - count)
    
    return remaining


def rate_limit(
    limit: int = DEFAULT_RATE_LIMIT,
    window: int = DEFAULT_RATE_WINDOW,
    key_prefix: str = "api",
    by_ip: bool = True,
    by_user: bool = True,
):
    """
    Rate limiting decorator for views.
    
    Args:
        limit: Maximum number of requests allowed in the window
        window: Time window in seconds
        key_prefix: Key prefix
        by_ip: Whether to rate limit by IP address
        by_user: Whether to rate limit by user ID
        
    Returns:
        Decorated function
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            # Skip rate limiting in debug mode if configured
            if getattr(settings, "DEBUG", False) and getattr(settings, "DISABLE_RATE_LIMIT_IN_DEBUG", False):
                return view_func(request, *args, **kwargs)
            
            # Get identifiers
            identifiers = []
            
            if by_ip:
                ip = get_client_ip(request)
                if ip:
                    identifiers.append(f"ip:{ip}")
            
            if by_user and request.user.is_authenticated:
                identifiers.append(f"user:{request.user.id}")
            
            # If no identifiers, skip rate limiting
            if not identifiers:
                return view_func(request, *args, **kwargs)
            
            # Check rate limit for each identifier
            for identifier in identifiers:
                if is_rate_limited(key_prefix, identifier, limit, window):
                    remaining = get_rate_limit_remaining(key_prefix, identifier, limit)
                    
                    # Log rate limit
                    logger.warning(f"Rate limit exceeded for {identifier}")
                    
                    # Return rate limit response
                    return JsonResponse(
                        {
                            "error": "Rate limit exceeded",
                            "limit": limit,
                            "window": window,
                            "remaining": remaining,
                            "retry_after": window,
                        },
                        status=429,
                    )
            
            # Call view function
            return view_func(request, *args, **kwargs)
        
        return wrapped_view
    
    return decorator


def get_client_ip(request: HttpRequest) -> Optional[str]:
    """
    Get client IP address from request.
    
    Args:
        request: HTTP request
        
    Returns:
        Client IP address or None
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip

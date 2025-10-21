"""
Rate limiting utilities for God Mode.

This module provides utilities for rate limiting API requests to God Mode.
"""

import logging
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple, Union

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse

logger = logging.getLogger(__name__)

# Constants
DEFAULT_RATE_LIMIT = 60  # requests per minute
DEFAULT_RATE_WINDOW = 60  # seconds
RATE_LIMIT_CACHE_PREFIX = "rate_limit:"
RATE_LIMIT_EXCEEDED_STATUS = 429  # Too Many Requests


def get_client_ip(request: HttpRequest) -> str:
    """
    Get client IP address.
    
    Args:
        request: HTTP request
        
    Returns:
        Client IP address
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


def get_rate_limit_key(
    request: HttpRequest, scope: str = "global", resource: Optional[str] = None
) -> str:
    """
    Get rate limit cache key.
    
    Args:
        request: HTTP request
        scope: Rate limit scope (global, ip, user, endpoint)
        resource: Resource identifier (e.g., endpoint name)
        
    Returns:
        Cache key
    """
    if scope == "ip":
        # Rate limit by IP address
        identifier = get_client_ip(request)
    elif scope == "user" and request.user.is_authenticated:
        # Rate limit by user ID
        identifier = str(request.user.id)
    elif scope == "endpoint" and resource:
        # Rate limit by endpoint
        identifier = resource
    else:
        # Global rate limit
        identifier = "global"
    
    return f"{RATE_LIMIT_CACHE_PREFIX}{scope}:{identifier}"


def check_rate_limit(
    request: HttpRequest,
    scope: str = "ip",
    resource: Optional[str] = None,
    limit: int = DEFAULT_RATE_LIMIT,
    window: int = DEFAULT_RATE_WINDOW,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Check if a request exceeds the rate limit.
    
    Args:
        request: HTTP request
        scope: Rate limit scope (global, ip, user, endpoint)
        resource: Resource identifier (e.g., endpoint name)
        limit: Maximum number of requests allowed in the window
        window: Time window in seconds
        
    Returns:
        Tuple of (allowed, rate_limit_info)
    """
    # Get cache key
    cache_key = get_rate_limit_key(request, scope, resource)
    
    # Get current time
    current_time = int(time.time())
    
    # Get rate limit data from cache
    rate_limit_data = cache.get(cache_key)
    
    if rate_limit_data is None:
        # Initialize rate limit data
        rate_limit_data = {
            "count": 0,
            "reset_time": current_time + window,
        }
    
    # Check if window has expired
    if current_time > rate_limit_data["reset_time"]:
        # Reset rate limit data
        rate_limit_data = {
            "count": 0,
            "reset_time": current_time + window,
        }
    
    # Increment request count
    rate_limit_data["count"] += 1
    
    # Calculate remaining requests
    remaining = max(0, limit - rate_limit_data["count"])
    
    # Calculate time until reset
    reset_in = max(0, rate_limit_data["reset_time"] - current_time)
    
    # Update cache
    cache.set(cache_key, rate_limit_data, window * 2)  # Set expiration to twice the window
    
    # Check if rate limit exceeded
    allowed = rate_limit_data["count"] <= limit
    
    # Prepare rate limit info
    rate_limit_info = {
        "limit": limit,
        "remaining": remaining,
        "reset": rate_limit_data["reset_time"],
        "reset_in": reset_in,
    }
    
    return allowed, rate_limit_info


def rate_limit_response(rate_limit_info: Dict[str, Any]) -> JsonResponse:
    """
    Create a rate limit exceeded response.
    
    Args:
        rate_limit_info: Rate limit information
        
    Returns:
        HTTP response
    """
    response = JsonResponse(
        {
            "error": "Rate limit exceeded",
            "message": "Too many requests. Please try again later.",
            "limit": rate_limit_info["limit"],
            "reset": rate_limit_info["reset"],
            "reset_in": rate_limit_info["reset_in"],
        },
        status=RATE_LIMIT_EXCEEDED_STATUS,
    )
    
    # Add rate limit headers
    response["X-RateLimit-Limit"] = str(rate_limit_info["limit"])
    response["X-RateLimit-Remaining"] = str(rate_limit_info["remaining"])
    response["X-RateLimit-Reset"] = str(rate_limit_info["reset"])
    response["Retry-After"] = str(rate_limit_info["reset_in"])
    
    return response


def add_rate_limit_headers(response: HttpResponse, rate_limit_info: Dict[str, Any]) -> HttpResponse:
    """
    Add rate limit headers to a response.
    
    Args:
        response: HTTP response
        rate_limit_info: Rate limit information
        
    Returns:
        HTTP response with rate limit headers
    """
    response["X-RateLimit-Limit"] = str(rate_limit_info["limit"])
    response["X-RateLimit-Remaining"] = str(rate_limit_info["remaining"])
    response["X-RateLimit-Reset"] = str(rate_limit_info["reset"])
    
    return response


def rate_limit(
    scope: str = "ip",
    limit: Optional[int] = None,
    window: Optional[int] = None,
    resource: Optional[str] = None,
):
    """
    Decorator for rate limiting views.
    
    Args:
        scope: Rate limit scope (global, ip, user, endpoint)
        limit: Maximum number of requests allowed in the window
        window: Time window in seconds
        resource: Resource identifier (e.g., endpoint name)
        
    Returns:
        Decorated view function
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            # Get rate limit settings
            rate_limit_settings = getattr(settings, "RATE_LIMIT_SETTINGS", {})
            
            # Get limit and window from settings or use defaults
            actual_limit = limit or rate_limit_settings.get("limit", DEFAULT_RATE_LIMIT)
            actual_window = window or rate_limit_settings.get("window", DEFAULT_RATE_WINDOW)
            
            # Get resource name
            actual_resource = resource or request.path
            
            # Check rate limit
            allowed, rate_limit_info = check_rate_limit(
                request, scope, actual_resource, actual_limit, actual_window
            )
            
            if not allowed:
                # Log rate limit exceeded
                logger.warning(
                    f"Rate limit exceeded: {scope}:{actual_resource} "
                    f"from {get_client_ip(request)} by {request.user.username if request.user.is_authenticated else 'anonymous'}"
                )
                
                # Return rate limit exceeded response
                return rate_limit_response(rate_limit_info)
            
            # Call the view function
            response = view_func(request, *args, **kwargs)
            
            # Add rate limit headers to response
            response = add_rate_limit_headers(response, rate_limit_info)
            
            return response
        
        return wrapped_view
    
    return decorator

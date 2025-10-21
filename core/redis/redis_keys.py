"""
Redis cache key management.

This module provides a standardized approach to cache key generation and TTL management,
ensuring consistency across the application.
"""

import hashlib
import inspect
import json
import logging
from typing import Any, List, Optional, Type, Union

from django.db import models
from django.http import HttpRequest

from core.redis_settings import CacheNamespace, CacheTTL, get_ttl_for_namespace
from core.redis_settings import CACHE_VERSION

logger = logging.getLogger(__name__)


def generate_key(
    namespace: Union[str, CacheNamespace],
    identifier: Any,
    *parts: Any,
    version: Optional[str] = None,
    include_hash: bool = True
) -> str:
    """
    Generate a standardized cache key.

    Args:
        namespace: Cache namespace
        identifier: Primary identifier
        *parts: Additional parts to include in the key
        version: Optional version override
        include_hash: Whether to include a hash for long keys

    Returns:
        Cache key
    """
    # Convert namespace to string if it's an enum
    if isinstance(namespace, CacheNamespace):
        namespace = str(namespace)
    elif not namespace.endswith(':'):
        namespace = f"{namespace}:"

    # Convert identifier to string
    identifier = str(identifier)

    # Build key parts
    key_parts = [identifier]

    # Add additional parts
    for part in parts:
        if part is not None:
            if isinstance(part, dict):
                # Sort dict items for consistent ordering
                part_str = json.dumps(part, sort_keys=True)
                # Use hash for dicts to keep key length manageable
                part_str = hashlib.md5(part_str.encode()).hexdigest()[:8]
                key_parts.append(part_str)
            else:
                key_parts.append(str(part))

    # Join parts with colons
    key = ":".join(key_parts)

    # Add version
    version = version or CACHE_VERSION
    versioned_key = f"{namespace}{key}:v{version}"

    # For long keys, use a hash to keep the key length manageable
    if include_hash and len(versioned_key) > 100:
        hashed_key = hashlib.md5(key.encode()).hexdigest()
        return f"{namespace}h:{hashed_key}:v{version}"

    return versioned_key


def model_cache_key(
    instance_or_class: Union[models.Model, Type[models.Model]],
    instance_id: Optional[Any] = None,
    *parts: Any,
    version: Optional[str] = None
) -> str:
    """
    Generate a cache key for a model instance.

    Args:
        instance_or_class: Model instance or class
        instance_id: Instance ID (required if instance_or_class is a class)
        *parts: Additional parts to include in the key
        version: Optional version override

    Returns:
        Cache key
    """
    # Determine model class and ID
    if isinstance(instance_or_class, models.Model):
        model_class = instance_or_class.__class__
        model_id = instance_or_class.pk
    else:
        model_class = instance_or_class
        model_id = instance_id

    if model_id is None:
        raise ValueError("Instance ID is required")

    # Determine namespace
    model_name = model_class.__name__.lower()
    namespace = None

    # Try to map model name to a namespace
    for ns in CacheNamespace:
        if ns.value == model_name:
            namespace = ns
            break

    # Default to MODEL namespace with model name
    if namespace is None:
        namespace = f"{CacheNamespace.MODEL}{model_name}"

    return generate_key(namespace, model_id, *parts, version=version)


def api_cache_key(
    view_func,
    request: HttpRequest,
    *args: Any,
    vary_on_headers: Optional[List[str]] = None,
    vary_on_cookies: Optional[List[str]] = None,
    vary_on_query_params: Optional[List[str]] = None,
    version: Optional[str] = None
) -> str:
    """
    Generate a cache key for an API response.

    Args:
        view_func: View function
        request: HTTP request
        *args: View function args
        vary_on_headers: Headers to include in the key
        vary_on_cookies: Cookies to include in the key
        vary_on_query_params: Query params to include in the key
        version: Optional version override

    Returns:
        Cache key
    """
    # Get view name and module
    view_name = view_func.__name__
    module_name = view_func.__module__

    # Build key parts
    key_parts = [module_name, view_name]

    # Add args
    if args:
        args_str = ":".join(str(arg) for arg in args)
        key_parts.append(args_str)

    # Add headers
    if vary_on_headers:
        headers = {}
        for header in vary_on_headers:
            header_value = request.headers.get(header)
            if header_value:
                headers[header] = header_value

        if headers:
            headers_str = json.dumps(headers, sort_keys=True)
            key_parts.append(f"h:{hashlib.md5(headers_str.encode()).hexdigest()[:8]}")

    # Add cookies
    if vary_on_cookies:
        cookies = {}
        for cookie in vary_on_cookies:
            cookie_value = request.COOKIES.get(cookie)
            if cookie_value:
                cookies[cookie] = cookie_value

        if cookies:
            cookies_str = json.dumps(cookies, sort_keys=True)
            key_parts.append(f"c:{hashlib.md5(cookies_str.encode()).hexdigest()[:8]}")

    # Add query params
    if vary_on_query_params:
        query_params = {}
        for param in vary_on_query_params:
            param_value = request.GET.get(param)
            if param_value:
                query_params[param] = param_value

        if query_params:
            params_str = json.dumps(query_params, sort_keys=True)
            key_parts.append(f"q:{hashlib.md5(params_str.encode()).hexdigest()[:8]}")
    elif request.GET:
        # If no specific query params are specified but there are query params,
        # include all of them in the cache key
        params_str = json.dumps(dict(request.GET.items()), sort_keys=True)
        key_parts.append(f"q:{hashlib.md5(params_str.encode()).hexdigest()[:8]}")

    # Add user ID if authenticated
    if request.user.is_authenticated:
        key_parts.append(f"u:{request.user.id}")

    # Join parts with colons
    identifier = ":".join(key_parts)

    return generate_key(CacheNamespace.API, identifier, version=version)


def function_cache_key(
    func,
    *args: Any,
    namespace: Optional[Union[str, CacheNamespace]] = None,
    version: Optional[str] = None,
    **kwargs: Any
) -> str:
    """
    Generate a cache key for a function result.

    Args:
        func: Function
        *args: Function args
        namespace: Optional namespace override
        version: Optional version override
        **kwargs: Function kwargs

    Returns:
        Cache key
    """
    # Get function name and module
    func_name = func.__name__
    module_name = func.__module__

    # Build identifier
    identifier = f"{module_name}.{func_name}"

    # Process args
    args_part = None
    if args:
        # Skip self/cls for methods
        if inspect.ismethod(func) and args:
            args_to_use = args[1:]
        else:
            args_to_use = args

        if args_to_use:
            args_str = ":".join(str(arg) for arg in args_to_use)
            args_part = hashlib.md5(args_str.encode()).hexdigest()[:8]

    # Process kwargs
    kwargs_part = None
    if kwargs:
        # Sort kwargs for consistent ordering
        kwargs_str = json.dumps(kwargs, sort_keys=True)
        kwargs_part = hashlib.md5(kwargs_str.encode()).hexdigest()[:8]

    # Determine namespace
    if namespace is None:
        namespace = CacheNamespace.DEFAULT

    return generate_key(namespace, identifier, args_part, kwargs_part, version=version)


def get_ttl_for_key(key: str) -> int:
    """
    Get the appropriate TTL for a cache key based on its namespace.

    Args:
        key: Cache key

    Returns:
        TTL in seconds
    """
    # Extract namespace from key
    parts = key.split(":", 1)
    if len(parts) < 2:
        return CacheTTL.DEFAULT

    namespace = parts[0]

    # Handle hashed keys
    if namespace.endswith("h"):
        namespace = namespace[:-1]

    # Get TTL for namespace
    return get_ttl_for_namespace(namespace)

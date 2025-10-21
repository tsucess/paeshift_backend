"""
Core Redis caching module for the entire application.

This module provides a comprehensive Redis caching system that can be used
across all applications to cache API responses, database queries, and other
expensive operations.

Features:
- Consistent caching interface across all applications
- Automatic serialization/deserialization of complex objects
- Configurable cache timeouts per data type
- Cache versioning to handle schema changes
- Cache invalidation helpers
- Monitoring and statistics
"""

import hashlib
import inspect
import json
import logging
import time
import traceback
from datetime import datetime, timedelta
from decimal import Decimal
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import redis
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Model, QuerySet
from django.http import HttpRequest, JsonResponse

from core.redis_settings import (
    CACHE_DEFAULT_TIMEOUT,
    CACHE_ENABLED,
    CACHE_STATS_INTERVAL,
    CACHE_TIMEOUTS,
    CACHE_VERSION,
    REDIS_DB_CACHE,
    get_redis_connection_params,
)

# Set up logging
logger = logging.getLogger(__name__)

# Define operation types for consistent logging
class CacheOp:
    GET = "get"
    SET = "set"
    DELETE = "delete"
    INVALIDATE = "invalidate"
    VALIDATE = "validate"
    STATS = "stats"
    LOCK = "lock"
    UNLOCK = "unlock"
    PUBLISH = "publish"
    SUBSCRIBE = "subscribe"

# Cache prefixes by data type
CACHE_PREFIXES = {
    "user": "user:",
    "job": "job:",
    "application": "app:",
    "profile": "profile:",
    "industry": "industry:",
    "subcategory": "subcat:",
    "whoami": "whoami:",
    "api": "api:",
    "query": "query:",
    "default": "cache:",
    # New prefixes for advanced features
    "ranking": "rank:",
    "activity": "activity:",
    "presence": "presence:",
    "notification": "notif:",
    "leaderboard": "leaderboard:",
    "lock": "lock:",
    "rate_limit": "ratelimit:",
}

# Monitoring settings
_cache_operations_counter = 0
_cache_hits = 0
_cache_misses = 0
_last_stats_time = time.time()

# Initialize Redis connection
try:
    # Get connection parameters from redis_settings
    connection_params = get_redis_connection_params(REDIS_DB_CACHE)
    redis_client = redis.Redis(**connection_params)

    # Test connection
    redis_client.ping()
    logger.info(f"Successfully connected to Redis cache at {connection_params['host']}:{connection_params['port']}")
except redis.ConnectionError as e:
    logger.warning(f"Could not connect to Redis: {str(e)}")
    logger.warning("Redis caching will be disabled. The application will continue to function but with reduced performance.")
    redis_client = None
    CACHE_ENABLED = False
except Exception as e:
    logger.error(f"Unexpected error connecting to Redis: {str(e)}")
    logger.warning("Redis caching will be disabled. The application will continue to function but with reduced performance.")
    redis_client = None
    CACHE_ENABLED = False

# Create a dummy Redis client for development if Redis is not available
if redis_client is None and settings.DEBUG:
    from fakeredis import FakeStrictRedis
    try:
        # Try to import fakeredis for development
        redis_client = FakeStrictRedis(decode_responses=True)
        logger.info("Using FakeRedis for development (Redis not available)")
        CACHE_ENABLED = True
    except ImportError:
        logger.warning("FakeRedis not installed. Install with: pip install fakeredis")
        # Continue without Redis


class CustomJSONEncoder(DjangoJSONEncoder):
    """
    Custom JSON encoder that handles Django models, QuerySets, Decimal objects,
    and file fields (ImageField, FileField).
    """

    def default(self, obj):
        # Handle Django models
        if isinstance(obj, Model):
            model_data = {
                "_model_type": obj.__class__.__name__,
                "_model_pk": obj.pk,
                "_model_app": obj._meta.app_label,
                "_model_repr": str(obj),
            }

            # Add non-relation fields with special handling for file fields
            for field in obj._meta.fields:
                if not field.is_relation:
                    value = getattr(obj, field.name)
                    # Skip file fields here as they'll be handled separately
                    if not hasattr(value, 'url'):
                        model_data[field.name] = value

            return model_data

        # Handle Django QuerySets
        elif isinstance(obj, QuerySet):
            return {
                "_queryset_type": obj.model.__name__,
                "_queryset_count": obj.count(),
                "_queryset_items": list(obj),
            }
        # Handle Decimal objects
        elif isinstance(obj, Decimal):
            return str(obj)
        # Handle datetime objects
        elif isinstance(obj, datetime):
            return obj.isoformat()
        # Handle sets
        elif isinstance(obj, set):
            return list(obj)
        # Handle ImageField, FileField and other file-like objects
        elif hasattr(obj, 'url'):
            try:
                return obj.url if obj else None
            except ValueError:
                # Handle case where file field has no file associated with it
                return None
        # Handle FieldFile objects
        elif hasattr(obj, 'name') and hasattr(obj, 'path') and hasattr(obj, 'file'):
            return obj.name if obj else None

        return super().default(obj)


def generate_cache_key(
    prefix: str, identifier: Any, namespace: Optional[str] = None
) -> str:
    """
    Generate a cache key for an object.

    Args:
        prefix: The cache prefix for this type of data
        identifier: The unique identifier for this object
        namespace: Optional namespace for grouping related keys

    Returns:
        A cache key string
    """
    # Convert identifier to string if it's not already
    if not isinstance(identifier, str):
        identifier = str(identifier)

    # Add namespace if provided
    if namespace:
        prefix = f"{prefix}{namespace}:"

    # Add version to ensure cache invalidation when schema changes
    versioned_key = f"{prefix}{identifier}:v{CACHE_VERSION}"

    # For long keys, use a hash to keep the key length manageable
    if len(versioned_key) > 100:
        hashed_key = hashlib.md5(identifier.encode()).hexdigest()
        return f"{prefix}h:{hashed_key}:v{CACHE_VERSION}"

    return versioned_key


def log_cache_stats() -> None:
    """
    Log cache statistics periodically.
    """
    global _cache_operations_counter, _cache_hits, _cache_misses, _last_stats_time

    _cache_operations_counter += 1

    # Log stats periodically
    if _cache_operations_counter % CACHE_STATS_INTERVAL == 0:
        current_time = time.time()
        elapsed = current_time - _last_stats_time

        total_ops = _cache_hits + _cache_misses
        hit_rate = (_cache_hits / total_ops * 100) if total_ops > 0 else 0

        logger.info(
            f"Cache stats: {_cache_hits} hits, {_cache_misses} misses, {hit_rate:.1f}% hit rate, {total_ops/elapsed:.1f} ops/sec"
        )

        # Reset counters
        _last_stats_time = current_time
        _cache_hits = 0
        _cache_misses = 0


def get_cached_data(key: str, bypass_cache: bool = False) -> Optional[Any]:
    """
    Get data from the Redis cache.

    Args:
        key: The cache key
        bypass_cache: If True, bypass the cache and return None

    Returns:
        The cached data or None if not found
    """
    global _cache_hits, _cache_misses
    start_time = time.time()
    operation_id = hashlib.md5(f"{key}:{time.time()}".encode()).hexdigest()[:8]

    if not CACHE_ENABLED or not redis_client or bypass_cache:
        logger.debug(f"Cache disabled, Redis client not available, or bypass requested [op_id={operation_id}]")
        return None

    try:
        # Get data from Redis
        cached_data = redis_client.get(key)

        if cached_data:
            # Parse the JSON data
            result = json.loads(cached_data)

            # Update hit counter
            _cache_hits += 1

            # Log cache stats periodically
            log_cache_stats()

            duration_ms = round((time.time() - start_time) * 1000, 2)
            logger.debug(
                f"Cache HIT: key={key} op_id={operation_id} duration_ms={duration_ms}"
            )
            return result

        # Update miss counter
        _cache_misses += 1

        # Log cache stats periodically
        log_cache_stats()

        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.debug(
            f"Cache MISS: key={key} op_id={operation_id} duration_ms={duration_ms}"
        )
        return None
    except json.JSONDecodeError as e:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.error(
            f"JSON decode error for key={key}: {str(e)} [op_id={operation_id}, duration_ms={duration_ms}]"
        )
        # Delete corrupted data
        try:
            redis_client.delete(key)
            logger.info(f"Deleted corrupted cache entry for key={key} [op_id={operation_id}]")
        except Exception as del_err:
            logger.error(f"Failed to delete corrupted cache entry: {str(del_err)} [op_id={operation_id}]")
        return None
    except redis.RedisError as e:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.error(
            f"Redis error for key={key}: {str(e)} [op_id={operation_id}, duration_ms={duration_ms}]"
        )
        return None
    except Exception as e:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.error(
            f"Unexpected error retrieving data from cache for key={key}: {str(e)} "
            f"[op_id={operation_id}, duration_ms={duration_ms}]\n{traceback.format_exc()}"
        )
        return None


def set_cached_data(key: str, data: Any, timeout: Optional[int] = None) -> bool:
    """
    Store data in the Redis cache.

    Args:
        key: The cache key
        data: The data to cache
        timeout: Optional timeout in seconds

    Returns:
        True if successful, False otherwise
    """
    start_time = time.time()
    operation_id = hashlib.md5(f"{key}:{time.time()}".encode()).hexdigest()[:8]

    if not CACHE_ENABLED or not redis_client:
        logger.debug(f"Cache disabled or Redis client not available [op_id={operation_id}]")
        return False

    if timeout is None:
        timeout = CACHE_DEFAULT_TIMEOUT

    try:
        # Serialize the data to JSON
        serialized_data = json.dumps(data, cls=CustomJSONEncoder)
        data_size_bytes = len(serialized_data.encode('utf-8'))

        # Store in Redis with expiration
        redis_client.setex(key, timeout, serialized_data)

        # Log cache stats periodically
        log_cache_stats()

        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.debug(
            f"Cache SET: key={key} size={data_size_bytes}B timeout={timeout}s "
            f"[op_id={operation_id}, duration_ms={duration_ms}]"
        )

        # Log warning for large objects
        if data_size_bytes > 1024 * 100:  # 100KB
            logger.warning(
                f"Large object cached: key={key} size={round(data_size_bytes/1024, 2)}KB "
                f"[op_id={operation_id}]"
            )

        return True
    except TypeError as e:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.error(
            f"JSON serialization error for key={key}: {str(e)} "
            f"[op_id={operation_id}, duration_ms={duration_ms}]"
        )
        return False
    except redis.RedisError as e:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.error(
            f"Redis error for key={key}: {str(e)} "
            f"[op_id={operation_id}, duration_ms={duration_ms}]"
        )
        return False
    except Exception as e:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.error(
            f"Unexpected error caching data for key={key}: {str(e)} "
            f"[op_id={operation_id}, duration_ms={duration_ms}]\n{traceback.format_exc()}"
        )
        return False


def delete_cached_data(key: str) -> bool:
    """
    Delete data from the Redis cache.

    Args:
        key: The cache key

    Returns:
        True if successful, False otherwise
    """
    start_time = time.time()
    operation_id = hashlib.md5(f"{key}:{time.time()}".encode()).hexdigest()[:8]

    if not CACHE_ENABLED or not redis_client:
        logger.debug(f"Cache disabled or Redis client not available [op_id={operation_id}]")
        return False

    try:
        # Check if key exists first
        exists = redis_client.exists(key)

        # Delete from Redis
        result = redis_client.delete(key)

        duration_ms = round((time.time() - start_time) * 1000, 2)
        if exists:
            logger.debug(
                f"Cache DELETE: key={key} [op_id={operation_id}, duration_ms={duration_ms}]"
            )
        else:
            logger.debug(
                f"Cache DELETE (key not found): key={key} [op_id={operation_id}, duration_ms={duration_ms}]"
            )

        return True
    except redis.RedisError as e:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.error(
            f"Redis error deleting key={key}: {str(e)} "
            f"[op_id={operation_id}, duration_ms={duration_ms}]"
        )
        return False
    except Exception as e:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.error(
            f"Unexpected error deleting data from cache for key={key}: {str(e)} "
            f"[op_id={operation_id}, duration_ms={duration_ms}]\n{traceback.format_exc()}"
        )
        return False


def invalidate_cache_pattern(pattern: str) -> int:
    """
    Invalidate all cache keys matching a pattern.

    Args:
        pattern: The pattern to match (e.g., "user:*")

    Returns:
        Number of keys invalidated
    """
    start_time = time.time()
    operation_id = hashlib.md5(f"{pattern}:{time.time()}".encode()).hexdigest()[:8]

    if not CACHE_ENABLED or not redis_client:
        logger.debug(f"Cache disabled or Redis client not available [op_id={operation_id}]")
        return 0

    try:
        # Find all keys matching the pattern
        keys = redis_client.keys(pattern)

        if not keys:
            duration_ms = round((time.time() - start_time) * 1000, 2)
            logger.debug(
                f"No keys found matching pattern: {pattern} "
                f"[op_id={operation_id}, duration_ms={duration_ms}]"
            )
            return 0

        # For large key sets, delete in batches to avoid blocking Redis
        batch_size = 1000
        total_deleted = 0

        for i in range(0, len(keys), batch_size):
            batch = keys[i:i+batch_size]
            deleted = redis_client.delete(*batch)
            total_deleted += deleted

            # Log progress for large deletions
            if len(keys) > batch_size and i + batch_size < len(keys):
                logger.debug(
                    f"Deleted batch {i//batch_size + 1}/{(len(keys) + batch_size - 1)//batch_size}: "
                    f"{deleted} keys [op_id={operation_id}]"
                )

        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.info(
            f"Invalidated {total_deleted} cache keys matching pattern: {pattern} "
            f"[op_id={operation_id}, duration_ms={duration_ms}]"
        )
        return total_deleted
    except redis.RedisError as e:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.error(
            f"Redis error invalidating pattern {pattern}: {str(e)} "
            f"[op_id={operation_id}, duration_ms={duration_ms}]"
        )
        return 0
    except Exception as e:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.error(
            f"Unexpected error invalidating cache for pattern {pattern}: {str(e)} "
            f"[op_id={operation_id}, duration_ms={duration_ms}]\n{traceback.format_exc()}"
        )
        return 0


def cache_function_result(
    timeout: Optional[int] = None,
    key_prefix: Optional[str] = None,
    namespace: Optional[str] = None,
    include_args: bool = True,
    include_kwargs: bool = True,
    cache_none: bool = False,
) -> Callable:
    """
    Decorator to cache function results in Redis.

    Args:
        timeout: Cache timeout in seconds
        key_prefix: Optional prefix for the cache key
        namespace: Optional namespace for grouping related keys
        include_args: Whether to include positional args in the cache key
        include_kwargs: Whether to include keyword args in the cache key
        cache_none: Whether to cache None results

    Returns:
        Decorated function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not CACHE_ENABLED or not redis_client:
                return func(*args, **kwargs)

            # Generate a cache key based on the function name and arguments
            func_name = func.__name__
            module_name = func.__module__

            # Use provided prefix or get from CACHE_PREFIXES
            prefix = key_prefix or CACHE_PREFIXES.get("default")

            # Build key components
            key_parts = [module_name, func_name]

            # Add args to key if requested
            if include_args and args:
                # Skip self/cls for methods
                if inspect.ismethod(func) and args:
                    args_str = str(args[1:])
                else:
                    args_str = str(args)
                key_parts.append(hashlib.md5(args_str.encode()).hexdigest())

            # Add kwargs to key if requested
            if include_kwargs and kwargs:
                # Sort kwargs for consistent ordering
                kwargs_str = str(sorted(kwargs.items()))
                key_parts.append(hashlib.md5(kwargs_str.encode()).hexdigest())

            # Join all parts to create the identifier
            identifier = ":".join(key_parts)

            # Generate the final cache key
            cache_key = generate_cache_key(prefix, identifier, namespace)

            # Try to get from cache first
            cached_result = get_cached_data(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for function {func_name}")
                return cached_result

            # Cache miss, call the function
            logger.debug(f"Cache miss for function {func_name}")
            result = func(*args, **kwargs)

            # Don't cache None results unless explicitly requested
            if result is not None or cache_none:
                # Use provided timeout or get from CACHE_TIMEOUTS
                cache_timeout = timeout or CACHE_TIMEOUTS.get("default")
                set_cached_data(cache_key, result, cache_timeout)

            return result

        return wrapper

    return decorator


def cache_api_response(
    timeout: Optional[int] = None,
    key_prefix: Optional[str] = None,
    namespace: Optional[str] = None,
    vary_on_headers: Optional[List[str]] = None,
    vary_on_cookies: Optional[List[str]] = None,
    vary_on_query_params: Optional[List[str]] = None,
) -> Callable:
    """
    Decorator to cache API responses in Redis.

    Args:
        timeout: Cache timeout in seconds
        key_prefix: Optional prefix for the cache key
        namespace: Optional namespace for grouping related keys
        vary_on_headers: List of HTTP headers to include in the cache key
        vary_on_cookies: List of cookies to include in the cache key
        vary_on_query_params: List of query parameters to include in the cache key

    Returns:
        Decorated function
    """

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            if not CACHE_ENABLED or not redis_client:
                return view_func(request, *args, **kwargs)

            # Only cache GET requests
            if request.method != "GET":
                return view_func(request, *args, **kwargs)

            # Generate a cache key based on the view function and request
            view_name = view_func.__name__
            module_name = view_func.__module__

            # Use provided prefix or get from CACHE_PREFIXES
            prefix = key_prefix or CACHE_PREFIXES.get("api")

            # Build key components
            key_parts = [module_name, view_name]

            # Add args to key
            if args:
                args_str = str(args)
                key_parts.append(hashlib.md5(args_str.encode()).hexdigest())

            # Add kwargs to key
            if kwargs:
                # Sort kwargs for consistent ordering
                kwargs_str = str(sorted(kwargs.items()))
                key_parts.append(hashlib.md5(kwargs_str.encode()).hexdigest())

            # Add specified headers to key
            if vary_on_headers:
                headers = {}
                for header in vary_on_headers:
                    header_value = request.headers.get(header)
                    if header_value:
                        headers[header] = header_value

                if headers:
                    headers_str = str(sorted(headers.items()))
                    key_parts.append(
                        f"h:{hashlib.md5(headers_str.encode()).hexdigest()}"
                    )

            # Add specified cookies to key
            if vary_on_cookies:
                cookies = {}
                for cookie in vary_on_cookies:
                    cookie_value = request.COOKIES.get(cookie)
                    if cookie_value:
                        cookies[cookie] = cookie_value

                if cookies:
                    cookies_str = str(sorted(cookies.items()))
                    key_parts.append(
                        f"c:{hashlib.md5(cookies_str.encode()).hexdigest()}"
                    )

            # Add specified query parameters to key
            if vary_on_query_params:
                query_params = {}
                for param in vary_on_query_params:
                    param_value = request.GET.get(param)
                    if param_value:
                        query_params[param] = param_value

                if query_params:
                    params_str = str(sorted(query_params.items()))
                    key_parts.append(
                        f"q:{hashlib.md5(params_str.encode()).hexdigest()}"
                    )
            elif request.GET:
                # If no specific query params are specified but there are query params,
                # include all of them in the cache key
                params_str = str(sorted(request.GET.items()))
                key_parts.append(f"q:{hashlib.md5(params_str.encode()).hexdigest()}")

            # Add user ID to key if authenticated
            if request.user.is_authenticated:
                key_parts.append(f"u:{request.user.id}")

            # Join all parts to create the identifier
            identifier = ":".join(key_parts)

            # Generate the final cache key
            cache_key = generate_cache_key(prefix, identifier, namespace)

            # Try to get from cache first
            cached_response = get_cached_data(cache_key)
            if cached_response is not None:
                logger.debug(f"Cache hit for API view {view_name}")
                return JsonResponse(cached_response)

            # Cache miss, call the view function
            logger.debug(f"Cache miss for API view {view_name}")
            response = view_func(request, *args, **kwargs)

            # Only cache JsonResponse objects
            if isinstance(response, JsonResponse):
                # Use provided timeout or get from CACHE_TIMEOUTS
                cache_timeout = timeout or CACHE_TIMEOUTS.get("default")

                # Extract the response data
                response_data = json.loads(response.content.decode("utf-8"))

                # Cache the response data
                set_cached_data(cache_key, response_data, cache_timeout)

            return response

        return wrapper

    return decorator


def cache_model_instance(
    model_type: str,
    instance_id: Any,
    data: Dict[str, Any],
    timeout: Optional[int] = None,
) -> bool:
    """
    Cache a model instance.

    Args:
        model_type: The type of model (e.g., "user", "job")
        instance_id: The ID of the instance
        data: The data to cache
        timeout: Optional timeout in seconds

    Returns:
        True if successful, False otherwise
    """
    # Get the prefix for this model type
    prefix = CACHE_PREFIXES.get(model_type, CACHE_PREFIXES["default"])

    # Generate the cache key
    cache_key = generate_cache_key(prefix, instance_id)

    # Get the timeout for this model type
    cache_timeout = timeout or CACHE_TIMEOUTS.get(model_type, CACHE_TIMEOUTS["default"])

    # Cache the data
    return set_cached_data(cache_key, data, cache_timeout)


def get_cached_model_instance(
    model_type: str, instance_id: Any
) -> Optional[Dict[str, Any]]:
    """
    Get a cached model instance.

    Args:
        model_type: The type of model (e.g., "user", "job")
        instance_id: The ID of the instance

    Returns:
        The cached instance data or None if not found
    """
    # Get the prefix for this model type
    prefix = CACHE_PREFIXES.get(model_type, CACHE_PREFIXES["default"])

    # Generate the cache key
    cache_key = generate_cache_key(prefix, instance_id)

    # Get the data from cache
    return get_cached_data(cache_key)


def invalidate_model_instance(model_type: str, instance_id: Any) -> bool:
    """
    Invalidate a cached model instance.

    Args:
        model_type: The type of model (e.g., "user", "job")
        instance_id: The ID of the instance

    Returns:
        True if successful, False otherwise
    """
    # Get the prefix for this model type
    prefix = CACHE_PREFIXES.get(model_type, CACHE_PREFIXES["default"])

    # Generate the cache key
    cache_key = generate_cache_key(prefix, instance_id)

    # Delete the data from cache
    return delete_cached_data(cache_key)


def invalidate_model_instances(model_type: str) -> int:
    """
    Invalidate all cached instances of a model type.

    Args:
        model_type: The type of model (e.g., "user", "job")

    Returns:
        Number of instances invalidated
    """
    # Get the prefix for this model type
    prefix = CACHE_PREFIXES.get(model_type, CACHE_PREFIXES["default"])

    # Generate the pattern
    pattern = f"{prefix}*"

    # Invalidate all matching keys
    return invalidate_cache_pattern(pattern)


def cache_whoami(
    user_id: int, data: Dict[str, Any], timeout: Optional[int] = None
) -> bool:
    """
    Cache a user's whoami data.

    Args:
        user_id: The ID of the user
        data: The whoami data to cache
        timeout: Optional timeout in seconds

    Returns:
        True if successful, False otherwise
    """
    return cache_model_instance("whoami", user_id, data, timeout)


def get_cached_whoami(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a user's cached whoami data.

    Args:
        user_id: The ID of the user

    Returns:
        The cached whoami data or None if not found
    """
    return get_cached_model_instance("whoami", user_id)


def invalidate_whoami(user_id: int) -> bool:
    """
    Invalidate a user's cached whoami data.

    Args:
        user_id: The ID of the user

    Returns:
        True if successful, False otherwise
    """
    return invalidate_model_instance("whoami", user_id)


def get_cache_stats() -> Dict[str, Any]:
    """
    Get statistics about the Redis cache.

    Returns:
        Dictionary with cache statistics
    """
    if not CACHE_ENABLED or not redis_client:
        return {"error": "Redis client not available"}

    try:
        # Get Redis info
        info = redis_client.info()

        # Get memory usage
        memory_used = info.get("used_memory", 0)
        memory_peak = info.get("used_memory_peak", 0)

        # Get key counts by prefix
        key_counts = {}
        for prefix_name, prefix in CACHE_PREFIXES.items():
            pattern = f"{prefix}*"
            count = len(redis_client.keys(pattern))
            key_counts[prefix_name] = count

        # Calculate total keys
        total_keys = sum(key_counts.values())

        # Calculate hit rate
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        total_ops = hits + misses
        hit_rate = (hits / total_ops * 100) if total_ops > 0 else 0

        return {
            "total_keys": total_keys,
            "key_counts_by_type": key_counts,
            "memory_used_bytes": memory_used,
            "memory_used_mb": round(memory_used / (1024 * 1024), 2),
            "memory_peak_bytes": memory_peak,
            "memory_peak_mb": round(memory_peak / (1024 * 1024), 2),
            "hit_rate": round(hit_rate, 2),
            "hits": hits,
            "misses": misses,
            "uptime_seconds": info.get("uptime_in_seconds", 0),
            "connected_clients": info.get("connected_clients", 0),
            "version": info.get("redis_version", "unknown"),
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {str(e)}")
        return {"error": str(e)}

"""
Redis client module.

This module provides a Redis client for the application, with support for
connection pooling, high availability, and error handling.
"""

import functools
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union

import redis
from redis.sentinel import Sentinel
from redis.cluster import RedisCluster

from core.redis.settings import (
    REDIS_DB_CACHE,
    get_redis_connection_params,
)

# Set up logging
logger = logging.getLogger(__name__)

# Constants for high availability
REDIS_SENTINEL_ENABLED = False  # Set to True to enable Sentinel
REDIS_SENTINEL_MASTER = "mymaster"
REDIS_SENTINEL_HOSTS = []  # List of (host, port) tuples
REDIS_SENTINEL_PASSWORD = None

REDIS_CLUSTER_ENABLED = False  # Set to True to enable Cluster
REDIS_CLUSTER_NODES = []  # List of (host, port) tuples
REDIS_CLUSTER_PASSWORD = None

REDIS_CONNECTION_POOL_ENABLED = True
REDIS_CONNECTION_POOL_MAX_CONNECTIONS = 100

REDIS_RETRY_ON_TIMEOUT = True
REDIS_RETRY_ON_ERROR = True
REDIS_MAX_RETRIES = 3
REDIS_RETRY_DELAY = 0.1  # 100ms

# Connection pools
_sentinel_pool = None
_cluster_pool = None
_standalone_pool = None


def get_redis_sentinel_client() -> redis.Redis:
    """
    Get a Redis client connected to a Sentinel-managed Redis instance.
    
    Returns:
        Redis client
    """
    global _sentinel_pool
    
    if not REDIS_SENTINEL_ENABLED or not REDIS_SENTINEL_HOSTS:
        logger.warning("Redis Sentinel is not enabled or no hosts configured")
        return get_redis_standalone_client()
    
    try:
        # Create Sentinel connection
        sentinel = Sentinel(
            REDIS_SENTINEL_HOSTS,
            socket_timeout=1.0,
            password=REDIS_SENTINEL_PASSWORD,
            db=REDIS_DB_CACHE,
        )
        
        # Create connection pool if not already created
        if _sentinel_pool is None:
            # Get master info
            master_host, master_port = sentinel.discover_master(REDIS_SENTINEL_MASTER)
            
            # Create connection pool
            _sentinel_pool = redis.ConnectionPool(
                host=master_host,
                port=master_port,
                db=REDIS_DB_CACHE,
                password=REDIS_SENTINEL_PASSWORD,
                max_connections=REDIS_CONNECTION_POOL_MAX_CONNECTIONS,
                retry_on_timeout=REDIS_RETRY_ON_TIMEOUT,
            )
            
            logger.info(
                f"Connected to Redis Sentinel master {REDIS_SENTINEL_MASTER} "
                f"at {master_host}:{master_port}"
            )
        
        # Create Redis client using the connection pool
        return redis.Redis(connection_pool=_sentinel_pool)
    except Exception as e:
        logger.error(f"Error connecting to Redis Sentinel: {str(e)}")
        return get_redis_standalone_client()


def get_redis_cluster_client() -> redis.RedisCluster:
    """
    Get a Redis client connected to a Redis Cluster.
    
    Returns:
        Redis client
    """
    global _cluster_pool
    
    if not REDIS_CLUSTER_ENABLED or not REDIS_CLUSTER_NODES:
        logger.warning("Redis Cluster is not enabled or no nodes configured")
        return get_redis_standalone_client()
    
    try:
        # Create connection pool if not already created
        if _cluster_pool is None:
            # Create cluster client
            _cluster_pool = RedisCluster(
                startup_nodes=REDIS_CLUSTER_NODES,
                password=REDIS_CLUSTER_PASSWORD,
                decode_responses=True,
                skip_full_coverage_check=True,
                retry_on_timeout=REDIS_RETRY_ON_TIMEOUT,
            )
            
            logger.info(f"Connected to Redis Cluster with {len(REDIS_CLUSTER_NODES)} nodes")
        
        return _cluster_pool
    except Exception as e:
        logger.error(f"Error connecting to Redis Cluster: {str(e)}")
        return get_redis_standalone_client()


def get_redis_standalone_client() -> redis.Redis:
    """
    Get a Redis client connected to a standalone Redis instance.
    
    Returns:
        Redis client
    """
    global _standalone_pool
    
    try:
        # Get connection parameters from settings
        params = get_redis_connection_params()
        
        # Create connection pool if not already created
        if _standalone_pool is None and REDIS_CONNECTION_POOL_ENABLED:
            _standalone_pool = redis.ConnectionPool(
                host=params.get("host", "localhost"),
                port=params.get("port", 6379),
                db=params.get("db", 0),
                password=params.get("password", None),
                max_connections=REDIS_CONNECTION_POOL_MAX_CONNECTIONS,
                retry_on_timeout=REDIS_RETRY_ON_TIMEOUT,
            )
            
            logger.info(
                f"Created Redis connection pool for {params.get('host', 'localhost')}:"
                f"{params.get('port', 6379)}"
            )
        
        # Create Redis client
        if _standalone_pool is not None:
            return redis.Redis(connection_pool=_standalone_pool)
        else:
            return redis.Redis(
                host=params.get("host", "localhost"),
                port=params.get("port", 6379),
                db=params.get("db", 0),
                password=params.get("password", None),
                retry_on_timeout=REDIS_RETRY_ON_TIMEOUT,
            )
    except Exception as e:
        logger.error(f"Error creating Redis standalone client: {str(e)}")
        return None


def get_redis_client() -> Union[redis.Redis, redis.RedisCluster, None]:
    """
    Get the appropriate Redis client based on configuration.
    
    Returns:
        Redis client
    """
    # Try Sentinel first if enabled
    if REDIS_SENTINEL_ENABLED:
        return get_redis_sentinel_client()
    
    # Try Cluster next if enabled
    if REDIS_CLUSTER_ENABLED:
        return get_redis_cluster_client()
    
    # Fall back to standalone
    return get_redis_standalone_client()


def with_redis_retry(max_retries: int = REDIS_MAX_RETRIES, retry_delay: float = REDIS_RETRY_DELAY):
    """
    Decorator for retrying Redis operations on failure.
    
    Args:
        max_retries: Maximum number of retries
        retry_delay: Delay between retries in seconds
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (redis.ConnectionError, redis.TimeoutError) as e:
                    last_error = e
                    
                    if attempt < max_retries:
                        logger.warning(
                            f"Redis operation failed (attempt {attempt + 1}/{max_retries + 1}): {str(e)}"
                        )
                        time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                    else:
                        logger.error(
                            f"Redis operation failed after {max_retries + 1} attempts: {str(e)}"
                        )
            
            # If we get here, all retries failed
            raise last_error
        
        return wrapper
    
    return decorator


# Initialize Redis client
redis_client = get_redis_client()

# Test connection
if redis_client:
    try:
        redis_client.ping()
        logger.info("Successfully connected to Redis")
    except Exception as e:
        logger.error(f"Error connecting to Redis: {str(e)}")
        redis_client = None
else:
    logger.error("Failed to initialize Redis client")

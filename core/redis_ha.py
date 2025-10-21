"""
Redis High Availability (HA) configuration.

This module provides utilities for configuring Redis in a high-availability setup,
including Sentinel support, connection pooling, and failover handling.
"""

import logging
import random
import time
from typing import Dict, List, Optional, Tuple, Union

import redis
from django.conf import settings
from redis.sentinel import Sentinel

logger = logging.getLogger(__name__)

# Constants
REDIS_SENTINEL_ENABLED = getattr(settings, "REDIS_SENTINEL_ENABLED", False)
REDIS_SENTINEL_MASTER = getattr(settings, "REDIS_SENTINEL_MASTER", "mymaster")
REDIS_SENTINEL_HOSTS = getattr(settings, "REDIS_SENTINEL_HOSTS", [])
REDIS_SENTINEL_SOCKET_TIMEOUT = getattr(settings, "REDIS_SENTINEL_SOCKET_TIMEOUT", 1.0)
REDIS_SENTINEL_PASSWORD = getattr(settings, "REDIS_SENTINEL_PASSWORD", None)
REDIS_SENTINEL_DB = getattr(settings, "REDIS_SENTINEL_DB", 0)

REDIS_CLUSTER_ENABLED = getattr(settings, "REDIS_CLUSTER_ENABLED", False)
REDIS_CLUSTER_NODES = getattr(settings, "REDIS_CLUSTER_NODES", [])
REDIS_CLUSTER_PASSWORD = getattr(settings, "REDIS_CLUSTER_PASSWORD", None)

REDIS_CONNECTION_POOL_ENABLED = getattr(settings, "REDIS_CONNECTION_POOL_ENABLED", True)
REDIS_CONNECTION_POOL_MAX_CONNECTIONS = getattr(
    settings, "REDIS_CONNECTION_POOL_MAX_CONNECTIONS", 100
)

REDIS_RETRY_ON_TIMEOUT = getattr(settings, "REDIS_RETRY_ON_TIMEOUT", True)
REDIS_RETRY_ON_ERROR = getattr(settings, "REDIS_RETRY_ON_ERROR", True)
REDIS_MAX_RETRIES = getattr(settings, "REDIS_MAX_RETRIES", 3)
REDIS_RETRY_DELAY = getattr(settings, "REDIS_RETRY_DELAY", 0.1)  # 100ms


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
        # Create Sentinel connection if not already created
        if _sentinel_pool is None:
            # Convert host strings to (host, port) tuples
            sentinel_hosts = []
            for host_str in REDIS_SENTINEL_HOSTS:
                if ":" in host_str:
                    host, port = host_str.split(":")
                    sentinel_hosts.append((host, int(port)))
                else:
                    sentinel_hosts.append((host_str, 26379))  # Default Sentinel port
            
            # Create Sentinel connection
            sentinel = Sentinel(
                sentinel_hosts,
                socket_timeout=REDIS_SENTINEL_SOCKET_TIMEOUT,
                password=REDIS_SENTINEL_PASSWORD,
            )
            
            # Get master connection pool
            master_host, master_port = sentinel.discover_master(REDIS_SENTINEL_MASTER)
            
            # Create connection pool
            _sentinel_pool = redis.ConnectionPool(
                host=master_host,
                port=master_port,
                db=REDIS_SENTINEL_DB,
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
        Redis Cluster client
    """
    global _cluster_pool
    
    if not REDIS_CLUSTER_ENABLED or not REDIS_CLUSTER_NODES:
        logger.warning("Redis Cluster is not enabled or no nodes configured")
        return get_redis_standalone_client()
    
    try:
        # Create Redis Cluster client if not already created
        if _cluster_pool is None:
            # Convert node strings to (host, port) tuples
            startup_nodes = []
            for node_str in REDIS_CLUSTER_NODES:
                if ":" in node_str:
                    host, port = node_str.split(":")
                    startup_nodes.append({"host": host, "port": int(port)})
                else:
                    startup_nodes.append({"host": node_str, "port": 6379})  # Default Redis port
            
            # Create Redis Cluster client
            from redis.cluster import RedisCluster
            
            _cluster_pool = RedisCluster(
                startup_nodes=startup_nodes,
                password=REDIS_CLUSTER_PASSWORD,
                decode_responses=False,
                skip_full_coverage_check=True,
                retry_on_timeout=REDIS_RETRY_ON_TIMEOUT,
            )
            
            logger.info(f"Connected to Redis Cluster with {len(startup_nodes)} nodes")
        
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
        from core.redis_settings import get_redis_connection_params
        
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
    def decorator(func):
        def wrapper(*args, **kwargs):
            retries = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except (redis.ConnectionError, redis.TimeoutError) as e:
                    retries += 1
                    if retries > max_retries:
                        logger.error(
                            f"Redis operation failed after {retries} retries: {str(e)}"
                        )
                        raise
                    
                    # Add jitter to retry delay to avoid thundering herd
                    jitter = random.uniform(0, 0.1)  # 0-100ms jitter
                    delay = retry_delay * (2 ** (retries - 1)) + jitter  # Exponential backoff
                    
                    logger.warning(
                        f"Redis operation failed, retrying in {delay:.2f}s "
                        f"(retry {retries}/{max_retries}): {str(e)}"
                    )
                    
                    time.sleep(delay)
        
        return wrapper
    
    return decorator


def check_redis_health() -> Dict[str, Union[bool, str, Dict]]:
    """
    Check the health of the Redis connection.
    
    Returns:
        Dictionary with health check results
    """
    result = {
        "healthy": False,
        "message": "",
        "details": {},
    }
    
    try:
        # Get Redis client
        client = get_redis_client()
        
        if client is None:
            result["message"] = "Failed to create Redis client"
            return result
        
        # Check connection
        ping_result = client.ping()
        
        if not ping_result:
            result["message"] = "Redis ping failed"
            return result
        
        # Get Redis info
        info = client.info()
        
        # Extract relevant info
        result["details"] = {
            "redis_version": info.get("redis_version", "unknown"),
            "uptime_seconds": info.get("uptime_in_seconds", 0),
            "connected_clients": info.get("connected_clients", 0),
            "used_memory_human": info.get("used_memory_human", "unknown"),
            "total_connections_received": info.get("total_connections_received", 0),
            "total_commands_processed": info.get("total_commands_processed", 0),
        }
        
        # Check if Redis is using too much memory
        if "used_memory" in info and "maxmemory" in info and info["maxmemory"] > 0:
            memory_usage_pct = info["used_memory"] / info["maxmemory"] * 100
            result["details"]["memory_usage_percent"] = f"{memory_usage_pct:.1f}%"
            
            if memory_usage_pct > 90:
                result["message"] = f"Redis memory usage is high: {memory_usage_pct:.1f}%"
                result["details"]["warnings"] = ["High memory usage"]
        
        # Check if Redis has many clients
        if info.get("connected_clients", 0) > 100:
            if "warnings" not in result["details"]:
                result["details"]["warnings"] = []
            result["details"]["warnings"].append("Many connected clients")
        
        # All checks passed
        result["healthy"] = True
        result["message"] = "Redis is healthy"
        
        return result
    except Exception as e:
        result["message"] = f"Redis health check failed: {str(e)}"
        return result


# Initialize the appropriate Redis client
redis_ha_client = get_redis_client()

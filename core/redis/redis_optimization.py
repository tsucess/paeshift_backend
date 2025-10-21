"""
Redis memory optimization module.

This module provides tools for optimizing Redis memory usage,
implementing cache eviction policies, and compressing cached data.
"""

import gzip
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Union

from django.conf import settings
from django.utils import timezone

from core.cache import redis_client, CACHE_PREFIXES
from core.redis_monitoring import get_memory_usage, get_key_count_by_prefix, analyze_key_size
from core.redis_settings import CACHE_ENABLED

logger = logging.getLogger(__name__)

# Constants
COMPRESSION_THRESHOLD = getattr(settings, "REDIS_COMPRESSION_THRESHOLD", 1024)  # bytes
COMPRESSION_LEVEL = getattr(settings, "REDIS_COMPRESSION_LEVEL", 6)  # 1-9, higher is more compression
COMPRESSION_PREFIX = "compressed:"
LRU_SAMPLE_SIZE = getattr(settings, "REDIS_LRU_SAMPLE_SIZE", 100)
TTL_EXTENSION_FACTOR = getattr(settings, "REDIS_TTL_EXTENSION_FACTOR", 2)  # Multiply TTL by this factor for popular keys


def compress_data(data: bytes) -> bytes:
    """
    Compress data using gzip.
    
    Args:
        data: Data to compress
        
    Returns:
        Compressed data
    """
    return gzip.compress(data, compresslevel=COMPRESSION_LEVEL)


def decompress_data(data: bytes) -> bytes:
    """
    Decompress data using gzip.
    
    Args:
        data: Compressed data
        
    Returns:
        Decompressed data
    """
    return gzip.decompress(data)


def set_compressed(key: str, value: Union[str, bytes], ttl: Optional[int] = None) -> bool:
    """
    Set a compressed value in Redis.
    
    Args:
        key: Redis key
        value: Value to store (string or bytes)
        ttl: Time to live in seconds
        
    Returns:
        True if successful, False otherwise
    """
    if not CACHE_ENABLED or not redis_client:
        return False
        
    try:
        # Convert value to bytes if it's a string
        if isinstance(value, str):
            value = value.encode("utf-8")
            
        # Compress the data
        compressed_data = compress_data(value)
        
        # Store with compression prefix
        compressed_key = f"{COMPRESSION_PREFIX}{key}"
        
        # Set in Redis with TTL if provided
        if ttl:
            redis_client.setex(compressed_key, ttl, compressed_data)
        else:
            redis_client.set(compressed_key, compressed_data)
            
        return True
    except Exception as e:
        logger.error(f"Error setting compressed data for key {key}: {str(e)}")
        return False


def get_compressed(key: str) -> Optional[bytes]:
    """
    Get a compressed value from Redis and decompress it.
    
    Args:
        key: Redis key
        
    Returns:
        Decompressed data or None if not found
    """
    if not CACHE_ENABLED or not redis_client:
        return None
        
    try:
        # Get with compression prefix
        compressed_key = f"{COMPRESSION_PREFIX}{key}"
        
        # Get from Redis
        compressed_data = redis_client.get(compressed_key)
        
        if compressed_data:
            # Decompress the data
            return decompress_data(compressed_data)
            
        return None
    except Exception as e:
        logger.error(f"Error getting compressed data for key {key}: {str(e)}")
        return None


def should_compress(data: Union[str, bytes]) -> bool:
    """
    Determine if data should be compressed based on size.
    
    Args:
        data: Data to check
        
    Returns:
        True if data should be compressed, False otherwise
    """
    # Convert to bytes if it's a string
    if isinstance(data, str):
        data = data.encode("utf-8")
        
    # Check if size exceeds threshold
    return len(data) > COMPRESSION_THRESHOLD


def compress_large_values(
    pattern: str = "*",
    sample_size: int = 100,
    min_size: int = COMPRESSION_THRESHOLD,
) -> Dict:
    """
    Compress large values in Redis.
    
    Args:
        pattern: Key pattern to match
        sample_size: Number of keys to sample
        min_size: Minimum size to compress
        
    Returns:
        Dictionary with compression statistics
    """
    if not CACHE_ENABLED or not redis_client:
        return {"error": "Redis client not available"}
        
    try:
        # Get keys matching the pattern
        keys = redis_client.keys(pattern)
        
        # If there are too many keys, sample them
        if len(keys) > sample_size:
            import random
            keys = random.sample(keys, sample_size)
            
        # Compress large values
        compressed_count = 0
        total_original_size = 0
        total_compressed_size = 0
        
        for key in keys:
            # Skip already compressed keys
            if key.startswith(COMPRESSION_PREFIX.encode("utf-8")):
                continue
                
            # Get the value
            value = redis_client.get(key)
            
            if value and len(value) >= min_size:
                # Get TTL
                ttl = redis_client.ttl(key)
                
                # Compress the value
                compressed_value = compress_data(value)
                
                # Calculate compression ratio
                original_size = len(value)
                compressed_size = len(compressed_value)
                
                # Only store if compression is effective
                if compressed_size < original_size:
                    # Store compressed value
                    compressed_key = f"{COMPRESSION_PREFIX}{key.decode('utf-8')}"
                    
                    # Set with TTL if it exists
                    if ttl > 0:
                        redis_client.setex(compressed_key, ttl, compressed_value)
                    else:
                        redis_client.set(compressed_key, compressed_value)
                        
                    # Delete original key
                    redis_client.delete(key)
                    
                    # Update statistics
                    compressed_count += 1
                    total_original_size += original_size
                    total_compressed_size += compressed_size
                    
        # Calculate overall statistics
        compression_ratio = (
            (total_original_size - total_compressed_size) / total_original_size * 100
            if total_original_size > 0
            else 0
        )
        
        return {
            "total_keys": len(keys),
            "compressed_keys": compressed_count,
            "total_original_size_bytes": total_original_size,
            "total_compressed_size_bytes": total_compressed_size,
            "space_saved_bytes": total_original_size - total_compressed_size,
            "space_saved_human": (
                f"{(total_original_size - total_compressed_size) / (1024 * 1024):.2f} MB"
                if total_original_size - total_compressed_size > 1024 * 1024
                else f"{(total_original_size - total_compressed_size) / 1024:.2f} KB"
            ),
            "compression_ratio": f"{compression_ratio:.2f}%",
        }
    except Exception as e:
        logger.error(f"Error compressing large values: {str(e)}")
        return {"error": str(e)}


def identify_unused_keys(
    pattern: str = "*",
    days: int = 7,
    sample_size: int = 1000,
) -> List[str]:
    """
    Identify keys that haven't been accessed in a specified number of days.
    
    Args:
        pattern: Key pattern to match
        days: Number of days to consider a key unused
        sample_size: Number of keys to sample
        
    Returns:
        List of unused keys
    """
    if not CACHE_ENABLED or not redis_client:
        return []
        
    try:
        # Get keys matching the pattern
        keys = redis_client.keys(pattern)
        
        # If there are too many keys, sample them
        if len(keys) > sample_size:
            import random
            keys = random.sample(keys, sample_size)
            
        # Check idle time for each key
        unused_keys = []
        for key in keys:
            # Get idle time using OBJECT IDLETIME
            idle_time = redis_client.execute_command("OBJECT", "IDLETIME", key)
            
            # Convert to days
            idle_days = idle_time / (24 * 60 * 60)
            
            # Check if unused
            if idle_days >= days:
                unused_keys.append(key.decode("utf-8"))
                
        return unused_keys
    except Exception as e:
        logger.error(f"Error identifying unused keys: {str(e)}")
        return []


def delete_unused_keys(
    pattern: str = "*",
    days: int = 7,
    sample_size: int = 1000,
    dry_run: bool = True,
) -> Dict:
    """
    Delete keys that haven't been accessed in a specified number of days.
    
    Args:
        pattern: Key pattern to match
        days: Number of days to consider a key unused
        sample_size: Number of keys to sample
        dry_run: If True, only report keys that would be deleted
        
    Returns:
        Dictionary with deletion statistics
    """
    if not CACHE_ENABLED or not redis_client:
        return {"error": "Redis client not available"}
        
    try:
        # Identify unused keys
        unused_keys = identify_unused_keys(pattern, days, sample_size)
        
        # Delete keys if not a dry run
        deleted_count = 0
        if not dry_run and unused_keys:
            # Delete in batches to avoid blocking Redis
            batch_size = 100
            for i in range(0, len(unused_keys), batch_size):
                batch = unused_keys[i:i + batch_size]
                deleted_count += redis_client.delete(*batch)
                
        return {
            "total_keys_checked": sample_size,
            "unused_keys_found": len(unused_keys),
            "deleted_keys": deleted_count if not dry_run else 0,
            "dry_run": dry_run,
            "unused_keys": unused_keys[:10],  # Show first 10 unused keys
        }
    except Exception as e:
        logger.error(f"Error deleting unused keys: {str(e)}")
        return {"error": str(e)}


def extend_ttl_for_popular_keys(
    pattern: str = "*",
    min_hits: int = 10,
    extension_factor: float = TTL_EXTENSION_FACTOR,
    sample_size: int = 1000,
) -> Dict:
    """
    Extend TTL for frequently accessed keys.
    
    Args:
        pattern: Key pattern to match
        min_hits: Minimum number of hits to consider a key popular
        extension_factor: Factor to multiply TTL by
        sample_size: Number of keys to sample
        
    Returns:
        Dictionary with extension statistics
    """
    if not CACHE_ENABLED or not redis_client:
        return {"error": "Redis client not available"}
        
    try:
        # Get keys matching the pattern
        keys = redis_client.keys(pattern)
        
        # If there are too many keys, sample them
        if len(keys) > sample_size:
            import random
            keys = random.sample(keys, sample_size)
            
        # Extend TTL for popular keys
        extended_count = 0
        
        for key in keys:
            # Skip keys without TTL
            ttl = redis_client.ttl(key)
            if ttl <= 0:
                continue
                
            # Check if key is popular using Redis OBJECT FREQ
            # Note: This requires Redis to be configured with maxmemory-policy=allkeys-lfu
            try:
                freq = redis_client.execute_command("OBJECT", "FREQ", key)
                
                # Extend TTL if popular
                if freq and freq >= min_hits:
                    # Calculate new TTL
                    new_ttl = int(ttl * extension_factor)
                    
                    # Set new TTL
                    redis_client.expire(key, new_ttl)
                    
                    # Update statistics
                    extended_count += 1
            except Exception:
                # OBJECT FREQ may not be available in all Redis versions
                pass
                
        return {
            "total_keys_checked": len(keys),
            "extended_keys": extended_count,
            "extension_factor": extension_factor,
        }
    except Exception as e:
        logger.error(f"Error extending TTL for popular keys: {str(e)}")
        return {"error": str(e)}


def optimize_memory_usage() -> Dict:
    """
    Optimize Redis memory usage by applying various optimization techniques.
    
    Returns:
        Dictionary with optimization statistics
    """
    if not CACHE_ENABLED or not redis_client:
        return {"error": "Redis client not available"}
        
    start_time = time.time()
    logger.info("Starting Redis memory optimization")
    
    try:
        # Get initial memory usage
        initial_memory = get_memory_usage()
        initial_key_count = get_key_count_by_prefix()
        
        # Apply optimization techniques
        
        # 1. Compress large values
        compression_stats = compress_large_values(
            pattern="*",
            sample_size=1000,
            min_size=COMPRESSION_THRESHOLD,
        )
        
        # 2. Delete unused keys
        unused_keys_stats = delete_unused_keys(
            pattern="*",
            days=7,
            sample_size=1000,
            dry_run=False,
        )
        
        # 3. Extend TTL for popular keys
        ttl_extension_stats = extend_ttl_for_popular_keys(
            pattern="*",
            min_hits=10,
            extension_factor=TTL_EXTENSION_FACTOR,
            sample_size=1000,
        )
        
        # Get final memory usage
        final_memory = get_memory_usage()
        final_key_count = get_key_count_by_prefix()
        
        # Calculate memory saved
        memory_saved = (
            float(initial_memory.get("used_memory_bytes", 0))
            - float(final_memory.get("used_memory_bytes", 0))
        )
        
        # Calculate keys removed
        keys_removed = (
            initial_key_count.get("total_keys", 0)
            - final_key_count.get("total_keys", 0)
        )
        
        elapsed = time.time() - start_time
        logger.info(f"Completed Redis memory optimization in {elapsed:.2f} seconds")
        
        return {
            "initial_memory": initial_memory,
            "final_memory": final_memory,
            "memory_saved_bytes": memory_saved,
            "memory_saved_human": (
                f"{memory_saved / (1024 * 1024):.2f} MB"
                if memory_saved > 1024 * 1024
                else f"{memory_saved / 1024:.2f} KB"
            ),
            "initial_key_count": initial_key_count,
            "final_key_count": final_key_count,
            "keys_removed": keys_removed,
            "compression_stats": compression_stats,
            "unused_keys_stats": unused_keys_stats,
            "ttl_extension_stats": ttl_extension_stats,
            "elapsed_seconds": elapsed,
            "timestamp": timezone.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error optimizing Redis memory usage: {str(e)}")
        return {"error": str(e)}

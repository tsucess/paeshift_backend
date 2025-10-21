"""
Redis-based distributed configuration utilities.

This module provides utilities for storing and retrieving configuration
values using Redis, which is useful for sharing configuration across
multiple servers or processes.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Set, Union

from core.cache import (
    delete_cached_data,
    delete_hash_field,
    get_cached_data,
    get_hash_all,
    get_hash_field,
    publish_notification,
    set_cached_data,
    set_hash_field,
)

logger = logging.getLogger(__name__)

# Constants
CONFIG_EXPIRATION = 60 * 60 * 24 * 30  # 30 days
CONFIG_PREFIX = "config:"


class RedisConfig:
    """
    Redis-based distributed configuration.
    
    This class provides methods for storing and retrieving configuration
    values using Redis.
    """
    
    def __init__(self, namespace: str = "app", expiration: int = CONFIG_EXPIRATION):
        """
        Initialize a Redis configuration.
        
        Args:
            namespace: Configuration namespace
            expiration: Expiration time in seconds
        """
        self.namespace = namespace
        self.key = f"{CONFIG_PREFIX}{namespace}"
        self.expiration = expiration
        
    def set(self, key: str, value: Any) -> bool:
        """
        Set a configuration value.
        
        Args:
            key: Configuration key
            value: Configuration value
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Set field in hash
            success = set_hash_field(self.key, key, value, self.expiration)
            
            if success:
                # Publish notification
                publish_notification(
                    f"config:{self.namespace}:notifications",
                    {
                        "type": "config_updated",
                        "namespace": self.namespace,
                        "key": key,
                        "value": value,
                    }
                )
                
            return success
        except Exception as e:
            logger.error(f"Error setting config {self.namespace}.{key}: {str(e)}")
            return False
            
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.
        
        Args:
            key: Configuration key
            default: Default value if not found
            
        Returns:
            Configuration value or default
        """
        try:
            # Get field from hash
            value = get_hash_field(self.key, key)
            
            if value is None:
                return default
                
            return value
        except Exception as e:
            logger.error(f"Error getting config {self.namespace}.{key}: {str(e)}")
            return default
            
    def get_all(self) -> Dict[str, Any]:
        """
        Get all configuration values.
        
        Returns:
            Dictionary of configuration values
        """
        try:
            # Get all fields from hash
            return get_hash_all(self.key)
        except Exception as e:
            logger.error(f"Error getting all config for {self.namespace}: {str(e)}")
            return {}
            
    def delete(self, key: str) -> bool:
        """
        Delete a configuration value.
        
        Args:
            key: Configuration key
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Delete field from hash
            success = delete_hash_field(self.key, key)
            
            if success:
                # Publish notification
                publish_notification(
                    f"config:{self.namespace}:notifications",
                    {
                        "type": "config_deleted",
                        "namespace": self.namespace,
                        "key": key,
                    }
                )
                
            return success
        except Exception as e:
            logger.error(f"Error deleting config {self.namespace}.{key}: {str(e)}")
            return False
            
    def clear(self) -> bool:
        """
        Clear all configuration values.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Delete hash
            success = delete_cached_data(self.key)
            
            if success:
                # Publish notification
                publish_notification(
                    f"config:{self.namespace}:notifications",
                    {
                        "type": "config_cleared",
                        "namespace": self.namespace,
                    }
                )
                
            return success
        except Exception as e:
            logger.error(f"Error clearing config for {self.namespace}: {str(e)}")
            return False


def get_config(namespace: str = "app") -> RedisConfig:
    """
    Get a Redis configuration.
    
    Args:
        namespace: Configuration namespace
        
    Returns:
        RedisConfig instance
    """
    return RedisConfig(namespace)


def set_config_value(namespace: str, key: str, value: Any) -> bool:
    """
    Set a configuration value.
    
    Args:
        namespace: Configuration namespace
        key: Configuration key
        value: Configuration value
        
    Returns:
        True if successful, False otherwise
    """
    config = get_config(namespace)
    return config.set(key, value)


def get_config_value(namespace: str, key: str, default: Any = None) -> Any:
    """
    Get a configuration value.
    
    Args:
        namespace: Configuration namespace
        key: Configuration key
        default: Default value if not found
        
    Returns:
        Configuration value or default
    """
    config = get_config(namespace)
    return config.get(key, default)


def get_all_config_values(namespace: str) -> Dict[str, Any]:
    """
    Get all configuration values.
    
    Args:
        namespace: Configuration namespace
        
    Returns:
        Dictionary of configuration values
    """
    config = get_config(namespace)
    return config.get_all()


def delete_config_value(namespace: str, key: str) -> bool:
    """
    Delete a configuration value.
    
    Args:
        namespace: Configuration namespace
        key: Configuration key
        
    Returns:
        True if successful, False otherwise
    """
    config = get_config(namespace)
    return config.delete(key)


def clear_config(namespace: str) -> bool:
    """
    Clear all configuration values.
    
    Args:
        namespace: Configuration namespace
        
    Returns:
        True if successful, False otherwise
    """
    config = get_config(namespace)
    return config.clear()

"""
Redis-based user presence tracking utilities.

This module provides utilities for tracking user presence (online status)
using Redis.
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set

from core.cache import get_user_presence, publish_notification, update_user_presence

logger = logging.getLogger(__name__)

# Constants
PRESENCE_EXPIRATION = 60 * 15  # 15 minutes for online/away
OFFLINE_EXPIRATION = 60  # 1 minute for offline (just to show the transition)

# Status constants
STATUS_ONLINE = "online"
STATUS_AWAY = "away"
STATUS_OFFLINE = "offline"


def set_user_presence(user_id: str, status: str = STATUS_ONLINE) -> bool:
    """
    Set a user's presence status.
    
    Args:
        user_id: User ID
        status: Status ("online", "away", "offline")
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Validate status
        valid_statuses = [STATUS_ONLINE, STATUS_AWAY, STATUS_OFFLINE]
        if status not in valid_statuses:
            logger.error(f"Invalid status: {status}. Must be one of {valid_statuses}")
            return False
            
        # Set expiration based on status
        expiration = PRESENCE_EXPIRATION
        if status == STATUS_OFFLINE:
            expiration = OFFLINE_EXPIRATION
            
        # Update presence in Redis
        return update_user_presence(user_id, status, expiration)
    except Exception as e:
        logger.error(f"Error setting user presence for user {user_id}: {str(e)}")
        return False


def get_presence(user_id: str) -> Dict[str, any]:
    """
    Get a user's presence status.
    
    Args:
        user_id: User ID
        
    Returns:
        Dictionary with presence data
    """
    try:
        # Get presence from Redis
        presence_data = get_user_presence(user_id)
        
        # Convert to more user-friendly format
        return {
            "user_id": user_id,
            "status": presence_data.get("status", STATUS_OFFLINE),
            "last_seen": presence_data.get("last_seen"),
            "is_online": presence_data.get("status") == STATUS_ONLINE,
            "is_away": presence_data.get("status") == STATUS_AWAY,
        }
    except Exception as e:
        logger.error(f"Error getting user presence for user {user_id}: {str(e)}")
        return {
            "user_id": user_id,
            "status": STATUS_OFFLINE,
            "last_seen": None,
            "is_online": False,
            "is_away": False,
        }


def get_online_users(redis_client=None) -> List[Dict[str, any]]:
    """
    Get all online users.
    
    Args:
        redis_client: Optional Redis client
        
    Returns:
        List of user presence data dictionaries
    """
    try:
        # Import here to avoid circular imports
        from core.cache import redis_client as default_redis_client
        
        # Use provided client or default
        client = redis_client or default_redis_client
        
        if not client:
            logger.error("Redis client not available")
            return []
            
        # Get all presence keys
        presence_keys = client.keys("presence:*")
        
        online_users = []
        for key in presence_keys:
            try:
                # Get presence data
                presence_data = client.get(key)
                if presence_data:
                    data = json.loads(presence_data)
                    if data.get("status") in [STATUS_ONLINE, STATUS_AWAY]:
                        user_id = data.get("user_id")
                        if user_id:
                            online_users.append({
                                "user_id": user_id,
                                "status": data.get("status"),
                                "last_seen": data.get("last_seen"),
                                "is_online": data.get("status") == STATUS_ONLINE,
                                "is_away": data.get("status") == STATUS_AWAY,
                            })
            except (json.JSONDecodeError, Exception) as e:
                logger.error(f"Error processing presence data: {str(e)}")
                
        return online_users
    except Exception as e:
        logger.error(f"Error getting online users: {str(e)}")
        return []


def heartbeat(user_id: str) -> bool:
    """
    Update a user's heartbeat to keep them online.
    
    Args:
        user_id: User ID
        
    Returns:
        True if successful, False otherwise
    """
    # Get current presence
    presence = get_presence(user_id)
    
    # If offline, set to online
    if presence.get("status") == STATUS_OFFLINE:
        return set_user_presence(user_id, STATUS_ONLINE)
        
    # Otherwise, just update the timestamp
    return update_user_presence(user_id, presence.get("status", STATUS_ONLINE))


def set_away(user_id: str) -> bool:
    """
    Set a user's status to away.
    
    Args:
        user_id: User ID
        
    Returns:
        True if successful, False otherwise
    """
    return set_user_presence(user_id, STATUS_AWAY)


def set_offline(user_id: str) -> bool:
    """
    Set a user's status to offline.
    
    Args:
        user_id: User ID
        
    Returns:
        True if successful, False otherwise
    """
    return set_user_presence(user_id, STATUS_OFFLINE)

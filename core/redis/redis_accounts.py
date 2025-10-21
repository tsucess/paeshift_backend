"""
Redis-based user activity tracking.

This module provides utilities for tracking user activity using Redis.
"""

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from django.core.cache import cache

logger = logging.getLogger(__name__)

# Constants
ACTIVITY_PREFIX = "activity:"
PRESENCE_PREFIX = "presence:"
LAST_SEEN_PREFIX = "last_seen:"
ACTIVITY_TIMEOUT = 60 * 60 * 24 * 30  # 30 days
PRESENCE_TIMEOUT = 60 * 5  # 5 minutes
LAST_SEEN_TIMEOUT = 60 * 60 * 24 * 7  # 7 days


def track_user_activity(user_id: str, activity_type: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
    """
    Track user activity.
    
    Args:
        user_id: User ID
        activity_type: Type of activity
        metadata: Optional metadata
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Generate activity key
        activity_key = f"{ACTIVITY_PREFIX}{user_id}"
        
        # Get current time
        now = time.time()
        
        # Create activity data
        activity_data = {
            "type": activity_type,
            "timestamp": now,
            "datetime": datetime.fromtimestamp(now).isoformat(),
        }
        
        # Add metadata if provided
        if metadata:
            activity_data["metadata"] = metadata
        
        # Convert to JSON
        activity_json = json.dumps(activity_data)
        
        # Add to activity list
        pipe = cache.client.pipeline()
        pipe.lpush(activity_key, activity_json)
        pipe.ltrim(activity_key, 0, 99)  # Keep only the last 100 activities
        pipe.expire(activity_key, ACTIVITY_TIMEOUT)
        pipe.execute()
        
        # Update last seen
        update_user_last_seen(user_id)
        
        # Update presence
        update_user_presence(user_id)
        
        return True
    except Exception as e:
        logger.error(f"Error tracking user activity: {str(e)}")
        return False


def get_user_activities(user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get user activities.
    
    Args:
        user_id: User ID
        limit: Maximum number of activities to return
        
    Returns:
        List of activities
    """
    try:
        # Generate activity key
        activity_key = f"{ACTIVITY_PREFIX}{user_id}"
        
        # Get activities
        activities = cache.client.lrange(activity_key, 0, limit - 1)
        
        # Parse JSON
        return [json.loads(activity) for activity in activities]
    except Exception as e:
        logger.error(f"Error getting user activities: {str(e)}")
        return []


def update_user_presence(user_id: str) -> bool:
    """
    Update user presence.
    
    Args:
        user_id: User ID
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Generate presence key
        presence_key = f"{PRESENCE_PREFIX}{user_id}"
        
        # Set presence
        cache.set(presence_key, time.time(), PRESENCE_TIMEOUT)
        
        return True
    except Exception as e:
        logger.error(f"Error updating user presence: {str(e)}")
        return False


def is_user_online(user_id: str) -> bool:
    """
    Check if a user is online.
    
    Args:
        user_id: User ID
        
    Returns:
        True if online, False otherwise
    """
    try:
        # Generate presence key
        presence_key = f"{PRESENCE_PREFIX}{user_id}"
        
        # Check presence
        return cache.get(presence_key) is not None
    except Exception as e:
        logger.error(f"Error checking user presence: {str(e)}")
        return False


def update_user_last_seen(user_id: str) -> bool:
    """
    Update user last seen timestamp.
    
    Args:
        user_id: User ID
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Generate last seen key
        last_seen_key = f"{LAST_SEEN_PREFIX}{user_id}"
        
        # Set last seen
        cache.set(last_seen_key, time.time(), LAST_SEEN_TIMEOUT)
        
        return True
    except Exception as e:
        logger.error(f"Error updating user last seen: {str(e)}")
        return False


def get_user_last_seen(user_id: str) -> Optional[float]:
    """
    Get user last seen timestamp.
    
    Args:
        user_id: User ID
        
    Returns:
        Last seen timestamp or None
    """
    try:
        # Generate last seen key
        last_seen_key = f"{LAST_SEEN_PREFIX}{user_id}"
        
        # Get last seen
        return cache.get(last_seen_key)
    except Exception as e:
        logger.error(f"Error getting user last seen: {str(e)}")
        return None

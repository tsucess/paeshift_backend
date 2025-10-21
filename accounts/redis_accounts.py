"""
Redis-based account management utilities.

This module provides utilities for managing user accounts using Redis,
including session management, user presence, and activity tracking.
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from core.redis.cache import (
    add_to_list,
    get_cached_data,
    get_list_range,
    publish_notification,
    set_cached_data,
)
from core.redis.redis_activity import add_activity
from core.redis.redis_presence import set_user_presence

logger = logging.getLogger(__name__)

User = get_user_model()

# Constants
SESSION_EXPIRATION = 60 * 60 * 24 * 7  # 7 days
ACTIVITY_EXPIRATION = 60 * 60 * 24 * 30  # 30 days
SESSION_PREFIX = "session:"
LOGIN_HISTORY_PREFIX = "login_history:"


class UserSession:
    """
    Redis-based user session management.
    
    This class provides methods for managing user sessions using Redis.
    """
    
    def __init__(self, user_id: str, session_id: Optional[str] = None):
        """
        Initialize a user session.
        
        Args:
            user_id: User ID
            session_id: Session ID (if None, use user_id)
        """
        self.user_id = user_id
        self.session_id = session_id or user_id
        self.session_key = f"{SESSION_PREFIX}{self.session_id}"
        self.login_history_key = f"{LOGIN_HISTORY_PREFIX}{user_id}"
        
    def create_session(self, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Create a new session.
        
        Args:
            metadata: Session metadata
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create session data
            session_data = {
                "user_id": self.user_id,
                "session_id": self.session_id,
                "created_at": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat(),
                "metadata": metadata or {},
            }
            
            # Store in Redis
            success = set_cached_data(self.session_key, session_data, SESSION_EXPIRATION)
            
            if success:
                # Add to login history
                self._add_to_login_history(session_data)
                
                # Set user as online
                set_user_presence(self.user_id, "online")
                
                # Add activity
                add_activity(
                    self.user_id,
                    "login",
                    {
                        "session_id": self.session_id,
                        "metadata": metadata or {},
                    }
                )
                
            return success
        except Exception as e:
            logger.error(f"Error creating session for user {self.user_id}: {str(e)}")
            return False
            
    def update_session(self, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Update an existing session.
        
        Args:
            metadata: Session metadata to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get current session data
            session_data = self.get_session()
            if not session_data:
                logger.error(f"Session {self.session_id} not found")
                return False
                
            # Update session data
            session_data["last_activity"] = datetime.now().isoformat()
            
            if metadata:
                session_data["metadata"].update(metadata)
                
            # Store in Redis
            return set_cached_data(self.session_key, session_data, SESSION_EXPIRATION)
        except Exception as e:
            logger.error(f"Error updating session {self.session_id}: {str(e)}")
            return False
            
    def end_session(self) -> bool:
        """
        End a session.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get current session data
            session_data = self.get_session()
            if not session_data:
                logger.error(f"Session {self.session_id} not found")
                return False
                
            # Update session data
            session_data["ended_at"] = datetime.now().isoformat()
            session_data["active"] = False
            
            # Store in Redis with shorter expiration
            success = set_cached_data(self.session_key, session_data, 60 * 60)  # 1 hour
            
            if success:
                # Set user as offline
                set_user_presence(self.user_id, "offline")
                
                # Add activity
                add_activity(
                    self.user_id,
                    "logout",
                    {
                        "session_id": self.session_id,
                        "duration": self._calculate_session_duration(session_data),
                    }
                )
                
            return success
        except Exception as e:
            logger.error(f"Error ending session {self.session_id}: {str(e)}")
            return False
            
    def get_session(self) -> Optional[Dict[str, Any]]:
        """
        Get session data.
        
        Returns:
            Session data or None if not found
        """
        try:
            return get_cached_data(self.session_key)
        except Exception as e:
            logger.error(f"Error getting session {self.session_id}: {str(e)}")
            return None
            
    def get_login_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get login history.
        
        Args:
            limit: Maximum number of entries to return
            
        Returns:
            List of login history entries
        """
        try:
            # Get login history from Redis
            history = get_list_range(self.login_history_key, 0, limit - 1)
            
            # Parse JSON entries
            parsed_history = []
            for entry in history:
                try:
                    parsed_history.append(json.loads(entry))
                except json.JSONDecodeError:
                    # Skip invalid JSON
                    continue
                    
            return parsed_history
        except Exception as e:
            logger.error(f"Error getting login history for user {self.user_id}: {str(e)}")
            return []
            
    def _add_to_login_history(self, session_data: Dict[str, Any]) -> bool:
        """
        Add a session to login history.
        
        Args:
            session_data: Session data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create history entry
            history_entry = {
                "session_id": session_data["session_id"],
                "created_at": session_data["created_at"],
                "metadata": session_data.get("metadata", {}),
            }
            
            # Add to list
            return add_to_list(
                self.login_history_key, 
                json.dumps(history_entry), 
                max_length=100,
                expiration=ACTIVITY_EXPIRATION
            )
        except Exception as e:
            logger.error(f"Error adding to login history for user {self.user_id}: {str(e)}")
            return False
            
    def _calculate_session_duration(self, session_data: Dict[str, Any]) -> int:
        """
        Calculate session duration in seconds.
        
        Args:
            session_data: Session data
            
        Returns:
            Session duration in seconds
        """
        try:
            # Get start and end times
            start_time = datetime.fromisoformat(session_data["created_at"])
            end_time = datetime.fromisoformat(session_data.get("ended_at") or datetime.now().isoformat())
            
            # Calculate duration
            duration = (end_time - start_time).total_seconds()
            
            return int(duration)
        except Exception as e:
            logger.error(f"Error calculating session duration: {str(e)}")
            return 0


class UserActivity:
    """
    Redis-based user activity tracking.
    
    This class provides methods for tracking user activity using Redis.
    """
    
    def __init__(self, user_id: str):
        """
        Initialize user activity tracking.
        
        Args:
            user_id: User ID
        """
        self.user_id = user_id
        self.activity_key = f"user_activity:{user_id}"
        
    def track_activity(self, activity_type: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Track a user activity.
        
        Args:
            activity_type: Type of activity
            metadata: Activity metadata
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create activity data
            activity_data = {
                "type": activity_type,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {},
            }
            
            # Add to activity feed
            success = add_activity(
                self.user_id,
                activity_type,
                activity_data,
                notify=False
            )
            
            if success:
                # Update user presence
                set_user_presence(self.user_id, "online")
                
            return success
        except Exception as e:
            logger.error(f"Error tracking activity for user {self.user_id}: {str(e)}")
            return False
            
    def get_activities(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get user activities.
        
        Args:
            limit: Maximum number of activities to return
            
        Returns:
            List of activity data dictionaries
        """
        from core.redis.redis_activity import get_activities
        return get_activities(self.user_id, limit)


# Signal receivers
@receiver(user_logged_in)
def user_logged_in_handler(sender, request, user, **kwargs):
    """
    Handle user login signal.
    
    Args:
        sender: Signal sender
        request: HTTP request
        user: User object
        **kwargs: Additional arguments
    """
    try:
        # Get metadata from request
        metadata = {
            "ip": request.META.get("REMOTE_ADDR"),
            "user_agent": request.META.get("HTTP_USER_AGENT"),
        }
        
        # Create session
        session = UserSession(str(user.id), request.session.session_key)
        session.create_session(metadata)
        
        logger.info(f"User {user.id} logged in")
    except Exception as e:
        logger.error(f"Error handling user login: {str(e)}")


@receiver(user_logged_out)
def user_logged_out_handler(sender, request, user, **kwargs):
    """
    Handle user logout signal.
    
    Args:
        sender: Signal sender
        request: HTTP request
        user: User object
        **kwargs: Additional arguments
    """
    try:
        if user:
            # End session
            session = UserSession(str(user.id), request.session.session_key)
            session.end_session()
            
            logger.info(f"User {user.id} logged out")
    except Exception as e:
        logger.error(f"Error handling user logout: {str(e)}")


def get_user_session(user_id: str, session_id: Optional[str] = None) -> UserSession:
    """
    Get a user session.
    
    Args:
        user_id: User ID
        session_id: Session ID (if None, use user_id)
        
    Returns:
        UserSession instance
    """
    return UserSession(user_id, session_id)


def get_user_activity(user_id: str) -> UserActivity:
    """
    Get user activity tracking.
    
    Args:
        user_id: User ID
        
    Returns:
        UserActivity instance
    """
    return UserActivity(user_id)


def track_user_activity(user_id: str, activity_type: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
    """
    Track a user activity.
    
    Args:
        user_id: User ID
        activity_type: Type of activity
        metadata: Activity metadata
        
    Returns:
        True if successful, False otherwise
    """
    activity = get_user_activity(user_id)
    return activity.track_activity(activity_type, metadata)


def get_user_login_history(user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get user login history.
    
    Args:
        user_id: User ID
        limit: Maximum number of entries to return
        
    Returns:
        List of login history entries
    """
    session = get_user_session(user_id)
    return session.get_login_history(limit)

"""
Redis-based activity feed utilities.

This module provides utilities for creating and managing activity feeds
using Redis lists.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

# Import Redis list utilities
from core.redis.utils import add_to_list, get_list_range, publish_notification

logger = logging.getLogger(__name__)

# Constants
ACTIVITY_FEED_MAX_LENGTH = 100
ACTIVITY_FEED_EXPIRATION = 60 * 60 * 24 * 30  # 30 days


class ActivityFeed:
    """
    Redis-based activity feed.

    This class provides methods for creating and managing activity feeds
    using Redis lists.
    """

    def __init__(
        self,
        user_id: str,
        max_length: int = ACTIVITY_FEED_MAX_LENGTH,
        expiration: int = ACTIVITY_FEED_EXPIRATION
    ):
        """
        Initialize an activity feed.

        Args:
            user_id: User ID
            max_length: Maximum number of activities to keep
            expiration: Expiration time in seconds
        """
        self.user_id = user_id
        self.key = f"activity:{user_id}"
        self.max_length = max_length
        self.expiration = expiration

    def add_activity(self, activity_data: Dict[str, Any], notify: bool = False) -> bool:
        """
        Add an activity to the feed.

        Args:
            activity_data: Activity data
            notify: Whether to send a notification

        Returns:
            True if successful, False otherwise
        """
        try:
            # Add timestamp if not provided
            if "timestamp" not in activity_data:
                activity_data["timestamp"] = datetime.now().isoformat()

            # Add to list
            success = add_to_list(
                self.key,
                json.dumps(activity_data),
                max_length=self.max_length,
                expiration=self.expiration
            )

            # Send notification if requested
            if success and notify:
                publish_notification(
                    f"user:{self.user_id}:notifications",
                    activity_data
                )

            return success
        except Exception as e:
            logger.error(f"Error adding activity to feed for user {self.user_id}: {str(e)}")
            return False

    def get_activities(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get activities from the feed.

        Args:
            limit: Maximum number of activities to return

        Returns:
            List of activity data dictionaries
        """
        try:
            # Get activities from list
            activities = get_list_range(self.key, 0, limit - 1)

            # Parse JSON activities
            parsed_activities = []
            for activity in activities:
                try:
                    parsed_activities.append(json.loads(activity))
                except json.JSONDecodeError:
                    # Skip invalid JSON
                    continue

            return parsed_activities
        except Exception as e:
            logger.error(f"Error getting activities from feed for user {self.user_id}: {str(e)}")
            return []


def get_activity_feed(user_id: str) -> ActivityFeed:
    """
    Get an activity feed.

    Args:
        user_id: User ID

    Returns:
        ActivityFeed instance
    """
    return ActivityFeed(user_id)


def add_activity(
    user_id: str,
    activity_type: str,
    activity_data: Dict[str, Any],
    notify: bool = False
) -> bool:
    """
    Add an activity to a user's feed.

    Args:
        user_id: User ID
        activity_type: Type of activity
        activity_data: Activity data
        notify: Whether to send a notification

    Returns:
        True if successful, False otherwise
    """
    # Add type to activity data
    activity_data["type"] = activity_type

    # Get activity feed
    feed = get_activity_feed(user_id)

    # Add activity
    return feed.add_activity(activity_data, notify)


def get_activities(user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Get activities from a user's feed.

    Args:
        user_id: User ID
        limit: Maximum number of activities to return

    Returns:
        List of activity data dictionaries
    """
    feed = get_activity_feed(user_id)
    return feed.get_activities(limit)


# Activity type constants
ACTIVITY_TYPE_SCORE_UPDATE = "score_update"
ACTIVITY_TYPE_JOB_COMPLETED = "job_completed"
ACTIVITY_TYPE_RATING_RECEIVED = "rating_received"
ACTIVITY_TYPE_PAYMENT_RECEIVED = "payment_received"
ACTIVITY_TYPE_MESSAGE = "message"


def add_score_update_activity(
    user_id: str,
    leaderboard_type: str,
    score: float,
    rank: Optional[int] = None,
    notify: bool = True
) -> bool:
    """
    Add a score update activity to a user's feed.

    Args:
        user_id: User ID
        leaderboard_type: Type of leaderboard
        score: New score
        rank: New rank (optional)
        notify: Whether to send a notification

    Returns:
        True if successful, False otherwise
    """
    activity_data = {
        "leaderboard_type": leaderboard_type,
        "score": score,
        "rank": rank,
    }

    return add_activity(user_id, ACTIVITY_TYPE_SCORE_UPDATE, activity_data, notify)


def add_job_completed_activity(
    user_id: str,
    job_id: str,
    job_title: str,
    notify: bool = True
) -> bool:
    """
    Add a job completed activity to a user's feed.

    Args:
        user_id: User ID
        job_id: Job ID
        job_title: Job title
        notify: Whether to send a notification

    Returns:
        True if successful, False otherwise
    """
    activity_data = {
        "job_id": job_id,
        "job_title": job_title,
    }

    return add_activity(user_id, ACTIVITY_TYPE_JOB_COMPLETED, activity_data, notify)


def add_rating_received_activity(
    user_id: str,
    rating: float,
    from_user_id: str,
    job_id: Optional[str] = None,
    notify: bool = True
) -> bool:
    """
    Add a rating received activity to a user's feed.

    Args:
        user_id: User ID
        rating: Rating value
        from_user_id: User ID of the rater
        job_id: Job ID (optional)
        notify: Whether to send a notification

    Returns:
        True if successful, False otherwise
    """
    activity_data = {
        "rating": rating,
        "from_user_id": from_user_id,
    }

    if job_id:
        activity_data["job_id"] = job_id

    return add_activity(user_id, ACTIVITY_TYPE_RATING_RECEIVED, activity_data, notify)


def add_payment_received_activity(
    user_id: str,
    amount: float,
    currency: str = "USD",
    job_id: Optional[str] = None,
    notify: bool = True
) -> bool:
    """
    Add a payment received activity to a user's feed.

    Args:
        user_id: User ID
        amount: Payment amount
        currency: Currency code
        job_id: Job ID (optional)
        notify: Whether to send a notification

    Returns:
        True if successful, False otherwise
    """
    activity_data = {
        "amount": amount,
        "currency": currency,
    }

    if job_id:
        activity_data["job_id"] = job_id

    return add_activity(user_id, ACTIVITY_TYPE_PAYMENT_RECEIVED, activity_data, notify)


def add_message_activity(
    user_id: str,
    message: str,
    from_user_id: str,
    notify: bool = True
) -> bool:
    """
    Add a message activity to a user's feed.

    Args:
        user_id: User ID
        message: Message text
        from_user_id: User ID of the sender
        notify: Whether to send a notification

    Returns:
        True if successful, False otherwise
    """
    activity_data = {
        "message": message,
        "from_user_id": from_user_id,
    }

    return add_activity(user_id, ACTIVITY_TYPE_MESSAGE, activity_data, notify)

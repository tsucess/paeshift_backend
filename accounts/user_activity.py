"""
User Activity Tracking Module

This module provides functions for tracking and analyzing user activity:
- Login tracking
- Session duration calculation
- Job view tracking
- Last seen timestamps
- Engagement scoring

Usage:
    from accounts.user_activity import track_user_login, track_user_activity, get_user_engagement_score
    track_user_login(user, request)
    track_user_activity(user, 'job_view', {'job_id': 123})
    score = get_user_engagement_score(user)
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone

from accounts.models import UserActivityLog
from gamification.models import UserActivity, UserPoints

User = get_user_model()
logger = logging.getLogger(__name__)

# Constants for activity tracking
SESSION_TIMEOUT = 30 * 60  # 30 minutes in seconds
LAST_SEEN_TIMEOUT = 24 * 60 * 60  # 24 hours in seconds
ENGAGEMENT_SCORE_CACHE_TIMEOUT = 60 * 60  # 1 hour in seconds

# Activity types
LOGIN_ACTIVITY = "login"
LOGOUT_ACTIVITY = "logout"
JOB_VIEW_ACTIVITY = "job_view"
JOB_APPLY_ACTIVITY = "job_apply"
PROFILE_UPDATE_ACTIVITY = "profile_update"
SEARCH_ACTIVITY = "search"
MESSAGE_ACTIVITY = "message"


def track_user_login(user: User, ip_address: Optional[str] = None) -> None:
    """
    Track user login activity and update session data.

    Args:
        user: User instance
        ip_address: Optional IP address
    """
    try:
        # Record login activity
        UserActivityLog.objects.create(
            user=user, activity_type=LOGIN_ACTIVITY, ip_address=ip_address
        )

        # Record in gamification system
        UserActivity.objects.create(
            user=user,
            activity_type=LOGIN_ACTIVITY,
            details={"ip_address": ip_address},
            points_earned=10,
        )

        # Update last seen timestamp in cache
        cache.set(f"last_seen:{user.id}", time.time(), LAST_SEEN_TIMEOUT)

        # Start new session
        cache.set(f"session_start:{user.id}", time.time(), SESSION_TIMEOUT)

        # Increment login streak if applicable
        update_login_streak(user)

        logger.info(f"User {user.username} logged in from {ip_address}")
    except Exception as e:
        logger.error(f"Error tracking user login: {str(e)}")


def track_user_logout(user: User) -> None:
    """
    Track user logout activity and calculate session duration.

    Args:
        user: User instance
    """
    try:
        # Get session start time
        session_start = cache.get(f"session_start:{user.id}")

        if session_start:
            # Calculate session duration
            session_duration = time.time() - session_start

            # Record logout activity with session duration
            UserActivityLog.objects.create(
                user=user,
                activity_type=LOGOUT_ACTIVITY,
                ip_address=None,
                details={"session_duration": session_duration},
            )

            # Record in gamification system
            UserActivity.objects.create(
                user=user,
                activity_type=LOGOUT_ACTIVITY,
                details={"session_duration": session_duration},
                points_earned=0,
            )

            # Clear session data
            cache.delete(f"session_start:{user.id}")

            logger.info(
                f"User {user.username} logged out after {session_duration:.2f} seconds"
            )
        else:
            logger.warning(
                f"User {user.username} logged out but no session start time found"
            )
    except Exception as e:
        logger.error(f"Error tracking user logout: {str(e)}")


def track_user_activity(
    user: User,
    activity_type: str,
    details: Dict[str, Any] = None,
    ip_address: Optional[str] = None,
    points: int = 0,
) -> None:
    """
    Track general user activity.

    Args:
        user: User instance
        activity_type: Type of activity
        details: Optional activity details
        ip_address: Optional IP address
        points: Gamification points to award
    """
    try:
        # Record activity in log
        UserActivityLog.objects.create(
            user=user, activity_type=activity_type, ip_address=ip_address
        )

        # Record in gamification system if points are awarded
        if points > 0:
            UserActivity.objects.create(
                user=user,
                activity_type=activity_type,
                details=details or {},
                points_earned=points,
            )

        # Update last seen timestamp
        cache.set(f"last_seen:{user.id}", time.time(), LAST_SEEN_TIMEOUT)

        # Extend session timeout
        if cache.get(f"session_start:{user.id}"):
            cache.touch(f"session_start:{user.id}", SESSION_TIMEOUT)

        logger.debug(f"User {user.username} activity: {activity_type}")
    except Exception as e:
        logger.error(f"Error tracking user activity: {str(e)}")


def track_job_view(user: User, job_id: int) -> None:
    """
    Track when a user views a job.

    Args:
        user: User instance
        job_id: ID of the job being viewed
    """
    details = {"job_id": job_id}
    track_user_activity(user, JOB_VIEW_ACTIVITY, details, points=5)


def update_login_streak(user: User) -> None:
    """
    Update user login streak in gamification system.

    Args:
        user: User instance
    """
    try:
        # Get user points record
        user_points, created = UserPoints.objects.get_or_create(user=user)

        # Get current date
        today = timezone.now().date()

        # Check if last streak update was yesterday
        if user_points.last_streak_update == today - timedelta(days=1):
            # Increment streak
            user_points.streak_days += 1
            user_points.last_streak_update = today
            user_points.save(update_fields=["streak_days", "last_streak_update"])

            # Award bonus points for streak milestones
            if user_points.streak_days in [7, 30, 90, 180, 365]:
                bonus_points = (
                    user_points.streak_days // 7 * 10
                )  # 10 points per week of streak
                user_points.add_xp(bonus_points)

                logger.info(
                    f"User {user.username} reached {user_points.streak_days} day streak, awarded {bonus_points} bonus points"
                )
        elif user_points.last_streak_update < today - timedelta(days=1):
            # Reset streak if more than a day has passed
            user_points.streak_days = 1
            user_points.last_streak_update = today
            user_points.save(update_fields=["streak_days", "last_streak_update"])
        elif user_points.last_streak_update < today:
            # Update date without changing streak if same day
            user_points.last_streak_update = today
            user_points.save(update_fields=["last_streak_update"])
    except Exception as e:
        logger.error(f"Error updating login streak: {str(e)}")


def get_user_last_seen(user: User) -> Optional[float]:
    """
    Get timestamp when user was last seen.

    Args:
        user: User instance

    Returns:
        Timestamp or None if not available
    """
    return cache.get(f"last_seen:{user.id}")


def get_user_session_duration(user: User) -> Optional[float]:
    """
    Get current session duration for user.

    Args:
        user: User instance

    Returns:
        Session duration in seconds or None if not in session
    """
    session_start = cache.get(f"session_start:{user.id}")
    if session_start:
        return time.time() - session_start
    return None


def get_active_users(minutes: int = 15) -> List[int]:
    """
    Get list of active user IDs within the specified time window.

    Args:
        minutes: Time window in minutes

    Returns:
        List of active user IDs
    """
    active_users = []
    cutoff_time = time.time() - (minutes * 60)

    # This is inefficient but works for demonstration
    # In production, use Redis SCAN with pattern matching
    for user in User.objects.values_list("id", flat=True):
        last_seen = cache.get(f"last_seen:{user}")
        if last_seen and last_seen > cutoff_time:
            active_users.append(user)

    return active_users


def get_user_engagement_score(user: User) -> float:
    """
    Calculate user engagement score based on activity metrics.

    Args:
        user: User instance

    Returns:
        Engagement score between 0 and 1
    """
    # Try to get cached score first
    cache_key = f"engagement_score:{user.id}"
    cached_score = cache.get(cache_key)
    if cached_score is not None:
        return cached_score

    try:
        # Get activity counts for the last 30 days
        thirty_days_ago = timezone.now() - timedelta(days=30)

        # Get activity logs
        activity_logs = UserActivityLog.objects.filter(
            user=user, created_at__gte=thirty_days_ago
        )

        # Count different types of activities
        login_count = activity_logs.filter(activity_type=LOGIN_ACTIVITY).count()
        job_view_count = activity_logs.filter(activity_type=JOB_VIEW_ACTIVITY).count()
        job_apply_count = activity_logs.filter(activity_type=JOB_APPLY_ACTIVITY).count()
        profile_update_count = activity_logs.filter(
            activity_type=PROFILE_UPDATE_ACTIVITY
        ).count()
        search_count = activity_logs.filter(activity_type=SEARCH_ACTIVITY).count()
        message_count = activity_logs.filter(activity_type=MESSAGE_ACTIVITY).count()

        # Get total activity count
        total_activity_count = activity_logs.count()

        # Get user points and level
        try:
            user_points = UserPoints.objects.get(user=user)
            points = user_points.total_points
            level = user_points.level
            streak_days = user_points.streak_days
        except UserPoints.DoesNotExist:
            points = 0
            level = 1
            streak_days = 0

        # Calculate engagement metrics
        activity_frequency = min(
            total_activity_count / 60.0, 1.0
        )  # Max 60 activities in 30 days
        login_frequency = min(login_count / 30.0, 1.0)  # Max 30 logins in 30 days
        job_interaction = min(
            (job_view_count + job_apply_count * 3) / 50.0, 1.0
        )  # Weight applications higher
        profile_completeness = min(
            profile_update_count / 5.0, 1.0
        )  # Max 5 profile updates
        communication = min(message_count / 20.0, 1.0)  # Max 20 messages
        gamification_progress = (
            min((points / 1000.0) + (level / 10.0) + (streak_days / 30.0), 1.0) / 3.0
        )

        # Calculate weighted engagement score
        engagement_score = (
            activity_frequency * 0.2
            + login_frequency * 0.2
            + job_interaction * 0.25
            + profile_completeness * 0.1
            + communication * 0.15
            + gamification_progress * 0.1
        )

        # Cache the score
        cache.set(cache_key, engagement_score, ENGAGEMENT_SCORE_CACHE_TIMEOUT)

        return engagement_score
    except Exception as e:
        logger.error(f"Error calculating engagement score: {str(e)}")
        return 0.0


def get_user_activity_summary(user: User) -> Dict[str, Any]:
    """
    Get summary of user activity metrics.

    Args:
        user: User instance

    Returns:
        Dictionary with activity metrics
    """
    try:
        # Get last seen timestamp
        last_seen_timestamp = get_user_last_seen(user)
        last_seen = None
        if last_seen_timestamp:
            last_seen = datetime.fromtimestamp(last_seen_timestamp).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

        # Get current session duration
        session_duration = get_user_session_duration(user)

        # Get activity counts for different time periods
        today = timezone.now().date()
        today_start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        week_ago = today_start - timedelta(days=7)
        month_ago = today_start - timedelta(days=30)

        # Get activity logs
        all_logs = UserActivityLog.objects.filter(user=user)
        today_logs = all_logs.filter(created_at__gte=today_start)
        week_logs = all_logs.filter(created_at__gte=week_ago)
        month_logs = all_logs.filter(created_at__gte=month_ago)

        # Get user points
        try:
            user_points = UserPoints.objects.get(user=user)
            points = user_points.total_points
            level = user_points.level
            streak_days = user_points.streak_days
        except UserPoints.DoesNotExist:
            points = 0
            level = 1
            streak_days = 0

        # Calculate engagement score
        engagement_score = get_user_engagement_score(user)

        return {
            "user_id": user.id,
            "username": user.username,
            "last_seen": last_seen,
            "current_session_duration": session_duration,
            "activity_today": today_logs.count(),
            "activity_week": week_logs.count(),
            "activity_month": month_logs.count(),
            "total_activity": all_logs.count(),
            "login_count_month": month_logs.filter(
                activity_type=LOGIN_ACTIVITY
            ).count(),
            "job_views_month": month_logs.filter(
                activity_type=JOB_VIEW_ACTIVITY
            ).count(),
            "job_applications_month": month_logs.filter(
                activity_type=JOB_APPLY_ACTIVITY
            ).count(),
            "points": points,
            "level": level,
            "streak_days": streak_days,
            "engagement_score": engagement_score,
        }
    except Exception as e:
        logger.error(f"Error getting user activity summary: {str(e)}")
        return {"user_id": user.id, "username": user.username, "error": str(e)}




# # ==
# # 📌 User Activity Endpoints
# # ==

# @accounts_router.get(
#     "/active-users/{last_minutes}/",
#     tags=["User Activity"],
#     response={200: ActiveUsersResponse, 500: ErrorOut},
#     summary="Get active user IDs",
#     description="Get a list of user IDs that have been active within the specified time window"
# )
# @time_view("get_active_users_api")
# @cache_api_response(timeout=60)  # Cache for 1 minute
# def get_active_users_endpoint(request, last_minutes: int):
#     """
#     Get a list of user IDs that have been active within the specified time window.

#     Args:
#         last_minutes: Time window in minutes (e.g., 15 for users active in the last 15 minutes)

#     Returns:
#         200: List of active user IDs
#         500: Server error
#     """
#     # Start timing for telemetry
#     start_time = time.time()

#     try:
#         # Validate input
#         if last_minutes <= 0:
#             last_minutes = 15  # Default to 15 minutes if invalid

#         # Get active users
#         active_user_ids = get_active_users(last_minutes)

#         # Create response
#         response = ActiveUsersResponse(
#             active_user_ids=active_user_ids,
#             count=len(active_user_ids),
#             minutes=last_minutes
#         )

#         # Log telemetry for successful operation
#         log_operation(
#             operation="get_active_users",
#             key=f"active_users:{last_minutes}",
#             success=True,
#             duration_ms=(time.time() - start_time) * 1000,
#             context="API endpoint: /active-users/{last_minutes}"
#         )

#         return 200, response

#     except Exception as e:
#         # Log telemetry for error
#         log_operation(
#             operation="get_active_users",
#             key=f"active_users:{last_minutes}",
#             success=False,
#             duration_ms=(time.time() - start_time) * 1000,
#             context=f"API endpoint: /active-users/{last_minutes} - Error: {str(e)}"
#         )

#         logger.error(f"Error getting active users: {str(e)}")
#         return 500, ErrorOut(error=f"An error occurred: {str(e)}")


# @accounts_router.get(
#     "/users/{user_id}/last-seen/",
#     tags=["User Activity"],
#     response={200: LastSeenResponse, 404: ErrorOut, 500: ErrorOut},
#     summary="Get user last seen",
#     description="Get the timestamp when a user was last seen"
# )
# @time_view("get_user_last_seen_api")
# @cache_api_response(timeout=60)  # Cache for 1 minute
# def get_user_last_seen_endpoint(request, user_id: int):
#     """
#     Get the timestamp when a user was last seen.

#     Args:
#         user_id: User ID

#     Returns:
#         200: Last seen timestamp
#         404: User not found
#         500: Server error
#     """
#     # Start timing for telemetry
#     start_time = time.time()

#     try:
#         # Find the user
#         try:
#             user = User.objects.get(pk=user_id)
#         except User.DoesNotExist:
#             return 404, ErrorOut(error="User not found")

#         # Get last seen timestamp
#         last_seen_timestamp = get_user_last_seen(user)

#         # Format timestamp if available
#         last_seen_formatted = None
#         is_online = False

#         if last_seen_timestamp:
#             # Format timestamp
#             last_seen_formatted = datetime.fromtimestamp(last_seen_timestamp).strftime("%Y-%m-%d %H:%M:%S")

#             # Check if user is online (active in the last 5 minutes)
#             is_online = (time.time() - last_seen_timestamp) < (5 * 60)  # 5 minutes

#         # Create response
#         response = LastSeenResponse(
#             user_id=user_id,
#             last_seen_timestamp=last_seen_timestamp,
#             last_seen_formatted=last_seen_formatted,
#             is_online=is_online
#         )

#         # Log telemetry for successful operation
#         log_operation(
#             operation="get_user_last_seen",
#             key=f"last_seen:{user_id}",
#             success=True,
#             duration_ms=(time.time() - start_time) * 1000,
#             context="API endpoint: /users/{user_id}/last-seen"
#         )

#         return 200, response

#     except Exception as e:
#         pass
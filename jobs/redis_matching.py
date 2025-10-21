"""
Redis-based job matching utilities.

This module provides utilities for matching jobs with users based on various criteria,
using Redis for efficient storage and retrieval.
"""

import json
import logging
import math
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from django.conf import settings
from django.contrib.auth import get_user_model

from core.cache import (
    add_to_sorted_set,
    get_cached_data,
    get_sorted_set_range,
    publish_notification,
    set_cached_data,
)
from core.redis_lock import redis_lock
from core.redis_metrics import time_function

logger = logging.getLogger(__name__)

User = get_user_model()

# Constants
MATCH_EXPIRATION = 60 * 60 * 24 * 7  # 7 days
MATCH_SCORE_THRESHOLD = 0.5  # Minimum score for a match


class JobMatcher:
    """
    Redis-based job matching.
    
    This class provides methods for matching jobs with users based on various criteria,
    using Redis for efficient storage and retrieval.
    """
    
    def __init__(self, job_id: str, expiration: int = MATCH_EXPIRATION):
        """
        Initialize a job matcher.
        
        Args:
            job_id: Job ID
            expiration: Expiration time in seconds
        """
        self.job_id = job_id
        self.matches_key = f"job_matches:{job_id}"
        self.expiration = expiration
        
    @time_function("job_matching", "match_job")
    def match_job(self, job_data: Dict[str, Any], user_ids: Optional[List[str]] = None) -> int:
        """
        Match a job with users.
        
        Args:
            job_data: Job data
            user_ids: Optional list of user IDs to match with (if None, match with all users)
            
        Returns:
            Number of matches found
        """
        try:
            # Get users to match with
            if user_ids is None:
                # Get all users
                users = User.objects.filter(is_active=True)
                user_ids = [str(user.id) for user in users]
                
            # Match job with users
            match_count = 0
            for user_id in user_ids:
                try:
                    # Get user data
                    user = User.objects.get(id=user_id)
                    
                    # Calculate match score
                    score = self._calculate_match_score(job_data, user)
                    
                    # If score is above threshold, add to matches
                    if score >= MATCH_SCORE_THRESHOLD:
                        # Add to sorted set
                        add_to_sorted_set(
                            self.matches_key, 
                            user_id, 
                            score, 
                            expiration=self.expiration
                        )
                        
                        match_count += 1
                        
                        # Notify user of match
                        self._notify_user_of_match(user_id, job_data, score)
                except User.DoesNotExist:
                    logger.warning(f"User {user_id} not found")
                except Exception as e:
                    logger.error(f"Error matching job {self.job_id} with user {user_id}: {str(e)}")
                    
            logger.info(f"Matched job {self.job_id} with {match_count} users")
            return match_count
        except Exception as e:
            logger.error(f"Error matching job {self.job_id}: {str(e)}")
            return 0
            
    def get_matches(self, limit: int = 100) -> List[Tuple[str, float]]:
        """
        Get job matches.
        
        Args:
            limit: Maximum number of matches to return
            
        Returns:
            List of (user_id, score) tuples
        """
        try:
            return get_sorted_set_range(
                self.matches_key, 
                start=0, 
                end=limit - 1, 
                desc=True, 
                with_scores=True
            )
        except Exception as e:
            logger.error(f"Error getting matches for job {self.job_id}: {str(e)}")
            return []
            
    def get_top_matches(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get top job matches with user details.
        
        Args:
            limit: Maximum number of matches to return
            
        Returns:
            List of match dictionaries with user details
        """
        try:
            # Get matches from Redis
            matches = self.get_matches(limit)
            
            # Get user details
            result = []
            for user_id, score in matches:
                try:
                    user = User.objects.get(id=user_id)
                    
                    # Create match data
                    match_data = {
                        "user_id": user_id,
                        "username": user.username,
                        "score": score,
                    }
                    
                    # Add profile data if available
                    if hasattr(user, "profile"):
                        match_data["profile"] = {
                            "name": getattr(user.profile, "name", None),
                            "avatar": getattr(user.profile, "avatar", None),
                        }
                        
                    result.append(match_data)
                except User.DoesNotExist:
                    logger.warning(f"User {user_id} not found")
                    
            return result
        except Exception as e:
            logger.error(f"Error getting top matches for job {self.job_id}: {str(e)}")
            return []
            
    def _calculate_match_score(self, job_data: Dict[str, Any], user: User) -> float:
        """
        Calculate match score between a job and a user.
        
        Args:
            job_data: Job data
            user: User object
            
        Returns:
            Match score (0-1)
        """
        # This is a simplified example. In a real application, you would
        # implement a more sophisticated matching algorithm based on your
        # specific requirements.
        
        # Initialize score components
        skill_score = 0.0
        location_score = 0.0
        activity_score = 0.0
        
        # Calculate skill match
        if hasattr(user, "profile") and hasattr(user.profile, "skills"):
            user_skills = set(getattr(user.profile, "skills", []))
            job_skills = set(job_data.get("skills", []))
            
            if user_skills and job_skills:
                # Calculate Jaccard similarity
                intersection = len(user_skills.intersection(job_skills))
                union = len(user_skills.union(job_skills))
                
                if union > 0:
                    skill_score = intersection / union
                    
        # Calculate location match
        if hasattr(user, "profile") and hasattr(user.profile, "location"):
            user_location = getattr(user.profile, "location", None)
            job_location = job_data.get("location")
            
            if user_location and job_location:
                # Calculate distance (simplified)
                try:
                    user_lat = user_location.get("latitude")
                    user_lng = user_location.get("longitude")
                    job_lat = job_location.get("latitude")
                    job_lng = job_location.get("longitude")
                    
                    if user_lat and user_lng and job_lat and job_lng:
                        # Calculate distance using Haversine formula
                        distance = self._calculate_distance(
                            user_lat, user_lng, job_lat, job_lng
                        )
                        
                        # Convert distance to score (closer is better)
                        max_distance = 100  # km
                        location_score = max(0, 1 - (distance / max_distance))
                except Exception as e:
                    logger.error(f"Error calculating location score: {str(e)}")
                    
        # Calculate activity score
        if hasattr(user, "last_login") and user.last_login:
            # More recent activity is better
            days_since_login = (datetime.now() - user.last_login.replace(tzinfo=None)).days
            activity_score = max(0, 1 - (days_since_login / 30))  # 30 days max
            
        # Combine scores with weights
        weights = {
            "skill": 0.5,
            "location": 0.3,
            "activity": 0.2,
        }
        
        final_score = (
            skill_score * weights["skill"] +
            location_score * weights["location"] +
            activity_score * weights["activity"]
        )
        
        return final_score
        
    def _calculate_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """
        Calculate distance between two points using Haversine formula.
        
        Args:
            lat1: Latitude of point 1
            lng1: Longitude of point 1
            lat2: Latitude of point 2
            lng2: Longitude of point 2
            
        Returns:
            Distance in kilometers
        """
        # Convert to radians
        lat1_rad = math.radians(lat1)
        lng1_rad = math.radians(lng1)
        lat2_rad = math.radians(lat2)
        lng2_rad = math.radians(lng2)
        
        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlng = lng2_rad - lng1_rad
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        # Earth radius in kilometers
        radius = 6371
        
        # Calculate distance
        distance = radius * c
        
        return distance
        
    def _notify_user_of_match(self, user_id: str, job_data: Dict[str, Any], score: float) -> bool:
        """
        Notify a user of a job match.
        
        Args:
            user_id: User ID
            job_data: Job data
            score: Match score
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create notification data
            notification_data = {
                "type": "job_match",
                "job_id": self.job_id,
                "job_title": job_data.get("title"),
                "score": score,
                "timestamp": datetime.now().isoformat(),
            }
            
            # Publish notification
            return publish_notification(
                f"user:{user_id}:notifications",
                notification_data
            )
        except Exception as e:
            logger.error(f"Error notifying user {user_id} of job match: {str(e)}")
            return False


class UserJobMatcher:
    """
    Redis-based user-job matching.
    
    This class provides methods for matching users with jobs based on various criteria,
    using Redis for efficient storage and retrieval.
    """
    
    def __init__(self, user_id: str, expiration: int = MATCH_EXPIRATION):
        """
        Initialize a user-job matcher.
        
        Args:
            user_id: User ID
            expiration: Expiration time in seconds
        """
        self.user_id = user_id
        self.matches_key = f"user_job_matches:{user_id}"
        self.expiration = expiration
        
    @time_function("job_matching", "match_user")
    def match_user(self, user_data: Dict[str, Any], job_ids: Optional[List[str]] = None) -> int:
        """
        Match a user with jobs.
        
        Args:
            user_data: User data
            job_ids: Optional list of job IDs to match with (if None, match with all jobs)
            
        Returns:
            Number of matches found
        """
        try:
            # Get jobs to match with
            if job_ids is None:
                # Get all jobs
                from jobs.models import Job
                jobs = Job.objects.filter(is_active=True)
                job_ids = [str(job.id) for job in jobs]
                
            # Match user with jobs
            match_count = 0
            for job_id in job_ids:
                try:
                    # Get job data
                    from jobs.models import Job
                    job = Job.objects.get(id=job_id)
                    
                    # Convert job to dictionary
                    job_data = {
                        "id": job.id,
                        "title": job.title,
                        "description": job.description,
                        "skills": job.skills,
                        "location": job.location,
                    }
                    
                    # Calculate match score
                    matcher = JobMatcher(job_id)
                    score = matcher._calculate_match_score(job_data, User.objects.get(id=self.user_id))
                    
                    # If score is above threshold, add to matches
                    if score >= MATCH_SCORE_THRESHOLD:
                        # Add to sorted set
                        add_to_sorted_set(
                            self.matches_key, 
                            job_id, 
                            score, 
                            expiration=self.expiration
                        )
                        
                        match_count += 1
                        
                        # Notify user of match
                        self._notify_user_of_match(job_data, score)
                except Job.DoesNotExist:
                    logger.warning(f"Job {job_id} not found")
                except Exception as e:
                    logger.error(f"Error matching user {self.user_id} with job {job_id}: {str(e)}")
                    
            logger.info(f"Matched user {self.user_id} with {match_count} jobs")
            return match_count
        except Exception as e:
            logger.error(f"Error matching user {self.user_id}: {str(e)}")
            return 0
            
    def get_matches(self, limit: int = 100) -> List[Tuple[str, float]]:
        """
        Get user-job matches.
        
        Args:
            limit: Maximum number of matches to return
            
        Returns:
            List of (job_id, score) tuples
        """
        try:
            return get_sorted_set_range(
                self.matches_key, 
                start=0, 
                end=limit - 1, 
                desc=True, 
                with_scores=True
            )
        except Exception as e:
            logger.error(f"Error getting matches for user {self.user_id}: {str(e)}")
            return []
            
    def get_top_matches(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get top user-job matches with job details.
        
        Args:
            limit: Maximum number of matches to return
            
        Returns:
            List of match dictionaries with job details
        """
        try:
            # Get matches from Redis
            matches = self.get_matches(limit)
            
            # Get job details
            result = []
            for job_id, score in matches:
                try:
                    from jobs.models import Job
                    job = Job.objects.get(id=job_id)
                    
                    # Create match data
                    match_data = {
                        "job_id": job_id,
                        "title": job.title,
                        "description": job.description,
                        "score": score,
                    }
                    
                    result.append(match_data)
                except Job.DoesNotExist:
                    logger.warning(f"Job {job_id} not found")
                    
            return result
        except Exception as e:
            logger.error(f"Error getting top matches for user {self.user_id}: {str(e)}")
            return []
            
    def _notify_user_of_match(self, job_data: Dict[str, Any], score: float) -> bool:
        """
        Notify a user of a job match.
        
        Args:
            job_data: Job data
            score: Match score
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create notification data
            notification_data = {
                "type": "job_match",
                "job_id": job_data.get("id"),
                "job_title": job_data.get("title"),
                "score": score,
                "timestamp": datetime.now().isoformat(),
            }
            
            # Publish notification
            return publish_notification(
                f"user:{self.user_id}:notifications",
                notification_data
            )
        except Exception as e:
            logger.error(f"Error notifying user {self.user_id} of job match: {str(e)}")
            return False


def match_job_with_users(job_id: str, job_data: Dict[str, Any], user_ids: Optional[List[str]] = None) -> int:
    """
    Match a job with users.
    
    Args:
        job_id: Job ID
        job_data: Job data
        user_ids: Optional list of user IDs to match with (if None, match with all users)
        
    Returns:
        Number of matches found
    """
    matcher = JobMatcher(job_id)
    return matcher.match_job(job_data, user_ids)


def match_user_with_jobs(user_id: str, user_data: Dict[str, Any], job_ids: Optional[List[str]] = None) -> int:
    """
    Match a user with jobs.
    
    Args:
        user_id: User ID
        user_data: User data
        job_ids: Optional list of job IDs to match with (if None, match with all jobs)
        
    Returns:
        Number of matches found
    """
    matcher = UserJobMatcher(user_id)
    return matcher.match_user(user_data, job_ids)


def get_job_matches(job_id: str, limit: int = 100) -> List[Tuple[str, float]]:
    """
    Get job matches.
    
    Args:
        job_id: Job ID
        limit: Maximum number of matches to return
        
    Returns:
        List of (user_id, score) tuples
    """
    matcher = JobMatcher(job_id)
    return matcher.get_matches(limit)


def get_user_job_matches(user_id: str, limit: int = 100) -> List[Tuple[str, float]]:
    """
    Get user-job matches.
    
    Args:
        user_id: User ID
        limit: Maximum number of matches to return
        
    Returns:
        List of (job_id, score) tuples
    """
    matcher = UserJobMatcher(user_id)
    return matcher.get_matches(limit)


def get_top_job_matches(job_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get top job matches with user details.
    
    Args:
        job_id: Job ID
        limit: Maximum number of matches to return
        
    Returns:
        List of match dictionaries with user details
    """
    matcher = JobMatcher(job_id)
    return matcher.get_top_matches(limit)


def get_top_user_job_matches(user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get top user-job matches with job details.
    
    Args:
        user_id: User ID
        limit: Maximum number of matches to return
        
    Returns:
        List of match dictionaries with job details
    """
    matcher = UserJobMatcher(user_id)
    return matcher.get_top_matches(limit)

"""
Redis-based leaderboard and ranking utilities.

This module provides utilities for creating and managing leaderboards
and rankings using Redis sorted sets.
"""

import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union

from core.cache import (
    add_to_sorted_set,
    get_sorted_set_range,
    get_sorted_set_rank,
)

logger = logging.getLogger(__name__)

# Constants
LEADERBOARD_EXPIRATION = 60 * 60 * 24 * 7  # 7 days


class Leaderboard:
    """
    Redis-based leaderboard.
    
    This class provides methods for creating and managing leaderboards
    using Redis sorted sets.
    """
    
    def __init__(self, name: str, expiration: int = LEADERBOARD_EXPIRATION):
        """
        Initialize a leaderboard.
        
        Args:
            name: Name of the leaderboard
            expiration: Expiration time in seconds
        """
        self.name = name
        self.key = f"leaderboard:{name}"
        self.expiration = expiration
        
    def add_score(self, member: str, score: float, increment: bool = False) -> bool:
        """
        Add a score to the leaderboard.
        
        Args:
            member: Member ID or name
            score: Score to add
            increment: Whether to increment the existing score
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if increment:
                # Get current score
                current_score = 0
                rankings = get_sorted_set_range(
                    self.key, 
                    start=0, 
                    end=-1, 
                    desc=True, 
                    with_scores=True
                )
                
                for m, s in rankings:
                    if m == str(member):
                        current_score = s
                        break
                        
                # Increment score
                score = current_score + score
                
            # Add to sorted set
            return add_to_sorted_set(
                self.key, 
                str(member), 
                score, 
                expiration=self.expiration
            )
        except Exception as e:
            logger.error(f"Error adding score to leaderboard {self.name}: {str(e)}")
            return False
            
    def get_rank(self, member: str) -> Optional[int]:
        """
        Get the rank of a member.
        
        Args:
            member: Member ID or name
            
        Returns:
            Rank of the member (0-based) or None if not found
        """
        try:
            return get_sorted_set_rank(self.key, str(member))
        except Exception as e:
            logger.error(f"Error getting rank from leaderboard {self.name}: {str(e)}")
            return None
            
    def get_score(self, member: str) -> Optional[float]:
        """
        Get the score of a member.
        
        Args:
            member: Member ID or name
            
        Returns:
            Score of the member or None if not found
        """
        try:
            # Get member's score
            rankings = get_sorted_set_range(
                self.key, 
                start=0, 
                end=-1, 
                desc=True, 
                with_scores=True
            )
            
            for m, score in rankings:
                if m == str(member):
                    return score
                    
            return None
        except Exception as e:
            logger.error(f"Error getting score from leaderboard {self.name}: {str(e)}")
            return None
            
    def get_top(self, limit: int = 10) -> List[Tuple[str, float]]:
        """
        Get the top members.
        
        Args:
            limit: Maximum number of members to return
            
        Returns:
            List of (member, score) tuples
        """
        try:
            return get_sorted_set_range(
                self.key, 
                start=0, 
                end=limit - 1, 
                desc=True, 
                with_scores=True
            )
        except Exception as e:
            logger.error(f"Error getting top from leaderboard {self.name}: {str(e)}")
            return []
            
    def get_around(self, member: str, radius: int = 2) -> List[Tuple[str, float]]:
        """
        Get members around a specific member.
        
        Args:
            member: Member ID or name
            radius: Number of members to include on each side
            
        Returns:
            List of (member, score) tuples
        """
        try:
            # Get member's rank
            rank = self.get_rank(member)
            if rank is None:
                return []
                
            # Get members around
            start = max(0, rank - radius)
            end = rank + radius
            
            return get_sorted_set_range(
                self.key, 
                start=start, 
                end=end, 
                desc=True, 
                with_scores=True
            )
        except Exception as e:
            logger.error(f"Error getting around from leaderboard {self.name}: {str(e)}")
            return []
            
    def get_range(self, start: int = 0, end: int = -1) -> List[Tuple[str, float]]:
        """
        Get a range of members.
        
        Args:
            start: Start index (0-based)
            end: End index (-1 for all)
            
        Returns:
            List of (member, score) tuples
        """
        try:
            return get_sorted_set_range(
                self.key, 
                start=start, 
                end=end, 
                desc=True, 
                with_scores=True
            )
        except Exception as e:
            logger.error(f"Error getting range from leaderboard {self.name}: {str(e)}")
            return []


def get_leaderboard(name: str) -> Leaderboard:
    """
    Get a leaderboard.
    
    Args:
        name: Name of the leaderboard
        
    Returns:
        Leaderboard instance
    """
    return Leaderboard(name)


def add_to_leaderboard(name: str, member: str, score: float, increment: bool = False) -> bool:
    """
    Add a score to a leaderboard.
    
    Args:
        name: Name of the leaderboard
        member: Member ID or name
        score: Score to add
        increment: Whether to increment the existing score
        
    Returns:
        True if successful, False otherwise
    """
    leaderboard = get_leaderboard(name)
    return leaderboard.add_score(member, score, increment)


def get_top_from_leaderboard(name: str, limit: int = 10) -> List[Tuple[str, float]]:
    """
    Get the top members from a leaderboard.
    
    Args:
        name: Name of the leaderboard
        limit: Maximum number of members to return
        
    Returns:
        List of (member, score) tuples
    """
    leaderboard = get_leaderboard(name)
    return leaderboard.get_top(limit)


def get_rank_in_leaderboard(name: str, member: str) -> Optional[int]:
    """
    Get the rank of a member in a leaderboard.
    
    Args:
        name: Name of the leaderboard
        member: Member ID or name
        
    Returns:
        Rank of the member (0-based) or None if not found
    """
    leaderboard = get_leaderboard(name)
    return leaderboard.get_rank(member)

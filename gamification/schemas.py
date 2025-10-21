# ==
# 📌 Python Standard Library
# ==
from datetime import datetime
from enum import Enum
from typing import List, Optional

# ==
# 📌 Ninja Framework
# ==
from ninja.orm import create_schema

# ==
# 📌 Pydantic Core
# ==
from pydantic import BaseModel, EmailStr, Field

# ==
# 📌 Local Imports
# ==
from core.schema_utils import HashableSchema
from gamification.models import (Achievement, Badge, RewardItem, UserPoints,
                                 UserReward)

# -------------------------------------------------------
# FEEDBACK & GAMIFICATION SCHEMAS
# -------------------------------------------------------


class FeedbackSchema(BaseModel):
    """Schema for user feedback submission"""

    message: str = Field(
        ..., min_length=5, max_length=1000, description="Detailed feedback message"
    )
    rating: Optional[int] = Field(5, ge=1, le=5, description="Rating from 1 to 5 stars")
    category: Optional[str] = Field(
        "general",
        pattern="^(general|bug|suggestion|compliment)$",
        description="Feedback category",
    )
    contact_email: Optional[EmailStr] = Field(
        None, description="Optional contact email"
    )


class BadgeType(str, Enum):
    """Types of badges available"""

    SKILL = "skill"
    ACTIVITY = "activity"
    MILESTONE = "milestone"
    SPECIAL = "special"


class AchievementType(str, Enum):
    """Types of achievements available"""

    JOB = "job"
    REVIEW = "review"
    PROGRESS = "progress"
    COMMUNITY = "community"


class BadgeSchema(HashableSchema):
    """Schema for badge definition"""

    id: int
    name: str = Field(..., max_length=100)
    description: str = Field(..., max_length=500)
    badge_type: BadgeType
    icon: Optional[str] = Field(None, description="URL to badge icon image")
    points: int = Field(..., ge=0, description="Points awarded for earning this badge")
    criteria: dict = Field(..., description="Criteria needed to earn this badge")
    is_active: bool = Field(True, description="Whether badge is currently earnable")
    created_at: datetime
    updated_at: Optional[datetime] = None


class UserBadgeSchema(HashableSchema):
    """Schema for user's earned badges"""

    id: int
    user_id: int
    badge: BadgeSchema
    earned_at: datetime
    progress: dict = Field(
        default_factory=dict, description="Current progress towards badge criteria"
    )
    is_notified: bool = Field(
        False, description="Whether user has been notified about this badge"
    )
    is_featured: bool = Field(
        False, description="Whether user has featured this badge on profile"
    )


class AchievementSchema(HashableSchema):
    """Schema for achievement definition"""

    id: int
    name: str = Field(..., max_length=100)
    description: str = Field(..., max_length=500)
    achievement_type: AchievementType
    icon: Optional[str] = Field(None, description="URL to achievement icon image")
    points: int = Field(..., ge=0, description="Points awarded for this achievement")
    criteria: dict = Field(
        ..., description="Criteria needed to unlock this achievement"
    )
    is_active: bool = Field(
        True, description="Whether achievement is currently available"
    )
    created_at: datetime
    updated_at: Optional[datetime] = None


class UserAchievementSchema(HashableSchema):
    """Schema for user's unlocked achievements"""

    id: int
    user_id: int
    achievement: AchievementSchema
    unlocked_at: datetime
    progress: dict = Field(
        default_factory=dict,
        description="Current progress towards achievement criteria",
    )
    is_notified: bool = Field(
        False, description="Whether user has been notified about this achievement"
    )
    is_featured: bool = Field(
        False, description="Whether user has featured this achievement on profile"
    )


class UserPointsSchema(HashableSchema):
    """Schema for tracking user's gamification points"""

    user_id: int
    total_points: int = Field(..., ge=0, description="Lifetime accumulated points")
    current_level: int = Field(..., ge=1, description="Current user level")
    points_to_next_level: int = Field(
        ..., ge=0, description="Points needed to reach next level"
    )
    last_level_up: Optional[datetime] = Field(
        None, description="When user last leveled up"
    )
    updated_at: datetime
    level_progress: float = Field(
        ..., ge=0, le=1, description="Progress to next level (0-1)"
    )


class GamificationProgressSchema(HashableSchema):
    """Complete gamification profile for a user"""

    badges: List[UserBadgeSchema] = Field(
        default_factory=list, description="All earned badges"
    )
    achievements: List[UserAchievementSchema] = Field(
        default_factory=list, description="All unlocked achievements"
    )
    points: UserPointsSchema
    recent_activity: List[dict] = Field(
        default_factory=list, description="Recent gamification events"
    )
    next_milestones: List[dict] = Field(
        default_factory=list, description="Upcoming achievable milestones"
    )


class CheckAchievementsRequestSchema(HashableSchema):
    """Request schema for checking achievement progress"""

    user_id: int = Field(
        ..., gt=0, description="ID of the user to check achievements for"
    )
    force_recalculation: bool = Field(
        False, description="Whether to force a full progress recalculation"
    )


class CheckBadgesRequestSchema(HashableSchema):
    """Request schema for checking badge progress"""

    user_id: int = Field(..., gt=0, description="ID of the user to check badges for")
    force_recalculation: bool = Field(
        False, description="Whether to force a full progress recalculation"
    )


class AchievementProgressSchema(HashableSchema):
    """Detailed progress for a specific achievement"""

    user_id: int
    achievement_id: int
    achievement_name: str
    progress: dict
    is_completed: bool
    completion_percentage: float = Field(..., ge=0, le=1)
    last_updated: datetime
    estimated_completion: Optional[datetime] = Field(
        None, description="Estimated completion time based on current rate"
    )


class BadgeProgressSchema(HashableSchema):
    """Detailed progress for a specific badge"""

    user_id: int
    badge_id: int
    badge_name: str
    progress: dict
    is_completed: bool
    completion_percentage: float = Field(..., ge=0, le=1)
    last_updated: datetime
    missing_requirements: List[str] = Field(
        default_factory=list, description="List of unmet criteria"
    )


class LevelUpSchema(HashableSchema):
    """Schema for level up events"""

    user_id: int
    previous_level: int = Field(..., ge=0, description="Level before this upgrade")
    current_level: int = Field(..., gt=0, description="New current level")
    points_to_next_level: int = Field(
        ..., ge=0, description="Points needed for next level"
    )
    total_points: int = Field(..., ge=0, description="Total accumulated points")
    last_level_up: datetime
    rewards: List[dict] = Field(
        default_factory=list, description="Rewards earned with this level up"
    )
    unlocked_features: List[str] = Field(
        default_factory=list, description="New features unlocked"
    )


class GamificationEventSchema(HashableSchema):
    """Schema for gamification events/notifications"""

    event_id: int
    user_id: int
    event_type: str = Field(..., pattern="^(badge|achievement|level|point)$")
    event_data: dict
    created_at: datetime
    is_read: bool = Field(False)
    is_celebrated: bool = Field(
        False, description="Whether user has viewed celebration"
    )


class LeaderboardEntrySchema(HashableSchema):
    """Schema for leaderboard entries"""

    user_id: int
    username: str
    profile_pic: Optional[str]
    level: int
    points: int
    position: int
    progress: float
    badges_count: int
    achievements_count: int


# Create schemas from models using Django Ninja's create_schema
GamificationUserPointsSchema = create_schema(
    UserPoints, name="GamificationUserPointsSchema"
)

GamificationAchievementSchema = create_schema(
    Achievement, name="GamificationAchievementSchema"
)


# For nested schemas, we need to define them explicitly
class GamificationUserAchievementSchema(HashableSchema):
    achievement: dict  # Will contain the achievement data
    unlocked_at: str


# Create schemas for the remaining models
GamificationBadgeSchema = create_schema(Badge, name="GamificationBadgeSchema")
GamificationRewardItemSchema = create_schema(
    RewardItem, name="GamificationRewardItemSchema"
)
UserRewardSchema = create_schema(UserReward, name="UserRewardSchema")

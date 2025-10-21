from datetime import datetime
from typing import List, Optional

from ninja import Schema, UploadedFile
from ninja.orm import create_schema
from pydantic import Field, field_validator

from core.schema_utils import HashableSchema

# == Base Schemas == #


class SuccessMessageSchema(HashableSchema):
    message: str


class Coordinates(HashableSchema):
    lat: float
    lng: float


class AddressResponse(HashableSchema):
    formatted_address: str
    street_address: str
    city: str
    state: str
    country: str


# == Location Schemas == #


class LocationSchema(HashableSchema):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    address: Optional[str] = None


class LocationCreateSchema(LocationSchema):
    pass  # Inherits everything from LocationSchema


# == Gamification Schemas == #

from gamification.models import (Achievement, Badge, RewardItem, Team,
                                 UserAchievement, UserPoints)

UserPointsSchema = create_schema(
    UserPoints, fields=["total_points", "level", "xp_to_next", "streak_days"]
)


class BadgeSchema(
    create_schema(
        Badge,
        fields=[
            "code",
            "name",
            "description",
            "tier",
            "image",
            "points",
            "share_message",
        ],
    )
):
    pass


class AchievementSchema(
    create_schema(
        Achievement,
        fields=[
            "code",
            "name",
            "description",
            "achievement_type",
            "points",
            "is_secret",
            "animation",
        ],
    )
):
    badge: Optional[BadgeSchema] = None  # Nested badge


class UserAchievementSchema(
    create_schema(UserAchievement, fields=["unlocked_at", "progress"])
):
    achievement: AchievementSchema


class RewardItemSchema(
    create_schema(
        RewardItem, fields=["name", "description", "cost", "reward_type", "image"]
    )
):
    is_available: bool = True


class TeamSchema(create_schema(Team, fields=["name", "invite_code", "created_at"])):
    pass


# == Leaderboard Schemas == #


class LeaderboardEntry(HashableSchema):
    user_id: int
    username: str
    avatar: Optional[str]
    points: int
    level: int
    position: int
    region: Optional[str]


class LeaderboardSchema(HashableSchema):
    leaderboard_type: str  # weekly, monthly, region-based etc.
    region: Optional[str]
    industry: Optional[str]
    entries: List[LeaderboardEntry]
    generated_at: datetime
    time_remaining: str


# == Social Sharing Schema == #


class SocialShareRequest(HashableSchema):
    user_id: int  # Comes from authenticated request or explicitly in POST
    achievement_id: Optional[int] = None
    badge_id: Optional[int] = None
    platform: str  # 'twitter', 'facebook', 'whatsapp'

    @field_validator("platform")
    def validate_platform(cls, v, info):
        if v not in {"twitter", "facebook", "whatsapp"}:
            raise ValueError("Platform must be 'twitter', 'facebook', or 'whatsapp'")
        return v

from datetime import datetime
from typing import Dict, Union, List, Optional

from ninja import Schema
from pydantic import BaseModel, Field


# ==
# 📌 Feedback Schemas
# ==
class FeedbackSchema(BaseModel):
    """
    Schema for user feedback submission with rating
    Includes validation for rating range and required fields
    """

    sender_user_id: int = Field(
        ..., gt=0, description="ID of the user sending the feedback"
    )

    message: str = Field(
        ..., min_length=10, max_length=1000, description="Detailed feedback message"
    )
    rating: int = Field(..., ge=1, le=5, description="Rating score (1-5 stars)")
    category: Optional[str] = Field(
        None,
        description="Optional feedback category",
        examples=["service", "communication", "professionalism"],
    )


class CompanyFeedbackSchema(BaseModel):
    """
    Schema for company feedback submission
    Company is automatically set as the receiver
    """
    user_id: Optional[int] = Field(
        None, gt=0, description="ID of the user sending the feedback (optional)"
    )
    message: str = Field(
        ..., min_length=10, max_length=1000, description="Detailed feedback message"
    )
    rating: int = Field(..., ge=1, le=5, description="Rating score (1-5 stars)")
    category: str = Field(
        "general", description="Feedback category",
        examples=["general", "bug", "feature", "ui", "other"]
    )


class FeedbackResponseSchema(Schema):
    """
    Response schema for feedback submission
    """
    message: str = "Feedback submitted successfully"
    feedback_id: int
    rating: int
    category: str
    created_at: str  # ISO format datetime


class AdminNotesSchema(BaseModel):
    """
    Schema for admin notes when resolving feedback
    """
    admin_notes: Optional[str] = Field(
        None, max_length=1000, description="Admin notes about the resolution"
    )


# ==
# 📌 Review Schemas
# ==
class ReviewSchema(Schema):
    """
    Complete review data including timestamps
    Used for review retrieval responses
    """

    id: int
    reviewer_id: int
    reviewed_id: int
    job_id: Optional[int]
    rating: float = Field(..., ge=1, le=5)
    feedback: Optional[str] = Field(None, max_length=500)
    created_at: datetime
    updated_at: Optional[datetime]
    reviewer_name: str
    reviewer_avatar: Optional[str]


class ReviewCreateSchema(Schema):
    sender_id: int
    receiver_id: Union[int, List[int]]  # single or multiple users
    rating: int
    feedback: Optional[str] = None
    job_id: Optional[int] = None

class RatingResultSchema(Schema):
    receiver_id: int
    status: str
    rating_id: Optional[int] = None
    message: str

class ReviewCreatedResponseSchema(Schema):
    results: List[RatingResultSchema]






class ReviewUpdateSchema(Schema):
    """
    Schema for updating existing reviews
    """

    rating: Optional[float] = Field(None, ge=1, le=5)
    feedback: Optional[str] = Field(None, max_length=500)






class MarkReadSchema(BaseModel):
    user_id: int
    review_id: int

class MarkReadResponseSchema(BaseModel):
    status: str
    message: str


class ReviewUpdateSchema(BaseModel):
    user_id: int
    review_id: int
    rating: Optional[float] = None
    feedback: Optional[str] = None

class UpdatedReviewSchema(BaseModel):
    id: int
    rating: float
    feedback: str
    sentiment: str
    review_type: str
    updated_at: str

class UpdateRatingResponseSchema(BaseModel):
    status: str
    message: str
    review: UpdatedReviewSchema





# ==
# 📌 Error Response Schemas
# ==
class ErrorResponseSchema(Schema):
    """
    Standard error response schema
    """
    error: str
    details: Optional[str] = None
    resolution: Optional[str] = None


class UnauthorizedResponseSchema(Schema):
    """
    Unauthorized error response schema
    """
    error: str = "Authentication required"
    details: str = "You must be logged in to access this resource"

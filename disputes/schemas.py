from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional

from ninja import Schema, UploadedFile
from pydantic import BaseModel, EmailStr, Field, validator

from jobs.schemas import UserSchema


# -------------------------------------------------------
# ENUMS
# -------------------------------------------------------
class JobStatusEnum(str, Enum):
    PENDING = "pending"
    UPCOMING = "upcoming"
    ONGOING = "ongoing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class ApplicationStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ONGOING = "ongoing"
    COMPLETED = "completed"


class JobType(str, Enum):
    SINGLE_DAY = "single_day"
    MULTIPLE_DAYS = "multiple_days"


class ShiftType(str, Enum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    NIGHT = "night"


class DisputeStatus(str, Enum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    REJECTED = "rejected"


# -------------------------------------------------------
# ERROR / SUCCESS SCHEMAS
# -------------------------------------------------------
class ErrorResponseSchema(Schema):
    error: str
    details: Optional[str] = None
    resolution: Optional[str] = None


class ConflictResponseSchema(ErrorResponseSchema):
    resolution: str


class UnauthorizedResponseSchema(ErrorResponseSchema):
    pass


class SuccessMessageSchema(Schema):
    message: str


class SuccessResponseSchema(Schema):
    message: str


# -------------------------------------------------------
# LOCATION SCHEMA
# -------------------------------------------------------
class LocationSchema(Schema):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    address: Optional[str] = None


# -------------------------------------------------------
# AUTH & USER SCHEMAS
# -------------------------------------------------------
class UserBaseSchema(Schema):
    id: int
    first_name: str
    last_name: str
    email: str


class LoginSchema(Schema):
    email: str
    password: str


class SignupSchema(Schema):
    first_name: str
    last_name: str
    email: str
    password: str
    confirm_password: str
    role: str


class PasswordResetSchema(BaseModel):
    user_id: str
    old_password: str
    new_password: str


class PasswordResetRequestSchema(Schema):
    email: str


# -------------------------------------------------------
# PROFILE SCHEMA
# -------------------------------------------------------


class UserSchema(BaseModel):
    id: int
    username: str
    email: str
    first_name: str
    last_name: str


class UserProfileSchema(BaseModel):
    user: UserSchema
    profile_pic_url: Optional[str] = None
    phone_number: Optional[str] = None
    location: Optional[LocationSchema] = None
    wallet_balance: Decimal = Decimal("0.00")
    rating: Optional[float] = None
    jobs_completed: int = 0
    created_at: datetime
    balance: int


class UserProfileUpdateSchema(Schema):
    user_id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None  # Email validation
    profile_pic: Optional[
        UploadedFile
    ] = None  # This will handle file uploads (profile picture)

    email: Optional[EmailStr] = None  # Email validation
    profile_pic: Optional[
        UploadedFile
    ] = None  # This will handle file uploads (profile picture)


# -------------------------------------------------------
# INDUSTRY / CATEGORY SCHEMA
# -------------------------------------------------------
class IndustrySchema(Schema):
    id: int
    name: str


class SubCategorySchema(Schema):
    id: int
    name: str
    industry_id: int
    industry_name: str


# -------------------------------------------------------
# JOB SCHEMAS
# -------------------------------------------------------
class JobListSchema(Schema):
    id: int
    title: str
    description: Optional[str] = ""
    employer_name: str
    status: str
    date: Optional[str] = None
    time: Optional[str] = None
    duration: Optional[str] = "0 hrs"
    amount: Decimal = Decimal("0.0")
    image: Optional[str] = None
    location: Optional[str] = None
    date_posted: str
    no_of_application: int
    latitude: Optional[float] = 0.0
    longitude: Optional[float] = 0.0
    is_shift_ongoing: bool = False
    updated_at: Optional[str] = None
    applicants_needed: int = 0
    job_type: Optional[str] = "Unknown"
    shift_type: Optional[str] = "Unknown"
    payment_status: Optional[str] = "Pending"
    total_amount: Decimal = Decimal("0.0")
    service_fee: Decimal = Decimal("0.0")
    start_date: Optional[str] = None
    start_time_str: Optional[str] = None
    end_time_str: Optional[str] = None


class JobDetailSchema(Schema):
    id: int
    title: str
    description: str
    status: str
    date: Optional[date]
    start_time: Optional[time]
    end_time: Optional[time]
    duration: str
    rate: str
    location: str
    latitude: Optional[float]
    longitude: Optional[float]
    is_shift_ongoing: Optional[bool] = None
    employer_name: str
    date_posted: Optional[datetime]
    updated_at: Optional[datetime]
    applicants_needed: int
    job_type: str
    shift_type: str
    payment_status: str
    total_amount: str
    service_fee: str
    start_date: Optional[str] = None

    start_time_str: Optional[str]
    end_time_str: Optional[str]
    # Human-friendly display fields
    date_posted: Optional[str] = None
    date_human: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    updated_at: Optional[str] = None
    start_time_human: Optional[str] = None
    end_time_human: Optional[str] = None

    # Date flags
    is_today: bool = False
    is_yesterday: bool = False
    is_this_week: bool = False
    is_this_month: bool = False

    applicants_count: int = 0
    applicants_user_ids: List[int] = []
    updated_at_human: Optional[str] = None


class CreateJobSchema(Schema):
    user_id: int
    title: str
    industry: int
    subcategory: str
    applicants_needed: int
    job_type: JobType
    shift_type: ShiftType
    date: str
    start_time: str
    end_time: str
    rate: float
    location: str


class JobCreatedResponseSchema(Schema):
    message: str
    job_id: int
    transaction_ref: str
    duration_hours: float
    employer: str


class JobCancellationSuccessSchema(Schema):
    message: str
    job_id: int
    new_status: JobStatusEnum
    job_details: Dict[str, Optional[object]]


# -------------------------------------------------------
# APPLICATION SCHEMAS
# -------------------------------------------------------


class ApplyJobResponse(Schema):
    detail: str


class ApplyJobSchema(Schema):
    user_id: int = Field(..., gt=0, description="ID of the user applying for the job.")
    job_id: int = Field(..., gt=0, description="ID of the job being applied for.")


class ApplicationListSchema(Schema):
    id: int
    job_id: int
    applicant_name: str
    is_accepted: bool
    applied_at: datetime


class ApplicantReviewSchema(Schema):
    applicant_id: int


# -------------------------------------------------------
# SAVED JOBS SCHEMAS
# -------------------------------------------------------
from pydantic import BaseModel, root_validator, validator


class SaveJobRequestSchema(BaseModel):
    user_id: int
    job_id: int


class UnsaveJobRequestSchema(Schema):
    user_id: int
    job_id: int


class SuccessMessageSchema(BaseModel):
    message: str


class SavedJobResponseSchema(BaseModel):
    saved_job_id: int
    job_id: int
    job_title: str
    employer: str
    saved_at: str
    message: str


class SuccessMessageSchema(BaseModel):
    message: str


class ErrorMessageSchema(BaseModel):
    error: str


# -------------------------------------------------------
# PAYMENT SCHEMAS
# -------------------------------------------------------
class PaymentSchema(Schema):
    job_id: int
    total: Decimal


class PaymentDetailSchema(Schema):
    id: int
    payer_name: str
    recipient_name: Optional[str] = None
    original_amount: Decimal
    service_fee: Decimal
    final_amount: Decimal
    payment_status: str
    created_at: datetime


class PaymentCreateSchema(Schema):
    user: UserSchema


class PaymentUpdateSchema(Schema):
    user: UserSchema


# -------------------------------------------------------
# REVIEW SCHEMAS
# -------------------------------------------------------
class ReviewSchema(Schema):
    reviewer_id: int
    reviewed_id: int
    rating: float
    feedback: Optional[str] = None
    created_at: datetime


class ReviewCreateSchema(Schema):
    reviewed_id: int
    job_id: Optional[int] = None
    rating: float = Field(..., ge=1, le=5)
    feedback: Optional[str] = Field(None, max_length=500)


class ReviewCreatedResponseSchema(Schema):
    message: str
    rating_id: int
    reviewed_user: Dict[str, Optional[object]]
    rating: float
    created_at: str


# -------------------------------------------------------
# DISPUTE SCHEMAS
# -------------------------------------------------------
class DisputeCreateSchema(Schema):
    job_id: int
    user_id: int
    title: str
    description: str


class DisputeCreatedResponseSchema(Schema):
    message: str
    dispute_id: int
    status: DisputeStatus
    created_at: str
    job_details: Dict[str, Optional[object]]


class DisputeUpdateSchema(Schema):
    user: UserSchema


# -------------------------------------------------------
# FEEDBACK SCHEMA
# -------------------------------------------------------


class FeedbackSchema(BaseModel):
    sender_user_id: int = Field(..., description="ID of the user sending the feedback")
    receiver_user_id: int = Field(
        ..., description="ID of the user receiving the feedback"
    )
    message: str = Field(..., description="Feedback message")
    rating: int = Field(..., ge=1, le=5, description="Rating between 1 and 5")

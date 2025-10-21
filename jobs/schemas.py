from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional

from ninja import Schema, UploadedFile
from pydantic import BaseModel, EmailStr, Field, validator

from core.schema_utils import HashableSchema


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
class ErrorResponseSchema(HashableSchema):
    error: str
    details: Optional[str] = None
    resolution: Optional[str] = None


class ConflictResponseSchema(ErrorResponseSchema):
    resolution: str


class UnauthorizedResponseSchema(ErrorResponseSchema):
    pass


class SuccessMessageSchema(HashableSchema):
    message: str


class SuccessResponseSchema(HashableSchema):
    message: str


# -------------------------------------------------------
# LOCATION SCHEMA
# -------------------------------------------------------
class LocationSchema(HashableSchema):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    address: Optional[str] = None


class LocationCreateSchema(LocationSchema):
    pass


# -------------------------------------------------------
# AUTH & USER SCHEMAS
# -------------------------------------------------------
class UserBaseSchema(HashableSchema):
    id: int
    first_name: str
    last_name: str
    email: str


class LoginSchema(HashableSchema):
    email: str
    password: str


class SignupSchema(HashableSchema):
    first_name: str
    last_name: str
    email: str
    password: str
    confirm_password: str
    role: str


class PasswordResetSchema(BaseModel):
    user_id: int
    old_password: str
    new_password: str


class PasswordResetRequestSchema(HashableSchema):
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
    industry_name: Optional[str] = None  # Make optional if needed

    @staticmethod
    def resolve_industry_name(obj):
        return obj.industry.name if obj.industry else None

    @staticmethod
    def resolve_industry_id(obj):
        return obj.industry.id if obj.industry else None


# -------------------------------------------------------
# JOB SCHEMAS
# -------------------------------------------------------

class ClientActionSchema(BaseModel):
    user_id: int  # passed by frontend to identify the client user


class JobDetailSchema(HashableSchema):
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
    industry_id: int
    industry_name: str

    subcategory: str
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
    accepted_applicants_count: int = 0
    applicants_user_ids: List[int] = []
    updated_at_human: Optional[str] = None
    # **Add these fields** if you want them in response:
    client_id: Optional[int] = None
    client_rating: Optional[float] = None
    client_profile_pic_url: Optional[str] = None
    # Shift timing fields
    actual_shift_start: Optional[str] = None
    actual_shift_end: Optional[str] = None

class CreateJobSchema(HashableSchema):
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
    pay_later: bool = False  # Optional field to indicate if payment should be made later


class EditJobSchema(Schema):
    job_id: int
    user_id: int
    title: Optional[str]
    industry: Optional[int]
    subcategory: Optional[str]
    applicants_needed: Optional[int]
    job_type: Optional[str]  # or Enum
    shift_type: Optional[str]  # or Enum
    date: Optional[str]
    start_time: Optional[str]
    end_time: Optional[str]
    rate: Optional[float]
    location: Optional[str]
    pay_later: Optional[bool] = False


class JobCancellationSuccessSchema(HashableSchema):
    message: str
    job_id: int
    new_status: JobStatusEnum
    job_details: Dict[str, Optional[object]]


class GeocodeRequest(HashableSchema):
    address: str


class GeocodeResponse(BaseModel):
    success: bool
    latitude: float | None
    longitude: float | None
    error: str | None
    attempts: int


# -------------------------------------------------------
# APPLICATION SCHEMAS
# -------------------------------------------------------


class LocationUpdateSchema(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    location: str | None = None  # Optional human-readable address

class ApplyJobResponse(BaseModel):
    detail: str
    application_id: Optional[int] = None

class ApplyJobSchema(HashableSchema):
    user_id: int = Field(..., gt=0, description="ID of the user applying for the job.")
    job_id: int = Field(..., gt=0, description="ID of the job being applied for.")


class ApplicationListSchema(Schema):
    application_id: int
    job_id: int
    job_title: str
    applicant_name: str
    status: str
    applied_at: datetime
    
    
class ApplicantReviewSchema(HashableSchema):
    applicant_id: int

class ApplicantInput(Schema):
    user_id: int
    
    

from pydantic import BaseModel, Field

class MarkArrivedSchema(BaseModel):
    applicant_id: int = Field(..., description="ID of the applicant arriving at the job location")
    client_id: int = Field(..., description="ID of the client who posted the job")
    application_id: int

class ErrorResponseSchema(Schema):
    status: str
    message: str
    
    
class ApplicationStatusQuery(Schema):
    user_id: int

class ApplicationStatusOut(Schema):
    application_id: int
    job_id: int
    applicant_id: int
    status: str
    status_changed_at: Optional[str]
    updated_at: Optional[str]
    created_at: Optional[str]
    is_shown_up: bool
    manual_rating: Optional[float]
    # location: Optional[Tuple[float, float]]
    
    
# -------------------------------------------------------
# SAVED JOBS SCHEMAS
# -------------------------------------------------------
from pydantic import BaseModel, root_validator, validator


class SaveJobRequestSchema(BaseModel):
    user_id: int
    job_id: int


class UnsaveJobRequestSchema(HashableSchema):
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
    
    


class JobPaymentDetailSchema(Schema):
    job_id: int
    status: str
    amount: Optional[float] = Field(default=None, description="Payment amount in the original currency")
    service_fee: Optional[float] = Field(default=None, description="Service fee amount")
    method: Optional[str] = Field(default=None, description="Payment method (e.g., paystack, flutterwave)")
    reference: Optional[str] = Field(default=None, description="Unique payment reference code")
    created_at: Optional[datetime] = Field(default=None, description="Timestamp when payment was created")
    updated_at: Optional[datetime] = Field(default=None, description="Timestamp when payment was last updated")


class GetJobsRequestSchema(BaseModel):
    user_id: int | None = None

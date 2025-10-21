from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from pydantic import BaseModel, EmailStr, Field
from userlocation.schemas import LocationSchema
# ==
# 📌 Auth Response Schemas
# ==
class LoginOut(BaseModel):
    message: str
    access_token: str
    refresh_token: str
    user_id: int
    role: str
    first_name: str
    last_name: str
    email: str
    profile_pic: Optional[str] = None

# ==
# 📌 Role Schemas
# ==
class RoleSwitchSchema(BaseModel):
    user_id: int
    new_role: str

# ==
# 📌 Utility Schemas
# ==

class LoginSchema(BaseModel):
    email: EmailStr
    password: str

class RefreshTokenSchema(BaseModel):
    """Schema for refreshing JWT tokens"""
    refresh: str

class TokenRefreshOut(BaseModel):
    """Schema for token refresh response"""
    access: str

class MessageOut(BaseModel):
    message: str

class ErrorOut(BaseModel):
    error: str



class PasswordResetVerifySchema(BaseModel):
    """Schema for verifying OTP and resetting password"""

    email: EmailStr
    code: str
    new_password: str = Field(min_length=8)
    confirm_password: str
    # Password matching is handled in the view function


# ==
# 📌 Security Schemas
# ==
class Toggle2FASchema(BaseModel):
    """Schema for enabling/disabling 2FA"""

    user_id: int
    enable: bool


# ==
# 📌 Profile Schemas
# ==
class UserSchema(BaseModel):
    """Basic user information"""

    id: int
    username: str
    email: str
    first_name: str
    last_name: str


class UserProfileResponse(BaseModel):
    """Response schema for user profile data"""

    user_id: int
    username: str
    first_name: str
    last_name: str
    email: str
    location: Optional[str] 
    phone_number: Optional[str] = None
    role: str
    wallet_balance: str
    badges: List[str]
    rating: float
    profile_pic_url: str
    job_stats: Dict[str, int]
    activity_stats: Dict[str, int]
    review_count: int

    """Comprehensive profile schema"""
    user: UserSchema
    profile_pic_url: Optional[str] = None
    phone_number: Optional[str] = None
    location: Optional[LocationSchema] = None
    wallet_balance: Decimal = Decimal("0.00")
    rating: Optional[float] = None
    jobs_completed: int = 0
    created_at: datetime
    balance: int
    error: str

# ==
# 📌 Auth Schemas
# ==
class EmailSignupSchema(BaseModel):
    first_name: str
    last_name: str
    email: str
    password: str
    confirm_password: str

class EmailLoginSchema(BaseModel):
    """Used for email/password login"""
    email: str
    password: str


class SocialLoginSchema(BaseModel):
    """
    Schema for social logins.
    The front-end would pass:
      provider: "google" or "facebook" or "apple"
      access_token: The token from the front-end's social login
      role: Optional role for the user (default: "applicant")
      connect_to_user_id: Optional user ID to connect the social account to
      email: Optional email for direct login
      direct_login: Optional flag to indicate direct login
    """
    provider: str
    access_token: str
    role: Optional[str]
    connect_to_user_id: Optional[int] = None
    email: Optional[str] = None
    direct_login: Optional[bool] = False


class SignupSchema(BaseModel):
    """Schema for user registration"""

    email: EmailStr
    password: str = Field(min_length=8)
    first_name: str = Field(min_length=2, max_length=30)
    last_name: str = Field(min_length=2, max_length=30)
    role: str

    # Email uniqueness is checked in the view function


class EmailSignupSchema(BaseModel):
    """Used for email/password signup"""

    first_name: str
    last_name: str
    email: str
    password: str
    confirm_password: str


class PasswordResetRequestSchema(BaseModel):
    """Schema for requesting password reset link"""

    email: EmailStr


class DeviceInfoSchema(BaseModel):
    """Schema for device information"""

    device_id: str
    device_name: str
    device_type: str = "unknown"
    ip_address: Optional[str] = None


class OTPRequestSchema(BaseModel):
    """Schema for requesting an OTP"""

    email: EmailStr
    type: str  # registration, login, password_reset, 2fa, sensitive_operation
    phone: Optional[str] = None
    operation: Optional[str] = None  # For sensitive operations


class OTPVerifySchema(BaseModel):
    """Schema for verifying an OTP"""

    email: EmailStr
    code: str
    type: str
    device_info: Optional[DeviceInfoSchema] = None


class PasswordResetSchema(BaseModel):
    """Schema for password reset (change password) endpoint"""

    user_id: int
    old_password: str
    new_password: str = Field(min_length=8)
    confirm_password: str
    # Password matching is handled on the frontend


class PasswordResetVerifySchema(BaseModel):
    """Schema for verifying OTP and resetting password"""

    email: EmailStr
    code: str
    new_password: str = Field(min_length=8)
    confirm_password: str
    # Password matching is handled in the view function


# ==
# 📌 Security Schemas
# ==
class Toggle2FASchema(BaseModel):
    """Schema for enabling/disabling 2FA"""

    user_id: int
    enable: bool


# ==
# 📌 Profile Schemas
# ==
class UserSchema(BaseModel):
    """Basic user information"""

    id: int
    username: str
    email: str
    first_name: str
    last_name: str


class AccountDetailsSchema(BaseModel):
    bank_name: str
    account_number: str
    account_holder: Optional[str] = None

class UserProfileResponse(BaseModel):
    user_id: int
    username: str
    first_name: str
    last_name: str
    email: str
    location: Optional[str]
    bio: Optional[str] = None  # Added missing bio field
    phone_number: Optional[str] = None
    role: str
    wallet_balance: str
    badges: List[str]
    rating: float
    profile_pic_url: str
    job_stats: Dict[str, int]
    activity_stats: Dict[str, int]
    review_count: int

    # ✅ New field
    account_details: Optional[AccountDetailsSchema] = None


# class UserProfileResponse(BaseModel):
#     """Response schema for user profile data"""

#     user_id: int
#     username: str
#     first_name: str
#     last_name: str
#     email: str
#     location: Optional[str] 
#     phone_number: Optional[str] = None
#     role: str
#     wallet_balance: str
#     badges: List[str]
#     rating: float
#     profile_pic_url: str
#     job_stats: Dict[str, int]
#     activity_stats: Dict[str, int]
#     review_count: int

class UserProfileSchema(BaseModel):
    """Comprehensive profile schema"""

    user: UserSchema
    profile_pic_url: Optional[str] = None
    phone_number: Optional[str] = None
    location: Optional[LocationSchema] = None
    wallet_balance: Decimal = Decimal("0.00")
    rating: Optional[float] = None
    jobs_completed: int = 0
    created_at: datetime
    balance: int
    
class ProfileUpdateForm(BaseModel):
    user_id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None






class AccountDetailsUploadSchema(BaseModel):
    user_id: int = Field(..., description="User ID for the profile to update")
    account_number: str = Field(..., description="Bank account number")
    bank_name: str = Field(..., description="Bank name")

class AccountDetailsDeleteSchema(BaseModel):
    pass  # No fields needed for delete







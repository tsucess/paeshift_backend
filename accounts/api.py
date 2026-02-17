# [MARKER] Python Standard Library Imports
# ==
import logging
import os
import time
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from ninja import Router, Form, File, Query, Schema
from ninja.files import UploadedFile
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.core.mail import send_mail
from django.http import HttpRequest, JsonResponse
from django.utils import timezone, translation
from django.utils.translation import gettext as _
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from ninja.errors import HttpError
from ninja.security import django_auth
from pydantic import BaseModel, Field, field_validator
from rest_framework_simplejwt.tokens import RefreshToken

# Import error handling and logging utilities
from core.exceptions import (
    AuthenticationError,
    ResourceNotFoundError,
    InternalServerError,
    ValidationError as PaeshiftValidationError,
)
from core.logging_utils import log_endpoint, logger as core_logger, api_logger

from payment.utils import get_wallet_balance

from .models import CustomUser, OTP


# ==
# [MARKER] Caching Imports for Phase 2.2c
# ==
from core.cache_utils import (
    cache_api_response,
    invalidate_cache,
    CACHE_TTL_PROFILE,
)
from core.dummy_decorators import time_view, hibernate, log_operation

# ==
# [MARKER] Local Application Imports
# ==
from .models import CustomUser as User
from .models import Profile, Role, UserActivityLog, TrustedDevice, ProfilePicture
from .schemas import *
from .utils import get_user_response
# from .user_activity import get_active_users, get_user_last_seen  # Temporarily commented out
from django.http import JsonResponse
# ==
# [MARKER] Setup
# ==
# Initialize channel_layer lazily to avoid import errors
channel_layer = None
# We'll initialize it when needed
logger = logging.getLogger(__name__)
accounts_router = Router(tags=["Core"])

# ==
# [MARKER] Local Schemas (for backward compatibility)
# ==
class MessageResponse(BaseModel):
    """Response schema with a message"""
    message: str

class ErrorResponse(BaseModel):
    """Response schema with an error message"""
    error: str

class ProfileResponse(BaseModel):
    """Response schema for user profile data"""
    user_id: int
    username: str
    first_name: str
    last_name: str
    email: str
    profile_pic_url: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    phone_number: Optional[str] = None

class ProfileUpdateSchema(BaseModel):
    """Schema for updating user profile"""
    user_id: int
    first_name: str = None
    last_name: str = None
    bio: str = None
    location: str = None
    phone_number: str = None

class PasswordChangeSchema(BaseModel):
    """Schema for password change"""
    user_id: int
    old_password: str
    new_password: str = Field(min_length=8)
    confirm_password: str
    # Password matching is handled on the frontend

class ActiveUsersResponse(BaseModel):
    """Response schema for active users"""
    active_user_ids: List[int]
    count: int
    minutes: int

class LastSeenResponse(BaseModel):
    """Response schema for user last seen"""
    user_id: int
    last_seen_timestamp: Optional[float] = None
    last_seen_formatted: Optional[str] = None
    is_online: bool




# Allowed types and max size (5 MB)
ALLOWED_FILE_TYPES = {"image/jpeg", "image/png", "image/gif"}
MAX_FILE_SIZE = 5 * 1024 * 1024

# Define valid roles as constants to avoid import issues
VALID_ROLES = ["applicant", "client", "admin"]




# ==
# [MARKER] API Endpoints
# ==


@accounts_router.get("/setup-db", tags=["Debug"])
def setup_database(request):
    """Setup database with migrations and tables"""
    try:
        from django.core.management import call_command
        from django.db import connection
        from django.conf import settings
        from .models import CustomUser as User
        import os

        setup_info = {}

        # Run migrations with more verbose output
        try:
            call_command('migrate', verbosity=2, interactive=False)
            setup_info['migrations'] = "SUCCESS - Migrations completed"
        except Exception as e:
            setup_info['migrations'] = f"FAILED - {str(e)}"

        # Skip makemigrations to avoid field default issues
        setup_info['makemigrations'] = "SKIPPED - Using existing migrations only"

        # Check tables after migration
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            setup_info['tables_after_migration'] = len(tables)
            setup_info['table_names'] = tables[:15]

        # Try to create a test user
        try:
            test_user = User.objects.create_user(
                username='setup_test',
                email='setup@test.com',
                password='testpass123'
            )
            setup_info['test_user_creation'] = f"SUCCESS - Created user {test_user.id}"
            test_user.delete()
        except Exception as e:
            setup_info['test_user_creation'] = f"FAILED - {str(e)}"

        return JsonResponse({
            "status": "success",
            "setup_info": setup_info
        })

    except Exception as e:
        return JsonResponse({
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__
        }, status=500)

@accounts_router.get("/test-db", tags=["Debug"])
def test_database(request):
    """Comprehensive database debugging"""
    debug_info = {}

    try:
        from django.db import connection
        from django.conf import settings
        from .models import CustomUser as User
        import os

        # Test 1: Database configuration info
        db_config = settings.DATABASES['default']
        debug_info['database_engine'] = db_config.get('ENGINE')
        debug_info['database_name'] = str(db_config.get('NAME'))  # Convert to string
        debug_info['database_options'] = db_config.get('OPTIONS', {})

        # Test 2: Check if database file exists (for SQLite)
        if 'sqlite' in db_config.get('ENGINE', ''):
            db_path = db_config.get('NAME')
            if db_path != ':memory:':
                debug_info['db_file_exists'] = os.path.exists(db_path)
                if os.path.exists(db_path):
                    stat = os.stat(db_path)
                    debug_info['db_file_permissions'] = oct(stat.st_mode)[-3:]
                    debug_info['db_file_size'] = stat.st_size
                    debug_info['db_file_owner'] = stat.st_uid
            else:
                debug_info['db_type'] = 'in_memory'

        # Test 3: Basic connection test
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            debug_info['basic_connection'] = "OK"

        # Test 4: Check if tables exist
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            debug_info['tables_exist'] = len(tables)
            debug_info['table_names'] = tables[:10]  # First 10 tables

        # Test 5: Try to count users (read operation)
        try:
            user_count = User.objects.count()
            debug_info['user_count'] = user_count
            debug_info['read_operation'] = "OK"
        except Exception as read_error:
            debug_info['read_operation'] = f"FAILED: {str(read_error)}"

        # Test 6: Try a simple write operation
        try:
            with connection.cursor() as cursor:
                cursor.execute("CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY, name TEXT)")
                cursor.execute("INSERT INTO test_table (name) VALUES ('test')")
                cursor.execute("SELECT COUNT(*) FROM test_table")
                count = cursor.fetchone()[0]
                cursor.execute("DROP TABLE test_table")
                debug_info['write_test'] = f"OK - inserted and deleted {count} rows"
        except Exception as write_error:
            debug_info['write_test'] = f"FAILED: {str(write_error)}"

        # Test 7: Try ORM write operation
        try:
            test_user = User.objects.create_user(
                username='debug_test_user',
                email='debug@test.com',
                password='testpass123'
            )
            user_id = test_user.id
            test_user.delete()
            debug_info['orm_write_test'] = f"OK - created and deleted user {user_id}"
        except Exception as orm_error:
            debug_info['orm_write_test'] = f"FAILED: {str(orm_error)}"

        return JsonResponse({
            "status": "success",
            "debug_info": debug_info
        })

    except Exception as e:
        debug_info['fatal_error'] = str(e)
        debug_info['error_type'] = type(e).__name__
        return JsonResponse({
            "status": "error",
            "debug_info": debug_info
        }, status=500)

@accounts_router.get("/test-email", tags=["Debug"])
def test_email(request):
    """Test email configuration and send a test email"""
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        import os

        # Get email configuration
        email_config = {
            "EMAIL_BACKEND": getattr(settings, 'EMAIL_BACKEND', 'Not set'),
            "EMAIL_HOST": getattr(settings, 'EMAIL_HOST', 'Not set'),
            "EMAIL_PORT": getattr(settings, 'EMAIL_PORT', 'Not set'),
            "EMAIL_USE_TLS": getattr(settings, 'EMAIL_USE_TLS', 'Not set'),
            "EMAIL_HOST_USER": getattr(settings, 'EMAIL_HOST_USER', 'Not set'),
            "EMAIL_HOST_PASSWORD": "***SET***" if getattr(settings, 'EMAIL_HOST_PASSWORD', '') else "NOT SET",
            "DEFAULT_FROM_EMAIL": getattr(settings, 'DEFAULT_FROM_EMAIL', 'Not set'),
        }

        # Try to send a test email
        try:
            send_mail(
                subject='Payshift Email Test',
                message='This is a test email from Payshift production environment.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=['taofeeq.muhammad22@gmail.com'],  # Send to self for testing
                fail_silently=False,
            )
            email_test = "SUCCESS - Test email sent"
        except Exception as e:
            email_test = f"FAILED - {str(e)}"

        return JsonResponse({
            "status": "success",
            "email_config": email_config,
            "email_test": email_test,
        })
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)

@accounts_router.post("/test-otp-send", tags=["Debug"])
def test_otp_send(request):
    """Test OTP sending directly"""
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        import random

        # Generate a test OTP
        test_otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])

        # Try to send email
        try:
            send_mail(
                subject='Test OTP - Payshift',
                message=f'Your test OTP code is: {test_otp}',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=['fakoredeabbas@gmail.com'],
                fail_silently=False,
            )
            email_result = f"SUCCESS - Test OTP {test_otp} sent to fakoredeabbas@gmail.com"
        except Exception as e:
            email_result = f"FAILED - {str(e)}"

        return JsonResponse({
            "status": "success",
            "email_backend": getattr(settings, 'EMAIL_BACKEND', 'Not set'),
            "email_result": email_result,
            "test_otp": test_otp,
        })
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)

@accounts_router.post("/test-signup", tags=["Auth"])
def test_signup(request, payload: SignupSchema):
    """Ultra-simple signup test endpoint"""
    try:
        from django.conf import settings
        from .models import CustomUser as User

        # Return database info first
        db_config = settings.DATABASES['default']

        response_data = {
            "status": "testing",
            "database_name": str(db_config.get('NAME')),
            "database_engine": db_config.get('ENGINE'),
            "payload_received": {
                "first_name": payload.first_name,
                "last_name": payload.last_name,
                "email": payload.email,
                "role": payload.role
            }
        }

        # Try to create user
        user = User.objects.create_user(
            username=payload.email,
            email=payload.email,
            password=payload.password,
            first_name=payload.first_name or "",
            last_name=payload.last_name or "",
            is_active=True
        )

        response_data.update({
            "status": "success",
            "message": "User created successfully",
            "user_id": user.id,
            "user_email": user.email
        })

        return JsonResponse(response_data, status=201)

    except Exception as e:
        return JsonResponse({
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
            "database_name": str(settings.DATABASES['default'].get('NAME', 'unknown')),
            "payload_received": {
                "first_name": payload.first_name,
                "last_name": payload.last_name,
                "email": payload.email,
                "role": payload.role
            }
        }, status=400)

@log_endpoint(core_logger)
@accounts_router.post("/signup", tags=["Auth"])
def signup_view(request, payload: SignupSchema):
    """
    Create new user with email verification via OTP.

    This endpoint:
    1. Creates a user with is_active=False
    2. Sends an OTP for email verification
    3. Returns a response indicating OTP verification is required
    """
    try:
        # Debug logging to track signup attempts
        core_logger.info(
            "Signup attempt",
            email=payload.email,
            role=payload.role,
            first_name=payload.first_name,
            last_name=payload.last_name
        )

        if User.objects.filter(email=payload.email).exists():
            core_logger.warning(f"Signup attempt with existing email: {payload.email}")
            return JsonResponse({"error": "Email already exists"}, status=409)

        if payload.role not in VALID_ROLES:
            core_logger.warning(f"Invalid role in signup attempt: {payload.role}")
            raise PaeshiftValidationError(
                f"Invalid role. Must be one of: {', '.join(VALID_ROLES)}",
                {"role": payload.role}
            )

        username = payload.email.split('@')[0]

        # # Create user first, then profile in separate transactions
        # # This avoids foreign key constraint issues
        # # Invalidate any cached user data
        # cache_keys = [
        #     f"user:{user.id}",
        #     f"whoami:{user.id}",
        #     f"profile:{user.id}"
        # ]

        # for key in cache_keys:
        #     cache.delete(key)

        # Step 1: Create the user using Django ORM (simpler and more reliable)
        try:
            # Check if the user already exists
            if User.objects.filter(email=payload.email).exists():
                logger.info(f"Signup attempt with existing email: {payload.email}")
                return JsonResponse({"error": "Email already exists"}, status=400)

            if User.objects.filter(username=username).exists():
                logger.info(f"Signup attempt with existing username: {username}")
                return JsonResponse({"error": "Username already exists"}, status=400)

            # Create user using Django ORM (more reliable than raw SQL)
            try:
                user = User.objects.create_user(
                    username=username,
                    email=payload.email,
                    password=payload.password,
                    first_name=payload.first_name,
                    last_name=payload.last_name,
                    is_active=False  # User needs to verify email first
                )

                # Set role if the field exists
                if hasattr(user, 'role'):
                    user.role = payload.role
                    user.save()
                    logger.info(f"Created inactive user with role using ORM: {payload.email}")
                else:
                    logger.info(f"Created inactive user without role field using ORM: {payload.email}")

            except Exception as e:
                logger.error(f"Error creating user with ORM: {str(e)}")
                return JsonResponse({"error": f"Error creating user: {str(e)}"}, status=400)

        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            return JsonResponse({"error": f"Error creating user: {str(e)}"}, status=400)

        # Step 2: Create the profile using raw SQL to bypass ORM constraints
        try:
            from django.db import connection
            # Check if profile already exists
            profile_exists = False
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) FROM accounts_profile WHERE user_id = %s",
                    [user.id]
                )
                profile_exists = cursor.fetchone()[0] > 0

            if profile_exists:
                # Update existing profile
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE accounts_profile SET role = %s WHERE user_id = %s",
                        [payload.role, user.id]
                    )
                logger.info(f"Updated profile with role: {payload.role}")
            else:
                # Create new profile using ORM instead of raw SQL
                try:
                    profile = Profile.objects.create(
                        user=user,
                        role=payload.role,
                        badges=[]  # Initialize badges as empty list
                    )
                    logger.info(f"Created profile with role: {payload.role}")
                except Exception as profile_error:
                    logger.error(f"Error creating profile with ORM: {str(profile_error)}")
                    # Fallback to signal handler
                    logger.info("Relying on signal handler to create profile")

            # Get the profile object
            try:
                profile = Profile.objects.get(user=user)
            except Profile.DoesNotExist:
                logger.warning(f"Could not retrieve profile for user {user.email} after creation")
                profile = None

        except Exception as e:
            logger.error(f"Error creating profile: {str(e)}")
            # Continue anyway - the signal handler will try to create the profile

        # Step 3: Send OTP for email verification
        try:
            # Import OTP utilities
            from .otp_api import request_otp, OTP_TYPE_REGISTRATION

            # Create OTP request payload
            from .schemas import OTPRequestSchema
            otp_payload = OTPRequestSchema(
                email=payload.email,
                type=OTP_TYPE_REGISTRATION,
                phone=profile.phone_number if profile and profile.phone_number else None
            )

            # Request OTP
            logger.info(f"[OTP] Requesting OTP for email: {payload.email}")
            logger.info(f"[OTP] OTP payload: email={otp_payload.email}, type={otp_payload.type}, phone={otp_payload.phone}")
            otp_response = request_otp(request, otp_payload)
            logger.info(f"[OTP] OTP request response: {otp_response}")

            # Store user ID in session for verification
            request.session['registration_user_id'] = user.id

            logger.info(f"[OTP] Verification OTP process completed for {payload.email}")
        except Exception as e:
            logger.error(f"[OTP] Error sending verification OTP to {payload.email}: {str(e)}")
            import traceback
            logger.error(f"[OTP] Full traceback: {traceback.format_exc()}")
            # Continue anyway - user can request OTP again

        # Get role from user model or profile
        try:
            role = user.role
        except AttributeError:
            # If role field doesn't exist on user model, get it from profile
            role = profile.role if profile else payload.role

        # Log successful signup
        core_logger.info(
            "User account created successfully",
            user_id=user.id,
            email=user.email,
            role=role
        )

        return JsonResponse({
            "message": "Account created successfully. Please verify your email.",
            "requires_verification": True,
            "verification_type": "registration",
            "verification_url": f"/accountsapp/verify/?email={user.email}",
            "user_id": user.id,
            "role": role,
            "email": user.email
        }, status=200)

    except PaeshiftValidationError:
        raise
    except IntegrityError as e:
        core_logger.error(f"IntegrityError during signup for {payload.email}: {str(e)}")
        error_msg = str(e).lower()
 
        if "username" in error_msg:
            return JsonResponse({"error": "Username already exists"}, status=409)
        elif "email" in error_msg:
            return JsonResponse({"error": "Email already exists"}, status=409)
        elif "foreign key constraint" in error_msg:
            # Handle foreign key constraint errors
            core_logger.error(f"Foreign key constraint error: {str(e)}")

            # Try to identify which foreign key is causing the issue
            if "role" in error_msg:
                raise PaeshiftValidationError("Invalid role selected", {"role": payload.role})
            elif "wallet" in error_msg:
                raise InternalServerError("Error creating user wallet")
            elif "profile" in error_msg:
                raise InternalServerError("Error creating user profile")
            else:
                raise InternalServerError(f"Database constraint error")
        else:
            raise InternalServerError("Database constraint error")

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        core_logger.error(f"SIGNUP ERROR for {payload.email}: {str(e)}")
        core_logger.error(f"FULL TRACEBACK: {error_details}")
        raise InternalServerError("Signup failed. Please try again.")








@log_endpoint(core_logger)
@accounts_router.post(
    "/verify-password-reset",
    tags=["Auth"],
    response={200: MessageOut, 400: ErrorOut, 401: ErrorOut, 404: ErrorOut}
)
@time_view
def verify_password_reset(request, payload: PasswordResetVerifySchema):
    """
    Verify a password reset OTP and set a new password.

    Args:
        payload: Password reset verification data including email, code, and new password

    Returns:
        200: Success message
        400: Error message
        401: Invalid OTP message
        404: User not found
    """
    try:
        email = payload.email.lower().strip()
        code = payload.code
        new_password = payload.new_password
        confirm_password = payload.confirm_password

        # Verify passwords match
        if new_password != confirm_password:
            raise PaeshiftValidationError(
                "New password and confirm password do not match",
                {"new_password": "***", "confirm_password": "***"}
            )

        # Get user ID from session or find by email
        user_id = request.session.get('password_reset_user_id')

        if not user_id:
            # Try to find user by email
            try:
                user = User.objects.get(email=email)
                user_id = user.id
            except User.DoesNotExist:
                raise ResourceNotFoundError("User", email)

        # Get the user
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise ResourceNotFoundError("User", user_id)

        # Verify OTP
        from .otp_api import verify_otp

        # Create verification payload
        from .schemas import OTPVerifySchema
        verify_payload = OTPVerifySchema(
            email=email,
            code=code,
            type="password_reset"
        )

        # Verify OTP
        status_code, response = verify_otp(request, verify_payload)

        if status_code != 200:
            # Return the error from verify_otp
            return status_code, response

        # OTP is valid - set new password
        user.set_password(new_password)
        user.save()

        # Invalidate all sessions and tokens for security
        if hasattr(user, 'auth_token_set'):
            user.auth_token_set.all().delete()

        # Log the activity
        UserActivityLog.objects.create(
            user=user,
            activity_type="password_reset",
            ip_address=request.META.get("REMOTE_ADDR")
        )

        # Clear session data
        if 'password_reset_user_id' in request.session:
            del request.session['password_reset_user_id']

        # Log successful password reset
        core_logger.info(
            "Password reset successfully",
            user_id=user.id,
            email=user.email
        )

        # Return success
        return 200, MessageOut(message="Password reset successfully. Please login with your new password.")

    except (PaeshiftValidationError, ResourceNotFoundError):
        raise
    except Exception as e:
        core_logger.error(f"Error resetting password: {str(e)}", exc_info=True)
        raise InternalServerError("Failed to reset password")


@log_endpoint(core_logger)
@accounts_router.post(
    "/change-password",
    tags=["Auth"],
    response={200: MessageOut, 400: ErrorOut, 404: ErrorOut, 500: ErrorOut}
)
@time_view
def change_password(request, data: PasswordChangeSchema):
    """
    Change a user's password.

    Args:
        data: Password change data including user_id, old_password, new_password, and confirm_password

    Returns:
        200: Password changed successfully
        400: Invalid password or passwords don't match
        404: User not found
        500: Server error
    """
    try:
        # Find the user
        try:
            user = User.objects.get(pk=data.user_id)
        except User.DoesNotExist:
            raise ResourceNotFoundError("User", data.user_id)

        # Verify old password
        if not user.check_password(data.old_password):
            raise PaeshiftValidationError("Old password is incorrect", {"user_id": data.user_id})

        # Verify new password and confirm password match
        if data.new_password != data.confirm_password:
            raise PaeshiftValidationError(
                "New password and confirm password do not match",
                {"new_password": "***", "confirm_password": "***"}
            )

        # Set new password
        user.set_password(data.new_password)
        user.save()

        # Invalidate all sessions and tokens for security
        if hasattr(user, 'auth_token_set'):
            user.auth_token_set.all().delete()

        # Log successful password change
        core_logger.info(
            "Password changed successfully",
            user_id=user.id,
            email=user.email
        )

        # Return success message
        return 200, MessageOut(message="Password changed successfully. Please login again.")

    except (ResourceNotFoundError, PaeshiftValidationError):
        raise
    except Exception as e:
        core_logger.error(f"Error changing password: {str(e)}", exc_info=True)
        raise InternalServerError("Failed to change password")

@cache_api_response(timeout=CACHE_TTL_PROFILE, prefix='profile:user')
@accounts_router.get(
    "/get-profile/{user_id}",
    tags=["User"],
    response={200: ProfileResponse, 404: ErrorOut, 500: ErrorOut},
    summary="Fetch user profile by ID",
)
def get_profile(request, user_id: int):
    try:
        # Optimize query with select_related for user
        user = User.objects.select_related('profile').get(pk=user_id)
        profile = user.profile if hasattr(user, 'profile') else None

        if not profile:
            return 404, ErrorOut(error="Profile not found.")

        # Get active profile picture
        active_pic = ProfilePicture.objects.filter(profile=profile, is_active=True).first()
        profile_pic_url = active_pic.image.url if active_pic and active_pic.image else None

        return 200, ProfileResponse(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            profile_pic_url=profile_pic_url,
            bio=profile.bio,
            location=profile.location or user.location,
            phone_number=profile.phone_number,
        )

    except User.DoesNotExist:
        return 404, ErrorOut(error="User not found.")
    except Exception as e:
        logger.error(f"Error fetching profile: {e}")
        return 500, ErrorOut(error=f"An error occurred: {str(e)}")


# [SUCCESS] Extra endpoint that supports /profile?user_id=3
@accounts_router.get(
    "/profile",
    tags=["User"],
    response={200: ProfileResponse, 400: ErrorOut, 404: ErrorOut},
    summary="Fetch user profile via query param",
)
def get_profile_by_query(request, user_id: int = Query(...)):
    return get_profile(request, user_id=user_id)






@log_endpoint(core_logger)
@accounts_router.post(
    "/profile/update",
    tags=["User"],
    response={200: ProfileResponse, 400: ErrorOut, 404: ErrorOut, 500: ErrorOut},
    summary="Update user profile",
)
def update_profile(
    request,
    data: ProfileUpdateSchema = Form(...),
    profile_picture: UploadedFile = File(None),
):
    start_time = time.time()
    try:
        # Validate file if provided
        if profile_picture:
            if profile_picture.content_type not in ALLOWED_FILE_TYPES:
                raise PaeshiftValidationError(
                    "Invalid file type. Allowed types: JPEG, PNG, GIF",
                    {"content_type": profile_picture.content_type}
                )
            if profile_picture.size > MAX_FILE_SIZE:
                raise PaeshiftValidationError(
                    "File too large. Max size is 5MB.",
                    {"file_size": profile_picture.size, "max_size": MAX_FILE_SIZE}
                )

        # Get user
        try:
            user = User.objects.get(pk=data.user_id)
        except User.DoesNotExist:
            raise ResourceNotFoundError("User", data.user_id)

        profile, _ = Profile.objects.get_or_create(user=user)

        # Update user fields
        user.first_name = data.first_name or user.first_name
        user.last_name = data.last_name or user.last_name
        user.location = data.location or user.location
        user.save()

        # Update profile fields
        profile.bio = data.bio or profile.bio
        profile.location = data.location or profile.location
        profile.phone_number = data.phone_number or profile.phone_number
        profile.save()

        if profile_picture:
            # Mark existing as inactive
            ProfilePicture.objects.filter(profile=profile, is_active=True).update(is_active=False)
            # Save new one
            ProfilePicture.objects.create(profile=profile, image=profile_picture, is_active=True)

        # Get new profile pic URL
        active_pic = ProfilePicture.objects.filter(profile=profile, is_active=True).first()
        profile_pic_url = active_pic.image.url if active_pic and active_pic.image else None

        # Log successful profile update
        core_logger.info(
            "Profile updated successfully",
            user_id=user.id,
            email=user.email,
            has_picture=profile_picture is not None
        )

        log_operation(
            operation="profile_update",
            key=f"user:{user.id}",
            success=True,
            duration_ms=(time.time() - start_time) * 1000,
        )

        return 200, ProfileResponse(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            profile_pic_url=profile_pic_url,
            bio=profile.bio,
            location=profile.location or user.location,
            phone_number=profile.phone_number,
        )

    except (PaeshiftValidationError, ResourceNotFoundError):
        raise
    except Exception as e:
        core_logger.error(f"Error updating profile: {e}", exc_info=True)
        raise InternalServerError("Failed to update profile")





@accounts_router.put("/switch-role", tags=["Account"])
def switch_user_role(request, payload: RoleSwitchSchema):
    try:
        user = CustomUser.objects.get(id=payload.user_id)
    except CustomUser.DoesNotExist:
        raise HttpError(404, str(_("User not found")))

    if payload.new_role not in VALID_ROLES:
        raise HttpError(400, str(_("Invalid role selected.")))

    if user.role == payload.new_role:
        return {"message": str(_("You're already using the selected role."))}

    user.role = payload.new_role
    user.save()

    if hasattr(user, "profile"):
        user.profile.role = payload.new_role
        user.profile.save()

    return {
        "message": str(_("Role switched successfully.")),
        "new_role": user.role,
        "user_id": user.id,
        "username": user.username,
    }

@accounts_router.post("/upload-account-details", tags=["Account"], response={200: MessageOut, 400: ErrorOut})
def upload_account_details(request, payload: AccountDetailsUploadSchema):
    """
    Upload or update bank account details for the user's profile by user_id.
    Requires both account_number and bank_name.
    """
    user_id = payload.user_id
    try:
        profile = Profile.objects.get(user_id=user_id)
        profile.account_details = {
            "account_number": payload.account_number,
            "bank_name": payload.bank_name
        }
        profile.save()
        return 200, MessageOut(message="Account details uploaded successfully.")
    except Profile.DoesNotExist:
        return 400, ErrorOut(error="Profile not found.")
    except Exception as e:
        return 400, ErrorOut(error=f"Error uploading account details: {str(e)}")

# @accounts_router.get("/get-account-details", tags=["Account"], response={200: dict, 400: ErrorOut})
# def get_account_details(request, user_id: int = Query(...)):
#     """
#     Get the uploaded bank account details for the user's profile by user_id.
#     """
#     try:
#         profile = Profile.objects.get(user_id=user_id)
#         if not profile.account_details:
#             return 400, ErrorOut(error="No account details found.")
#         return 200, profile.account_details
#     except Profile.DoesNotExist:
#         return 400, ErrorOut(error="Profile not found.")
#     except Exception as e:
#         return 400, ErrorOut(error=f"Error fetching account details: {str(e)}")


@cache_api_response(timeout=CACHE_TTL_PROFILE, prefix='account_details:user')
@accounts_router.get("/get-account-details", tags=["Account"], response={200: dict, 400: ErrorOut})
def get_account_details(request, user_id: int = Query(...)):
    """
    Get the uploaded bank account details for the user's profile by user_id.
    """
    try:
        # Optimize query with select_related for user
        profile = Profile.objects.select_related('user').get(user_id=user_id)

        # Return empty dict if account_details is empty or None
        details = profile.account_details or {}

        return 200, details

    except Profile.DoesNotExist:
        return 400, ErrorOut(error="Profile not found.")
    except Exception as e:
        return 400, ErrorOut(error=f"Error fetching account details: {str(e)}")



from ninja import Schema
from typing import List
from .models import Profile, ProfilePicture  # adjust import as needed

class PictureOut(Schema):
    url: str
    is_active: bool
    uploaded_at: str



@accounts_router.get(
    "/user_profile_pictures_full/",
    tags=["User"],
    response=List[PictureOut],
    summary="Fetch full details of user's profile pictures",
)
def user_profile_pictures_full(request, user_id: int):
    """
    Returns a list of profile picture metadata for a user.
    Includes URL, is_active flag, and uploaded timestamp.
    """
    try:
        profile = Profile.objects.get(user__id=user_id)
    except Profile.DoesNotExist:
        return []

    pictures = ProfilePicture.objects.filter(profile=profile).order_by("-uploaded_at")

    return [
        PictureOut(
            url=pic.image.url,
            is_active=pic.is_active,
            uploaded_at=pic.uploaded_at.isoformat()
        )
        for pic in pictures if pic.image
    ]




# @accounts_router.get(
#     "/user_profile_pictures/",
#     tags=["User"],
#     response=List[str],
#     summary="Fetch all profile picture URLs uploaded by a user",
# )
# def list_user_profile_pictures(request, user_id: int):
#     """
#     Return a list of image URLs from ProfilePicture model filtered by user.
#     Example: /accountsapp/user_profile_pictures/?user_id=3
#     """
#     try:
#         profile = Profile.objects.get(user__id=user_id)
#     except Profile.DoesNotExist:
#         return []

#     pictures = ProfilePicture.objects.filter(profile=profile).order_by("-uploaded_at")
#     return [pic.image.url for pic in pictures if pic.image]




# ==
# [MARKER] Security Endpoints
# ==
@accounts_router.post(
    "/verify-sensitive-operation",
    tags=["Security"],
    response={200: MessageOut, 400: ErrorOut, 401: ErrorOut}
)
@time_view
def verify_sensitive_operation(request, payload: OTPVerifySchema):
    """
    Verify an OTP for a sensitive operation.

    Args:
        payload: OTP verification data including email, code, and type

    Returns:
        200: Success message with verification token
        400: Error message
        401: Invalid OTP message
    """
    try:
        email = payload.email.lower().strip()
        code = payload.code

        # Verify OTP type
        if payload.type != "sensitive_operation":
            return 400, ErrorOut(error="Invalid verification type. Expected 'sensitive_operation'.")

        # Get pending operation from session
        pending_operation = request.session.get('pending_operation')

        if not pending_operation:
            return 400, ErrorOut(error="No pending operation found.")

        # Get the user
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return 404, ErrorOut(error="User not found.")

        # Verify OTP
        from .otp_api import verify_otp

        # Create verification payload
        verify_payload = OTPVerifySchema(
            email=email,
            code=code,
            type="sensitive_operation"
        )

        # Verify OTP
        status_code, response = verify_otp(request, verify_payload)

        if status_code != 200:
            # Return the error from verify_otp
            return status_code, response

        # OTP is valid - mark operation as verified
        operation_name = pending_operation.get('name', 'unknown')

        # Store verification in session
        import time
        verified_operations = request.session.get('verified_operations', {})
        verified_operations[operation_name] = time.time()
        request.session['verified_operations'] = verified_operations

        # Log the activity
        UserActivityLog.objects.create(
            user=user,
            activity_type=f"verified_operation_{operation_name}",
            ip_address=request.META.get("REMOTE_ADDR")
        )

        # Return success with original operation details
        return 200, MessageOut(
            message=f"Operation '{operation_name}' verified successfully. You can now proceed."
        )

    except Exception as e:
        logger.error(f"Error verifying sensitive operation: {str(e)}")
        return 400, ErrorOut(error="Error verifying operation. Please try again.")
    
    
@log_endpoint(core_logger)
@accounts_router.post(
    "/toggle-2fa",
    tags=["Security"],
    response={200: MessageOut, 400: ErrorOut, 404: ErrorOut}
)
@time_view
def toggle_2fa(request, payload: Toggle2FASchema):
    """
    Enable or disable two-factor authentication for a user.

    Args:
        payload: Toggle2FA data including user_id and enable flag

    Returns:
        200: Success message
        400: Error message
        404: User not found
    """
    try:
        # Find the user
        try:
            user = User.objects.get(pk=payload.user_id)
        except User.DoesNotExist:
            raise ResourceNotFoundError("User", payload.user_id)

        # Get or create profile
        profile, created = Profile.objects.get_or_create(user=user)

        # Update 2FA setting
        profile.has_2fa_enabled = payload.enable
        profile.save()

        # Log the activity
        activity_type = "2fa_enabled" if payload.enable else "2fa_disabled"
        UserActivityLog.objects.create(
            user=user,
            activity_type=activity_type,
            ip_address=request.META.get("REMOTE_ADDR")
        )

        # Log 2FA toggle
        status = "enabled" if payload.enable else "disabled"
        core_logger.info(
            f"Two-factor authentication {status}",
            user_id=user.id,
            email=user.email,
            status=status
        )

        # Return success message
        return 200, MessageOut(message=f"Two-factor authentication {status} successfully.")

    except ResourceNotFoundError:
        raise
    except Exception as e:
        core_logger.error(f"Error toggling 2FA: {str(e)}", exc_info=True)
        raise InternalServerError("Failed to toggle 2FA")


# ==
# [MARKER] Auth Endpoints
# ==

@log_endpoint(core_logger)
@accounts_router.post(
    "/verify-login",
    tags=["Auth"],
    response={200: LoginOut, 400: ErrorOut, 401: ErrorOut}
)
@time_view
def verify_login(request, payload: OTPVerifySchema):
    """
    Verify a login OTP and complete the login process.

    Args:
        payload: OTP verification data including email, code, and type

    Returns:
        200: Login success with tokens
        400: Error message
        401: Invalid OTP message
    """
    try:
        email = payload.email.lower().strip()
        code = payload.code

        # Verify OTP type is valid for login
        valid_types = ["login", "2fa"]
        if payload.type not in valid_types:
            raise PaeshiftValidationError(
                f"Invalid verification type. Expected one of: {', '.join(valid_types)}",
                {"type": payload.type}
            )

        # Get pending login info from session
        pending_login = request.session.get('pending_login')

        if not pending_login:
            raise PaeshiftValidationError(
                "No pending login found. Please try logging in again.",
                {}
            )

        # Get the user
        try:
            user = User.objects.get(id=pending_login.get('user_id'))
        except User.DoesNotExist:
            raise ResourceNotFoundError("User", pending_login.get('user_id'))

        # Verify OTP
        from .otp_api import verify_otp

        # Create verification payload
        verify_payload = OTPVerifySchema(
            email=email,
            code=code,
            type=payload.type
        )

        # Verify OTP
        status_code, response = verify_otp(request, verify_payload)

        if status_code != 200:
            # Return the error from verify_otp
            return status_code, response

        # OTP is valid - complete login

        # Login with explicit backend
        from django.contrib.auth import get_backends
        backend = get_backends()[0]  # Use the first backend

        login(request, user, backend=backend.__class__.__name__)

        # Generate JWT Tokens
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        # Try to get role from the User model, with fallback
        try:
            role_name = user.role
        except AttributeError:
            # If role field doesn't exist, use a default role
            role_name = 'client'
            core_logger.warning(f"Role field not found on user model, using default role: {role_name}")

        # Get or create profile
        try:
            profile, created = Profile.objects.get_or_create(
                user=user,
                defaults={
                    "role": role_name or "client",
                    "badges": []
                }
            )
            # Get role from profile if we couldn't get it from user
            if role_name == 'client' and profile.role:
                role_name = profile.role
        except Exception as e:
            core_logger.error(f"Error getting or creating profile for user {user.email}: {str(e)}")
            profile = None

        # Store device as trusted
        device_info = pending_login.get('device_info', {})
        if device_info:
            TrustedDevice.create_trusted_device(user, device_info)

        # Log the login activity
        UserActivityLog.objects.create(
            user=user,
            activity_type="login_verified",
            ip_address=request.META.get('REMOTE_ADDR')
        )

        # Clear session data
        if 'pending_login' in request.session:
            del request.session['pending_login']

        # Log successful login verification
        api_logger.log_authentication(user.id, True, "Login verified successfully")
        core_logger.info(
            "Login verified successfully",
            user_id=user.id,
            email=user.email,
            role=role_name
        )

        # Return login success with tokens
        return 200, LoginOut(
            message="Login successful",
            access_token=access_token,
            refresh_token=str(refresh),
            user_id=user.id,
            role=role_name,
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            profile_pic=profile.profile_pic.url if profile and profile.profile_pic else None
        )

    except (PaeshiftValidationError, ResourceNotFoundError):
        raise
    except Exception as e:
        core_logger.error(f"Error verifying login: {str(e)}", exc_info=True)
        raise InternalServerError("Failed to verify login")

@log_endpoint(core_logger)
@accounts_router.post(
    "/verify-registration",
    tags=["Auth"],
    response={200: MessageOut, 400: ErrorOut, 401: ErrorOut}
)
@time_view
def verify_registration(request, payload: OTPVerifySchema):
    """
    Verify a registration OTP and activate the user account.

    Args:
        payload: OTP verification data including email, code, and type

    Returns:
        200: Success message
        400: Error message
        401: Invalid OTP message
    """
    try:
        email = payload.email.lower().strip()
        code = payload.code

        # Verify OTP type
        if payload.type != "registration":
            raise PaeshiftValidationError(
                "Invalid verification type. Expected 'registration'.",
                {"type": payload.type}
            )

        # Get user ID from session
        user_id = request.session.get('registration_user_id')

        if not user_id:
            # Try to find user by email
            try:
                user = User.objects.get(email=email, is_active=False)
                user_id = user.id
            except User.DoesNotExist:
                raise ResourceNotFoundError("User", email)

        # Get the user
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise ResourceNotFoundError("User", user_id)

        # Verify OTP
        from .otp_api import verify_otp

        # Create verification payload
        verify_payload = OTPVerifySchema(
            email=email,
            code=code,
            type="registration"
        )

        # Verify OTP
        core_logger.info(f"[VERIFY_REG] Calling verify_otp for email: {email}")
        status_code, response = verify_otp(request, verify_payload)
        core_logger.info(f"[VERIFY_REG] verify_otp returned status: {status_code}, response: {response}")

        if status_code != 200:
            # Return the error from verify_otp
            core_logger.warning(f"[VERIFY_REG] OTP verification failed with status {status_code}")
            return status_code, response

        # OTP is valid - activate the user
        core_logger.info(f"[VERIFY_REG] OTP verified successfully. Activating user {user.id} ({email})")
        user.is_active = True
        user.save()
        core_logger.info(f"[VERIFY_REG] User {user.id} is_active set to: {user.is_active}")

        # Verify the change was saved
        user.refresh_from_db()
        core_logger.info(f"[VERIFY_REG] After refresh_from_db, user {user.id} is_active: {user.is_active}")

        # Log the activity (with error handling)
        try:
            UserActivityLog.objects.create(
                user=user,
                activity_type="account_verified",
                ip_address=request.META.get("REMOTE_ADDR")
            )
        except Exception as log_error:
            core_logger.warning(f"Failed to create activity log for user {user.id}: {str(log_error)}")
            # Continue anyway - logging failure shouldn't block verification

        # Clear session data
        if 'registration_user_id' in request.session:
            del request.session['registration_user_id']

        # Log successful verification
        core_logger.info(
            "Account verified successfully",
            user_id=user.id,
            email=user.email
        )

        # Return success
        return 200, MessageOut(message="Account verified successfully. You can now log in.")

    except (PaeshiftValidationError, ResourceNotFoundError):
        raise
    except Exception as e:
        core_logger.error(f"Error verifying registration: {str(e)}", exc_info=True)
        raise InternalServerError("Failed to verify registration")

@log_endpoint(core_logger)
@accounts_router.post(
    "/request-password-reset",
    tags=["Auth"],
    response={200: MessageOut}
)
@time_view
def request_password_reset(request, payload: PasswordResetRequestSchema):
    """
    Initiate password reset process by sending OTP.

    Args:
        payload: Password reset request data including email

    Returns:
        200: Success message (always returns success to prevent email enumeration)

    Security Note: Always returns success to prevent email enumeration.
    """
    # Start timing
    start_time = time.time()

    # Normalize email
    email = payload.email.lower().strip()

    try:
        # Check if user exists
        try:
            user = User.objects.get(email=email)
            user_exists = True
        except User.DoesNotExist:
            user_exists = False

        # Only proceed if user exists
        if user_exists:
            # Send OTP for password reset
            try:
                # Import OTP utilities
                from .otp_api import request_otp, OTP_TYPE_PASSWORD_RESET

                # Create OTP request payload
                from .schemas import OTPRequestSchema
                otp_payload = OTPRequestSchema(
                    email=email,
                    type=OTP_TYPE_PASSWORD_RESET,
                    phone=user.profile.phone_number if hasattr(user, 'profile') and user.profile.phone_number else None
                )

                # Request OTP
                request_otp(request, otp_payload)

                # Store user ID in session for verification
                request.session['password_reset_user_id'] = user.id

                core_logger.info(
                    "Password reset OTP sent",
                    user_id=user.id,
                    email=email
                )
            except Exception as e:
                core_logger.error(f"Error sending password reset OTP: {str(e)}", exc_info=True)
                # Continue anyway - we'll still return success to prevent email enumeration

            # Log telemetry for successful operation
            log_operation(
                operation="password_reset_request",
                key=f"user:{user.id}:password_reset",
                success=True,
                duration_ms=(time.time() - start_time) * 1000,
                context="API endpoint: /request-password-reset"
            )
        else:
            # Log telemetry for non-existent user (but don't expose this information)
            core_logger.warning(
                "Password reset requested for non-existent email",
                email=email
            )
            log_operation(
                operation="password_reset_request",
                key=f"email:{email}",
                success=False,
                duration_ms=(time.time() - start_time) * 1000,
                context="API endpoint: /request-password-reset - User not found"
            )

    except Exception as e:
        # Log error but don't expose it
        core_logger.warning(f"Password reset error for {email}: {str(e)}", exc_info=True)

        # Log telemetry for error
        log_operation(
            operation="password_reset_request",
            key=f"email:{email}",
            success=False,
            duration_ms=(time.time() - start_time) * 1000,
            context=f"API endpoint: /request-password-reset - Error: {str(e)}"
        )

    return MessageOut(message="If an account exists with this email, a verification code has been sent")







@log_endpoint(core_logger)
@accounts_router.post("/login-simple", tags=["Auth"])
def login_simple(request, payload: LoginSchema):
    """Simple login without Profile dependencies"""
    try:
        user = authenticate(request, username=payload.email, password=payload.password)
        if not user:
            api_logger.log_authentication(None, False, "Invalid credentials")
            raise AuthenticationError("Invalid email or password")

        if not user.is_active:
            api_logger.log_authentication(user.id, False, "Account not activated")
            raise AuthenticationError("Account not activated. Please verify your email.")

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        # Get role from user model
        role_name = getattr(user, 'role', 'client')

        # Log successful authentication
        api_logger.log_authentication(user.id, True, "Simple login successful")
        core_logger.info(
            "User logged in successfully",
            user_id=user.id,
            email=user.email,
            role=role_name
        )

        return JsonResponse({
            "message": "Login successful",
            "access_token": access_token,
            "refresh_token": str(refresh),
            "user_id": user.id,
            "role": role_name,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email
        }, status=200)

    except AuthenticationError:
        raise
    except Exception as e:
        core_logger.error(f"Simple login error: {str(e)}", exc_info=True)
        raise InternalServerError("Login failed. Please try again.")




@log_endpoint(core_logger)
@accounts_router.post("/login", tags=["Auth"])
def login_view(request, payload: LoginSchema):
    """
    Authenticate user and return JWT tokens.
    """
    try:
        from django.contrib.auth import get_backends
        from .models import Profile, UserActivityLog

        backend = get_backends()[0]

        # Authenticate user
        user = authenticate(request, username=payload.email, password=payload.password)
        if not user:
            api_logger.log_authentication(None, False, "Invalid credentials")
            raise AuthenticationError("Invalid email or password")

        # Check if user is active
        if not user.is_active:
            api_logger.log_authentication(user.id, False, "Account not verified")
            raise AuthenticationError("Account not verified. Please check your email.")

        # Login user
        login(request, user, backend=backend.__class__.__name__)

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        # Get role
        role_name = getattr(user, 'role', 'client')

        # Ensure profile exists
        try:
            profile, created = Profile.objects.get_or_create(
                user=user,
                defaults={'role': role_name}
            )
        except Exception as e:
            core_logger.warning(f"Error creating profile: {str(e)}")
            profile = None

        # Log activity
        try:
            UserActivityLog.objects.create(
                user=user,
                activity_type="login",
                ip_address=request.META.get('REMOTE_ADDR')
            )
        except Exception as e:
            core_logger.warning(f"Error logging activity: {str(e)}")

        # Log successful authentication
        api_logger.log_authentication(user.id, True, "Login successful")
        core_logger.info(f"User {user.id} logged in successfully")

        return JsonResponse({
            "message": "Login successful",
            "access_token": access_token,
            "refresh_token": str(refresh),
            "user_id": user.id,
            "role": role_name,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email
        }, status=200)

    except AuthenticationError:
        raise
    except Exception as e:
        core_logger.error(f"Login error: {str(e)}", exc_info=True)
        raise InternalServerError("Login failed. Please try again.")


@log_endpoint(core_logger)
@accounts_router.post("/token/refresh/", tags=["Auth"], response={200: TokenRefreshOut, 400: ErrorOut, 401: ErrorOut})
def refresh_token(request, payload: RefreshTokenSchema):
    """
    Refresh an expired access token using a refresh token.

    Request body:
    {
        "refresh": "your_refresh_token_here"
    }

    Returns:
    {
        "access": "new_access_token"
    }
    """
    try:
        # Get refresh token from payload
        refresh_token_str = payload.refresh

        if not refresh_token_str:
            raise PaeshiftValidationError("Refresh token is required")

        # Validate and refresh the token
        try:
            refresh = RefreshToken(refresh_token_str)
            new_access_token = str(refresh.access_token)

            core_logger.info("Token refreshed successfully")
            return 200, TokenRefreshOut(access=new_access_token)
        except Exception as e:
            core_logger.error(f"Token refresh error: {str(e)}")
            raise AuthenticationError("Invalid or expired refresh token")

    except (PaeshiftValidationError, AuthenticationError):
        raise
    except Exception as e:
        core_logger.error(f"Unexpected error in token refresh: {str(e)}", exc_info=True)
        raise InternalServerError("An error occurred while refreshing the token")













@accounts_router.get("/debug/user-auth-info", tags=["Debug"])
def debug_user_auth_info(request):
    """Debug endpoint to check user authentication info"""
    try:
        user = User.objects.filter(email="fakoredeabbas@gmail.com").first()
        if not user:
            return JsonResponse({"error": "User not found"}, status=404)

        # Check if user has a usable password
        has_usable_password = user.has_usable_password()

        # Check authentication backends
        from django.contrib.auth import get_backends
        backends = [backend.__class__.__name__ for backend in get_backends()]

        # Test authentication with different approaches
        auth_tests = {}

        # Test 1: Direct authenticate with email
        from django.contrib.auth import authenticate
        test_user_email = authenticate(username="fakoredeabbas@gmail.com", password="@Kol@de1234")
        auth_tests["email_as_username"] = test_user_email is not None

        # Test 2: Check if username field is different
        auth_tests["username_field"] = user.USERNAME_FIELD
        auth_tests["actual_username"] = getattr(user, user.USERNAME_FIELD)

        return JsonResponse({
            "user_id": user.id,
            "email": user.email,
            "username": user.username,
            "is_active": user.is_active,
            "has_usable_password": has_usable_password,
            "auth_backends": backends,
            "auth_tests": auth_tests,
            "username_field": user.USERNAME_FIELD
        })

    except Exception as e:
        import traceback
        return JsonResponse({
            "error": str(e),
            "traceback": traceback.format_exc()
        }, status=500)

@accounts_router.post(
    "/logout",
    tags=["Auth"],
    response={200: MessageOut}
)
@time_view
def logout_view(request: HttpRequest):
    """
    Logs out the current user and invalidates related cache entries.

    Args:
        request: HTTP request with authenticated user

    Returns:
        200: Success message
    """
    # Start timing
    start_time = time.time()

    # Get user ID before logout
    user_id = request.user.id if request.user.is_authenticated else None

    # Perform Django's logout which clears the session data for the authenticated user
    logout(request)

    # Flush the session data completely
    request.session.flush()

    # Invalidate Redis cache for this user
    if user_id:
        # Clear all user-related cache keys
        cache_keys = [
            f"user:{user_id}",
            f"profile:{user_id}",
            f"whoami:{user_id}",
            f"user_logged_in:{user_id}",
            f"last_seen:{user_id}",
            # Legacy keys
            f"user_{user_id}_logged_in"
        ]

        for key in cache_keys:
            cache.delete(key)

        # Log telemetry for successful operation
        log_operation(
            operation="logout",
            key=f"user:{user_id}",
            success=True,
            duration_ms=(time.time() - start_time) * 1000,
            context="API endpoint: /logout"
        )

    # Return a response
    return MessageOut(message="Logged out successfully")




@accounts_router.get(
    "/whoami/{user_id}",
    tags=["Auth"],
    response={200: UserProfileResponse, 401: ErrorOut, 404: ErrorOut}
)
def whoami(request, user_id: int):
    start_time = time.time()

    if user_id == 0:
        if not request.user.is_authenticated:
            return 401, ErrorOut(error="Not authenticated")
        user_id = request.user.id

    try:
        user = User.objects.get(id=user_id)
        profile, _ = Profile.objects.get_or_create(user=user)

        # [SUCCESS] Profile picture
        from accounts.models import ProfilePicture
        active_pic = ProfilePicture.objects.filter(profile=profile, is_active=True).first()
        pic_url = active_pic.image.url if active_pic and active_pic.image else ""

        # [SUCCESS] Account details (if exist)
        account_details = None
        if hasattr(profile, "account_details") and profile.account_details:
            # account_details is a JSONField (dictionary), not an object
            account_details = {
                "bank_name": profile.account_details.get("bank_name", ""),
                "account_number": profile.account_details.get("account_number", ""),
                "account_holder": profile.account_details.get("account_holder", user.get_full_name()),
            }

        # [SUCCESS] Calculate real statistics
        from jobs.models import Job, Application
        from django.db.models import Count, Q

        # Job statistics (for clients)
        jobs_posted = Job.objects.filter(client=user)
        total_jobs_posted = jobs_posted.count()
        total_completed_jobs = jobs_posted.filter(status=Job.Status.COMPLETED).count()
        total_cancelled_jobs = jobs_posted.filter(status=Job.Status.CANCELED).count()

        # Workers engaged (unique applicants who applied to client's jobs)
        total_workers_engaged = Application.objects.filter(
            job__client=user
        ).values('applicant').distinct().count()

        # Activity statistics (for applicants)
        applications = Application.objects.filter(applicant=user)
        total_applied_jobs = applications.count()

        # Employers worked with (unique clients whose jobs the user applied to and got accepted)
        total_employers_worked_with = applications.filter(
            status=Application.Status.ACCEPTED
        ).values('job__client').distinct().count()

        # Get actual rating from profile
        actual_rating = profile.rating if profile else 5.0

        # Get review count
        try:
            from rating.models import Review
            review_count = Review.objects.filter(reviewed=user).count()
        except ImportError:
            review_count = 0

        response = {
            "user_id": int(user.id),
            "username": str(user.username),
            "email": str(user.email),
            "first_name": str(user.first_name),
            "last_name": str(user.last_name),
            "location": str(getattr(profile, 'location', None) or ""),
            "bio": str(getattr(profile, 'bio', None) or ""),
            "phone_number": str(getattr(profile, 'phone_number', None) or ""),
            "role": str(getattr(profile, 'role', 'client')),
            "wallet_balance": str(get_wallet_balance(user)),
            "badges": list(getattr(profile, 'badges', []) or []),
            "profile_pic_url": str(pic_url),
            "rating": float(actual_rating),
            "review_count": int(review_count),
            "job_stats": {
                "total_jobs_posted": total_jobs_posted,
                "total_workers_engaged": total_workers_engaged,
                "total_completed_jobs": total_completed_jobs,
                "total_cancelled_jobs": total_cancelled_jobs,
            },
            "activity_stats": {
                "total_applied_jobs": total_applied_jobs,
                "total_employers_worked_with": total_employers_worked_with,
            },
            # [SUCCESS] Include account details
            "account_details": account_details,
        }

        # Normalize None strings
        for field in ["location", "bio", "phone_number"]:
            if response[field] == "None":
                response[field] = None

        log_operation(
            operation="whoami",
            key=f"user:{user_id}",
            success=True,
            duration_ms=(time.time() - start_time) * 1000,
            context="API endpoint: /whoami/{user_id}"
        )

        return 200, UserProfileResponse(**response)

    except User.DoesNotExist:
        log_operation(
            operation="whoami",
            key=f"user:{user_id}",
            success=False,
            duration_ms=(time.time() - start_time) * 1000,
            context="API endpoint: /whoami/{user_id} - User not found"
        )
        return 404, ErrorOut(error="User not found")

    except Exception as e:
        log_operation(
            operation="whoami",
            key=f"user:{user_id}",
            success=False,
            duration_ms=(time.time() - start_time) * 1000,
            context=f"API endpoint: /whoami/{user_id} - Unexpected error: {str(e)}"
        )
        logger.error(f"Unexpected error in whoami endpoint for user {user_id}: {str(e)}", exc_info=True)
        return 500, ErrorOut(error="Internal server error")


# @accounts_router.get(
#     "/whoami/{user_id}",
#     tags=["Auth"],
#     response={200: UserProfileResponse, 401: ErrorOut, 404: ErrorOut}
# )
# def whoami(request, user_id: int):
#     """
#     Get user details and activity stats.

#     Args:
#         user_id: User ID to get details for. Special case: user_id=0 returns current authenticated user.

#     Returns:
#         200: User profile information
#         401: Not authenticated (when user_id=0 and not logged in)
#         404: User not found

#     This endpoint uses the hibernate decorator to cache results permanently
#     while automatically invalidating the cache when the underlying data changes.
#     """
#     # Start timing
#     start_time = time.time()

#     # For current user (user_id=0)
#     if user_id == 0:
#         if not request.user.is_authenticated:
#             return 401, ErrorOut(error="Not authenticated")
#         user_id = request.user.id

#     # Create response directly without any caching to avoid DjangoGetter issues
#     try:
#         user = User.objects.get(id=user_id)
#         profile, _ = Profile.objects.get_or_create(user=user)

#         # Get profile picture URL
#         from accounts.models import ProfilePicture
#         active_pic = ProfilePicture.objects.filter(profile=profile, is_active=True).first()
#         pic_url = active_pic.image.url if active_pic and active_pic.image else ""

#         # Create response dictionary directly with explicit type conversion
#         response = {
#             "user_id": int(user.id),
#             "username": str(user.username),
#             "email": str(user.email),
#             "first_name": str(user.first_name),
#             "last_name": str(user.last_name),
#             "location": str(getattr(profile, 'location', None) or getattr(user, 'location', None) or ""),
#             "bio": str(getattr(profile, 'bio', None) or ""),
#             "phone_number": str(getattr(profile, 'phone_number', None) or ""),
#             "role": str(getattr(profile, 'role', 'client')),
#             "wallet_balance": str(get_wallet_balance(user)),
#             "badges": list(getattr(profile, 'badges', []) or []),
#             "profile_pic_url": str(pic_url),
#             "rating": float(5.0),
#             "review_count": int(0),
#             "job_stats": {
#                 "total_jobs_posted": int(0),
#                 "total_workers_engaged": int(0),
#                 "total_completed_jobs": int(0),
#                 "total_cancelled_jobs": int(0),
#             },
#             "activity_stats": {
#                 "total_applied_jobs": int(0),
#                 "total_employers_worked_with": int(0),
#             }
#         }

#         # Handle None values for optional fields
#         if response["location"] == "None":
#             response["location"] = None
#         if response["bio"] == "None":
#             response["bio"] = None
#         if response["phone_number"] == "None":
#             response["phone_number"] = None

#         # Log telemetry for successful operation
#         log_operation(
#             operation="whoami",
#             key=f"user:{user_id}",
#             success=True,
#             duration_ms=(time.time() - start_time) * 1000,
#             context="API endpoint: /whoami/{user_id}"
#         )

#         return 200, UserProfileResponse(**response)
#     except User.DoesNotExist:
#         # Log telemetry for error
#         log_operation(
#             operation="whoami",
#             key=f"user:{user_id}",
#             success=False,
#             duration_ms=(time.time() - start_time) * 1000,
#             context="API endpoint: /whoami/{user_id} - User not found"
#         )

#         return 404, ErrorOut(error="User not found")


# Import the hibernate decorator
# from payment.models import Wallet  # Temporarily commented out
# @hibernate(depends_on=[User, Profile, Wallet])
# def get_hibernated_user_response_by_id(user_id):
#     """
#     Get user response with hibernation based on user_id.
#
#     This function is decorated with @hibernate, which means:
#     1. Results are cached permanently
#     2. Cache is automatically invalidated when User, Profile, or Wallet models change
#     3. Function is only called once for each user_id until the cache is invalidated
#
#     Args:
#         user_id: User ID
#
#     Returns:
#         User response dict
#     """
#     logger.debug(f"Generating hibernated user response for user_id={user_id}")
#     user = User.objects.get(id=user_id)
#     return get_user_response(user)


# ==
# [MARKER] User Activity Endpoints
# ==

# Temporarily commented out - depends on gamification app
# @accounts_router.get(
#     "/active-users/{last_minutes}/",
#     tags=["User Activity"],
#     response={200: ActiveUsersResponse, 500: ErrorOut},
#     summary="Get active user IDs",
#     description="Get a list of user IDs that have been active within the specified time window"
# )
# @time_view("get_active_users_api")
# @cache_api_response(timeout=60)  # Cache for 1 minute
def get_active_users_endpoint_disabled(request, last_minutes: int):
    """
    Get a list of user IDs that have been active within the specified time window.

    Args:
        last_minutes: Time window in minutes (e.g., 15 for users active in the last 15 minutes)

    Returns:
        200: List of active user IDs
        500: Server error
    """
    # Start timing for telemetry
    start_time = time.time()

    try:
        # Validate input
        if last_minutes <= 0:
            last_minutes = 15  # Default to 15 minutes if invalid

        # Get active users
        active_user_ids = get_active_users(last_minutes)

        # Create response
        response = ActiveUsersResponse(
            active_user_ids=active_user_ids,
            count=len(active_user_ids),
            minutes=last_minutes
        )

        # Log telemetry for successful operation
        log_operation(
            operation="get_active_users",
            key=f"active_users:{last_minutes}",
            success=True,
            duration_ms=(time.time() - start_time) * 1000,
            context="API endpoint: /active-users/{last_minutes}"
        )

        return 200, response

    except Exception as e:
        # Log telemetry for error
        log_operation(
            operation="get_active_users",
            key=f"active_users:{last_minutes}",
            success=False,
            duration_ms=(time.time() - start_time) * 1000,
            context=f"API endpoint: /active-users/{last_minutes} - Error: {str(e)}"
        )

        logger.error(f"Error getting active users: {str(e)}")
        return 500, ErrorOut(error=f"An error occurred: {str(e)}")


# Temporarily commented out - depends on gamification app
# @accounts_router.get(
#     "/users/{user_id}/last-seen/",
#     tags=["User Activity"],
#     response={200: LastSeenResponse, 404: ErrorOut, 500: ErrorOut},
#     summary="Get user last seen",
#     description="Get the timestamp when a user was last seen"
# )
# @time_view("get_user_last_seen_api")
# @cache_api_response(timeout=60)  # Cache for 1 minute
def get_user_last_seen_endpoint_disabled(request, user_id: int):
    """
    Get the timestamp when a user was last seen.

    Args:
        user_id: User ID

    Returns:
        200: Last seen timestamp
        404: User not found
        500: Server error
    """
    # Start timing for telemetry
    start_time = time.time()

    try:
        # Find the user
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return 404, ErrorOut(error="User not found")

        # Get last seen timestamp
        last_seen_timestamp = get_user_last_seen(user)

        # Format timestamp if available
        last_seen_formatted = None
        is_online = False

        if last_seen_timestamp:
            # Format timestamp
            last_seen_formatted = datetime.fromtimestamp(last_seen_timestamp).strftime("%Y-%m-%d %H:%M:%S")

            # Check if user is online (active in the last 5 minutes)
            is_online = (time.time() - last_seen_timestamp) < (5 * 60)  # 5 minutes

        # Create response
        response = LastSeenResponse(
            user_id=user_id,
            last_seen_timestamp=last_seen_timestamp,
            last_seen_formatted=last_seen_formatted,
            is_online=is_online
        )

        # Log telemetry for successful operation
        log_operation(
            operation="get_user_last_seen",
            key=f"last_seen:{user_id}",
            success=True,
            duration_ms=(time.time() - start_time) * 1000,
            context="API endpoint: /users/{user_id}/last-seen"
        )

        return 200, response

    except Exception as e:
        pass

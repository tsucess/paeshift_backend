"""
API endpoints for OTP verification.

This module provides API endpoints for:
1. Initial account verification
2. Login from new devices
3. Two-factor authentication (2FA)
4. Password reset verification
5. Sensitive operations verification
"""

import logging
import json
from datetime import timedelta
from typing import Dict, List, Optional, Any

from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ObjectDoesNotExist
from ninja import Router
from ninja.security import HttpBearer

from .models import OTP, Profile, UserActivityLog
from .utils import generate_otp, send_otp_email, send_otp_sms, rate_limit_otp_requests
from .schemas import MessageOut, OTPRequestSchema, OTPVerifySchema, DeviceInfoSchema

# Initialize logger
logger = logging.getLogger(__name__)

# Initialize router
otp_router = Router(tags=["OTP"])

# Get User model
User = get_user_model()

# OTP Types
OTP_TYPE_REGISTRATION = "registration"
OTP_TYPE_LOGIN = "login"
OTP_TYPE_PASSWORD_RESET = "password_reset"
OTP_TYPE_2FA = "2fa"
OTP_TYPE_SENSITIVE_OP = "sensitive_operation"

# Device verification settings
DEVICE_VERIFICATION_DAYS = 30  # How long to trust a verified device


@otp_router.post(
    "/request",
    response={200: MessageOut, 400: MessageOut, 429: MessageOut}
)
def request_otp(request, payload: OTPRequestSchema):
    """
    Request an OTP for various verification purposes.
    
    Args:
        payload: OTP request data including email and purpose
        
    Returns:
        200: Success message
        400: Error message
        429: Rate limit exceeded message
    """
    try:
        email = payload.email.lower().strip()
        otp_type = payload.type
        phone = payload.phone
        operation = payload.operation
        
        # Validate OTP type
        valid_types = [
            OTP_TYPE_REGISTRATION, 
            OTP_TYPE_LOGIN, 
            OTP_TYPE_PASSWORD_RESET,
            OTP_TYPE_2FA,
            OTP_TYPE_SENSITIVE_OP
        ]
        
        if otp_type not in valid_types:
            logger.warning(f"Invalid OTP type requested: {otp_type}")
            return 400, {"message": f"Invalid OTP type. Must be one of: {', '.join(valid_types)}"}
        
        # For registration, check if email already exists
        if otp_type == OTP_TYPE_REGISTRATION:
            if User.objects.filter(email=email).exists():
                logger.info(f"Registration OTP requested for existing email: {email}")
                # Don't reveal that the email exists for security reasons
                return 200, {"message": "If the email exists, an OTP has been sent."}
        
        # For other types, verify the user exists
        elif not User.objects.filter(email=email).exists():
            logger.info(f"OTP requested for non-existent email: {email}")
            # Don't reveal that the email doesn't exist for security reasons
            return 200, {"message": "If the email exists, an OTP has been sent."}
        
        # Get user if exists (for non-registration flows)
        user = None
        if otp_type != OTP_TYPE_REGISTRATION:
            try:
                user = User.objects.get(email=email)
                
                # Check if user is locked out
                if OTP.is_user_locked_out(user):
                    logger.warning(f"OTP requested for locked out user: {email}")
                    return 400, {
                        "message": f"Account temporarily locked due to too many failed attempts. "
                                  f"Please try again after {OTP.LOCKOUT_MINUTES} minutes."
                    }
            except User.DoesNotExist:
                # Already handled above, but keeping this for clarity
                pass
        
        # Generate OTP
        otp_code = generate_otp()
        
        # Store OTP with metadata
        metadata = {
            "type": otp_type,
            "email": email,
            "operation": operation,
            "ip_address": request.META.get("REMOTE_ADDR", "unknown"),
            "user_agent": request.META.get("HTTP_USER_AGENT", "unknown"),
        }
        
        # Create or update OTP
        if user:
            # Delete existing OTPs for this user and type
            OTP.objects.filter(user=user).delete()
            
            # Create new OTP
            otp = OTP.objects.create(
                user=user,
                code=otp_code,
                metadata=json.dumps(metadata)
            )
            
            # Send OTP via email
            send_otp_email(user, otp_code)
            
            # Send OTP via SMS if phone number is available
            if phone:
                send_otp_sms(phone, otp_code)
            elif hasattr(user, 'profile') and user.profile.phone_number:
                send_otp_sms(user.profile.phone_number, otp_code)
                
            # Log the activity
            UserActivityLog.objects.create(
                user=user,
                activity_type=f"otp_request_{otp_type}",
                ip_address=request.META.get("REMOTE_ADDR")
            )
        else:
            # For registration, we don't have a user yet, so just send the email
            if otp_type == OTP_TYPE_REGISTRATION:
                # Store OTP in session for later verification
                request.session["registration_otp"] = {
                    "code": otp_code,
                    "email": email,
                    "created_at": timezone.now().isoformat(),
                    "metadata": metadata
                }
                
                # Send OTP via email
                send_mail_to_nonuser(email, otp_code)
                
                # Send OTP via SMS if phone number is provided
                if phone:
                    send_otp_sms(phone, otp_code)
        
        logger.info(f"OTP sent for {otp_type} to {email}")
        return 200, {"message": "OTP sent successfully. Please check your email or phone."}
        
    except Exception as e:
        logger.error(f"Error sending OTP: {str(e)}")
        return 400, {"message": "Error sending OTP. Please try again later."}


@otp_router.post(
    "/verify",
    response={200: MessageOut, 400: MessageOut, 401: MessageOut}
)
def verify_otp(request, payload: OTPVerifySchema):
    """
    Verify an OTP code.
    
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
        otp_type = payload.type
        device_info = payload.device_info
        
        # For registration OTP verification
        if otp_type == OTP_TYPE_REGISTRATION:
            # Get OTP from session
            registration_otp = request.session.get("registration_otp")
            
            if not registration_otp:
                logger.warning(f"No registration OTP found in session for {email}")
                return 400, {"message": "No OTP found. Please request a new one."}
            
            # Verify email matches
            if registration_otp["email"] != email:
                logger.warning(f"Email mismatch in registration OTP verification: {email}")
                return 401, {"message": "Invalid OTP."}
            
            # Verify code
            if registration_otp["code"] != code:
                logger.warning(f"Invalid registration OTP code for {email}")
                return 401, {"message": "Invalid OTP."}
            
            # Verify not expired
            created_at = timezone.datetime.fromisoformat(registration_otp["created_at"])
            if timezone.now() > created_at + timedelta(minutes=OTP.EXPIRY_MINUTES):
                logger.warning(f"Expired registration OTP for {email}")
                return 401, {"message": "OTP has expired. Please request a new one."}
            
            # OTP is valid for registration
            # Clear the OTP from session
            del request.session["registration_otp"]
            
            # Return success with verification token
            verification_token = generate_verification_token(email, otp_type)
            return 200, {
                "message": "OTP verified successfully.",
                "verification_token": verification_token
            }
        
        # For other OTP types
        else:
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                logger.warning(f"OTP verification attempted for non-existent user: {email}")
                return 401, {"message": "Invalid OTP."}
            
            # Check if user is locked out
            if OTP.is_user_locked_out(user):
                logger.warning(f"OTP verification attempted for locked out user: {email}")
                return 400, {
                    "message": f"Account temporarily locked due to too many failed attempts. "
                              f"Please try again after {OTP.LOCKOUT_MINUTES} minutes."
                }
            
            # Get the latest OTP for this user
            otp = OTP.objects.filter(user=user).order_by('-created_at').first()
            
            if not otp:
                logger.warning(f"No OTP found for user: {email}")
                return 400, {"message": "No OTP found. Please request a new one."}
            
            # Verify OTP
            if otp.code != code:
                # Invalid OTP - increment attempts counter
                is_locked = otp.increment_attempts()
                remaining = OTP.MAX_ATTEMPTS - otp.attempts
                
                if is_locked:
                    logger.warning(f"User locked out after too many OTP attempts: {email}")
                    return 400, {
                        "message": f"Too many failed attempts. Account locked for {OTP.LOCKOUT_MINUTES} minutes."
                    }
                else:
                    logger.warning(f"Invalid OTP for {email}. Attempts: {otp.attempts}/{OTP.MAX_ATTEMPTS}")
                    return 401, {
                        "message": f"Invalid OTP. {remaining} attempts remaining."
                    }
            
            # Check if OTP is valid (not expired)
            if not otp.is_valid():
                logger.warning(f"Expired OTP for {email}")
                return 401, {"message": "OTP has expired. Please request a new one."}
            
            # OTP is valid
            otp.mark_as_verified()
            
            # If device info is provided, store it for trusted devices
            if device_info and otp_type in [OTP_TYPE_LOGIN, OTP_TYPE_2FA]:
                store_trusted_device(user, device_info)
            
            # Log the activity
            UserActivityLog.objects.create(
                user=user,
                activity_type=f"otp_verified_{otp_type}",
                ip_address=request.META.get("REMOTE_ADDR")
            )
            
            # Generate verification token
            verification_token = generate_verification_token(email, otp_type)
            
            # Return success with verification token
            return 200, {
                "message": "OTP verified successfully.",
                "verification_token": verification_token
            }
    
    except Exception as e:
        logger.error(f"Error verifying OTP: {str(e)}")
        return 400, {"message": "Error verifying OTP. Please try again later."}


# Helper functions

def send_mail_to_nonuser(email, otp_code):
    """Send OTP email to a non-user (for registration)"""
    from django.core.mail import send_mail
    from django.conf import settings
    
    try:
        send_mail(
            subject="Your Registration Verification Code",
            message=(
                f"Hello,\n\n"
                f"Your verification code for account registration is: {otp_code}\n\n"
                f"This code will expire in 5 minutes.\n\n"
                f"If you did not request this code, please ignore this email.\n\n"
                f"Do not share this code with anyone.\n\n"
                f"Regards,\nThe Security Team"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        logger.info(f"Registration OTP email sent to {email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send registration OTP email to {email}: {str(e)}")
        return False


def generate_verification_token(email, otp_type):
    """Generate a verification token for the given email and OTP type"""
    import uuid
    import hashlib
    from django.conf import settings
    
    # Create a unique token
    unique_str = f"{email}:{otp_type}:{uuid.uuid4()}:{settings.SECRET_KEY}"
    token = hashlib.sha256(unique_str.encode()).hexdigest()
    
    return token


def store_trusted_device(user, device_info):
    """Store device information as a trusted device"""
    from django.core.cache import cache
    
    # Create a unique device identifier
    device_id = f"{device_info.device_id}:{device_info.device_name}"
    
    # Store in cache with expiration
    cache_key = f"trusted_device:{user.id}:{device_id}"
    cache.set(
        cache_key,
        {
            "device_id": device_info.device_id,
            "device_name": device_info.device_name,
            "device_type": device_info.device_type,
            "trusted_at": timezone.now().isoformat(),
            "ip_address": device_info.ip_address,
        },
        60 * 60 * 24 * DEVICE_VERIFICATION_DAYS  # Cache for DEVICE_VERIFICATION_DAYS days
    )
    
    logger.info(f"Stored trusted device for user {user.id}: {device_info.device_name}")
    return True

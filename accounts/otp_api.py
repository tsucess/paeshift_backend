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

from .models import OTP, TemporaryOTP, Profile, UserActivityLog
from .utils import generate_otp, send_otp_email, send_otp_sms, rate_limit_otp_requests, send_mail_to_nonuser
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

        logger.info(f"[OTP] request_otp called with email={email}, type={otp_type}, phone={phone}")
        logger.info(f"[OTP] OTP_TYPE_REGISTRATION constant value: {OTP_TYPE_REGISTRATION}")
        logger.info(f"[OTP] Comparing: otp_type ({repr(otp_type)}) == OTP_TYPE_REGISTRATION ({repr(OTP_TYPE_REGISTRATION)}) = {otp_type == OTP_TYPE_REGISTRATION}")

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
        
        # For registration, we still need to send OTP even if user exists
        # (user is created before OTP is requested in signup flow)
        if otp_type == OTP_TYPE_REGISTRATION:
            logger.info(f"Registration OTP requested for email: {email}")
        
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
            # For registration, we don't have a user yet, so use TemporaryOTP model
            if otp_type == OTP_TYPE_REGISTRATION:
                # Delete any existing OTPs for this email
                TemporaryOTP.objects.filter(email=email, otp_type=otp_type).delete()

                # Create new temporary OTP in database
                temp_otp = TemporaryOTP.objects.create(
                    email=email,
                    code=otp_code,
                    otp_type=otp_type,
                    metadata=json.dumps(metadata)
                )
                logger.info(f"[OTP] Created TemporaryOTP in database for {email}, ID: {temp_otp.id}")

                # Send OTP via email with retry logic
                email_sent = send_mail_to_nonuser(email, otp_code)
                if not email_sent:
                    logger.warning(f"Initial email send failed for {email}, will retry")
                    # Attempt retry after short delay
                    import time
                    time.sleep(2)
                    email_sent = send_mail_to_nonuser(email, otp_code)
                    if not email_sent:
                        logger.error(f"Failed to send OTP email to {email} after retry")

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
            logger.info(f"[OTP_VERIFY] Looking for registration OTP for {email}")
            # Get OTP from database
            temp_otp = TemporaryOTP.objects.filter(
                email=email,
                otp_type=otp_type
            ).order_by('-created_at').first()

            if not temp_otp:
                logger.warning(f"[OTP_VERIFY] No registration OTP found in database for {email}")
                return 400, {"message": "No OTP found. Please request a new one."}

            logger.info(f"[OTP_VERIFY] Found OTP for {email}, ID: {temp_otp.id}, is_verified: {temp_otp.is_verified}")

            # Check if OTP is valid (not expired, not too many attempts)
            if not temp_otp.is_valid():
                logger.warning(f"[OTP_VERIFY] Registration OTP is invalid (expired or too many attempts) for {email}")
                return 401, {"message": "OTP has expired or too many attempts. Please request a new one."}

            # Verify code
            if temp_otp.code != code:
                logger.warning(f"[OTP_VERIFY] Invalid registration OTP code for {email}. Expected: {temp_otp.code}, Got: {code}")
                temp_otp.increment_attempts()
                return 401, {"message": "Invalid OTP."}

            logger.info(f"[OTP_VERIFY] OTP code matches for {email}. Marking as verified and deleting.")
            # OTP is valid for registration
            # Mark as verified and delete
            temp_otp.mark_as_verified()
            temp_otp.delete()
            logger.info(f"[OTP] Registration OTP verified successfully for {email}")

            # Return success with verification token
            verification_token = generate_verification_token(email, otp_type)
            logger.info(f"[OTP_VERIFY] Generated verification token for {email}")
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

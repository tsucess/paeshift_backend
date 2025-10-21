"""
Decorators for protecting sensitive operations with OTP verification.

This module provides decorators for:
1. Requiring OTP verification for sensitive operations
2. Checking if a device is trusted
"""

import functools
import json
import logging
from typing import Callable, Dict, Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpRequest, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse

from .models import TrustedDevice, OTP
from .otp_api import request_otp, OTP_TYPE_SENSITIVE_OP

# Initialize logger
logger = logging.getLogger(__name__)

# Get User model
User = get_user_model()


def require_otp_verification(operation_name: str):
    """
    Decorator to require OTP verification for sensitive operations.
    
    Args:
        operation_name: Name of the operation (used for logging and in OTP messages)
        
    Returns:
        Decorator function
    """
    def decorator(view_func: Callable):
        @functools.wraps(view_func)
        def wrapped_view(request: HttpRequest, *args, **kwargs):
            # Skip for unauthenticated users (they'll be redirected to login)
            if not request.user.is_authenticated:
                return view_func(request, *args, **kwargs)
            
            # Check if operation is already verified
            verified_operations = request.session.get('verified_operations', {})
            if operation_name in verified_operations:
                # Check if verification is still valid (within 30 minutes)
                import time
                verification_time = verified_operations[operation_name]
                if time.time() - verification_time < 30 * 60:  # 30 minutes
                    # Verification is still valid
                    return view_func(request, *args, **kwargs)
            
            # Operation needs verification
            # Store original request path and args in session
            request.session['pending_operation'] = {
                'name': operation_name,
                'path': request.path,
                'args': json.dumps(kwargs),
                'method': request.method,
            }
            
            # For API requests, return JSON response
            if request.headers.get('Accept') == 'application/json' or request.path.startswith('/api/'):
                return JsonResponse({
                    "error": f"Operation '{operation_name}' requires verification",
                    "requires_verification": True,
                    "verification_type": "sensitive_operation",
                    "operation": operation_name,
                    "user_id": request.user.id,
                    "email": request.user.email,
                }, status=403)
            
            # For regular requests, redirect to OTP verification page
            # Send OTP first
            from .schemas import OTPRequestSchema
            try:
                # Get user profile for phone number
                phone = None
                if hasattr(request.user, 'profile') and hasattr(request.user.profile, 'phone_number'):
                    phone = request.user.profile.phone_number
                
                # Create OTP request payload
                otp_payload = OTPRequestSchema(
                    email=request.user.email,
                    type=OTP_TYPE_SENSITIVE_OP,
                    phone=phone,
                    operation=operation_name
                )
                
                # Request OTP
                request_otp(request, otp_payload)
                
                logger.info(f"Sent OTP for sensitive operation '{operation_name}' to {request.user.email}")
            except Exception as e:
                logger.error(f"Error sending OTP for sensitive operation: {str(e)}")
            
            # Redirect to verification page
            return redirect(reverse("verify_sensitive_operation"))
        
        return wrapped_view
    
    return decorator

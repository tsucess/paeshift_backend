"""
Multi-factor authentication utilities for God Mode.

This module provides utilities for implementing TOTP-based MFA for God Mode access.
"""

import base64
import hmac
import logging
import os
import time
from typing import Optional, Tuple

import pyotp
import qrcode
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import HttpRequest
from io import BytesIO

User = get_user_model()
logger = logging.getLogger(__name__)

# Constants
MFA_SECRET_LENGTH = 32  # Length of the MFA secret in bytes
MFA_ISSUER = "Payshift God Mode"  # Issuer name for TOTP
MFA_DIGITS = 6  # Number of digits in TOTP code
MFA_INTERVAL = 30  # TOTP interval in seconds
MFA_WINDOW = 1  # Number of intervals to check before/after current time
MFA_VERIFICATION_TIMEOUT = 300  # Timeout for MFA verification in seconds
MFA_SESSION_KEY = "godmode_mfa_verified"  # Session key for MFA verification status
MFA_CACHE_PREFIX = "mfa_secret:"  # Cache prefix for MFA secrets
MFA_CACHE_TIMEOUT = 60 * 60 * 24 * 30  # 30 days


def generate_mfa_secret() -> str:
    """
    Generate a random MFA secret.
    
    Returns:
        Base32 encoded secret
    """
    # Generate random bytes
    random_bytes = os.urandom(MFA_SECRET_LENGTH)
    
    # Encode as base32
    secret = base64.b32encode(random_bytes).decode("utf-8")
    
    return secret


def get_totp_uri(user: User, secret: str) -> str:
    """
    Get the TOTP URI for QR code generation.
    
    Args:
        user: User object
        secret: MFA secret
        
    Returns:
        TOTP URI
    """
    # Create TOTP object
    totp = pyotp.TOTP(secret)
    
    # Generate URI
    uri = totp.provisioning_uri(
        name=user.email,
        issuer_name=MFA_ISSUER,
    )
    
    return uri


def generate_qr_code(uri: str) -> bytes:
    """
    Generate a QR code for the TOTP URI.
    
    Args:
        uri: TOTP URI
        
    Returns:
        QR code image as bytes
    """
    # Create QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(uri)
    qr.make(fit=True)
    
    # Create image
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save to bytes
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    
    return buffer.getvalue()


def verify_totp_code(secret: str, code: str) -> bool:
    """
    Verify a TOTP code.
    
    Args:
        secret: MFA secret
        code: TOTP code
        
    Returns:
        True if valid, False otherwise
    """
    # Create TOTP object
    totp = pyotp.TOTP(secret)
    
    # Verify code
    return totp.verify(code, valid_window=MFA_WINDOW)


def get_user_mfa_secret(user_id: int) -> Optional[str]:
    """
    Get the MFA secret for a user.
    
    Args:
        user_id: User ID
        
    Returns:
        MFA secret or None if not set
    """
    from godmode.models import MFASecret
    
    try:
        # Try to get from database
        mfa_secret = MFASecret.objects.get(user_id=user_id)
        return mfa_secret.secret
    except MFASecret.DoesNotExist:
        # Try to get from cache
        cache_key = f"{MFA_CACHE_PREFIX}{user_id}"
        return cache.get(cache_key)


def set_user_mfa_secret(user_id: int, secret: str) -> bool:
    """
    Set the MFA secret for a user.
    
    Args:
        user_id: User ID
        secret: MFA secret
        
    Returns:
        True if successful, False otherwise
    """
    from godmode.models import MFASecret
    
    try:
        # Store in database
        mfa_secret, created = MFASecret.objects.update_or_create(
            user_id=user_id,
            defaults={"secret": secret},
        )
        
        # Store in cache
        cache_key = f"{MFA_CACHE_PREFIX}{user_id}"
        cache.set(cache_key, secret, MFA_CACHE_TIMEOUT)
        
        return True
    except Exception as e:
        logger.error(f"Error setting MFA secret for user {user_id}: {str(e)}")
        return False


def is_mfa_enabled(user_id: int) -> bool:
    """
    Check if MFA is enabled for a user.
    
    Args:
        user_id: User ID
        
    Returns:
        True if enabled, False otherwise
    """
    return get_user_mfa_secret(user_id) is not None


def is_mfa_verified(request: HttpRequest) -> bool:
    """
    Check if MFA is verified for the current session.
    
    Args:
        request: HTTP request
        
    Returns:
        True if verified, False otherwise
    """
    # Check session
    return request.session.get(MFA_SESSION_KEY, False)


def set_mfa_verified(request: HttpRequest, verified: bool = True) -> None:
    """
    Set MFA verification status for the current session.
    
    Args:
        request: HTTP request
        verified: Verification status
    """
    # Set session
    request.session[MFA_SESSION_KEY] = verified
    
    # If verified, log the verification
    if verified and request.user.is_authenticated:
        logger.info(f"MFA verified for user {request.user.id}")


def setup_mfa(user_id: int) -> Tuple[str, str]:
    """
    Set up MFA for a user.
    
    Args:
        user_id: User ID
        
    Returns:
        Tuple of (secret, uri)
    """
    # Generate secret
    secret = generate_mfa_secret()
    
    # Get user
    user = User.objects.get(id=user_id)
    
    # Generate URI
    uri = get_totp_uri(user, secret)
    
    # Store secret temporarily (will be confirmed later)
    cache_key = f"mfa_setup:{user_id}"
    cache.set(cache_key, secret, MFA_VERIFICATION_TIMEOUT)
    
    return secret, uri


def confirm_mfa_setup(user_id: int, code: str) -> bool:
    """
    Confirm MFA setup by verifying a TOTP code.
    
    Args:
        user_id: User ID
        code: TOTP code
        
    Returns:
        True if successful, False otherwise
    """
    # Get temporary secret
    cache_key = f"mfa_setup:{user_id}"
    secret = cache.get(cache_key)
    
    if not secret:
        logger.warning(f"MFA setup expired for user {user_id}")
        return False
    
    # Verify code
    if not verify_totp_code(secret, code):
        logger.warning(f"Invalid MFA code for user {user_id}")
        return False
    
    # Store secret permanently
    success = set_user_mfa_secret(user_id, secret)
    
    # Delete temporary secret
    cache.delete(cache_key)
    
    return success


def disable_mfa(user_id: int) -> bool:
    """
    Disable MFA for a user.
    
    Args:
        user_id: User ID
        
    Returns:
        True if successful, False otherwise
    """
    from godmode.models import MFASecret
    
    try:
        # Delete from database
        MFASecret.objects.filter(user_id=user_id).delete()
        
        # Delete from cache
        cache_key = f"{MFA_CACHE_PREFIX}{user_id}"
        cache.delete(cache_key)
        
        return True
    except Exception as e:
        logger.error(f"Error disabling MFA for user {user_id}: {str(e)}")
        return False

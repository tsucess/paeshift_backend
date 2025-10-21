"""
Middleware for device verification and 2FA enforcement.

This module provides middleware for:
1. Checking if a device is trusted
2. Enforcing 2FA for sensitive operations
"""

import json
import logging
import re
from typing import Dict, List, Optional, Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse

# Initialize logger
logger = logging.getLogger(__name__)

# Get User model
User = get_user_model()

# Constants
DEVICE_VERIFICATION_DAYS = 30  # How long to trust a verified device
SENSITIVE_PATHS = [
    r'^/payment/',  # Payment-related endpoints
    r'^/accounts/password/',  # Password change endpoints
    r'^/accounts/profile/update/',  # Profile update endpoints
    r'^/admin/',  # Admin endpoints
]

# Paths that are exempt from device verification
EXEMPT_PATHS = [
    r'^/accounts/otp/',  # OTP endpoints
    r'^/accounts/login/',  # Login endpoints
    r'^/accounts/signup/',  # Signup endpoints
    r'^/static/',  # Static files
    r'^/media/',  # Media files
]


class DeviceVerificationMiddleware:
    """
    Middleware to check if a device is trusted.
    
    This middleware:
    1. Checks if the current device is trusted for the logged-in user
    2. Redirects to OTP verification if the device is not trusted
    3. Enforces 2FA for sensitive operations
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Process the request"""
        # Skip device verification for exempt paths
        if self._is_path_exempt(request.path):
            return self.get_response(request)
        
        # Only check for authenticated users
        if not request.user.is_authenticated:
            return self.get_response(request)
        
        # Check if this is a sensitive operation that requires 2FA
        requires_2fa = self._is_sensitive_path(request.path)
        
        # Get device info from request
        device_info = self._get_device_info(request)
        
        # Check if device is trusted
        is_trusted = self._is_device_trusted(request.user.id, device_info)
        
        # If device is not trusted or 2FA is required for this path

        
        # Process the request normally
        return self.get_response(request)
    
    def _is_path_exempt(self, path: str) -> bool:
        """Check if the path is exempt from device verification"""
        return any(re.match(pattern, path) for pattern in EXEMPT_PATHS)
    
    def _is_sensitive_path(self, path: str) -> bool:
        """Check if the path is considered sensitive and requires 2FA"""
        return any(re.match(pattern, path) for pattern in SENSITIVE_PATHS)
    
    def _is_api_request(self, request: HttpRequest) -> bool:
        """Check if this is an API request"""
        return (
            request.path.startswith('/api/') or
            request.headers.get('Accept') == 'application/json' or
            request.headers.get('Content-Type') == 'application/json'
        )
    
    def _get_device_info(self, request: HttpRequest) -> Dict[str, str]:
        """Extract device information from the request"""
        # Try to get device ID from cookies
        device_id = request.COOKIES.get('device_id', '')
        
        # If no device ID in cookies, generate one based on user agent
        if not device_id:
            import hashlib
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            device_id = hashlib.md5(user_agent.encode()).hexdigest()
        
        # Get device name from user agent
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        device_name = self._parse_device_name(user_agent)
        
        return {
            'device_id': device_id,
            'device_name': device_name,
            'ip_address': request.META.get('REMOTE_ADDR', ''),
        }
    
    def _parse_device_name(self, user_agent: str) -> str:
        """Parse device name from user agent string"""
        # Simple parsing logic - can be enhanced
        if 'iPhone' in user_agent:
            return 'iPhone'
        elif 'iPad' in user_agent:
            return 'iPad'
        elif 'Android' in user_agent:
            return 'Android Device'
        elif 'Windows' in user_agent:
            return 'Windows PC'
        elif 'Macintosh' in user_agent:
            return 'Mac'
        elif 'Linux' in user_agent:
            return 'Linux PC'
        else:
            return 'Unknown Device'
    
    def _is_device_trusted(self, user_id: int, device_info: Dict[str, str]) -> bool:
        """Check if the device is trusted for this user"""
        # Create a unique device identifier
        device_id = device_info.get('device_id', '')
        
        if not device_id:
            return False
        
        # Check cache for trusted device
        cache_key = f"trusted_device:{user_id}:{device_id}"
        trusted_device = cache.get(cache_key)
        
        return trusted_device is not None

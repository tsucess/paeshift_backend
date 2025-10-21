"""
Middleware for God Mode security.

This module provides middleware for enforcing security measures for God Mode access.
"""

import logging
import re
from typing import Callable, Optional

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse

from godmode.mfa import is_mfa_enabled, is_mfa_verified

logger = logging.getLogger(__name__)

# Constants
GODMODE_URL_PATTERN = re.compile(r"^/godmode/")
GODMODE_API_URL_PATTERN = re.compile(r"^/godmode/api/")
MFA_EXEMPT_URLS = [
    "/godmode/mfa/setup/",
    "/godmode/mfa/verify/",
    "/godmode/mfa/qr-code/",
]


class GodModeSecurityMiddleware:
    """
    Middleware to enforce security measures for God Mode access.
    
    This middleware:
    1. Enforces MFA for God Mode access
    2. Implements IP restrictions
    3. Adds additional security headers
    4. Logs access attempts
    """
    
    def __init__(self, get_response: Callable):
        """
        Initialize middleware.
        
        Args:
            get_response: Get response function
        """
        self.get_response = get_response
        
    def __call__(self, request: HttpRequest) -> HttpResponse:
        """
        Process request.
        
        Args:
            request: HTTP request
            
        Returns:
            HTTP response
        """
        # Check if this is a God Mode URL
        path = request.path
        
        if GODMODE_URL_PATTERN.match(path) and not any(path.startswith(url) for url in MFA_EXEMPT_URLS):
            # Check if user is authenticated
            if not request.user.is_authenticated:
                logger.warning(f"Unauthenticated access attempt to God Mode: {path}")
                return redirect_to_login(path)
            
            # Check if user is a superuser
            if not request.user.is_superuser:
                logger.warning(f"Non-superuser access attempt to God Mode: {path} by {request.user.username}")
                return HttpResponse("Access denied. God Mode requires superuser privileges.", status=403)
            
            # Check IP restrictions if enabled
            if hasattr(settings, "GODMODE_IP_WHITELIST") and settings.GODMODE_IP_WHITELIST:
                client_ip = self._get_client_ip(request)
                if client_ip not in settings.GODMODE_IP_WHITELIST:
                    logger.warning(f"Access attempt from non-whitelisted IP: {client_ip} to {path} by {request.user.username}")
                    return HttpResponse("Access denied. Your IP address is not authorized.", status=403)
            
            # Check MFA if enabled
            if is_mfa_enabled(request.user.id) and not is_mfa_verified(request):
                logger.info(f"Redirecting to MFA verification: {path} by {request.user.username}")
                
                # Don't redirect API requests
                if GODMODE_API_URL_PATTERN.match(path):
                    return HttpResponse("MFA verification required", status=401)
                
                # Store the original URL in the session
                request.session["mfa_redirect_url"] = path
                
                # Redirect to MFA verification
                return redirect(reverse("godmode:mfa_verify"))
        
        # Process the request
        response = self.get_response(request)
        
        # Add security headers for God Mode pages
        if GODMODE_URL_PATTERN.match(path):
            response["X-Frame-Options"] = "DENY"
            response["X-Content-Type-Options"] = "nosniff"
            response["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"
            
            # Add Content-Security-Policy header if not already set
            if "Content-Security-Policy" not in response:
                response["Content-Security-Policy"] = (
                    "default-src 'self'; "
                    "script-src 'self' 'unsafe-inline'; "
                    "style-src 'self' 'unsafe-inline'; "
                    "img-src 'self' data:; "
                    "connect-src 'self'; "
                    "font-src 'self'; "
                    "object-src 'none'; "
                    "media-src 'self'; "
                    "frame-src 'self'; "
                    "frame-ancestors 'none'; "
                    "form-action 'self';"
                )
        
        return response
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """
        Get client IP address.
        
        Args:
            request: HTTP request
            
        Returns:
            Client IP address
        """
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip

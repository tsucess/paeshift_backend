"""
Webhook signature verification utilities.

This module provides utilities for verifying webhook signatures from payment gateways.
"""

import hashlib
import hmac
import logging
import time
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Union

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse

from godmode.audit import log_security_event

logger = logging.getLogger(__name__)

# Constants
WEBHOOK_NONCE_CACHE_PREFIX = "webhook:nonce:"
WEBHOOK_NONCE_CACHE_TIMEOUT = 60 * 60 * 24  # 24 hours
WEBHOOK_IP_WHITELIST_CACHE_KEY = "webhook:ip_whitelist"
WEBHOOK_IP_WHITELIST_CACHE_TIMEOUT = 60 * 60  # 1 hour


def get_client_ip(request: HttpRequest) -> str:
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


def get_webhook_ip_whitelist() -> List[str]:
    """
    Get the webhook IP whitelist.
    
    Returns:
        List of allowed IP addresses
    """
    # Try to get from cache
    whitelist = cache.get(WEBHOOK_IP_WHITELIST_CACHE_KEY)
    
    if whitelist is None:
        # Get from settings
        whitelist = getattr(settings, "WEBHOOK_IP_WHITELIST", {})
        
        # Cache whitelist
        cache.set(WEBHOOK_IP_WHITELIST_CACHE_KEY, whitelist, WEBHOOK_IP_WHITELIST_CACHE_TIMEOUT)
    
    return whitelist


def is_ip_whitelisted(ip: str, gateway: str) -> bool:
    """
    Check if an IP address is in the whitelist for a gateway.
    
    Args:
        ip: IP address
        gateway: Payment gateway
        
    Returns:
        True if IP is whitelisted, False otherwise
    """
    # Get whitelist
    whitelist = get_webhook_ip_whitelist()
    
    # Check if gateway has a whitelist
    if gateway not in whitelist:
        # No whitelist for this gateway means all IPs are allowed
        return True
    
    # Check if IP is in whitelist
    return ip in whitelist[gateway]


def verify_paystack_signature(request: HttpRequest) -> bool:
    """
    Verify Paystack webhook signature.
    
    Args:
        request: HTTP request
        
    Returns:
        True if signature is valid, False otherwise
    """
    # Get signature from header
    signature = request.headers.get("X-Paystack-Signature")
    if not signature:
        logger.warning("Paystack webhook received without signature")
        return False
    
    # Get request body as bytes for signature verification
    payload = request.body
    
    # Compute HMAC with SHA512
    h = hmac.new(settings.PAYSTACK_SECRET_KEY.encode(), payload, hashlib.sha512)
    computed_signature = h.hexdigest()
    
    # Compare signatures
    return signature == computed_signature


def verify_flutterwave_signature(request: HttpRequest) -> bool:
    """
    Verify Flutterwave webhook signature.
    
    Args:
        request: HTTP request
        
    Returns:
        True if signature is valid, False otherwise
    """
    # Get signature from header
    signature = request.headers.get("verif-hash")
    if not signature:
        logger.warning("Flutterwave webhook received without signature")
        return False
    
    # Compare with secret hash
    return signature == settings.FLUTTERWAVE_WEBHOOK_HASH


def is_webhook_replay(request: HttpRequest, gateway: str, reference: str) -> bool:
    """
    Check if a webhook is a replay.
    
    Args:
        request: HTTP request
        gateway: Payment gateway
        reference: Payment reference
        
    Returns:
        True if webhook is a replay, False otherwise
    """
    # Generate nonce
    nonce = f"{gateway}:{reference}"
    
    # Check if nonce exists
    if cache.get(f"{WEBHOOK_NONCE_CACHE_PREFIX}{nonce}"):
        return True
    
    # Store nonce
    cache.set(f"{WEBHOOK_NONCE_CACHE_PREFIX}{nonce}", True, WEBHOOK_NONCE_CACHE_TIMEOUT)
    
    return False


def verify_webhook_signature(gateway: str):
    """
    Decorator to verify webhook signature.
    
    Args:
        gateway: Payment gateway
        
    Returns:
        Decorated view function
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            # Get client IP
            client_ip = get_client_ip(request)
            
            # Check IP whitelist
            if not is_ip_whitelisted(client_ip, gateway):
                # Log security event
                log_security_event(
                    request=request,
                    action=f"Webhook from non-whitelisted IP for {gateway}",
                    severity="high",
                    details={
                        "ip_address": client_ip,
                        "gateway": gateway,
                    },
                )
                
                # Return unauthorized response
                return HttpResponse(status=403)
            
            # Verify signature
            if gateway == "paystack":
                is_valid = verify_paystack_signature(request)
            elif gateway == "flutterwave":
                is_valid = verify_flutterwave_signature(request)
            else:
                # Unknown gateway
                logger.warning(f"Unknown gateway: {gateway}")
                return HttpResponse(status=400)
            
            if not is_valid:
                # Log security event
                log_security_event(
                    request=request,
                    action=f"Invalid webhook signature for {gateway}",
                    severity="high",
                    details={
                        "ip_address": client_ip,
                        "gateway": gateway,
                    },
                )
                
                # Return unauthorized response
                return HttpResponse(status=401)
            
            # Check for replay attacks
            try:
                # Parse payload
                import json
                payload = json.loads(request.body)
                
                # Get reference
                if gateway == "paystack":
                    reference = payload.get("data", {}).get("reference")
                elif gateway == "flutterwave":
                    reference = payload.get("data", {}).get("tx_ref")
                else:
                    reference = None
                
                if reference and is_webhook_replay(request, gateway, reference):
                    # Log security event
                    log_security_event(
                        request=request,
                        action=f"Webhook replay detected for {gateway}",
                        severity="medium",
                        details={
                            "ip_address": client_ip,
                            "gateway": gateway,
                            "reference": reference,
                        },
                    )
                    
                    # Return success response to acknowledge webhook
                    # This is to prevent the payment gateway from retrying
                    return HttpResponse(status=200)
            except Exception as e:
                logger.exception(f"Error checking for webhook replay: {str(e)}")
            
            # Call the view function
            return view_func(request, *args, **kwargs)
        
        return wrapped_view
    
    return decorator

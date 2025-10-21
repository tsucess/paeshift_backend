"""
IP restriction utilities for God Mode.

This module provides utilities for restricting access to God Mode based on IP address.
"""

import ipaddress
import logging
from functools import wraps
from typing import Callable, List, Optional, Union

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from godmode.audit import log_security_event

logger = logging.getLogger(__name__)

# Constants
IP_WHITELIST_CACHE_KEY = "godmode:ip_whitelist"
IP_WHITELIST_CACHE_TIMEOUT = 60 * 60  # 1 hour


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


def is_ip_in_network(ip: str, network: str) -> bool:
    """
    Check if an IP address is in a network.
    
    Args:
        ip: IP address
        network: Network in CIDR notation
        
    Returns:
        True if IP is in network, False otherwise
    """
    try:
        ip_obj = ipaddress.ip_address(ip)
        network_obj = ipaddress.ip_network(network)
        return ip_obj in network_obj
    except ValueError:
        return False


def is_ip_whitelisted(ip: str, whitelist: Optional[List[str]] = None) -> bool:
    """
    Check if an IP address is in the whitelist.
    
    Args:
        ip: IP address
        whitelist: List of allowed IP addresses or networks
        
    Returns:
        True if IP is whitelisted, False otherwise
    """
    # Get whitelist from settings if not provided
    if whitelist is None:
        whitelist = getattr(settings, "GODMODE_IP_WHITELIST", [])
    
    # Check if whitelist is empty
    if not whitelist:
        # No whitelist means all IPs are allowed
        return True
    
    # Check if IP is in whitelist
    for allowed_ip in whitelist:
        if "/" in allowed_ip:
            # Network in CIDR notation
            if is_ip_in_network(ip, allowed_ip):
                return True
        else:
            # Single IP address
            if ip == allowed_ip:
                return True
    
    return False


def get_ip_whitelist() -> List[str]:
    """
    Get the IP whitelist.
    
    Returns:
        List of allowed IP addresses or networks
    """
    # Try to get from cache
    whitelist = cache.get(IP_WHITELIST_CACHE_KEY)
    
    if whitelist is None:
        # Get from database
        from godmode.models import IPWhitelist
        
        whitelist = list(IPWhitelist.objects.filter(enabled=True).values_list("ip_address", flat=True))
        
        # Add IPs from settings
        settings_whitelist = getattr(settings, "GODMODE_IP_WHITELIST", [])
        whitelist.extend(settings_whitelist)
        
        # Remove duplicates
        whitelist = list(set(whitelist))
        
        # Cache whitelist
        cache.set(IP_WHITELIST_CACHE_KEY, whitelist, IP_WHITELIST_CACHE_TIMEOUT)
    
    return whitelist


def invalidate_ip_whitelist_cache() -> None:
    """
    Invalidate the IP whitelist cache.
    """
    cache.delete(IP_WHITELIST_CACHE_KEY)


def ip_whitelist_required(view_func: Callable) -> Callable:
    """
    Decorator to require IP to be in whitelist.
    
    Args:
        view_func: View function
        
    Returns:
        Decorated view function
    """
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        # Get client IP
        client_ip = get_client_ip(request)
        
        # Get whitelist
        whitelist = get_ip_whitelist()
        
        # Check if IP is whitelisted
        if not is_ip_whitelisted(client_ip, whitelist):
            # Log security event
            log_security_event(
                request=request,
                action="Access denied due to IP restriction",
                severity="high",
                details={
                    "ip_address": client_ip,
                    "path": request.path,
                },
            )
            
            # Return access denied response
            return render(
                request,
                "godmode/access_denied.html",
                {
                    "reason": "Your IP address is not authorized to access this resource.",
                    "ip_address": client_ip,
                },
                status=403,
            )
        
        # Call the view function
        return view_func(request, *args, **kwargs)
    
    return wrapped_view

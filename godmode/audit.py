"""
Audit logging utilities for God Mode.

This module provides utilities for logging audit events for God Mode operations.
"""

import json
import logging
from typing import Any, Dict, Optional

from django.http import HttpRequest
from django.utils import timezone

logger = logging.getLogger(__name__)


def log_audit(
    request: HttpRequest,
    action_type: str,
    action: str,
    object_type: Optional[str] = None,
    object_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Log an audit event.
    
    Args:
        request: HTTP request
        action_type: Type of action (e.g., login, view, create, update, delete)
        action: Description of the action
        object_type: Type of object being acted upon (e.g., User, Job, Payment)
        object_id: ID of the object being acted upon
        details: Additional details about the action
        
    Returns:
        True if successful, False otherwise
    """
    from godmode.models import AuditLog
    
    try:
        # Get user information
        user = request.user if request.user.is_authenticated else None
        
        # Get IP address
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(",")[0]
        else:
            ip_address = request.META.get("REMOTE_ADDR")
        
        # Get user agent
        user_agent = request.META.get("HTTP_USER_AGENT")
        
        # Create audit log
        audit_log = AuditLog(
            user=user,
            action_type=action_type,
            action=action,
            object_type=object_type,
            object_id=object_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
            timestamp=timezone.now(),
        )
        
        # Save audit log
        audit_log.save()
        
        # Also log to the logger
        log_message = f"AUDIT: {action_type.upper()}: {action}"
        if object_type and object_id:
            log_message += f" | {object_type}:{object_id}"
        if user:
            log_message += f" | User:{user.username}"
        if ip_address:
            log_message += f" | IP:{ip_address}"
        if details:
            log_message += f" | Details:{json.dumps(details)}"
        
        logger.info(log_message)
        
        return True
    except Exception as e:
        logger.exception(f"Error logging audit event: {str(e)}")
        return False


def log_security_event(
    request: HttpRequest,
    action: str,
    severity: str = "medium",
    details: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Log a security event.
    
    Args:
        request: HTTP request
        action: Description of the security event
        severity: Severity of the event (low, medium, high, critical)
        details: Additional details about the event
        
    Returns:
        True if successful, False otherwise
    """
    # Add severity to details
    details = details or {}
    details["severity"] = severity
    
    # Log as a security event
    return log_audit(
        request=request,
        action_type="security",
        action=action,
        details=details,
    )


def log_data_access(
    request: HttpRequest,
    object_type: str,
    object_id: str,
    action: str = "view",
    details: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Log a data access event.
    
    Args:
        request: HTTP request
        object_type: Type of object being accessed
        object_id: ID of the object being accessed
        action: Type of access (view, export, etc.)
        details: Additional details about the access
        
    Returns:
        True if successful, False otherwise
    """
    # Log as a data access event
    return log_audit(
        request=request,
        action_type="view" if action == "view" else action,
        action=f"Access {object_type}",
        object_type=object_type,
        object_id=object_id,
        details=details,
    )


def log_data_modification(
    request: HttpRequest,
    object_type: str,
    object_id: str,
    action: str,
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
    details: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Log a data modification event.
    
    Args:
        request: HTTP request
        object_type: Type of object being modified
        object_id: ID of the object being modified
        action: Type of modification (create, update, delete)
        before: State of the object before modification
        after: State of the object after modification
        details: Additional details about the modification
        
    Returns:
        True if successful, False otherwise
    """
    # Combine before and after states with details
    combined_details = details or {}
    
    if before:
        combined_details["before"] = before
    
    if after:
        combined_details["after"] = after
    
    # Log as a data modification event
    return log_audit(
        request=request,
        action_type=action,
        action=f"{action.capitalize()} {object_type}",
        object_type=object_type,
        object_id=object_id,
        details=combined_details,
    )

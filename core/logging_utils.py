"""
Logging utilities for Paeshift application.

This module provides structured logging utilities for consistent logging
across all API endpoints and business logic.
"""

import json
import logging
import time
import uuid
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Dict, Optional

from django.http import HttpRequest


class StructuredLogger:
    """Provides structured logging with context information."""
    
    def __init__(self, name: str):
        """Initialize logger."""
        self.logger = logging.getLogger(name)
    
    def _build_context(
        self,
        level: str,
        message: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Build structured log context."""
        context = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
        }
        context.update(kwargs)
        return context
    
    def info(self, message: str, **kwargs) -> None:
        """Log info level message."""
        context = self._build_context("INFO", message, **kwargs)
        self.logger.info(json.dumps(context))
    
    def warning(self, message: str, **kwargs) -> None:
        """Log warning level message."""
        context = self._build_context("WARNING", message, **kwargs)
        self.logger.warning(json.dumps(context))
    
    def error(self, message: str, **kwargs) -> None:
        """Log error level message."""
        context = self._build_context("ERROR", message, **kwargs)
        self.logger.error(json.dumps(context))
    
    def debug(self, message: str, **kwargs) -> None:
        """Log debug level message."""
        context = self._build_context("DEBUG", message, **kwargs)
        self.logger.debug(json.dumps(context))
    
    def critical(self, message: str, **kwargs) -> None:
        """Log critical level message."""
        context = self._build_context("CRITICAL", message, **kwargs)
        self.logger.critical(json.dumps(context))


class RequestLogger:
    """Logs HTTP request/response information."""
    
    def __init__(self, logger: StructuredLogger):
        """Initialize request logger."""
        self.logger = logger
    
    @staticmethod
    def get_request_context(request: HttpRequest) -> Dict[str, Any]:
        """Extract context information from request."""
        return {
            "request_id": getattr(request, 'request_id', str(uuid.uuid4())),
            "method": request.method,
            "path": request.path,
            "user_id": getattr(request.user, 'id', None),
            "user_email": getattr(request.user, 'email', None),
            "ip_address": RequestLogger.get_client_ip(request),
        }
    
    @staticmethod
    def get_client_ip(request: HttpRequest) -> str:
        """Get client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def log_request(self, request: HttpRequest, **kwargs) -> None:
        """Log incoming request."""
        context = self.get_request_context(request)
        context.update(kwargs)
        self.logger.info("Incoming request", **context)
    
    def log_response(
        self,
        request: HttpRequest,
        status_code: int,
        duration_ms: float,
        **kwargs
    ) -> None:
        """Log outgoing response."""
        context = self.get_request_context(request)
        context.update({
            "status_code": status_code,
            "duration_ms": duration_ms,
            **kwargs
        })
        self.logger.info("Outgoing response", **context)
    
    def log_error(
        self,
        request: HttpRequest,
        error: Exception,
        status_code: int = 500,
        **kwargs
    ) -> None:
        """Log error during request processing."""
        context = self.get_request_context(request)
        context.update({
            "error": str(error),
            "error_type": error.__class__.__name__,
            "status_code": status_code,
            **kwargs
        })
        self.logger.error("Request error", **context)


class APILogger:
    """Logs API-specific events."""
    
    def __init__(self, logger: StructuredLogger):
        """Initialize API logger."""
        self.logger = logger
    
    def log_authentication(
        self,
        user_id: Optional[int],
        success: bool,
        reason: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log authentication event."""
        context = {
            "event": "authentication",
            "user_id": user_id,
            "success": success,
            "reason": reason,
            **kwargs
        }
        level = "info" if success else "warning"
        getattr(self.logger, level)("Authentication event", **context)
    
    def log_authorization(
        self,
        user_id: int,
        resource: str,
        action: str,
        allowed: bool,
        **kwargs
    ) -> None:
        """Log authorization event."""
        context = {
            "event": "authorization",
            "user_id": user_id,
            "resource": resource,
            "action": action,
            "allowed": allowed,
            **kwargs
        }
        level = "info" if allowed else "warning"
        getattr(self.logger, level)("Authorization event", **context)
    
    def log_data_modification(
        self,
        user_id: int,
        resource: str,
        action: str,
        resource_id: Any,
        **kwargs
    ) -> None:
        """Log data modification event."""
        context = {
            "event": "data_modification",
            "user_id": user_id,
            "resource": resource,
            "action": action,
            "resource_id": str(resource_id),
            **kwargs
        }
        self.logger.info("Data modification", **context)
    
    def log_payment(
        self,
        user_id: int,
        amount: float,
        status: str,
        gateway: str,
        **kwargs
    ) -> None:
        """Log payment event."""
        context = {
            "event": "payment",
            "user_id": user_id,
            "amount": amount,
            "status": status,
            "gateway": gateway,
            **kwargs
        }
        self.logger.info("Payment event", **context)


def log_endpoint(logger: StructuredLogger):
    """
    Decorator to log API endpoint calls with timing and error information.
    
    Usage:
        @log_endpoint(logger)
        def my_api_endpoint(request):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            start_time = time.time()
            request_id = str(uuid.uuid4())
            request.request_id = request_id
            
            try:
                # Log incoming request
                logger.info(
                    f"API call: {func.__name__}",
                    request_id=request_id,
                    method=request.method,
                    path=request.path,
                    user_id=getattr(request.user, 'id', None),
                )
                
                # Execute endpoint
                response = func(request, *args, **kwargs)
                
                # Log successful response
                duration_ms = (time.time() - start_time) * 1000
                status_code = getattr(response, 'status_code', 200)
                logger.info(
                    f"API call completed: {func.__name__}",
                    request_id=request_id,
                    status_code=status_code,
                    duration_ms=round(duration_ms, 2),
                )
                
                return response
            
            except Exception as e:
                # Log error
                duration_ms = (time.time() - start_time) * 1000
                logger.error(
                    f"API call failed: {func.__name__}",
                    request_id=request_id,
                    error=str(e),
                    error_type=e.__class__.__name__,
                    duration_ms=round(duration_ms, 2),
                )
                raise
        
        return wrapper
    return decorator


def log_database_operation(logger: StructuredLogger):
    """
    Decorator to log database operations.
    
    Usage:
        @log_database_operation(logger)
        def my_db_operation():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                logger.debug(
                    f"Database operation: {func.__name__}",
                    duration_ms=round(duration_ms, 2),
                    success=True,
                )
                return result
            
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.error(
                    f"Database operation failed: {func.__name__}",
                    error=str(e),
                    error_type=e.__class__.__name__,
                    duration_ms=round(duration_ms, 2),
                )
                raise
        
        return wrapper
    return decorator


# Create module-level logger instances
logger = StructuredLogger(__name__)
request_logger = RequestLogger(logger)
api_logger = APILogger(logger)


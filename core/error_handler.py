"""
Centralized error handling for Paeshift application.

This module provides error handling utilities and middleware for consistent
error responses across all API endpoints.
"""

import json
import logging
import traceback
from typing import Any, Dict, Optional, Tuple

from django.http import JsonResponse
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework.exceptions import APIException

from .exceptions import (
    PaeshiftException,
    ValidationError,
    AuthenticationError,
    AuthorizationError,
    ResourceNotFoundError,
    ConflictError,
    BusinessLogicError,
    ExternalServiceError,
    DatabaseError,
    RateLimitError,
    InternalServerError,
)

logger = logging.getLogger(__name__)


class ErrorResponse:
    """Standardized error response builder."""
    
    @staticmethod
    def build(
        error: Exception,
        request_id: Optional[str] = None,
        include_traceback: bool = False
    ) -> Dict[str, Any]:
        """
        Build a standardized error response.
        
        Args:
            error: The exception that occurred
            request_id: Optional request ID for tracking
            include_traceback: Whether to include traceback (dev only)
        
        Returns:
            Dictionary with standardized error format
        """
        response = {
            "success": False,
            "error": None,
            "error_code": None,
            "details": {},
            "timestamp": None,
        }
        
        if request_id:
            response["request_id"] = request_id
        
        # Handle Paeshift custom exceptions
        if isinstance(error, PaeshiftException):
            response["error"] = error.message
            response["error_code"] = error.error_code
            response["details"] = error.details
            response["status_code"] = error.status_code
        
        # Handle Django validation errors
        elif isinstance(error, DjangoValidationError):
            response["error"] = "Validation error"
            response["error_code"] = "VALIDATION_ERROR"
            response["details"] = {"errors": error.messages}
            response["status_code"] = 400
        
        # Handle database integrity errors
        elif isinstance(error, IntegrityError):
            response["error"] = "Data integrity constraint violated"
            response["error_code"] = "DATABASE_INTEGRITY_ERROR"
            response["details"] = {"error": str(error)}
            response["status_code"] = 409
            logger.error(f"Database integrity error: {error}")
        
        # Handle DRF API exceptions
        elif isinstance(error, APIException):
            response["error"] = error.detail
            response["error_code"] = error.__class__.__name__
            response["status_code"] = error.status_code
        
        # Handle generic exceptions
        else:
            response["error"] = "An unexpected error occurred"
            response["error_code"] = "INTERNAL_SERVER_ERROR"
            response["status_code"] = 500
            logger.error(f"Unexpected error: {error}", exc_info=True)
        
        # Add traceback in development
        if include_traceback:
            response["traceback"] = traceback.format_exc()
        
        return response
    
    @staticmethod
    def get_status_code(error: Exception) -> int:
        """Get HTTP status code for error."""
        if isinstance(error, PaeshiftException):
            return error.status_code
        elif isinstance(error, APIException):
            return error.status_code
        elif isinstance(error, IntegrityError):
            return 409
        elif isinstance(error, DjangoValidationError):
            return 400
        else:
            return 500


class ErrorHandlingMiddleware:
    """
    Middleware for handling exceptions and returning standardized error responses.
    
    Add to MIDDLEWARE in settings.py:
    'core.error_handler.ErrorHandlingMiddleware',
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        try:
            response = self.get_response(request)
            return response
        except Exception as e:
            return self.handle_exception(e, request)
    
    def handle_exception(self, error: Exception, request) -> JsonResponse:
        """Handle exception and return standardized error response."""
        request_id = getattr(request, 'request_id', None)
        include_traceback = getattr(request, 'DEBUG', False)
        
        error_response = ErrorResponse.build(
            error,
            request_id=request_id,
            include_traceback=include_traceback
        )
        
        status_code = error_response.pop("status_code", 500)
        
        # Log the error
        self._log_error(error, request, error_response)
        
        return JsonResponse(error_response, status=status_code)
    
    @staticmethod
    def _log_error(error: Exception, request, error_response: Dict) -> None:
        """Log error with context information."""
        log_data = {
            "method": request.method,
            "path": request.path,
            "error_code": error_response.get("error_code"),
            "error": error_response.get("error"),
            "user_id": getattr(request.user, 'id', None),
        }
        
        if isinstance(error, PaeshiftException):
            logger.warning(f"Business logic error: {json.dumps(log_data)}")
        elif isinstance(error, (ValidationError, AuthenticationError, AuthorizationError)):
            logger.warning(f"Client error: {json.dumps(log_data)}")
        else:
            logger.error(f"Server error: {json.dumps(log_data)}", exc_info=True)


def handle_api_error(func):
    """
    Decorator for API endpoints to handle exceptions and return standardized responses.
    
    Usage:
        @handle_api_error
        def my_api_endpoint(request):
            ...
    """
    def wrapper(request, *args, **kwargs):
        try:
            return func(request, *args, **kwargs)
        except PaeshiftException as e:
            error_response = ErrorResponse.build(e)
            status_code = error_response.pop("status_code")
            return JsonResponse(error_response, status=status_code)
        except Exception as e:
            error_response = ErrorResponse.build(e)
            status_code = error_response.pop("status_code", 500)
            logger.error(f"Unhandled error in {func.__name__}: {e}", exc_info=True)
            return JsonResponse(error_response, status=status_code)
    
    return wrapper


def convert_django_error_to_paeshift(error: Exception) -> PaeshiftException:
    """
    Convert Django exceptions to Paeshift exceptions.
    
    Args:
        error: Django exception
    
    Returns:
        Corresponding Paeshift exception
    """
    if isinstance(error, DjangoValidationError):
        return ValidationError(str(error))
    elif isinstance(error, IntegrityError):
        error_str = str(error).lower()
        if "unique constraint" in error_str or "duplicate" in error_str:
            return ConflictError("This resource already exists")
        else:
            return DatabaseError("Database integrity constraint violated")
    else:
        return InternalServerError(str(error))


# Standard error response schemas for documentation
ERROR_RESPONSE_SCHEMA = {
    "success": False,
    "error": "Error message",
    "error_code": "ERROR_CODE",
    "details": {},
    "request_id": "optional-request-id",
    "timestamp": "2024-01-01T00:00:00Z"
}

VALIDATION_ERROR_SCHEMA = {
    "success": False,
    "error": "Validation error",
    "error_code": "VALIDATION_ERROR",
    "details": {
        "field": "field_name",
        "reason": "Field is required"
    }
}

AUTHENTICATION_ERROR_SCHEMA = {
    "success": False,
    "error": "Authentication failed",
    "error_code": "AUTHENTICATION_ERROR",
    "details": {}
}

AUTHORIZATION_ERROR_SCHEMA = {
    "success": False,
    "error": "Permission denied",
    "error_code": "AUTHORIZATION_ERROR",
    "details": {}
}

NOT_FOUND_ERROR_SCHEMA = {
    "success": False,
    "error": "Resource not found",
    "error_code": "RESOURCE_NOT_FOUND",
    "details": {
        "resource_type": "User",
        "resource_id": "123"
    }
}

CONFLICT_ERROR_SCHEMA = {
    "success": False,
    "error": "Conflict with existing data",
    "error_code": "CONFLICT_ERROR",
    "details": {}
}

RATE_LIMIT_ERROR_SCHEMA = {
    "success": False,
    "error": "Rate limit exceeded",
    "error_code": "RATE_LIMIT_EXCEEDED",
    "details": {
        "retry_after": 60
    }
}

INTERNAL_SERVER_ERROR_SCHEMA = {
    "success": False,
    "error": "Internal server error",
    "error_code": "INTERNAL_SERVER_ERROR",
    "details": {}
}


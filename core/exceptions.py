"""
Custom exception classes for Paeshift application.

This module defines all custom exceptions used throughout the application
for consistent error handling and better error categorization.
"""

from typing import Any, Dict, Optional


class PaeshiftException(Exception):
    """
    Base exception class for all Paeshift custom exceptions.
    
    All custom exceptions should inherit from this class to ensure
    consistent error handling across the application.
    """
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the exception.
        
        Args:
            message: Human-readable error message
            error_code: Machine-readable error code (e.g., 'USER_NOT_FOUND')
            status_code: HTTP status code (default: 500)
            details: Additional error details as dictionary
        """
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON response."""
        return {
            "error": self.message,
            "error_code": self.error_code,
            "details": self.details
        }


# ============================================================================
# VALIDATION EXCEPTIONS
# ============================================================================

class ValidationError(PaeshiftException):
    """Raised when input validation fails."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=400,
            details=details
        )


class InvalidInputError(ValidationError):
    """Raised when input data is invalid or malformed."""
    
    def __init__(self, message: str, field: Optional[str] = None):
        details = {"field": field} if field else {}
        super().__init__(message, details)


class MissingFieldError(ValidationError):
    """Raised when a required field is missing."""
    
    def __init__(self, field_name: str):
        super().__init__(
            f"Required field '{field_name}' is missing",
            {"field": field_name}
        )


class InvalidEmailError(ValidationError):
    """Raised when email format is invalid."""
    
    def __init__(self, email: str):
        super().__init__(
            f"Invalid email format: {email}",
            {"email": email}
        )


class InvalidPhoneError(ValidationError):
    """Raised when phone number format is invalid."""
    
    def __init__(self, phone: str):
        super().__init__(
            f"Invalid phone format: {phone}",
            {"phone": phone}
        )


# ============================================================================
# AUTHENTICATION & AUTHORIZATION EXCEPTIONS
# ============================================================================

class AuthenticationError(PaeshiftException):
    """Raised when authentication fails."""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            status_code=401
        )


class InvalidCredentialsError(AuthenticationError):
    """Raised when credentials are invalid."""
    
    def __init__(self):
        super().__init__("Invalid email or password")


class TokenExpiredError(AuthenticationError):
    """Raised when JWT token has expired."""
    
    def __init__(self):
        super().__init__("Authentication token has expired")


class InvalidTokenError(AuthenticationError):
    """Raised when JWT token is invalid or malformed."""
    
    def __init__(self):
        super().__init__("Invalid or malformed authentication token")


class AuthorizationError(PaeshiftException):
    """Raised when user lacks required permissions."""
    
    def __init__(self, message: str = "Permission denied"):
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            status_code=403
        )


class InsufficientPermissionsError(AuthorizationError):
    """Raised when user lacks specific permissions."""
    
    def __init__(self, required_permission: str):
        super().__init__(
            f"This action requires '{required_permission}' permission"
        )


# ============================================================================
# RESOURCE EXCEPTIONS
# ============================================================================

class ResourceNotFoundError(PaeshiftException):
    """Raised when a requested resource is not found."""
    
    def __init__(self, resource_type: str, resource_id: Any):
        super().__init__(
            message=f"{resource_type} with ID {resource_id} not found",
            error_code="RESOURCE_NOT_FOUND",
            status_code=404,
            details={"resource_type": resource_type, "resource_id": str(resource_id)}
        )


class UserNotFoundError(ResourceNotFoundError):
    """Raised when a user is not found."""
    
    def __init__(self, user_id: Any):
        super().__init__("User", user_id)


class JobNotFoundError(ResourceNotFoundError):
    """Raised when a job is not found."""
    
    def __init__(self, job_id: Any):
        super().__init__("Job", job_id)


class ApplicationNotFoundError(ResourceNotFoundError):
    """Raised when an application is not found."""
    
    def __init__(self, application_id: Any):
        super().__init__("Application", application_id)


class PaymentNotFoundError(ResourceNotFoundError):
    """Raised when a payment is not found."""
    
    def __init__(self, payment_id: Any):
        super().__init__("Payment", payment_id)


class ReviewNotFoundError(ResourceNotFoundError):
    """Raised when a review is not found."""
    
    def __init__(self, review_id: Any):
        super().__init__("Review", review_id)


# ============================================================================
# CONFLICT EXCEPTIONS
# ============================================================================

class ConflictError(PaeshiftException):
    """Raised when there's a conflict with existing data."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code="CONFLICT_ERROR",
            status_code=409,
            details=details
        )


class DuplicateError(ConflictError):
    """Raised when trying to create a duplicate resource."""
    
    def __init__(self, resource_type: str, field: str, value: Any):
        super().__init__(
            f"{resource_type} with {field} '{value}' already exists",
            {"resource_type": resource_type, "field": field, "value": str(value)}
        )


class DuplicateEmailError(DuplicateError):
    """Raised when email already exists."""
    
    def __init__(self, email: str):
        super().__init__("User", "email", email)


class DuplicatePhoneError(DuplicateError):
    """Raised when phone number already exists."""
    
    def __init__(self, phone: str):
        super().__init__("User", "phone", phone)


class DuplicateFeedbackError(ConflictError):
    """Raised when feedback already exists for a job."""
    
    def __init__(self):
        super().__init__(
            "You have already submitted feedback for this job",
            {"reason": "duplicate_feedback"}
        )


class InvalidStateTransitionError(ConflictError):
    """Raised when an invalid state transition is attempted."""
    
    def __init__(self, current_state: str, requested_state: str):
        super().__init__(
            f"Cannot transition from '{current_state}' to '{requested_state}'",
            {"current_state": current_state, "requested_state": requested_state}
        )


# ============================================================================
# BUSINESS LOGIC EXCEPTIONS
# ============================================================================

class BusinessLogicError(PaeshiftException):
    """Raised when business logic constraints are violated."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code="BUSINESS_LOGIC_ERROR",
            status_code=400,
            details=details
        )


class InsufficientFundsError(BusinessLogicError):
    """Raised when user has insufficient funds."""
    
    def __init__(self, required: float, available: float):
        super().__init__(
            f"Insufficient funds. Required: {required}, Available: {available}",
            {"required": required, "available": available}
        )


class InvalidJobStatusError(BusinessLogicError):
    """Raised when job status is invalid for the operation."""
    
    def __init__(self, job_id: Any, current_status: str, required_status: str):
        super().__init__(
            f"Job {job_id} is in '{current_status}' status, but '{required_status}' is required",
            {"job_id": str(job_id), "current_status": current_status, "required_status": required_status}
        )


class InvalidApplicationStatusError(BusinessLogicError):
    """Raised when application status is invalid for the operation."""
    
    def __init__(self, app_id: Any, current_status: str):
        super().__init__(
            f"Cannot perform this action on application in '{current_status}' status",
            {"application_id": str(app_id), "current_status": current_status}
        )


class NoApplicantsError(BusinessLogicError):
    """Raised when trying to start a shift with no accepted applicants."""
    
    def __init__(self, job_id: Any):
        super().__init__(
            f"No applicants have been accepted for job {job_id}",
            {"job_id": str(job_id)}
        )


class UnauthorizedActionError(BusinessLogicError):
    """Raised when user attempts unauthorized action."""
    
    def __init__(self, action: str, reason: str):
        super().__init__(
            f"Cannot {action}: {reason}",
            {"action": action, "reason": reason}
        )


# ============================================================================
# EXTERNAL SERVICE EXCEPTIONS
# ============================================================================

class ExternalServiceError(PaeshiftException):
    """Raised when external service call fails."""
    
    def __init__(self, service_name: str, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=f"{service_name} error: {message}",
            error_code="EXTERNAL_SERVICE_ERROR",
            status_code=502,
            details=details or {"service": service_name}
        )


class PaymentGatewayError(ExternalServiceError):
    """Raised when payment gateway call fails."""
    
    def __init__(self, gateway: str, message: str):
        super().__init__(gateway, message, {"gateway": gateway})


class EmailServiceError(ExternalServiceError):
    """Raised when email service fails."""
    
    def __init__(self, message: str):
        super().__init__("Email Service", message)


class SMSServiceError(ExternalServiceError):
    """Raised when SMS service fails."""
    
    def __init__(self, message: str):
        super().__init__("SMS Service", message)


class LocationServiceError(ExternalServiceError):
    """Raised when location service fails."""
    
    def __init__(self, message: str):
        super().__init__("Location Service", message)


# ============================================================================
# DATABASE EXCEPTIONS
# ============================================================================

class DatabaseError(PaeshiftException):
    """Raised when database operation fails."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            status_code=500,
            details=details
        )


class DatabaseConnectionError(DatabaseError):
    """Raised when database connection fails."""
    
    def __init__(self):
        super().__init__("Failed to connect to database")


class DatabaseIntegrityError(DatabaseError):
    """Raised when database integrity constraint is violated."""
    
    def __init__(self, message: str):
        super().__init__(message, {"type": "integrity_constraint"})


# ============================================================================
# RATE LIMITING EXCEPTIONS
# ============================================================================

class RateLimitError(PaeshiftException):
    """Raised when rate limit is exceeded."""
    
    def __init__(self, message: str = "Rate limit exceeded", retry_after: Optional[int] = None):
        details = {"retry_after": retry_after} if retry_after else {}
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            details=details
        )


# ============================================================================
# GENERIC EXCEPTIONS
# ============================================================================

class InternalServerError(PaeshiftException):
    """Raised for unexpected internal server errors."""
    
    def __init__(self, message: str = "Internal server error", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code="INTERNAL_SERVER_ERROR",
            status_code=500,
            details=details
        )


class NotImplementedError(PaeshiftException):
    """Raised when a feature is not yet implemented."""
    
    def __init__(self, feature: str):
        super().__init__(
            f"Feature '{feature}' is not yet implemented",
            error_code="NOT_IMPLEMENTED",
            status_code=501
        )


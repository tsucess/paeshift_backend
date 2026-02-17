"""
Logging configuration for Paeshift application.

This module provides centralized logging configuration with JSON formatting
and structured logging support.

Usage in settings.py:
    from core.logging_config import get_logging_config
    LOGGING = get_logging_config()
"""

import os
from pathlib import Path

# Check if pythonjsonlogger is available
try:
    import pythonjsonlogger.jsonlogger
    HAS_JSON_LOGGER = True
except ImportError:
    HAS_JSON_LOGGER = False


def get_logging_config(debug: bool = False, log_dir: str = "logs"):
    """
    Get logging configuration dictionary.

    Args:
        debug: Whether to enable debug logging
        log_dir: Directory to store log files

    Returns:
        Dictionary with logging configuration
    """
    # Create logs directory if it doesn't exist (with parents)
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    # Determine which formatter to use for file handlers
    file_formatter = "json" if HAS_JSON_LOGGER else "verbose"

    formatters = {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {asctime} {message}",
            "style": "{",
        },
    }

    # Only add JSON formatter if pythonjsonlogger is available
    if HAS_JSON_LOGGER:
        formatters["json"] = {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
        }

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": formatters,
        "filters": {
            "require_debug_false": {
                "()": "django.utils.log.RequireDebugFalse",
            },
            "require_debug_true": {
                "()": "django.utils.log.RequireDebugTrue",
            },
        },
        "handlers": {
            # Console handler for development
            "console": {
                "level": "DEBUG" if debug else "INFO",
                "class": "logging.StreamHandler",
                "formatter": "simple",
            },
            # File handler for all logs
            "file": {
                "level": "INFO",
                "class": "logging.handlers.RotatingFileHandler",
                "filename": os.path.join(log_dir, "paeshift.log"),
                "maxBytes": 1024 * 1024 * 10,  # 10MB
                "backupCount": 10,
                "formatter": file_formatter,
            },
            # File handler for errors
            "error_file": {
                "level": "ERROR",
                "class": "logging.handlers.RotatingFileHandler",
                "filename": os.path.join(log_dir, "errors.log"),
                "maxBytes": 1024 * 1024 * 10,  # 10MB
                "backupCount": 10,
                "formatter": file_formatter,
            },
            # File handler for API logs
            "api_file": {
                "level": "INFO",
                "class": "logging.handlers.RotatingFileHandler",
                "filename": os.path.join(log_dir, "api.log"),
                "maxBytes": 1024 * 1024 * 10,  # 10MB
                "backupCount": 10,
                "formatter": file_formatter,
            },
            # File handler for authentication logs
            "auth_file": {
                "level": "INFO",
                "class": "logging.handlers.RotatingFileHandler",
                "filename": os.path.join(log_dir, "auth.log"),
                "maxBytes": 1024 * 1024 * 10,  # 10MB
                "backupCount": 10,
                "formatter": file_formatter,
            },
            # File handler for payment logs
            "payment_file": {
                "level": "INFO",
                "class": "logging.handlers.RotatingFileHandler",
                "filename": os.path.join(log_dir, "payment.log"),
                "maxBytes": 1024 * 1024 * 10,  # 10MB
                "backupCount": 10,
                "formatter": file_formatter,
            },
            # File handler for database logs - Use NullHandler to avoid Windows file locking issues
            "database_file": {
                "level": "DEBUG" if debug else "INFO",
                "class": "logging.NullHandler",
            },
            # Mail handler for critical errors (production only)
            "mail_admins": {
                "level": "ERROR",
                "filters": ["require_debug_false"],
                "class": "django.utils.log.AdminEmailHandler",
                "include_html": True,
            },
        },
        "loggers": {
            # Root logger
            "": {
                "handlers": ["console", "file", "error_file"],
                "level": "DEBUG" if debug else "INFO",
                "propagate": True,
            },
            # Django logger
            "django": {
                "handlers": ["console", "file"],
                "level": "INFO",
                "propagate": False,
            },
            # Django request logger
            "django.request": {
                "handlers": ["console", "file", "error_file", "mail_admins"],
                "level": "ERROR",
                "propagate": False,
            },
            # Django database logger
            "django.db.backends": {
                "handlers": ["database_file"],
                "level": "DEBUG" if debug else "INFO",
                "propagate": False,
            },
            # Paeshift core logger
            "core": {
                "handlers": ["console", "file", "api_file"],
                "level": "DEBUG" if debug else "INFO",
                "propagate": False,
            },
            # Paeshift accounts logger
            "accounts": {
                "handlers": ["console", "file", "auth_file"],
                "level": "DEBUG" if debug else "INFO",
                "propagate": False,
            },
            # Paeshift payment logger
            "payment": {
                "handlers": ["console", "file", "payment_file"],
                "level": "DEBUG" if debug else "INFO",
                "propagate": False,
            },
            # Paeshift jobs logger
            "jobs": {
                "handlers": ["console", "file", "api_file"],
                "level": "DEBUG" if debug else "INFO",
                "propagate": False,
            },
            # Paeshift rating logger
            "rating": {
                "handlers": ["console", "file", "api_file"],
                "level": "DEBUG" if debug else "INFO",
                "propagate": False,
            },
            # Paeshift notifications logger
            "notifications": {
                "handlers": ["console", "file", "api_file"],
                "level": "DEBUG" if debug else "INFO",
                "propagate": False,
            },
            # Paeshift gamification logger
            "gamification": {
                "handlers": ["console", "file", "api_file"],
                "level": "DEBUG" if debug else "INFO",
                "propagate": False,
            },
            # Paeshift jobchat logger
            "jobchat": {
                "handlers": ["console", "file", "api_file"],
                "level": "DEBUG" if debug else "INFO",
                "propagate": False,
            },
            # Paeshift disputes logger
            "disputes": {
                "handlers": ["console", "file", "api_file"],
                "level": "DEBUG" if debug else "INFO",
                "propagate": False,
            },
            # Paeshift userlocation logger
            "userlocation": {
                "handlers": ["console", "file", "api_file"],
                "level": "DEBUG" if debug else "INFO",
                "propagate": False,
            },
        },
    }


# Logging configuration for different environments
# Note: These are created lazily when get_logging_config is called from settings.py
# to avoid issues with relative paths during module import
LOGGING_CONFIG_DEVELOPMENT = None
LOGGING_CONFIG_PRODUCTION = None
LOGGING_CONFIG_TESTING = None


# Log level constants
LOG_LEVEL_DEBUG = "DEBUG"
LOG_LEVEL_INFO = "INFO"
LOG_LEVEL_WARNING = "WARNING"
LOG_LEVEL_ERROR = "ERROR"
LOG_LEVEL_CRITICAL = "CRITICAL"


# Log categories
LOG_CATEGORY_API = "api"
LOG_CATEGORY_AUTH = "auth"
LOG_CATEGORY_PAYMENT = "payment"
LOG_CATEGORY_DATABASE = "database"
LOG_CATEGORY_BUSINESS = "business"
LOG_CATEGORY_SECURITY = "security"
LOG_CATEGORY_PERFORMANCE = "performance"


# Sensitive fields to exclude from logs
SENSITIVE_FIELDS = {
    "password",
    "token",
    "secret",
    "api_key",
    "credit_card",
    "ssn",
    "phone",
    "email",
    "access_token",
    "refresh_token",
}


def should_log_field(field_name: str) -> bool:
    """Check if field should be logged (not sensitive)."""
    field_lower = field_name.lower()
    return not any(
        sensitive in field_lower
        for sensitive in SENSITIVE_FIELDS
    )


def sanitize_log_data(data: dict) -> dict:
    """Remove sensitive fields from log data."""
    sanitized = {}
    for key, value in data.items():
        if should_log_field(key):
            sanitized[key] = value
        else:
            sanitized[key] = "***REDACTED***"
    return sanitized


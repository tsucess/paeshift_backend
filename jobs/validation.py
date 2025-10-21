"""
Validation utilities for the jobs application.

This module provides validation functions for various data types,
with detailed error messages and flexible format handling.
"""

import logging
import re
from datetime import date, datetime, time
from typing import Any, Dict, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# Time format patterns
TIME_FORMATS = [
    "%H:%M:%S",  # 24-hour with seconds (14:30:00)
    "%H:%M",  # 24-hour without seconds (14:30)
    "%I:%M:%S%p",  # 12-hour with seconds (02:30:00PM)
    "%I:%M%p",  # 12-hour without seconds (02:30PM)
    "%I:%M %p",  # 12-hour with space (02:30 PM)
]

# Date format patterns
DATE_FORMATS = [
    "%Y-%m-%d",  # ISO format (2023-01-31)
    "%d/%m/%Y",  # Day/Month/Year (31/01/2023)
    "%m/%d/%Y",  # Month/Day/Year (01/31/2023)
    "%d-%m-%Y",  # Day-Month-Year (31-01-2023)
    "%m-%d-%Y",  # Month-Day-Year (01-31-2023)
]


def validate_time(time_str: str) -> Tuple[bool, Optional[time], Optional[str]]:
    """
    Validate a time string against multiple formats.

    Args:
        time_str: The time string to validate

    Returns:
        Tuple of (is_valid, parsed_time, error_message)
    """
    if not time_str:
        return False, None, "Time cannot be empty"

    # Try each format
    for fmt in TIME_FORMATS:
        try:
            parsed_time = datetime.strptime(time_str, fmt).time()
            return True, parsed_time, None
        except ValueError:
            continue

    # If we get here, none of the formats matched
    valid_formats = ", ".join(
        [
            "HH:MM:SS (24-hour with seconds)",
            "HH:MM (24-hour without seconds)",
            "HH:MM:SSAM/PM (12-hour with seconds)",
            "HH:MMAM/PM (12-hour without seconds)",
            "HH:MM AM/PM (12-hour with space)",
        ]
    )

    return (
        False,
        None,
        f"Invalid time format: '{time_str}'. Valid formats are: {valid_formats}",
    )


def validate_date(date_str: str) -> Tuple[bool, Optional[date], Optional[str]]:
    """
    Validate a date string against multiple formats.

    Args:
        date_str: The date string to validate

    Returns:
        Tuple of (is_valid, parsed_date, error_message)
    """
    if not date_str:
        return False, None, "Date cannot be empty"

    # Try each format
    for fmt in DATE_FORMATS:
        try:
            parsed_date = datetime.strptime(date_str, fmt).date()
            return True, parsed_date, None
        except ValueError:
            continue

    # If we get here, none of the formats matched
    valid_formats = ", ".join(
        [
            "YYYY-MM-DD (ISO format)",
            "DD/MM/YYYY (Day/Month/Year)",
            "MM/DD/YYYY (Month/Day/Year)",
            "DD-MM-YYYY (Day-Month-Year)",
            "MM-DD-YYYY (Month-Day-Year)",
        ]
    )

    return (
        False,
        None,
        f"Invalid date format: '{date_str}'. Valid formats are: {valid_formats}",
    )


def validate_job_times(start_time: time, end_time: time) -> Tuple[bool, Optional[str]]:
    """
    Validate that job start and end times make sense.

    Args:
        start_time: The job start time
        end_time: The job end time

    Returns:
        Tuple of (is_valid, error_message)
    """
    if start_time == end_time:
        return False, "Start time and end time cannot be the same"

    # We allow end_time < start_time for overnight shifts
    return True, None


def validate_job_dates(
    job_date: date, start_date: Optional[date] = None, end_date: Optional[date] = None
) -> Tuple[bool, Optional[str]]:
    """
    Validate job dates.

    Args:
        job_date: The primary job date
        start_date: Optional job start date for multi-day jobs
        end_date: Optional job end date for multi-day jobs

    Returns:
        Tuple of (is_valid, error_message)
    """
    today = datetime.now().date()

    # For single-day jobs
    if not start_date and not end_date:
        if job_date < today:
            return False, f"Job date ({job_date}) cannot be in the past"
        return True, None

    # For multi-day jobs
    if start_date and end_date:
        if start_date > end_date:
            return (
                False,
                f"Start date ({start_date}) cannot be after end date ({end_date})",
            )
        if start_date < today:
            return False, f"Start date ({start_date}) cannot be in the past"

    return True, None


def format_validation_errors(errors: Dict[str, str]) -> Dict[str, Any]:
    """
    Format validation errors for API response.

    Args:
        errors: Dictionary of field errors

    Returns:
        Formatted error response
    """
    return {
        "error": "Validation error",
        "details": errors,
        "message": "Please correct the errors and try again.",
    }

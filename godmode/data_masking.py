"""
Data masking utilities for God Mode.

This module provides utilities for masking sensitive data in God Mode.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# Constants
EMAIL_PATTERN = re.compile(r"^([a-zA-Z0-9_\-\.]+)@([a-zA-Z0-9_\-\.]+)\.([a-zA-Z]{2,5})$")
PHONE_PATTERN = re.compile(r"^\+?[0-9]{10,15}$")
CREDIT_CARD_PATTERN = re.compile(r"^[0-9]{13,19}$")
SSN_PATTERN = re.compile(r"^[0-9]{3}-?[0-9]{2}-?[0-9]{4}$")
ADDRESS_PATTERN = re.compile(r"^[0-9]+\s+.+$")


def mask_email(email: str) -> str:
    """
    Mask an email address.
    
    Args:
        email: Email address
        
    Returns:
        Masked email address
    """
    if not email or not EMAIL_PATTERN.match(email):
        return email
    
    parts = email.split("@")
    username = parts[0]
    domain = parts[1]
    
    # Mask username
    if len(username) <= 2:
        masked_username = "*" * len(username)
    else:
        masked_username = username[0] + "*" * (len(username) - 2) + username[-1]
    
    return f"{masked_username}@{domain}"


def mask_phone(phone: str) -> str:
    """
    Mask a phone number.
    
    Args:
        phone: Phone number
        
    Returns:
        Masked phone number
    """
    if not phone or not PHONE_PATTERN.match(phone):
        return phone
    
    # Remove non-digit characters
    digits = re.sub(r"\D", "", phone)
    
    # Keep country code and last 2 digits
    if len(digits) <= 4:
        return "*" * len(digits)
    else:
        return digits[0:2] + "*" * (len(digits) - 4) + digits[-2:]


def mask_credit_card(card_number: str) -> str:
    """
    Mask a credit card number.
    
    Args:
        card_number: Credit card number
        
    Returns:
        Masked credit card number
    """
    if not card_number or not CREDIT_CARD_PATTERN.match(card_number):
        return card_number
    
    # Remove non-digit characters
    digits = re.sub(r"\D", "", card_number)
    
    # Keep first 6 and last 4 digits
    return digits[0:6] + "*" * (len(digits) - 10) + digits[-4:]


def mask_ssn(ssn: str) -> str:
    """
    Mask a Social Security Number.
    
    Args:
        ssn: Social Security Number
        
    Returns:
        Masked Social Security Number
    """
    if not ssn or not SSN_PATTERN.match(ssn):
        return ssn
    
    # Remove non-digit characters
    digits = re.sub(r"\D", "", ssn)
    
    # Mask all but last 4 digits
    return "***-**-" + digits[-4:]


def mask_address(address: str) -> str:
    """
    Mask an address.
    
    Args:
        address: Address
        
    Returns:
        Masked address
    """
    if not address or not ADDRESS_PATTERN.match(address):
        return address
    
    # Split into lines
    lines = address.split("\n")
    
    # Mask the first line (street address)
    parts = lines[0].split(" ", 1)
    if len(parts) > 1:
        number = parts[0]
        street = parts[1]
        lines[0] = f"{number} ***"
    
    return "\n".join(lines)


def mask_name(name: str) -> str:
    """
    Mask a name.
    
    Args:
        name: Name
        
    Returns:
        Masked name
    """
    if not name:
        return name
    
    # Split into parts
    parts = name.split(" ")
    
    # Mask each part
    masked_parts = []
    for part in parts:
        if len(part) <= 1:
            masked_parts.append(part)
        else:
            masked_parts.append(part[0] + "*" * (len(part) - 1))
    
    return " ".join(masked_parts)


def mask_dict(
    data: Dict[str, Any],
    sensitive_keys: Optional[List[str]] = None,
    mask_all: bool = False,
) -> Dict[str, Any]:
    """
    Mask sensitive data in a dictionary.
    
    Args:
        data: Dictionary to mask
        sensitive_keys: List of sensitive keys to mask
        mask_all: Whether to mask all values
        
    Returns:
        Masked dictionary
    """
    if not data:
        return data
    
    # Default sensitive keys
    if sensitive_keys is None:
        sensitive_keys = [
            "password",
            "secret",
            "token",
            "key",
            "auth",
            "credential",
            "ssn",
            "social_security",
            "credit_card",
            "card_number",
            "cvv",
            "cvc",
            "pin",
            "account_number",
            "routing_number",
            "bank_account",
            "passport",
            "license",
            "id_number",
        ]
    
    # Create a copy of the dictionary
    masked_data = {}
    
    # Mask each value
    for key, value in data.items():
        # Check if key is sensitive
        is_sensitive = mask_all or any(
            sensitive_key.lower() in key.lower() for sensitive_key in sensitive_keys
        )
        
        # Mask based on value type
        if isinstance(value, dict):
            masked_data[key] = mask_dict(value, sensitive_keys, is_sensitive)
        elif isinstance(value, list):
            masked_data[key] = [
                mask_dict(item, sensitive_keys, is_sensitive) if isinstance(item, dict) else item
                for item in value
            ]
        elif isinstance(value, str):
            if is_sensitive:
                if EMAIL_PATTERN.match(value):
                    masked_data[key] = mask_email(value)
                elif PHONE_PATTERN.match(value):
                    masked_data[key] = mask_phone(value)
                elif CREDIT_CARD_PATTERN.match(value):
                    masked_data[key] = mask_credit_card(value)
                elif SSN_PATTERN.match(value):
                    masked_data[key] = mask_ssn(value)
                elif ADDRESS_PATTERN.match(value):
                    masked_data[key] = mask_address(value)
                else:
                    # Generic masking
                    if len(value) <= 4:
                        masked_data[key] = "*" * len(value)
                    else:
                        masked_data[key] = value[0:2] + "*" * (len(value) - 4) + value[-2:]
            else:
                masked_data[key] = value
        else:
            masked_data[key] = value
    
    return masked_data


def mask_sensitive_data(
    data: Union[Dict[str, Any], List[Dict[str, Any]]],
    sensitive_keys: Optional[List[str]] = None,
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Mask sensitive data in a dictionary or list of dictionaries.
    
    Args:
        data: Data to mask
        sensitive_keys: List of sensitive keys to mask
        
    Returns:
        Masked data
    """
    if isinstance(data, list):
        return [mask_dict(item, sensitive_keys) if isinstance(item, dict) else item for item in data]
    elif isinstance(data, dict):
        return mask_dict(data, sensitive_keys)
    else:
        return data

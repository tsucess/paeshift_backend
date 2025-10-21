"""
Export encryption utilities for God Mode.

This module provides utilities for encrypting exported data from God Mode.
"""

import base64
import hashlib
import logging
import os
from typing import Optional, Tuple

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Constants
EXPORT_KEY_CACHE_PREFIX = "godmode:export_key:"
EXPORT_KEY_CACHE_TIMEOUT = 60 * 60 * 24  # 24 hours
DEFAULT_ITERATIONS = 100000
DEFAULT_KEY_LENGTH = 32


def generate_key(password: str, salt: Optional[bytes] = None) -> Tuple[bytes, bytes]:
    """
    Generate an encryption key from a password.
    
    Args:
        password: Password
        salt: Salt (generated if not provided)
        
    Returns:
        Tuple of (key, salt)
    """
    # Generate salt if not provided
    if salt is None:
        salt = os.urandom(16)
    
    # Generate key
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=DEFAULT_KEY_LENGTH,
        salt=salt,
        iterations=DEFAULT_ITERATIONS,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    
    return key, salt


def encrypt_data(data: bytes, password: str) -> Tuple[bytes, bytes]:
    """
    Encrypt data with a password.
    
    Args:
        data: Data to encrypt
        password: Password
        
    Returns:
        Tuple of (encrypted_data, salt)
    """
    # Generate key
    key, salt = generate_key(password)
    
    # Create Fernet cipher
    cipher = Fernet(key)
    
    # Encrypt data
    encrypted_data = cipher.encrypt(data)
    
    return encrypted_data, salt


def decrypt_data(encrypted_data: bytes, password: str, salt: bytes) -> bytes:
    """
    Decrypt data with a password.
    
    Args:
        encrypted_data: Encrypted data
        password: Password
        salt: Salt
        
    Returns:
        Decrypted data
    """
    # Generate key
    key, _ = generate_key(password, salt)
    
    # Create Fernet cipher
    cipher = Fernet(key)
    
    # Decrypt data
    decrypted_data = cipher.decrypt(encrypted_data)
    
    return decrypted_data


def get_export_key(export_id: str, password: str) -> Tuple[bytes, bytes]:
    """
    Get or generate an encryption key for an export.
    
    Args:
        export_id: Export ID
        password: Password
        
    Returns:
        Tuple of (key, salt)
    """
    # Try to get from cache
    cache_key = f"{EXPORT_KEY_CACHE_PREFIX}{export_id}"
    cached_data = cache.get(cache_key)
    
    if cached_data:
        # Verify password
        key, salt = cached_data
        
        # Generate key from password and salt
        test_key, _ = generate_key(password, salt)
        
        # Check if keys match
        if test_key == key:
            return key, salt
    
    # Generate new key
    key, salt = generate_key(password)
    
    # Cache key
    cache.set(cache_key, (key, salt), EXPORT_KEY_CACHE_TIMEOUT)
    
    return key, salt


def encrypt_export(export_path: str, password: str) -> Tuple[str, bytes]:
    """
    Encrypt an export file.
    
    Args:
        export_path: Path to export file
        password: Password
        
    Returns:
        Tuple of (encrypted_path, salt)
    """
    # Read export file
    with open(export_path, "rb") as f:
        data = f.read()
    
    # Encrypt data
    encrypted_data, salt = encrypt_data(data, password)
    
    # Write encrypted data
    encrypted_path = f"{export_path}.enc"
    with open(encrypted_path, "wb") as f:
        f.write(encrypted_data)
    
    return encrypted_path, salt


def decrypt_export(encrypted_path: str, password: str, salt: bytes) -> str:
    """
    Decrypt an export file.
    
    Args:
        encrypted_path: Path to encrypted export file
        password: Password
        salt: Salt
        
    Returns:
        Path to decrypted file
    """
    # Read encrypted file
    with open(encrypted_path, "rb") as f:
        encrypted_data = f.read()
    
    # Decrypt data
    decrypted_data = decrypt_data(encrypted_data, password, salt)
    
    # Write decrypted data
    decrypted_path = encrypted_path.replace(".enc", "")
    with open(decrypted_path, "wb") as f:
        f.write(decrypted_data)
    
    return decrypted_path

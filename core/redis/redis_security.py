"""
Redis cache security utilities.

This module provides utilities for encrypting sensitive data in Redis
and implementing access control for cached data.
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.http import HttpRequest

from core.cache import get_cached_data, set_cached_data
from core.redis_keys import CacheNamespace, generate_key
from core.redis_settings import CACHE_ENABLED

logger = logging.getLogger(__name__)

# Constants
DEFAULT_ENCRYPTION_KEY = getattr(
    settings, "REDIS_ENCRYPTION_KEY", None
)
DEFAULT_ENCRYPTION_SALT = getattr(
    settings, "REDIS_ENCRYPTION_SALT", b"payshift_redis_salt"
)
DEFAULT_HMAC_KEY = getattr(
    settings, "REDIS_HMAC_KEY", None
)

# Generate keys if not provided
if not DEFAULT_ENCRYPTION_KEY:
    # Generate a random key for development
    # In production, this should be set in settings
    DEFAULT_ENCRYPTION_KEY = base64.urlsafe_b64encode(os.urandom(32)).decode()
    logger.warning(
        "No REDIS_ENCRYPTION_KEY found in settings. "
        "Generated a random key for development. "
        "This key will change on restart, invalidating all encrypted cache entries."
    )

if not DEFAULT_HMAC_KEY:
    # Generate a random key for development
    # In production, this should be set in settings
    DEFAULT_HMAC_KEY = base64.urlsafe_b64encode(os.urandom(32)).decode()
    logger.warning(
        "No REDIS_HMAC_KEY found in settings. "
        "Generated a random key for development. "
        "This key will change on restart, invalidating all signed cache entries."
    )


def derive_key(password: str, salt: bytes) -> bytes:
    """
    Derive a key from a password and salt using PBKDF2.
    
    Args:
        password: Password string
        salt: Salt bytes
        
    Returns:
        Derived key bytes
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


def get_fernet(key: Optional[str] = None, salt: Optional[bytes] = None) -> Fernet:
    """
    Get a Fernet cipher for encryption/decryption.
    
    Args:
        key: Encryption key (defaults to settings.REDIS_ENCRYPTION_KEY)
        salt: Salt for key derivation (defaults to settings.REDIS_ENCRYPTION_SALT)
        
    Returns:
        Fernet cipher
    """
    key = key or DEFAULT_ENCRYPTION_KEY
    salt = salt or DEFAULT_ENCRYPTION_SALT
    
    # Derive a key from the password and salt
    derived_key = derive_key(key, salt)
    
    # Create a Fernet cipher
    return Fernet(derived_key)


def encrypt_data(data: Any, key: Optional[str] = None, salt: Optional[bytes] = None) -> str:
    """
    Encrypt data for storage in Redis.
    
    Args:
        data: Data to encrypt
        key: Encryption key (defaults to settings.REDIS_ENCRYPTION_KEY)
        salt: Salt for key derivation (defaults to settings.REDIS_ENCRYPTION_SALT)
        
    Returns:
        Encrypted data as a string
    """
    # Serialize data to JSON
    serialized = json.dumps(data)
    
    # Get Fernet cipher
    fernet = get_fernet(key, salt)
    
    # Encrypt data
    encrypted = fernet.encrypt(serialized.encode())
    
    # Return as base64 string
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_data(
    encrypted_data: str, key: Optional[str] = None, salt: Optional[bytes] = None
) -> Any:
    """
    Decrypt data from Redis.
    
    Args:
        encrypted_data: Encrypted data string
        key: Encryption key (defaults to settings.REDIS_ENCRYPTION_KEY)
        salt: Salt for key derivation (defaults to settings.REDIS_ENCRYPTION_SALT)
        
    Returns:
        Decrypted data
        
    Raises:
        ValueError: If decryption fails
    """
    try:
        # Decode base64
        encrypted = base64.urlsafe_b64decode(encrypted_data)
        
        # Get Fernet cipher
        fernet = get_fernet(key, salt)
        
        # Decrypt data
        decrypted = fernet.decrypt(encrypted)
        
        # Parse JSON
        return json.loads(decrypted.decode())
    except (InvalidToken, json.JSONDecodeError) as e:
        logger.error(f"Error decrypting data: {str(e)}")
        raise ValueError(f"Decryption failed: {str(e)}")


def sign_data(data: Any, key: Optional[str] = None) -> Tuple[Any, str]:
    """
    Sign data with HMAC for integrity verification.
    
    Args:
        data: Data to sign
        key: HMAC key (defaults to settings.REDIS_HMAC_KEY)
        
    Returns:
        Tuple of (data, signature)
    """
    key = key or DEFAULT_HMAC_KEY
    
    # Serialize data to JSON
    serialized = json.dumps(data)
    
    # Calculate HMAC
    signature = hmac.new(
        key.encode(),
        serialized.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return data, signature


def verify_signature(data: Any, signature: str, key: Optional[str] = None) -> bool:
    """
    Verify the signature of data.
    
    Args:
        data: Data to verify
        signature: Expected signature
        key: HMAC key (defaults to settings.REDIS_HMAC_KEY)
        
    Returns:
        True if signature is valid, False otherwise
    """
    key = key or DEFAULT_HMAC_KEY
    
    # Serialize data to JSON
    serialized = json.dumps(data)
    
    # Calculate HMAC
    expected_signature = hmac.new(
        key.encode(),
        serialized.encode(),
        hashlib.sha256
    ).hexdigest()
    
    # Compare signatures using constant-time comparison
    return hmac.compare_digest(signature, expected_signature)


def cache_encrypted(
    key: str,
    data: Any,
    ttl: int,
    encryption_key: Optional[str] = None,
    salt: Optional[bytes] = None,
) -> bool:
    """
    Cache encrypted data in Redis.
    
    Args:
        key: Cache key
        data: Data to cache
        ttl: Cache TTL in seconds
        encryption_key: Encryption key
        salt: Salt for key derivation
        
    Returns:
        True if successful, False otherwise
    """
    if not CACHE_ENABLED:
        return False
    
    try:
        # Encrypt data
        encrypted = encrypt_data(data, encryption_key, salt)
        
        # Cache encrypted data
        return set_cached_data(key, {"_encrypted": encrypted}, ttl)
    except Exception as e:
        logger.error(f"Error caching encrypted data for key {key}: {str(e)}")
        return False


def get_encrypted_cache(
    key: str,
    encryption_key: Optional[str] = None,
    salt: Optional[bytes] = None,
) -> Optional[Any]:
    """
    Get encrypted data from Redis cache.
    
    Args:
        key: Cache key
        encryption_key: Encryption key
        salt: Salt for key derivation
        
    Returns:
        Decrypted data or None if not found
    """
    if not CACHE_ENABLED:
        return None
    
    try:
        # Get from cache
        cached = get_cached_data(key)
        
        if not cached or not isinstance(cached, dict) or "_encrypted" not in cached:
            return None
        
        # Decrypt data
        return decrypt_data(cached["_encrypted"], encryption_key, salt)
    except Exception as e:
        logger.error(f"Error getting encrypted data for key {key}: {str(e)}")
        return None


def cache_with_acl(
    key: str,
    data: Any,
    ttl: int,
    user_id: Optional[int] = None,
    roles: Optional[List[str]] = None,
    permissions: Optional[List[str]] = None,
) -> bool:
    """
    Cache data with access control.
    
    Args:
        key: Cache key
        data: Data to cache
        ttl: Cache TTL in seconds
        user_id: User ID allowed to access this data
        roles: Roles allowed to access this data
        permissions: Permissions required to access this data
        
    Returns:
        True if successful, False otherwise
    """
    if not CACHE_ENABLED:
        return False
    
    try:
        # Create ACL metadata
        acl = {}
        if user_id is not None:
            acl["user_id"] = user_id
        if roles:
            acl["roles"] = roles
        if permissions:
            acl["permissions"] = permissions
        
        # Sign the data
        signed_data, signature = sign_data(data)
        
        # Cache data with ACL and signature
        cache_data = {
            "data": signed_data,
            "signature": signature,
            "acl": acl,
            "_protected": True,
        }
        
        return set_cached_data(key, cache_data, ttl)
    except Exception as e:
        logger.error(f"Error caching data with ACL for key {key}: {str(e)}")
        return False


def get_cache_with_acl(
    key: str,
    user: Optional[AbstractUser] = None,
) -> Optional[Any]:
    """
    Get data from cache with access control check.
    
    Args:
        key: Cache key
        user: User requesting the data
        
    Returns:
        Data if access is allowed, None otherwise
    """
    if not CACHE_ENABLED:
        return None
    
    try:
        # Get from cache
        cached = get_cached_data(key)
        
        if not cached or not isinstance(cached, dict) or not cached.get("_protected"):
            return None
        
        # Extract data, signature, and ACL
        data = cached.get("data")
        signature = cached.get("signature")
        acl = cached.get("acl", {})
        
        # Verify signature
        if not verify_signature(data, signature):
            logger.warning(f"Invalid signature for key {key}")
            return None
        
        # Check ACL if user is provided
        if user and acl:
            # Check user ID
            if "user_id" in acl and acl["user_id"] != user.id:
                logger.warning(
                    f"Access denied for user {user.id} to key {key}: "
                    f"user_id mismatch"
                )
                return None
            
            # Check roles
            if "roles" in acl:
                has_role = False
                for role in acl["roles"]:
                    # Check if user has the role
                    # This depends on your role implementation
                    if hasattr(user, "has_role") and callable(getattr(user, "has_role")):
                        if user.has_role(role):
                            has_role = True
                            break
                    elif hasattr(user, "groups") and role in [g.name for g in user.groups.all()]:
                        has_role = True
                        break
                
                if not has_role:
                    logger.warning(
                        f"Access denied for user {user.id} to key {key}: "
                        f"missing required role"
                    )
                    return None
            
            # Check permissions
            if "permissions" in acl:
                for permission in acl["permissions"]:
                    if not user.has_perm(permission):
                        logger.warning(
                            f"Access denied for user {user.id} to key {key}: "
                            f"missing permission {permission}"
                        )
                        return None
        
        # Access allowed
        return data
    except Exception as e:
        logger.error(f"Error getting data with ACL for key {key}: {str(e)}")
        return None


def cache_sensitive_data(
    namespace: Union[str, CacheNamespace],
    identifier: Any,
    data: Any,
    ttl: int,
    user_id: Optional[int] = None,
    roles: Optional[List[str]] = None,
    permissions: Optional[List[str]] = None,
    encryption_key: Optional[str] = None,
) -> bool:
    """
    Cache sensitive data with encryption and access control.
    
    Args:
        namespace: Cache namespace
        identifier: Cache identifier
        data: Data to cache
        ttl: Cache TTL in seconds
        user_id: User ID allowed to access this data
        roles: Roles allowed to access this data
        permissions: Permissions required to access this data
        encryption_key: Custom encryption key
        
    Returns:
        True if successful, False otherwise
    """
    if not CACHE_ENABLED:
        return False
    
    try:
        # Generate cache key
        key = generate_key(namespace, identifier)
        
        # Encrypt data
        encrypted = encrypt_data(data, encryption_key)
        
        # Create ACL metadata
        acl = {}
        if user_id is not None:
            acl["user_id"] = user_id
        if roles:
            acl["roles"] = roles
        if permissions:
            acl["permissions"] = permissions
        
        # Cache encrypted data with ACL
        cache_data = {
            "_encrypted": encrypted,
            "acl": acl,
            "_sensitive": True,
        }
        
        return set_cached_data(key, cache_data, ttl)
    except Exception as e:
        logger.error(
            f"Error caching sensitive data for {namespace}:{identifier}: {str(e)}"
        )
        return False


def get_sensitive_data(
    namespace: Union[str, CacheNamespace],
    identifier: Any,
    user: Optional[AbstractUser] = None,
    encryption_key: Optional[str] = None,
) -> Optional[Any]:
    """
    Get sensitive data from cache with decryption and access control.
    
    Args:
        namespace: Cache namespace
        identifier: Cache identifier
        user: User requesting the data
        encryption_key: Custom encryption key
        
    Returns:
        Decrypted data if access is allowed, None otherwise
    """
    if not CACHE_ENABLED:
        return None
    
    try:
        # Generate cache key
        key = generate_key(namespace, identifier)
        
        # Get from cache
        cached = get_cached_data(key)
        
        if not cached or not isinstance(cached, dict) or not cached.get("_sensitive"):
            return None
        
        # Extract encrypted data and ACL
        encrypted = cached.get("_encrypted")
        acl = cached.get("acl", {})
        
        # Check ACL if user is provided
        if user and acl:
            # Check user ID
            if "user_id" in acl and acl["user_id"] != user.id:
                logger.warning(
                    f"Access denied for user {user.id} to {namespace}:{identifier}: "
                    f"user_id mismatch"
                )
                return None
            
            # Check roles
            if "roles" in acl:
                has_role = False
                for role in acl["roles"]:
                    # Check if user has the role
                    if hasattr(user, "has_role") and callable(getattr(user, "has_role")):
                        if user.has_role(role):
                            has_role = True
                            break
                    elif hasattr(user, "groups") and role in [g.name for g in user.groups.all()]:
                        has_role = True
                        break
                
                if not has_role:
                    logger.warning(
                        f"Access denied for user {user.id} to {namespace}:{identifier}: "
                        f"missing required role"
                    )
                    return None
            
            # Check permissions
            if "permissions" in acl:
                for permission in acl["permissions"]:
                    if not user.has_perm(permission):
                        logger.warning(
                            f"Access denied for user {user.id} to {namespace}:{identifier}: "
                            f"missing permission {permission}"
                        )
                        return None
        
        # Decrypt data
        return decrypt_data(encrypted, encryption_key)
    except Exception as e:
        logger.error(
            f"Error getting sensitive data for {namespace}:{identifier}: {str(e)}"
        )
        return None


def cache_encrypted_api(
    ttl: int,
    namespace: Union[str, CacheNamespace] = CacheNamespace.API,
    vary_on_headers: Optional[List[str]] = None,
    vary_on_cookies: Optional[List[str]] = None,
    vary_on_query_params: Optional[List[str]] = None,
    encryption_key: Optional[str] = None,
) -> Callable:
    """
    Decorator for caching API responses with encryption.
    
    Args:
        ttl: Cache TTL in seconds
        namespace: Cache namespace
        vary_on_headers: Headers to include in the cache key
        vary_on_cookies: Cookies to include in the cache key
        vary_on_query_params: Query params to include in the cache key
        encryption_key: Custom encryption key
        
    Returns:
        Decorated function
    """
    def decorator(view_func: Callable) -> Callable:
        from functools import wraps
        
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            if not CACHE_ENABLED:
                return view_func(request, *args, **kwargs)
            
            # Only cache GET requests
            if request.method != "GET":
                return view_func(request, *args, **kwargs)
            
            # Generate cache key
            from core.redis_keys import api_cache_key
            cache_key = api_cache_key(
                view_func,
                request,
                *args,
                vary_on_headers=vary_on_headers,
                vary_on_cookies=vary_on_cookies,
                vary_on_query_params=vary_on_query_params,
            )
            
            # Try to get from cache
            cached_data = get_encrypted_cache(cache_key, encryption_key)
            if cached_data is not None:
                from django.http import JsonResponse
                return JsonResponse(cached_data)
            
            # Cache miss, call the view function
            response = view_func(request, *args, **kwargs)
            
            # Only cache JsonResponse objects
            if hasattr(response, "content"):
                try:
                    # Extract the response data
                    response_data = json.loads(response.content.decode("utf-8"))
                    
                    # Cache the response data
                    cache_encrypted(cache_key, response_data, ttl, encryption_key)
                except Exception as e:
                    logger.error(
                        f"Error caching encrypted API response: {str(e)}"
                    )
            
            return response
        
        return wrapper
    
    return decorator

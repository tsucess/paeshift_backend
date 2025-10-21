"""
Tests for Redis cache security.
"""

import json
import unittest
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User, Group, Permission
from django.test import TestCase

from core.redis_security import (
    encrypt_data,
    decrypt_data,
    sign_data,
    verify_signature,
    cache_encrypted,
    get_encrypted_cache,
    cache_with_acl,
    get_cache_with_acl,
    cache_sensitive_data,
    get_sensitive_data,
)


class RedisCacheSecurityTests(TestCase):
    """Test Redis cache security features."""

    def test_encrypt_decrypt_data(self):
        """Test encrypting and decrypting data."""
        # Test data
        test_data = {"key": "value", "nested": {"key2": "value2"}}
        
        # Encrypt data
        encrypted = encrypt_data(test_data)
        
        # Verify encrypted data is a string
        self.assertIsInstance(encrypted, str)
        
        # Decrypt data
        decrypted = decrypt_data(encrypted)
        
        # Verify decrypted data matches original
        self.assertEqual(decrypted, test_data)

    def test_sign_verify_data(self):
        """Test signing and verifying data."""
        # Test data
        test_data = {"key": "value", "nested": {"key2": "value2"}}
        
        # Sign data
        signed_data, signature = sign_data(test_data)
        
        # Verify signature is a string
        self.assertIsInstance(signature, str)
        
        # Verify signature
        is_valid = verify_signature(signed_data, signature)
        
        # Verify signature is valid
        self.assertTrue(is_valid)
        
        # Verify invalid signature is detected
        is_valid = verify_signature(signed_data, signature + "x")
        self.assertFalse(is_valid)
        
        # Verify modified data is detected
        modified_data = signed_data.copy()
        modified_data["key"] = "modified"
        is_valid = verify_signature(modified_data, signature)
        self.assertFalse(is_valid)

    @patch("core.redis_security.set_cached_data")
    def test_cache_encrypted(self, mock_set):
        """Test caching encrypted data."""
        # Setup mock
        mock_set.return_value = True
        
        # Test data
        test_data = {"key": "value"}
        
        # Cache encrypted data
        result = cache_encrypted("test_key", test_data, 300)
        
        # Verify result
        self.assertTrue(result)
        mock_set.assert_called_once()
        
        # Verify encrypted data was passed to set_cached_data
        args, kwargs = mock_set.call_args
        self.assertEqual(args[0], "test_key")
        self.assertIn("_encrypted", args[1])
        self.assertEqual(args[2], 300)

    @patch("core.redis_security.get_cached_data")
    def test_get_encrypted_cache(self, mock_get):
        """Test getting encrypted data from cache."""
        # Test data
        test_data = {"key": "value"}
        
        # Encrypt data
        encrypted = encrypt_data(test_data)
        
        # Setup mock to return encrypted data
        mock_get.return_value = {"_encrypted": encrypted}
        
        # Get encrypted data
        result = get_encrypted_cache("test_key")
        
        # Verify result
        self.assertEqual(result, test_data)
        mock_get.assert_called_once_with("test_key")

    @patch("core.redis_security.set_cached_data")
    def test_cache_with_acl(self, mock_set):
        """Test caching data with access control."""
        # Setup mock
        mock_set.return_value = True
        
        # Test data
        test_data = {"key": "value"}
        
        # Cache data with ACL
        result = cache_with_acl(
            "test_key", test_data, 300, user_id=123, roles=["admin"], permissions=["view_data"]
        )
        
        # Verify result
        self.assertTrue(result)
        mock_set.assert_called_once()
        
        # Verify ACL data was passed to set_cached_data
        args, kwargs = mock_set.call_args
        self.assertEqual(args[0], "test_key")
        self.assertIn("data", args[1])
        self.assertIn("signature", args[1])
        self.assertIn("acl", args[1])
        self.assertEqual(args[1]["acl"]["user_id"], 123)
        self.assertEqual(args[1]["acl"]["roles"], ["admin"])
        self.assertEqual(args[1]["acl"]["permissions"], ["view_data"])
        self.assertEqual(args[2], 300)

    @patch("core.redis_security.get_cached_data")
    def test_get_cache_with_acl_allowed(self, mock_get):
        """Test getting data with access control when access is allowed."""
        # Test data
        test_data = {"key": "value"}
        
        # Sign data
        signed_data, signature = sign_data(test_data)
        
        # Setup mock to return signed data with ACL
        mock_get.return_value = {
            "data": signed_data,
            "signature": signature,
            "acl": {"user_id": 123},
            "_protected": True,
        }
        
        # Create mock user
        user = MagicMock()
        user.id = 123
        
        # Get data with ACL
        result = get_cache_with_acl("test_key", user)
        
        # Verify result
        self.assertEqual(result, signed_data)
        mock_get.assert_called_once_with("test_key")

    @patch("core.redis_security.get_cached_data")
    def test_get_cache_with_acl_denied(self, mock_get):
        """Test getting data with access control when access is denied."""
        # Test data
        test_data = {"key": "value"}
        
        # Sign data
        signed_data, signature = sign_data(test_data)
        
        # Setup mock to return signed data with ACL
        mock_get.return_value = {
            "data": signed_data,
            "signature": signature,
            "acl": {"user_id": 123},
            "_protected": True,
        }
        
        # Create mock user with different ID
        user = MagicMock()
        user.id = 456
        
        # Get data with ACL
        result = get_cache_with_acl("test_key", user)
        
        # Verify access was denied
        self.assertIsNone(result)
        mock_get.assert_called_once_with("test_key")

    @patch("core.redis_security.set_cached_data")
    def test_cache_sensitive_data(self, mock_set):
        """Test caching sensitive data with encryption and access control."""
        # Setup mock
        mock_set.return_value = True
        
        # Test data
        test_data = {"key": "value"}
        
        # Cache sensitive data
        result = cache_sensitive_data(
            "user", 123, test_data, 300, user_id=123, roles=["admin"]
        )
        
        # Verify result
        self.assertTrue(result)
        mock_set.assert_called_once()
        
        # Verify encrypted data with ACL was passed to set_cached_data
        args, kwargs = mock_set.call_args
        self.assertIn("_encrypted", args[1])
        self.assertIn("acl", args[1])
        self.assertEqual(args[1]["acl"]["user_id"], 123)
        self.assertEqual(args[1]["acl"]["roles"], ["admin"])
        self.assertEqual(args[2], 300)

    @patch("core.redis_security.get_cached_data")
    def test_get_sensitive_data_allowed(self, mock_get):
        """Test getting sensitive data when access is allowed."""
        # Test data
        test_data = {"key": "value"}
        
        # Encrypt data
        encrypted = encrypt_data(test_data)
        
        # Setup mock to return encrypted data with ACL
        mock_get.return_value = {
            "_encrypted": encrypted,
            "acl": {"user_id": 123},
            "_sensitive": True,
        }
        
        # Create mock user
        user = MagicMock()
        user.id = 123
        
        # Get sensitive data
        result = get_sensitive_data("user", 123, user)
        
        # Verify result
        self.assertEqual(result, test_data)
        mock_get.assert_called_once()

    @patch("core.redis_security.get_cached_data")
    def test_get_sensitive_data_denied(self, mock_get):
        """Test getting sensitive data when access is denied."""
        # Test data
        test_data = {"key": "value"}
        
        # Encrypt data
        encrypted = encrypt_data(test_data)
        
        # Setup mock to return encrypted data with ACL
        mock_get.return_value = {
            "_encrypted": encrypted,
            "acl": {"user_id": 123},
            "_sensitive": True,
        }
        
        # Create mock user with different ID
        user = MagicMock()
        user.id = 456
        
        # Get sensitive data
        result = get_sensitive_data("user", 123, user)
        
        # Verify access was denied
        self.assertIsNone(result)
        mock_get.assert_called_once()


if __name__ == "__main__":
    unittest.main()

"""
Tests for core Redis caching functionality.
"""

import json
import unittest
from unittest.mock import patch, MagicMock, call

from django.db import models
from django.http import HttpRequest, JsonResponse
from django.test import TestCase

from core.cache import (
    get_cached_data,
    set_cached_data,
    delete_cached_data,
    invalidate_cache_pattern,
    cache_function_result,
    cache_api_response,
    generate_cache_key,
    get_cache_stats,
    CustomJSONEncoder,
)


class TestModel(models.Model):
    """Test model for serialization."""
    name = models.CharField(max_length=100)
    
    class Meta:
        app_label = "test_app"


class CacheCoreTests(TestCase):
    """Test core Redis caching functionality."""

    @patch("core.cache.redis_client")
    def test_get_cached_data(self, mock_redis):
        """Test getting data from cache."""
        # Setup mock
        mock_redis.get.return_value = b'{"key": "value"}'
        
        # Call function
        result = get_cached_data("test_key")
        
        # Verify result
        self.assertEqual(result, {"key": "value"})
        mock_redis.get.assert_called_once_with("test_key")

    @patch("core.cache.redis_client")
    def test_get_cached_data_not_found(self, mock_redis):
        """Test getting data that's not in cache."""
        # Setup mock
        mock_redis.get.return_value = None
        
        # Call function
        result = get_cached_data("test_key")
        
        # Verify result
        self.assertIsNone(result)
        mock_redis.get.assert_called_once_with("test_key")

    @patch("core.cache.redis_client")
    def test_set_cached_data(self, mock_redis):
        """Test setting data in cache."""
        # Setup mock
        mock_redis.setex.return_value = True
        
        # Call function
        result = set_cached_data("test_key", {"key": "value"}, 300)
        
        # Verify result
        self.assertTrue(result)
        mock_redis.setex.assert_called_once()
        # Verify key and timeout
        self.assertEqual(mock_redis.setex.call_args[0][0], "test_key")
        self.assertEqual(mock_redis.setex.call_args[0][1], 300)

    @patch("core.cache.redis_client")
    def test_delete_cached_data(self, mock_redis):
        """Test deleting data from cache."""
        # Setup mock
        mock_redis.exists.return_value = True
        mock_redis.delete.return_value = 1
        
        # Call function
        result = delete_cached_data("test_key")
        
        # Verify result
        self.assertTrue(result)
        mock_redis.delete.assert_called_once_with("test_key")

    @patch("core.cache.redis_client")
    def test_invalidate_cache_pattern(self, mock_redis):
        """Test invalidating cache by pattern."""
        # Setup mock
        mock_redis.keys.return_value = ["key1", "key2", "key3"]
        mock_redis.delete.return_value = 3
        
        # Call function
        result = invalidate_cache_pattern("test_pattern")
        
        # Verify result
        self.assertEqual(result, 3)
        mock_redis.keys.assert_called_once_with("test_pattern")
        mock_redis.delete.assert_called_once_with("key1", "key2", "key3")

    def test_generate_cache_key(self):
        """Test cache key generation."""
        # Test with simple identifier
        key1 = generate_cache_key("test", "123")
        self.assertTrue(key1.startswith("test:123:v"))
        
        # Test with namespace
        key2 = generate_cache_key("test", "123", namespace="ns")
        self.assertTrue(key2.startswith("test:ns:123:v"))
        
        # Test with long identifier (should be hashed)
        long_id = "x" * 200
        key3 = generate_cache_key("test", long_id)
        self.assertTrue(key3.startswith("test:h:"))
        self.assertTrue(len(key3) < 100)

    @patch("core.cache.redis_client")
    def test_cache_function_result_decorator(self, mock_redis):
        """Test cache_function_result decorator."""
        # Setup mock
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True
        
        # Define decorated function
        @cache_function_result(timeout=300)
        def test_func(arg1, arg2=None):
            return f"{arg1}_{arg2}"
        
        # Call function
        result = test_func("value1", arg2="value2")
        
        # Verify result
        self.assertEqual(result, "value1_value2")
        mock_redis.get.assert_called_once()
        mock_redis.setex.assert_called_once()

    @patch("core.cache.redis_client")
    def test_cache_function_result_hit(self, mock_redis):
        """Test cache_function_result decorator with cache hit."""
        # Setup mock
        mock_redis.get.return_value = b'"cached_result"'
        
        # Define decorated function
        @cache_function_result(timeout=300)
        def test_func():
            return "original_result"
        
        # Call function
        result = test_func()
        
        # Verify result
        self.assertEqual(result, "cached_result")
        mock_redis.get.assert_called_once()
        mock_redis.setex.assert_not_called()

    @patch("core.cache.redis_client")
    def test_cache_api_response_decorator(self, mock_redis):
        """Test cache_api_response decorator."""
        # Setup mock
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True
        
        # Define decorated function
        @cache_api_response(timeout=300)
        def test_view(request):
            return JsonResponse({"key": "value"})
        
        # Create mock request
        request = MagicMock(spec=HttpRequest)
        request.method = "GET"
        request.user.is_authenticated = False
        request.GET = {}
        
        # Call function
        response = test_view(request)
        
        # Verify result
        self.assertEqual(json.loads(response.content), {"key": "value"})
        mock_redis.get.assert_called_once()
        mock_redis.setex.assert_called_once()

    @patch("core.cache.redis_client")
    def test_cache_api_response_hit(self, mock_redis):
        """Test cache_api_response decorator with cache hit."""
        # Setup mock
        mock_redis.get.return_value = b'{"key": "cached_value"}'
        
        # Define decorated function
        @cache_api_response(timeout=300)
        def test_view(request):
            return JsonResponse({"key": "original_value"})
        
        # Create mock request
        request = MagicMock(spec=HttpRequest)
        request.method = "GET"
        request.user.is_authenticated = False
        request.GET = {}
        
        # Call function
        response = test_view(request)
        
        # Verify result
        self.assertEqual(json.loads(response.content), {"key": "cached_value"})
        mock_redis.get.assert_called_once()
        mock_redis.setex.assert_not_called()

    @patch("core.cache.redis_client")
    def test_cache_api_response_non_get(self, mock_redis):
        """Test cache_api_response decorator with non-GET request."""
        # Define decorated function
        @cache_api_response(timeout=300)
        def test_view(request):
            return JsonResponse({"key": "value"})
        
        # Create mock request
        request = MagicMock(spec=HttpRequest)
        request.method = "POST"
        
        # Call function
        response = test_view(request)
        
        # Verify result
        self.assertEqual(json.loads(response.content), {"key": "value"})
        mock_redis.get.assert_not_called()
        mock_redis.setex.assert_not_called()

    def test_custom_json_encoder(self):
        """Test CustomJSONEncoder with Django models."""
        # Create test model instance
        model = TestModel(id=1, name="Test")
        
        # Encode with CustomJSONEncoder
        encoded = json.dumps(model, cls=CustomJSONEncoder)
        decoded = json.loads(encoded)
        
        # Verify result
        self.assertEqual(decoded["_model_type"], "TestModel")
        self.assertEqual(decoded["_model_pk"], 1)
        self.assertEqual(decoded["name"], "Test")

    @patch("core.cache.redis_client")
    def test_get_cache_stats(self, mock_redis):
        """Test getting cache statistics."""
        # Setup mock
        mock_redis.info.return_value = {
            "used_memory": 1024 * 1024,
            "used_memory_peak": 2 * 1024 * 1024,
            "keyspace_hits": 800,
            "keyspace_misses": 200,
            "uptime_in_seconds": 3600,
            "connected_clients": 5,
            "redis_version": "6.0.0",
        }
        mock_redis.keys.return_value = ["key1", "key2", "key3"]
        
        # Call function
        stats = get_cache_stats()
        
        # Verify result
        self.assertIn("total_keys", stats)
        self.assertIn("memory_used_bytes", stats)
        self.assertIn("hit_rate", stats)
        self.assertIn("uptime_seconds", stats)


if __name__ == "__main__":
    unittest.main()

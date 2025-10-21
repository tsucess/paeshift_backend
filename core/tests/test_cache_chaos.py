"""
Chaos testing for Redis cache.

This module provides tests that simulate various failure scenarios to verify
the resilience of the Redis caching system.
"""

import json
import random
import time
import unittest
from unittest.mock import patch, MagicMock, call

from django.test import TestCase, override_settings

from core.cache import (
    get_cached_data,
    set_cached_data,
    delete_cached_data,
    invalidate_cache_pattern,
    cache_function_result,
    cache_api_response,
)


class RedisChaosTests(TestCase):
    """Chaos tests for Redis cache."""

    @patch("core.cache.redis_client")
    def test_redis_connection_failure(self, mock_redis):
        """Test behavior when Redis connection fails."""
        # Setup mock to simulate connection failure
        mock_redis.get.side_effect = Exception("Connection refused")
        
        # Call function
        result = get_cached_data("test_key")
        
        # Verify graceful failure
        self.assertIsNone(result)

    @patch("core.cache.redis_client")
    def test_redis_timeout(self, mock_redis):
        """Test behavior when Redis operation times out."""
        # Setup mock to simulate timeout
        mock_redis.get.side_effect = TimeoutError("Operation timed out")
        
        # Call function
        result = get_cached_data("test_key")
        
        # Verify graceful failure
        self.assertIsNone(result)

    @patch("core.cache.redis_client")
    def test_redis_memory_full(self, mock_redis):
        """Test behavior when Redis is out of memory."""
        # Setup mock to simulate OOM error
        mock_redis.setex.side_effect = Exception("OOM command not allowed when used memory > 'maxmemory'")
        
        # Call function
        result = set_cached_data("test_key", "test_value", 300)
        
        # Verify graceful failure
        self.assertFalse(result)

    @patch("core.cache.redis_client")
    def test_corrupted_cache_data(self, mock_redis):
        """Test behavior with corrupted cache data."""
        # Setup mock to return corrupted JSON
        mock_redis.get.return_value = b"not valid json"
        
        # Call function
        result = get_cached_data("test_key")
        
        # Verify graceful failure
        self.assertIsNone(result)
        # Verify corrupted data was deleted
        mock_redis.delete.assert_called_once_with("test_key")

    @patch("core.cache.redis_client")
    def test_intermittent_failures(self, mock_redis):
        """Test behavior with intermittent Redis failures."""
        # Setup mock to fail every other call
        mock_redis.get.side_effect = [
            Exception("Connection refused"),
            b'{"key": "value"}',
            Exception("Connection refused"),
            b'{"key": "value2"}',
        ]
        
        # First call - should fail gracefully
        result1 = get_cached_data("test_key")
        self.assertIsNone(result1)
        
        # Second call - should succeed
        result2 = get_cached_data("test_key")
        self.assertEqual(result2, {"key": "value"})
        
        # Third call - should fail gracefully
        result3 = get_cached_data("test_key")
        self.assertIsNone(result3)
        
        # Fourth call - should succeed
        result4 = get_cached_data("test_key")
        self.assertEqual(result4, {"key": "value2"})

    @patch("core.cache.redis_client")
    def test_partial_failures(self, mock_redis):
        """Test behavior with partial Redis failures."""
        # Setup mock to succeed for get but fail for delete
        mock_redis.get.return_value = b'{"key": "value"}'
        mock_redis.delete.side_effect = Exception("Connection refused")
        
        # Get should succeed
        result = get_cached_data("test_key")
        self.assertEqual(result, {"key": "value"})
        
        # Delete should fail gracefully
        delete_result = delete_cached_data("test_key")
        self.assertFalse(delete_result)

    @patch("core.cache.redis_client")
    def test_large_data_handling(self, mock_redis):
        """Test handling of large data objects."""
        # Create a large data object (>1MB)
        large_data = {"large_field": "x" * (1024 * 1024)}
        
        # Setup mock
        mock_redis.setex.return_value = True
        
        # Call function
        with self.assertLogs(level="WARNING") as log:
            result = set_cached_data("test_key", large_data, 300)
        
        # Verify result
        self.assertTrue(result)
        # Verify warning was logged
        self.assertTrue(any("Large object cached" in msg for msg in log.output))

    @patch("core.cache.redis_client")
    def test_many_keys_invalidation(self, mock_redis):
        """Test invalidation of many keys."""
        # Setup mock to return many keys
        mock_redis.keys.return_value = [f"key{i}".encode() for i in range(5000)]
        
        # Setup delete to handle batches
        mock_redis.delete.return_value = 1000
        
        # Call function
        result = invalidate_cache_pattern("test_pattern")
        
        # Verify result
        self.assertEqual(result, 5000)
        # Verify delete was called for each batch
        self.assertEqual(mock_redis.delete.call_count, 5)

    @override_settings(CACHE_ENABLED=False)
    def test_cache_disabled(self):
        """Test behavior when cache is disabled."""
        # With cache disabled, all operations should be no-ops
        
        # Get should return None
        result1 = get_cached_data("test_key")
        self.assertIsNone(result1)
        
        # Set should return False
        result2 = set_cached_data("test_key", "test_value", 300)
        self.assertFalse(result2)
        
        # Delete should return False
        result3 = delete_cached_data("test_key")
        self.assertFalse(result3)
        
        # Invalidate should return 0
        result4 = invalidate_cache_pattern("test_pattern")
        self.assertEqual(result4, 0)

    @patch("core.cache.redis_client")
    def test_decorator_with_redis_failure(self, mock_redis):
        """Test cache decorator behavior with Redis failures."""
        # Setup mock to fail
        mock_redis.get.side_effect = Exception("Connection refused")
        
        # Define decorated function
        @cache_function_result(timeout=300)
        def test_func():
            return "test_result"
        
        # Call function
        result = test_func()
        
        # Verify function still works despite cache failure
        self.assertEqual(result, "test_result")

    @patch("core.cache.redis_client")
    def test_api_decorator_with_redis_failure(self, mock_redis):
        """Test API cache decorator behavior with Redis failures."""
        # Setup mock to fail
        mock_redis.get.side_effect = Exception("Connection refused")
        
        # Define decorated function
        @cache_api_response(timeout=300)
        def test_view(request):
            from django.http import JsonResponse
            return JsonResponse({"key": "value"})
        
        # Create mock request
        request = MagicMock()
        request.method = "GET"
        
        # Call function
        result = test_view(request)
        
        # Verify function still works despite cache failure
        self.assertEqual(json.loads(result.content), {"key": "value"})


class RedisReliabilityTests(TestCase):
    """Reliability tests for Redis cache."""

    @patch("core.cache.redis_client")
    def test_concurrent_access(self, mock_redis):
        """Test behavior with concurrent access."""
        # This is a simplified simulation of concurrent access
        # In a real test, you would use threads or processes
        
        # Setup mock
        mock_redis.get.return_value = None
        
        # Define a function that uses the cache
        def cached_function(key):
            value = get_cached_data(key)
            if value is None:
                value = f"computed_value_{key}"
                set_cached_data(key, value, 300)
            return value
        
        # Call function multiple times with the same key
        results = [cached_function("test_key") for _ in range(10)]
        
        # Verify all calls returned the same result
        self.assertEqual(len(set(results)), 1)
        self.assertEqual(results[0], "computed_value_test_key")

    @patch("core.cache.redis_client")
    def test_high_load(self, mock_redis):
        """Test behavior under high load."""
        # Setup mock
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True
        
        # Generate many unique keys
        keys = [f"test_key_{i}" for i in range(1000)]
        
        # Call functions with many keys
        start_time = time.time()
        for key in keys:
            get_cached_data(key)
            set_cached_data(key, f"value_{key}", 300)
        end_time = time.time()
        
        # Verify performance is reasonable
        duration = end_time - start_time
        self.assertLess(duration, 5.0)  # Should complete in under 5 seconds

    @patch("core.cache.redis_client")
    def test_random_failures(self, mock_redis):
        """Test behavior with random failures."""
        # Setup mock to randomly fail
        def random_failure(*args, **kwargs):
            if random.random() < 0.3:  # 30% chance of failure
                raise Exception("Random failure")
            return b'{"key": "value"}'
        
        mock_redis.get.side_effect = random_failure
        
        # Call function multiple times
        results = []
        for _ in range(100):
            try:
                result = get_cached_data("test_key")
                results.append(result)
            except Exception:
                results.append(None)
        
        # Verify some calls succeeded and some failed
        self.assertTrue(any(r is None for r in results))
        self.assertTrue(any(r is not None for r in results))


if __name__ == "__main__":
    unittest.main()

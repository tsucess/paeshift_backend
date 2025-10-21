"""
Tests for Redis cache error handling.
"""

import json
import unittest
from unittest.mock import patch, MagicMock

from django.test import TestCase

from core.cache import (
    get_cached_data,
    set_cached_data,
    delete_cached_data,
    invalidate_cache_pattern,
)


class CacheErrorHandlingTests(TestCase):
    """Test error handling in Redis cache operations."""

    @patch("core.cache.redis_client")
    def test_get_cached_data_json_error(self, mock_redis):
        """Test handling of JSON decode errors in get_cached_data."""
        # Setup mock to return invalid JSON
        mock_redis.get.return_value = b"invalid json"

        # Call function
        result = get_cached_data("test_key")

        # Verify result
        self.assertIsNone(result)
        # Verify corrupted data was deleted
        mock_redis.delete.assert_called_once_with("test_key")

    @patch("core.cache.redis_client")
    def test_get_cached_data_redis_error(self, mock_redis):
        """Test handling of Redis errors in get_cached_data."""
        # Setup mock to raise Redis error
        mock_redis.get.side_effect = Exception("Redis connection error")

        # Call function
        result = get_cached_data("test_key")

        # Verify result
        self.assertIsNone(result)

    @patch("core.cache.redis_client")
    def test_set_cached_data_large_object(self, mock_redis):
        """Test warning for large objects in set_cached_data."""
        # Create a large object (>100KB)
        large_data = {"large_field": "x" * 102400}

        # Call function with large data
        with self.assertLogs(level="WARNING") as log:
            result = set_cached_data("test_key", large_data)

        # Verify result
        self.assertTrue(result)
        # Verify warning was logged
        self.assertTrue(any("Large object cached" in msg for msg in log.output))

    @patch("core.cache.redis_client")
    def test_invalidate_cache_pattern_batching(self, mock_redis):
        """Test batching in invalidate_cache_pattern."""
        # Setup mock to return a large number of keys
        mock_redis.keys.return_value = [f"key{i}" for i in range(2500)]
        mock_redis.delete.return_value = 1000  # Each batch deletes 1000 keys

        # Call function
        result = invalidate_cache_pattern("test_pattern")

        # Verify result
        self.assertEqual(result, 2500)
        # Verify delete was called for each batch
        self.assertEqual(mock_redis.delete.call_count, 3)


if __name__ == "__main__":
    unittest.main()

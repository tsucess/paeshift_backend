"""
Tests for Redis distributed locking and cache stampede protection.
"""

import time
import unittest
from unittest.mock import patch, MagicMock, call

from django.test import TestCase

from core.redis_locks import (
    DistributedLock,
    distributed_lock,
    with_distributed_lock,
    get_with_stampede_protection,
    cache_with_stampede_protection,
    LockAcquisitionError,
)


class RedisLocksTests(TestCase):
    """Test Redis distributed locking and cache stampede protection."""

    @patch("core.redis_locks.redis_client")
    def test_distributed_lock_acquire_release(self, mock_redis):
        """Test acquiring and releasing a distributed lock."""
        # Setup mock
        mock_redis.set.return_value = True
        mock_redis.eval.return_value = 1
        
        # Create lock
        lock = DistributedLock("test_lock")
        
        # Acquire lock
        result = lock.acquire()
        
        # Verify result
        self.assertTrue(result)
        self.assertTrue(lock.acquired)
        mock_redis.set.assert_called_once()
        
        # Release lock
        release_result = lock.release()
        
        # Verify release
        self.assertTrue(release_result)
        self.assertFalse(lock.acquired)
        mock_redis.eval.assert_called_once()

    @patch("core.redis_locks.redis_client")
    def test_distributed_lock_context_manager(self, mock_redis):
        """Test distributed lock as context manager."""
        # Setup mock
        mock_redis.set.return_value = True
        mock_redis.eval.return_value = 1
        
        # Use lock as context manager
        with distributed_lock("test_lock") as lock:
            self.assertTrue(lock.acquired)
        
        # Verify lock was released
        self.assertFalse(lock.acquired)
        mock_redis.set.assert_called_once()
        mock_redis.eval.assert_called_once()

    @patch("core.redis_locks.redis_client")
    def test_distributed_lock_acquisition_failure(self, mock_redis):
        """Test lock acquisition failure."""
        # Setup mock to simulate lock already taken
        mock_redis.set.return_value = False
        
        # Create lock with short timeout
        lock = DistributedLock("test_lock", max_retries=2, sleep_time=0.01)
        
        # Try to acquire lock
        with self.assertRaises(LockAcquisitionError):
            lock.acquire()
        
        # Verify lock was not acquired
        self.assertFalse(lock.acquired)
        self.assertEqual(mock_redis.set.call_count, 3)  # Initial + 2 retries

    @patch("core.redis_locks.redis_client")
    def test_with_distributed_lock_decorator(self, mock_redis):
        """Test with_distributed_lock decorator."""
        # Setup mock
        mock_redis.set.return_value = True
        mock_redis.eval.return_value = 1
        
        # Define decorated function
        @with_distributed_lock("test_lock")
        def test_func():
            return "success"
        
        # Call function
        result = test_func()
        
        # Verify result
        self.assertEqual(result, "success")
        mock_redis.set.assert_called_once()
        mock_redis.eval.assert_called_once()

    @patch("core.redis_locks.redis_client")
    def test_with_distributed_lock_dynamic_name(self, mock_redis):
        """Test with_distributed_lock with dynamic lock name."""
        # Setup mock
        mock_redis.set.return_value = True
        mock_redis.eval.return_value = 1
        
        # Define decorated function with dynamic lock name
        @with_distributed_lock("test_lock_{arg0}_{kwarg1}")
        def test_func(arg1, kwarg1=None):
            return f"{arg1}_{kwarg1}"
        
        # Call function
        result = test_func("value1", kwarg1="value2")
        
        # Verify result
        self.assertEqual(result, "value1_value2")
        mock_redis.set.assert_called_once()
        # Check that the lock name was formatted correctly
        self.assertTrue("test_lock_value1_value2" in str(mock_redis.set.call_args))

    @patch("core.redis_locks.get_cached_data")
    @patch("core.redis_locks.set_cached_data")
    @patch("core.redis_locks.redis_client")
    def test_get_with_stampede_protection_cache_hit(self, mock_redis, mock_set, mock_get):
        """Test get_with_stampede_protection with cache hit."""
        # Setup mocks
        mock_get.return_value = "cached_value"
        mock_redis.ttl.return_value = 100  # Far from expiration
        
        # Define getter function
        getter_func = MagicMock(return_value="fresh_value")
        
        # Call function
        result = get_with_stampede_protection("test_key", getter_func, 300)
        
        # Verify result
        self.assertEqual(result, "cached_value")
        mock_get.assert_called_once_with("test_key")
        getter_func.assert_not_called()  # Getter should not be called for cache hit

    @patch("core.redis_locks.get_cached_data")
    @patch("core.redis_locks.set_cached_data")
    @patch("core.redis_locks.redis_client")
    def test_get_with_stampede_protection_cache_miss(self, mock_redis, mock_set, mock_get):
        """Test get_with_stampede_protection with cache miss."""
        # Setup mocks
        mock_get.return_value = None
        mock_redis.set.return_value = True  # Lock acquisition succeeds
        
        # Define getter function
        getter_func = MagicMock(return_value="fresh_value")
        
        # Call function
        result = get_with_stampede_protection("test_key", getter_func, 300)
        
        # Verify result
        self.assertEqual(result, "fresh_value")
        mock_get.assert_called_with("test_key")
        getter_func.assert_called_once()
        mock_set.assert_called_once_with("test_key", "fresh_value", 300)

    @patch("core.redis_locks.get_with_stampede_protection")
    def test_cache_with_stampede_protection_decorator(self, mock_get_with_protection):
        """Test cache_with_stampede_protection decorator."""
        # Setup mock
        mock_get_with_protection.return_value = "result"
        
        # Define decorated function
        @cache_with_stampede_protection(300)
        def test_func(arg1, arg2):
            return f"{arg1}_{arg2}"
        
        # Call function
        result = test_func("value1", "value2")
        
        # Verify result
        self.assertEqual(result, "result")
        mock_get_with_protection.assert_called_once()
        # Verify the correct arguments were passed
        args, kwargs = mock_get_with_protection.call_args
        self.assertEqual(args[1], test_func)  # Second arg should be the original function
        self.assertEqual(args[2], 300)  # Third arg should be the TTL
        self.assertEqual(args[3:], ("value1", "value2"))  # Rest should be the function args


if __name__ == "__main__":
    unittest.main()

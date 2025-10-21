"""
Tests for the cache synchronization functionality.
"""

import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

from accounts.models import CustomUser as User
from core.cache import redis_client
from godmode.cache_sync import CacheSyncManager
from godmode.cache_utils import ensure_timestamp_in_cache_data
from payment.models import Payment


class CacheSyncTestCase(TestCase):
    """Test case for cache synchronization functionality."""

    def setUp(self):
        """Set up test data."""
        # Create test user
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpassword",
        )

        # Create test payment
        self.payment = Payment.objects.create(
            payer=self.user,
            original_amount=100.00,
            service_fee=10.00,
            final_amount=90.00,
            pay_code="test-payment-123",
            payment_method="paystack",
            status="Pending",
        )

        # Create cache sync manager
        self.sync_manager = CacheSyncManager()

        # Mock Redis client
        self.redis_mock = MagicMock()
        self.redis_patcher = patch("godmode.cache_sync.redis_client", self.redis_mock)
        self.redis_patcher.start()

        # Mock CACHE_ENABLED
        self.cache_enabled_patcher = patch("godmode.cache_sync.CACHE_ENABLED", True)
        self.cache_enabled_patcher.start()

    def tearDown(self):
        """Clean up after tests."""
        self.redis_patcher.stop()
        self.cache_enabled_patcher.stop()

    def test_ensure_timestamp_in_cache_data(self):
        """Test ensuring timestamp in cache data."""
        # Test with no timestamp
        data = {"id": 1, "name": "Test"}
        result = ensure_timestamp_in_cache_data(data)
        self.assertIn("timestamp", result)
        self.assertTrue(isinstance(result["timestamp"], str))

        # Test with existing timestamp
        data = {"id": 1, "name": "Test", "updated_at": "2023-01-01T00:00:00"}
        result = ensure_timestamp_in_cache_data(data)
        self.assertEqual(result["updated_at"], "2023-01-01T00:00:00")
        self.assertNotIn("timestamp", result)

    def test_get_model_and_id_from_key(self):
        """Test extracting model name and ID from a Redis key."""
        # Test normal key
        model_name, model_id = self.sync_manager.get_model_and_id_from_key("payment:123")
        self.assertEqual(model_name, "payment")
        self.assertEqual(model_id, 123)

        # Test permanent key
        model_name, model_id = self.sync_manager.get_model_and_id_from_key("permanent:payment:123")
        self.assertEqual(model_name, "payment")
        self.assertEqual(model_id, 123)

        # Test invalid key
        model_name, model_id = self.sync_manager.get_model_and_id_from_key("invalid-key")
        self.assertIsNone(model_name)
        self.assertIsNone(model_id)

    def test_get_db_model(self):
        """Test getting the Django model class for a model name."""
        # Test valid model
        model_class = self.sync_manager.get_db_model("payment")
        self.assertEqual(model_class, Payment)

        # Test invalid model
        model_class = self.sync_manager.get_db_model("invalid_model")
        self.assertIsNone(model_class)

    @patch("godmode.cache_sync.CacheSyncManager.get_cached_data")
    @patch("godmode.cache_sync.CacheSyncManager.get_model_and_id_from_key")
    @patch("godmode.cache_sync.CacheSyncManager.get_db_model")
    def test_sync_key_to_db(self, mock_get_db_model, mock_get_model_and_id, mock_get_cached_data):
        """Test synchronizing a Redis key to the database."""
        # Mock return values
        mock_get_model_and_id.return_value = ("payment", self.payment.id)
        mock_get_db_model.return_value = Payment
        mock_get_cached_data.return_value = {
            "id": self.payment.id,
            "original_amount": "150.00",
            "service_fee": "15.00",
            "final_amount": "135.00",
            "status": "Completed",
            "updated_at": (timezone.now() + timedelta(hours=1)).isoformat(),
        }

        # Test sync
        result = self.sync_manager.sync_key_to_db(f"payment:{self.payment.id}")
        self.assertTrue(result)

        # Verify payment was updated
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "Completed")
        self.assertEqual(float(self.payment.original_amount), 150.00)
        self.assertEqual(float(self.payment.service_fee), 15.00)
        self.assertEqual(float(self.payment.final_amount), 135.00)

    @patch("godmode.cache_sync.CacheSyncManager.get_cached_data")
    @patch("godmode.cache_sync.CacheSyncManager.get_model_and_id_from_key")
    @patch("godmode.cache_sync.CacheSyncManager.get_db_model")
    def test_sync_key_to_db_older_cache(self, mock_get_db_model, mock_get_model_and_id, mock_get_cached_data):
        """Test synchronizing a Redis key to the database with older cache data."""
        # Update payment to have a newer timestamp
        self.payment.status = "Completed"
        self.payment.save()

        # Mock return values
        mock_get_model_and_id.return_value = ("payment", self.payment.id)
        mock_get_db_model.return_value = Payment
        mock_get_cached_data.return_value = {
            "id": self.payment.id,
            "original_amount": "150.00",
            "service_fee": "15.00",
            "final_amount": "135.00",
            "status": "Pending",
            "updated_at": (timezone.now() - timedelta(hours=1)).isoformat(),
        }

        # Test sync without force
        result = self.sync_manager.sync_key_to_db(f"payment:{self.payment.id}")
        self.assertFalse(result)

        # Verify payment was not updated
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "Completed")

        # Test sync with force
        result = self.sync_manager.sync_key_to_db(f"payment:{self.payment.id}", force=True)
        self.assertTrue(result)

        # Verify payment was updated
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "Pending")

    @patch("godmode.cache_sync.CacheSyncManager.get_model_keys")
    @patch("godmode.cache_sync.CacheSyncManager.sync_key_to_db")
    def test_sync_model_to_db(self, mock_sync_key_to_db, mock_get_model_keys):
        """Test synchronizing all Redis keys for a model to the database."""
        # Mock return values
        mock_get_model_keys.return_value = [f"payment:{self.payment.id}", "payment:999"]
        mock_sync_key_to_db.side_effect = [True, False]

        # Test sync
        result = self.sync_manager.sync_model_to_db("payment")

        # Verify results
        self.assertEqual(result["model"], "payment")
        self.assertEqual(result["stats"]["total_keys"], 2)
        self.assertEqual(result["stats"]["synced_keys"], 1)
        self.assertEqual(result["stats"]["error_keys"], 1)
        self.assertEqual(len(result["log"]), 2)

    @patch("godmode.cache_sync.redis_client.keys")
    @patch("godmode.cache_sync.CacheSyncManager.sync_key_to_db")
    def test_sync_all_to_db(self, mock_sync_key_to_db, mock_keys):
        """Test synchronizing all Redis keys to the database."""
        # Mock return values
        mock_keys.return_value = [
            b"payment:123",
            b"user:456",
            b"celery:task:789",  # Should be skipped
        ]
        mock_sync_key_to_db.side_effect = [True, True]

        # Test sync
        result = self.sync_manager.sync_all_to_db()

        # Verify results
        self.assertEqual(result["stats"]["total_keys"], 2)
        self.assertEqual(result["stats"]["synced_keys"], 2)
        self.assertEqual(len(result["log"]), 2)
        self.assertEqual(mock_sync_key_to_db.call_count, 2)


class CacheUtilsTestCase(TestCase):
    """Test case for cache utilities."""

    def setUp(self):
        """Set up test data."""
        # Create test user
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpassword",
        )

        # Mock Redis client
        self.redis_mock = MagicMock()
        self.redis_patcher = patch("godmode.cache_utils.redis_client", self.redis_mock)
        self.redis_patcher.start()

        # Mock CACHE_ENABLED
        self.cache_enabled_patcher = patch("godmode.cache_utils.CACHE_ENABLED", True)
        self.cache_enabled_patcher.start()

    def tearDown(self):
        """Clean up after tests."""
        self.redis_patcher.stop()
        self.cache_enabled_patcher.stop()

    def test_ensure_timestamp_in_cache_data(self):
        """Test ensuring timestamp in cache data."""
        from godmode.cache_utils import ensure_timestamp_in_cache_data

        # Test with no timestamp
        data = {"id": 1, "name": "Test"}
        result = ensure_timestamp_in_cache_data(data)
        self.assertIn("timestamp", result)
        self.assertTrue(isinstance(result["timestamp"], str))

        # Test with existing timestamp
        data = {"id": 1, "name": "Test", "updated_at": "2023-01-01T00:00:00"}
        result = ensure_timestamp_in_cache_data(data)
        self.assertEqual(result["updated_at"], "2023-01-01T00:00:00")
        self.assertNotIn("timestamp", result)

    @patch("godmode.cache_utils.redis_client.get")
    @patch("godmode.cache_utils.redis_client.ttl")
    def test_get_cache_key_info(self, mock_ttl, mock_get):
        """Test getting information about a cache key."""
        from godmode.cache_utils import get_cache_key_info

        # Mock return values
        mock_get.return_value = json.dumps({
            "id": 123,
            "name": "Test",
            "updated_at": "2023-01-01T00:00:00",
        }).encode()
        mock_ttl.return_value = 3600

        # Test get cache key info
        result = get_cache_key_info("test:123")

        # Verify results
        self.assertEqual(result["key"], "test:123")
        self.assertEqual(result["type"], "json")
        self.assertEqual(result["ttl"], 3600)
        self.assertEqual(result["timestamp"], "2023-01-01T00:00:00")
        self.assertEqual(result["fields"], ["id", "name", "updated_at"])

    @patch("godmode.cache_utils.redis_client.keys")
    def test_get_model_cache_keys(self, mock_keys):
        """Test getting all Redis keys for a specific model."""
        from godmode.cache_utils import get_model_cache_keys

        # Mock return values
        mock_keys.side_effect = [
            [b"payment:123", b"payment:456"],
            [b"permanent:payment:789"],
        ]

        # Test get model cache keys
        result = get_model_cache_keys("payment")

        # Verify results
        self.assertEqual(len(result), 3)
        self.assertIn("payment:123", result)
        self.assertIn("payment:456", result)
        self.assertIn("permanent:payment:789", result)

    @patch("godmode.cache_utils.redis_client.info")
    @patch("godmode.cache_utils.redis_client.keys")
    def test_get_cache_stats(self, mock_keys, mock_info):
        """Test getting Redis cache statistics."""
        from godmode.cache_utils import get_cache_stats

        # Mock return values
        mock_info.return_value = {
            "used_memory": 1024 * 1024,  # 1 MB
            "used_memory_peak": 2 * 1024 * 1024,  # 2 MB
            "maxmemory": 10 * 1024 * 1024,  # 10 MB
            "keyspace_hits": 100,
            "keyspace_misses": 20,
            "uptime_in_seconds": 86400,  # 1 day
            "db0": {"keys": 50},
        }
        mock_keys.return_value = [
            b"payment:123",
            b"payment:456",
            b"user:789",
            b"celery:task:123",
        ]

        # Test get cache stats
        result = get_cache_stats()

        # Verify results
        self.assertEqual(result["memory"]["used_memory"], 1024 * 1024)
        self.assertEqual(result["memory"]["used_memory_human"], "1.00 MB")
        self.assertEqual(result["hit_rate"]["hits"], 100)
        self.assertEqual(result["hit_rate"]["misses"], 20)
        self.assertEqual(result["hit_rate"]["hit_rate"], "83.33%")
        self.assertEqual(result["keys"]["total"], 50)
        self.assertEqual(len(result["keys"]["patterns"]), 3)

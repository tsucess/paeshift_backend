"""
Tests for Redis High Availability (HA) configuration.
"""

import unittest
from unittest.mock import patch, MagicMock, call

from django.test import TestCase, override_settings

from core.redis_ha import (
    get_redis_sentinel_client,
    get_redis_cluster_client,
    get_redis_standalone_client,
    get_redis_client,
    with_redis_retry,
    check_redis_health,
)


class RedisHATests(TestCase):
    """Test Redis High Availability configuration."""

    @patch("core.redis_ha.redis.ConnectionPool")
    @patch("core.redis_ha.redis.Redis")
    @patch("core.redis_ha.get_redis_connection_params")
    def test_get_redis_standalone_client(self, mock_params, mock_redis, mock_pool):
        """Test getting a standalone Redis client."""
        # Setup mocks
        mock_params.return_value = {
            "host": "localhost",
            "port": 6379,
            "db": 0,
            "password": None,
        }
        mock_pool.return_value = "pool"
        mock_redis.return_value = "client"
        
        # Call function
        client = get_redis_standalone_client()
        
        # Verify result
        self.assertEqual(client, "client")
        mock_pool.assert_called_once()
        mock_redis.assert_called_once_with(connection_pool="pool")

    @patch("core.redis_ha.REDIS_SENTINEL_ENABLED", True)
    @patch("core.redis_ha.REDIS_SENTINEL_HOSTS", ["localhost:26379"])
    @patch("core.redis_ha.Sentinel")
    @patch("core.redis_ha.redis.ConnectionPool")
    @patch("core.redis_ha.redis.Redis")
    def test_get_redis_sentinel_client(self, mock_redis, mock_pool, mock_sentinel):
        """Test getting a Redis Sentinel client."""
        # Setup mocks
        sentinel_instance = MagicMock()
        sentinel_instance.discover_master.return_value = ("master_host", 6379)
        mock_sentinel.return_value = sentinel_instance
        mock_pool.return_value = "pool"
        mock_redis.return_value = "client"
        
        # Call function
        client = get_redis_sentinel_client()
        
        # Verify result
        self.assertEqual(client, "client")
        mock_sentinel.assert_called_once()
        sentinel_instance.discover_master.assert_called_once()
        mock_pool.assert_called_once()
        mock_redis.assert_called_once_with(connection_pool="pool")

    @patch("core.redis_ha.REDIS_CLUSTER_ENABLED", True)
    @patch("core.redis_ha.REDIS_CLUSTER_NODES", ["localhost:6379", "localhost:6380"])
    @patch("core.redis_ha.RedisCluster")
    def test_get_redis_cluster_client(self, mock_cluster):
        """Test getting a Redis Cluster client."""
        # Setup mock
        mock_cluster.return_value = "cluster_client"
        
        # Call function
        client = get_redis_cluster_client()
        
        # Verify result
        self.assertEqual(client, "cluster_client")
        mock_cluster.assert_called_once()

    @patch("core.redis_ha.REDIS_SENTINEL_ENABLED", False)
    @patch("core.redis_ha.REDIS_CLUSTER_ENABLED", False)
    @patch("core.redis_ha.get_redis_standalone_client")
    def test_get_redis_client_standalone(self, mock_standalone):
        """Test getting the appropriate Redis client (standalone)."""
        # Setup mock
        mock_standalone.return_value = "standalone_client"
        
        # Call function
        client = get_redis_client()
        
        # Verify result
        self.assertEqual(client, "standalone_client")
        mock_standalone.assert_called_once()

    @patch("core.redis_ha.REDIS_SENTINEL_ENABLED", True)
    @patch("core.redis_ha.get_redis_sentinel_client")
    def test_get_redis_client_sentinel(self, mock_sentinel):
        """Test getting the appropriate Redis client (sentinel)."""
        # Setup mock
        mock_sentinel.return_value = "sentinel_client"
        
        # Call function
        client = get_redis_client()
        
        # Verify result
        self.assertEqual(client, "sentinel_client")
        mock_sentinel.assert_called_once()

    @patch("core.redis_ha.REDIS_SENTINEL_ENABLED", False)
    @patch("core.redis_ha.REDIS_CLUSTER_ENABLED", True)
    @patch("core.redis_ha.get_redis_cluster_client")
    def test_get_redis_client_cluster(self, mock_cluster):
        """Test getting the appropriate Redis client (cluster)."""
        # Setup mock
        mock_cluster.return_value = "cluster_client"
        
        # Call function
        client = get_redis_client()
        
        # Verify result
        self.assertEqual(client, "cluster_client")
        mock_cluster.assert_called_once()

    def test_with_redis_retry_decorator(self):
        """Test the Redis retry decorator."""
        import redis
        
        # Create a function that fails twice then succeeds
        mock_func = MagicMock()
        mock_func.side_effect = [
            redis.ConnectionError("Connection refused"),
            redis.TimeoutError("Timeout"),
            "success",
        ]
        
        # Apply decorator
        decorated_func = with_redis_retry(max_retries=3, retry_delay=0.01)(mock_func)
        
        # Call function
        result = decorated_func()
        
        # Verify result
        self.assertEqual(result, "success")
        self.assertEqual(mock_func.call_count, 3)

    def test_with_redis_retry_max_retries(self):
        """Test the Redis retry decorator with max retries exceeded."""
        import redis
        
        # Create a function that always fails
        mock_func = MagicMock()
        mock_func.side_effect = redis.ConnectionError("Connection refused")
        
        # Apply decorator
        decorated_func = with_redis_retry(max_retries=2, retry_delay=0.01)(mock_func)
        
        # Call function
        with self.assertRaises(redis.ConnectionError):
            decorated_func()
        
        # Verify call count
        self.assertEqual(mock_func.call_count, 3)  # Initial + 2 retries

    @patch("core.redis_ha.get_redis_client")
    def test_check_redis_health_healthy(self, mock_client):
        """Test checking Redis health when healthy."""
        # Setup mock
        client_instance = MagicMock()
        client_instance.ping.return_value = True
        client_instance.info.return_value = {
            "redis_version": "6.0.0",
            "uptime_in_seconds": 3600,
            "connected_clients": 10,
            "used_memory_human": "100M",
            "used_memory": 100 * 1024 * 1024,
            "maxmemory": 1024 * 1024 * 1024,  # 1GB
            "total_connections_received": 1000,
            "total_commands_processed": 10000,
        }
        mock_client.return_value = client_instance
        
        # Call function
        result = check_redis_health()
        
        # Verify result
        self.assertTrue(result["healthy"])
        self.assertEqual(result["message"], "Redis is healthy")
        self.assertIn("details", result)
        self.assertIn("redis_version", result["details"])
        self.assertIn("memory_usage_percent", result["details"])

    @patch("core.redis_ha.get_redis_client")
    def test_check_redis_health_unhealthy(self, mock_client):
        """Test checking Redis health when unhealthy."""
        # Setup mock
        client_instance = MagicMock()
        client_instance.ping.return_value = False
        mock_client.return_value = client_instance
        
        # Call function
        result = check_redis_health()
        
        # Verify result
        self.assertFalse(result["healthy"])
        self.assertEqual(result["message"], "Redis ping failed")

    @patch("core.redis_ha.get_redis_client")
    def test_check_redis_health_warning(self, mock_client):
        """Test checking Redis health with warnings."""
        # Setup mock
        client_instance = MagicMock()
        client_instance.ping.return_value = True
        client_instance.info.return_value = {
            "redis_version": "6.0.0",
            "uptime_in_seconds": 3600,
            "connected_clients": 150,  # High number of clients
            "used_memory_human": "900M",
            "used_memory": 900 * 1024 * 1024,
            "maxmemory": 1024 * 1024 * 1024,  # 1GB (90% used)
            "total_connections_received": 1000,
            "total_commands_processed": 10000,
        }
        mock_client.return_value = client_instance
        
        # Call function
        result = check_redis_health()
        
        # Verify result
        self.assertTrue(result["healthy"])
        self.assertIn("warnings", result["details"])
        self.assertEqual(len(result["details"]["warnings"]), 2)  # Memory and clients warnings


if __name__ == "__main__":
    unittest.main()

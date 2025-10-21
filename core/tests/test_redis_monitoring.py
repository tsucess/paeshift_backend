"""
Tests for Redis monitoring and observability.
"""

import json
import unittest
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.utils import timezone

from core.redis_monitoring import (
    get_cache_stats,
    record_stats,
    get_historical_stats,
    check_alerts,
    trigger_alert,
    analyze_key_size,
    get_dashboard_data,
    get_recent_alerts,
)


class RedisMonitoringTests(TestCase):
    """Test Redis monitoring and observability."""

    @patch("core.redis_monitoring.redis_client")
    def test_get_cache_stats(self, mock_redis):
        """Test getting cache statistics."""
        # Setup mock
        mock_redis.info.return_value = {
            "used_memory": 1024 * 1024,  # 1MB
            "used_memory_peak": 2 * 1024 * 1024,  # 2MB
            "used_memory_rss": 1.5 * 1024 * 1024,  # 1.5MB
            "maxmemory": 10 * 1024 * 1024,  # 10MB
            "keyspace_hits": 800,
            "keyspace_misses": 200,
            "uptime_in_seconds": 3600,
            "connected_clients": 5,
            "redis_version": "6.0.0",
            "evicted_keys": 10,
            "expired_keys": 20,
        }
        mock_redis.keys.return_value = ["key1", "key2", "key3"]
        
        # Call function
        stats = get_cache_stats()
        
        # Verify result
        self.assertNotIn("error", stats)
        self.assertEqual(stats["total_keys"], 3)
        self.assertEqual(float(stats["memory_usage_percent"].rstrip("%")), 10.0)  # 1MB / 10MB * 100
        self.assertEqual(float(stats["hit_rate_numeric"]), 80.0)  # 800 / 1000 * 100

    @patch("core.redis_monitoring.redis_client")
    @patch("core.redis_monitoring.get_cache_stats")
    @patch("core.redis_monitoring.check_alerts")
    def test_record_stats(self, mock_check_alerts, mock_get_stats, mock_redis):
        """Test recording cache statistics."""
        # Setup mocks
        mock_get_stats.return_value = {"test": "stats"}
        mock_redis.set.return_value = True
        mock_redis.expire.return_value = True
        
        # Call function
        result = record_stats()
        
        # Verify result
        self.assertTrue(result)
        mock_get_stats.assert_called_once()
        self.assertEqual(mock_redis.set.call_count, 3)  # hourly, daily, weekly
        self.assertEqual(mock_redis.expire.call_count, 3)  # hourly, daily, weekly
        mock_check_alerts.assert_called_once_with({"test": "stats"})

    @patch("core.redis_monitoring.redis_client")
    def test_get_historical_stats(self, mock_redis):
        """Test getting historical statistics."""
        # Setup mock
        mock_redis.keys.return_value = ["stats:hourly:2023-01-01-01", "stats:hourly:2023-01-01-02"]
        mock_redis.get.side_effect = [
            json.dumps({"timestamp": "2023-01-01T01:00:00", "hit_rate_numeric": 80.0}),
            json.dumps({"timestamp": "2023-01-01T02:00:00", "hit_rate_numeric": 85.0}),
        ]
        
        # Call function
        stats = get_historical_stats(period="hourly", days=1)
        
        # Verify result
        self.assertEqual(len(stats), 2)
        self.assertEqual(stats[0]["hit_rate_numeric"], 80.0)
        self.assertEqual(stats[1]["hit_rate_numeric"], 85.0)

    def test_check_alerts(self):
        """Test checking for alert conditions."""
        # Test data with alert conditions
        stats = {
            "memory_usage_percent": "85.0%",
            "hit_rate_numeric": 40.0,
            "evicted_keys": 2000,
        }
        
        # Mock trigger_alert to avoid side effects
        with patch("core.redis_monitoring.trigger_alert") as mock_trigger:
            # Call function
            alerts = check_alerts(stats)
            
            # Verify result
            self.assertEqual(len(alerts), 3)  # memory, hit rate, evictions
            self.assertEqual(alerts[0]["type"], "memory_usage")
            self.assertEqual(alerts[1]["type"], "hit_rate")
            self.assertEqual(alerts[2]["type"], "evictions")
            self.assertEqual(mock_trigger.call_count, 3)

    @patch("core.redis_monitoring.redis_client")
    def test_trigger_alert(self, mock_redis):
        """Test triggering an alert."""
        # Setup mock
        mock_redis.exists.return_value = False
        mock_redis.setex.return_value = True
        mock_redis.lpush.return_value = True
        mock_redis.expire.return_value = True
        
        # Test alert
        alert = {
            "type": "memory_usage",
            "severity": "warning",
            "message": "Memory usage is high",
            "threshold": 80,
            "value": 85,
            "timestamp": timezone.now().isoformat(),
        }
        
        # Call function
        with self.assertLogs(level="WARNING") as log:
            result = trigger_alert(alert)
        
        # Verify result
        self.assertTrue(result)
        mock_redis.exists.assert_called_once()
        mock_redis.setex.assert_called_once()
        mock_redis.lpush.assert_called_once()
        mock_redis.expire.assert_called_once()
        self.assertTrue(any("Memory usage is high" in msg for msg in log.output))

    @patch("core.redis_monitoring.redis_client")
    def test_analyze_key_size(self, mock_redis):
        """Test analyzing key size distribution."""
        # Setup mock
        mock_redis.keys.return_value = ["key1", "key2", "key3"]
        mock_redis.type.side_effect = [b"string", b"hash", b"list"]
        mock_redis.get.return_value = b"value1"
        mock_redis.hgetall.return_value = {b"field1": b"value1", b"field2": b"value2"}
        mock_redis.lrange.return_value = [b"item1", b"item2", b"item3"]
        
        # Call function
        result = analyze_key_size()
        
        # Verify result
        self.assertEqual(result["total_keys"], 3)
        self.assertEqual(result["sampled_keys"], 3)
        self.assertTrue("largest_keys" in result)
        self.assertTrue("total_size_bytes" in result)
        self.assertTrue("avg_size_bytes" in result)

    @patch("core.redis_monitoring.get_cache_stats")
    @patch("core.redis_monitoring.get_historical_stats")
    @patch("core.redis_monitoring.get_recent_alerts")
    @patch("core.redis_monitoring.analyze_key_size")
    @patch("core.redis_monitoring.get_slow_operations")
    def test_get_dashboard_data(
        self, mock_slow_ops, mock_analyze, mock_alerts, mock_hist_stats, mock_stats
    ):
        """Test getting dashboard data."""
        # Setup mocks
        mock_stats.return_value = {
            "timestamp": "2023-01-01T00:00:00",
            "hit_rate_numeric": 80.0,
            "used_memory_human": "1.0 MB",
            "total_keys": 100,
        }
        mock_hist_stats.return_value = [
            {
                "timestamp": "2023-01-01T00:00:00",
                "hit_rate_numeric": 80.0,
                "used_memory_human": "1.0 MB",
                "total_keys": 100,
            },
            {
                "timestamp": "2023-01-01T01:00:00",
                "hit_rate_numeric": 85.0,
                "used_memory_human": "1.1 MB",
                "total_keys": 110,
            },
        ]
        mock_alerts.return_value = [{"type": "memory_usage", "timestamp": "2023-01-01T00:00:00"}]
        mock_analyze.return_value = {"total_keys": 100}
        mock_slow_ops.return_value = [{"operation": "get", "duration_ms": 150.5}]
        
        # Call function
        result = get_dashboard_data()
        
        # Verify result
        self.assertEqual(result["current_stats"], mock_stats.return_value)
        self.assertEqual(len(result["historical_stats"]["hit_rate_over_time"]), 2)
        self.assertEqual(len(result["historical_stats"]["memory_usage_over_time"]), 2)
        self.assertEqual(len(result["historical_stats"]["keys_over_time"]), 2)
        self.assertEqual(result["recent_alerts"], mock_alerts.return_value)
        self.assertEqual(result["key_size_distribution"], mock_analyze.return_value)
        self.assertEqual(result["slow_operations"], mock_slow_ops.return_value)


if __name__ == "__main__":
    unittest.main()

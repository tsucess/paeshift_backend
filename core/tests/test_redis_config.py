"""
Tests for Redis cache configuration.
"""

import unittest
from unittest.mock import patch

from django.db import models
from django.test import TestCase, override_settings

from core.redis_settings import (
    CacheNamespace,
    CacheTTL,
    get_ttl_for_namespace,
    get_ttl_for_model,
)


# Test models
class TestUser(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = "accounts"


class TestProfile(models.Model):
    user = models.ForeignKey(TestUser, on_delete=models.CASCADE)

    class Meta:
        app_label = "accounts"


class RedisCacheConfigTests(TestCase):
    """Test Redis cache configuration."""

    def test_get_ttl_for_namespace(self):
        """Test getting TTL for a namespace."""
        # Test with string namespace
        ttl1 = get_ttl_for_namespace("user")
        self.assertEqual(ttl1, CacheTTL.STANDARD)

        # Test with enum namespace
        ttl2 = get_ttl_for_namespace(CacheNamespace.JOB)
        self.assertEqual(ttl2, CacheTTL.DAILY)

        # Test with unknown namespace
        ttl3 = get_ttl_for_namespace("unknown")
        self.assertEqual(ttl3, CacheTTL.DEFAULT)

    @patch("core.redis_settings.CACHE_TIMEOUTS", {
        "user": CacheTTL.STANDARD,
    })
    def test_get_ttl_for_model(self):
        """Test getting TTL for a model."""
        # Mock the settings
        model_ttl_map = {"accounts.TestUser": CacheTTL.STANDARD}
        with patch("django.conf.settings.CACHE_MODEL_TTL_MAP", model_ttl_map):
            # Test with model in map
            ttl1 = get_ttl_for_model(TestUser)
            self.assertEqual(ttl1, CacheTTL.STANDARD)

            # Test with model not in map
            ttl2 = get_ttl_for_model(TestProfile)
            # Should use the namespace-based TTL
            self.assertIsNotNone(ttl2)


if __name__ == "__main__":
    unittest.main()

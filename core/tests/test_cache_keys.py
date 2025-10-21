"""
Tests for Redis cache key management.
"""

import unittest
from unittest.mock import patch, MagicMock

from django.db import models
from django.http import HttpRequest
from django.test import TestCase

from core.redis_keys import (
    CacheNamespace,
    CacheTTL,
    generate_key,
    model_cache_key,
    api_cache_key,
    function_cache_key,
    get_ttl_for_key,
)


# Test models
class TestModel(models.Model):
    name = models.CharField(max_length=100)
    
    class Meta:
        app_label = "test_app"


class CacheKeyTests(TestCase):
    """Test cache key generation and TTL management."""

    def test_generate_key(self):
        """Test basic key generation."""
        # Test with string namespace
        key1 = generate_key("test", "123")
        self.assertTrue(key1.startswith("test:123:v"))
        
        # Test with enum namespace
        key2 = generate_key(CacheNamespace.USER, "456")
        self.assertTrue(key2.startswith("user:456:v"))
        
        # Test with additional parts
        key3 = generate_key(CacheNamespace.JOB, "789", "part1", "part2")
        self.assertTrue(key3.startswith("job:789:part1:part2:v"))
        
        # Test with custom version
        key4 = generate_key(CacheNamespace.API, "abc", version="2.0")
        self.assertTrue(key4.endswith(":v2.0"))
        
        # Test with dict part (should be hashed)
        key5 = generate_key(CacheNamespace.QUERY, "query", {"param1": "value1"})
        self.assertTrue(key5.startswith("query:query:"))
        self.assertTrue(len(key5.split(":")) == 4)  # namespace, id, hash, version

    def test_model_cache_key(self):
        """Test model cache key generation."""
        # Test with model instance
        model = TestModel(id=123, name="Test")
        key1 = model_cache_key(model)
        self.assertTrue(key1.startswith("model:testmodel:123:v"))
        
        # Test with model class and ID
        key2 = model_cache_key(TestModel, 456)
        self.assertTrue(key2.startswith("model:testmodel:456:v"))
        
        # Test with additional parts
        key3 = model_cache_key(model, parts=["detail", "full"])
        self.assertTrue("detail" in key3)
        self.assertTrue("full" in key3)
        
        # Test with missing ID
        with self.assertRaises(ValueError):
            model_cache_key(TestModel)

    def test_api_cache_key(self):
        """Test API cache key generation."""
        # Mock request and view function
        request = MagicMock(spec=HttpRequest)
        request.user.is_authenticated = True
        request.user.id = 789
        request.GET = {"param1": "value1"}
        request.COOKIES = {"cookie1": "value1"}
        request.headers = {"header1": "value1"}
        
        def test_view(request):
            return None
        
        # Test basic API key
        key1 = api_cache_key(test_view, request)
        self.assertTrue(key1.startswith("api:"))
        self.assertTrue("test_view" in key1)
        
        # Test with varying on specific query params
        key2 = api_cache_key(test_view, request, vary_on_query_params=["param1"])
        self.assertTrue("q:" in key2)
        
        # Test with varying on headers
        key3 = api_cache_key(test_view, request, vary_on_headers=["header1"])
        self.assertTrue("h:" in key3)
        
        # Test with varying on cookies
        key4 = api_cache_key(test_view, request, vary_on_cookies=["cookie1"])
        self.assertTrue("c:" in key4)
        
        # Test with authenticated user
        self.assertTrue("u:789" in key1)
        
        # Test with unauthenticated user
        request.user.is_authenticated = False
        key5 = api_cache_key(test_view, request)
        self.assertFalse("u:" in key5)

    def test_function_cache_key(self):
        """Test function cache key generation."""
        # Test function
        def test_func(arg1, arg2, kwarg1=None):
            return None
        
        # Test basic function key
        key1 = function_cache_key(test_func, "value1", "value2")
        self.assertTrue("test_func" in key1)
        
        # Test with kwargs
        key2 = function_cache_key(test_func, "value1", "value2", kwarg1="value3")
        self.assertNotEqual(key1, key2)
        
        # Test with custom namespace
        key3 = function_cache_key(test_func, "value1", "value2", namespace=CacheNamespace.JOB)
        self.assertTrue(key3.startswith("job:"))
        
        # Test with method
        class TestClass:
            def test_method(self, arg1):
                return None
        
        instance = TestClass()
        key4 = function_cache_key(instance.test_method, "value1")
        self.assertTrue("test_method" in key4)

    def test_get_ttl_for_key(self):
        """Test TTL determination from cache key."""
        # Test with model namespace
        key1 = "model:testmodel:123:v1.0"
        ttl1 = get_ttl_for_key(key1)
        self.assertEqual(ttl1, CacheTTL.DAILY)
        
        # Test with API namespace
        key2 = "api:test_view:v1.0"
        ttl2 = get_ttl_for_key(key2)
        self.assertEqual(ttl2, CacheTTL.STANDARD)
        
        # Test with unknown namespace
        key3 = "unknown:123:v1.0"
        ttl3 = get_ttl_for_key(key3)
        self.assertEqual(ttl3, CacheTTL.DEFAULT)
        
        # Test with hashed key
        key4 = "modelh:abcdef:v1.0"
        ttl4 = get_ttl_for_key(key4)
        self.assertEqual(ttl4, CacheTTL.DAILY)


if __name__ == "__main__":
    unittest.main()

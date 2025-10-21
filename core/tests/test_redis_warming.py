"""
Tests for Redis cache warming.
"""

import threading
import unittest
from unittest.mock import patch, MagicMock, call

from django.db import models
from django.test import TestCase, override_settings

from core.redis_warming import (
    warm_model_cache,
    warm_frequently_accessed_models,
    warm_api_endpoints,
    warm_cache,
    schedule_cache_warming,
    warm_cache_on_startup,
)


# Test models
class TestModel(models.Model):
    name = models.CharField(max_length=100)
    
    class Meta:
        app_label = "test_app"
    
    def cache(self):
        """Mock cache method."""
        return True


class RedisCacheWarmingTests(TestCase):
    """Test Redis cache warming functionality."""

    @patch("core.redis_warming.RedisCachedModelMixin", MagicMock())
    @patch("core.redis_warming.issubclass")
    def test_warm_model_cache(self, mock_issubclass):
        """Test warming a model's cache."""
        # Setup mock
        mock_issubclass.return_value = True
        
        # Create mock model and queryset
        model = TestModel()
        model.pk = 1
        model.cache = MagicMock()
        
        queryset = MagicMock()
        queryset.count.return_value = 1
        queryset.__getitem__.return_value = [model]
        
        # Mock model class
        model_class = MagicMock()
        model_class.__name__ = "TestModel"
        model_class.objects.all.return_value = queryset
        
        # Call function
        total, cached = warm_model_cache(model_class, batch_size=10)
        
        # Verify result
        self.assertEqual(total, 1)
        self.assertEqual(cached, 1)
        model.cache.assert_called_once()

    @patch("core.redis_warming.warm_model_cache")
    @patch("django.apps.apps.get_model")
    @patch("django.contrib.auth.get_user_model")
    def test_warm_frequently_accessed_models(self, mock_get_user, mock_get_model, mock_warm):
        """Test warming frequently accessed models."""
        # Setup mocks
        mock_get_user.return_value = MagicMock()
        mock_get_model.return_value = MagicMock()
        mock_warm.return_value = (10, 10)
        
        # Call function
        results = warm_frequently_accessed_models()
        
        # Verify result
        self.assertTrue(len(results) > 0)
        mock_warm.assert_called()

    @patch("django.test.Client")
    def test_warm_api_endpoints(self, mock_client):
        """Test warming API endpoints."""
        # Setup mock
        client_instance = MagicMock()
        client_instance.get.return_value.status_code = 200
        mock_client.return_value = client_instance
        
        # Call function
        results = warm_api_endpoints()
        
        # Verify result
        self.assertTrue(len(results) > 0)
        client_instance.get.assert_called()

    @patch("core.redis_warming.warm_frequently_accessed_models")
    @patch("core.redis_warming.warm_api_endpoints")
    def test_warm_cache(self, mock_endpoints, mock_models):
        """Test warming the entire cache."""
        # Setup mocks
        mock_models.return_value = {"TestModel": (10, 10)}
        mock_endpoints.return_value = {"test_endpoint": True}
        
        # Call function
        result = warm_cache()
        
        # Verify result
        self.assertIn("models", result)
        self.assertIn("endpoints", result)
        self.assertIn("elapsed_seconds", result)
        self.assertIn("timestamp", result)
        mock_models.assert_called_once()
        mock_endpoints.assert_called_once()

    @patch("core.redis_warming.CACHE_ENABLED", True)
    @patch("core.redis_warming.importlib.import_module")
    def test_schedule_cache_warming_celery(self, mock_import):
        """Test scheduling cache warming with Celery."""
        # Setup mock to simulate Celery available
        mock_celery = MagicMock()
        mock_celery.current_app.conf.beat_schedule = {}
        mock_import.return_value = mock_celery
        
        # Mock ImportError for django_q to test Celery path
        def side_effect(name):
            if name == "celery":
                return mock_celery
            raise ImportError("Module not found")
        
        mock_import.side_effect = side_effect
        
        # Call function
        with patch("core.redis_warming.importlib.import_module", mock_import):
            schedule_cache_warming()
        
        # Verify Celery was used
        self.assertEqual(len(mock_celery.current_app.conf.beat_schedule), 1)

    @patch("core.redis_warming.CACHE_ENABLED", True)
    @patch("core.redis_warming.threading.Thread")
    def test_warm_cache_on_startup(self, mock_thread):
        """Test warming cache on startup."""
        # Setup mock
        thread_instance = MagicMock()
        mock_thread.return_value = thread_instance
        
        # Call function
        warm_cache_on_startup()
        
        # Verify thread was started
        mock_thread.assert_called_once()
        thread_instance.start.assert_called_once()

    @override_settings(CACHE_WARM_ON_STARTUP=False)
    @patch("core.redis_warming.CACHE_ENABLED", True)
    @patch("core.redis_warming.threading.Thread")
    def test_warm_cache_on_startup_disabled(self, mock_thread):
        """Test warming cache on startup when disabled."""
        # Call function
        warm_cache_on_startup()
        
        # Verify thread was not started
        mock_thread.assert_not_called()


if __name__ == "__main__":
    unittest.main()

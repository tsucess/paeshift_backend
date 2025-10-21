"""
Tests for Redis cache invalidation.
"""

import unittest
from unittest.mock import patch, MagicMock, call

from django.db import models, transaction
from django.test import TestCase

from core.redis_invalidation import (
    invalidate_model_cache,
    invalidate_model_class_cache,
    register_model_dependency,
    register_invalidation_handler,
    transaction_invalidator,
)


# Test models
class TestParentModel(models.Model):
    name = models.CharField(max_length=100)
    
    class Meta:
        app_label = "test_app"


class TestChildModel(models.Model):
    parent = models.ForeignKey(TestParentModel, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    
    class Meta:
        app_label = "test_app"


class CacheInvalidationTests(TestCase):
    """Test cache invalidation functionality."""

    @patch("core.redis_invalidation.delete_cached_data")
    def test_invalidate_model_cache(self, mock_delete):
        """Test invalidating a model instance cache."""
        # Setup
        mock_delete.return_value = True
        parent = TestParentModel(id=1, name="Parent")
        
        # Call function
        result = invalidate_model_cache(parent, cascade=False)
        
        # Verify result
        self.assertTrue(result)
        mock_delete.assert_called_once()

    @patch("core.redis_invalidation.invalidate_cache_pattern")
    def test_invalidate_model_class_cache(self, mock_invalidate_pattern):
        """Test invalidating all cache entries for a model class."""
        # Setup
        mock_invalidate_pattern.return_value = 5
        
        # Call function
        result = invalidate_model_class_cache(TestParentModel)
        
        # Verify result
        self.assertEqual(result, 5)
        mock_invalidate_pattern.assert_called_once()

    @patch("core.redis_invalidation.invalidate_model_cache")
    def test_model_dependency_invalidation(self, mock_invalidate):
        """Test cascading invalidation through model dependencies."""
        # Setup
        mock_invalidate.return_value = True
        parent = TestParentModel(id=1, name="Parent")
        child = TestChildModel(id=1, parent=parent, name="Child")
        
        # Register dependency
        register_model_dependency(TestParentModel, TestChildModel)
        
        # Mock _get_related_instances to return our child
        with patch("core.redis_invalidation._get_related_instances") as mock_get_related:
            mock_get_related.return_value = [child]
            
            # Call function with cascade=True
            invalidate_model_cache(parent, cascade=True)
            
            # Verify child was invalidated
            mock_invalidate.assert_called_with(child, cascade=False, reason="cascade from TestParentModel")

    @patch("core.redis_invalidation.invalidate_model_cache")
    def test_custom_invalidation_handler(self, mock_invalidate):
        """Test custom invalidation handler."""
        # Setup
        mock_invalidate.return_value = True
        parent = TestParentModel(id=1, name="Parent")
        
        # Create a custom handler
        handler_called = False
        def custom_handler(instance):
            nonlocal handler_called
            handler_called = True
        
        # Register handler
        register_invalidation_handler(TestParentModel, custom_handler)
        
        # Call function
        invalidate_model_cache(parent, cascade=False)
        
        # Verify handler was called
        self.assertTrue(handler_called)

    @patch("core.redis_invalidation.invalidate_model_cache")
    def test_transaction_aware_invalidation(self, mock_invalidate):
        """Test transaction-aware invalidation."""
        # Setup
        mock_invalidate.return_value = True
        parent = TestParentModel(id=1, name="Parent")
        
        # Start transaction
        transaction_invalidator.start()
        
        # Add to transaction
        transaction_invalidator.add(parent, reason="test")
        
        # Verify not invalidated yet
        mock_invalidate.assert_not_called()
        
        # Commit transaction
        transaction_invalidator.commit()
        
        # Verify invalidated after commit
        mock_invalidate.assert_called_once()


if __name__ == "__main__":
    unittest.main()

"""
Standardized Redis Caching Test Script.

This script tests the standardized Redis caching functionality:
1. Function Caching with cache_function
2. API Response Caching with cache_api_response
3. Model Caching with RedisCachedModel
"""

import os
import sys
import time
import random
import json
from datetime import datetime
from typing import Dict, List, Any, Optional

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "payshift.settings")
import django
django.setup()

# Import Django components
from django.db import models
from django.http import HttpRequest, JsonResponse
from django.utils import timezone

# Import Redis caching utilities
from core.redis import (
    # Core
    CACHE_ENABLED,
    redis_client,
    
    # Decorators
    cache_function,
    cache_api_response,
    cache_method_result,
    
    # Model caching
    RedisCachedModel,
    cache_model,
    get_cached_model,
    invalidate_model_cache,
    
    # Monitoring
    get_cache_stats,
    
    # Warming
    warm_model_cache,
)

from core.redis.utils import (
    get_cached_data,
    set_cached_data,
    delete_cached_data,
    invalidate_cache_pattern,
)

# Test constants
TEST_COUNT = 100
CACHE_TIMEOUT = 3600  # 1 hour

# Define a test model that uses RedisCachedModel
class TestProduct(models.Model, RedisCachedModel):
    """Test product model with Redis caching."""
    
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Redis caching configuration
    redis_cache_enabled = True
    redis_cache_prefix = "test_product"
    redis_cache_timeout = 3600  # 1 hour
    redis_cache_related = []
    redis_cache_exclude = ["internal_notes"]
    
    class Meta:
        app_label = "test_app"
        
    def __str__(self):
        return self.name


# 1. Test Function Caching with cache_function
@cache_function(namespace='test_data', ttl=CACHE_TIMEOUT)
def get_test_data(data_id: int) -> Dict:
    """
    Get test data with caching.
    
    This function will cache the result for the specified TTL.
    The cache key will include the data_id parameter.
    
    Args:
        data_id: Data ID
        
    Returns:
        Test data dictionary
    """
    print(f"Cache miss for data_id={data_id}, generating test data")
    
    # Simulate expensive operation
    time.sleep(0.1)
    
    # Generate test data
    return {
        "id": data_id,
        "name": f"Test Data {data_id}",
        "value": random.randint(1, 1000),
        "created_at": datetime.now().isoformat(),
    }


# 2. Test API Response Caching with cache_api_response
@cache_api_response(timeout=CACHE_TIMEOUT, vary_on_query_params=['user_id'])
def get_user_profile_api(request: HttpRequest) -> JsonResponse:
    """
    Get user profile API with caching.
    
    This function will cache the result for the specified timeout.
    The cache key will include the user_id query parameter.
    
    Args:
        request: HTTP request
        
    Returns:
        JSON response with user profile data
    """
    user_id = request.GET.get('user_id', '1')
    print(f"Cache miss for user_id={user_id}, fetching profile")
    
    # Simulate expensive operation
    time.sleep(0.1)
    
    # Generate user profile data
    profile_data = {
        "id": int(user_id),
        "username": f"user_{user_id}",
        "email": f"user_{user_id}@example.com",
        "bio": f"Bio for user {user_id}",
        "skills": ["Python", "Django", "Redis"],
        "created_at": datetime.now().isoformat(),
    }
    
    return JsonResponse({"user_id": user_id, "profile": profile_data})


# 3. Test Method Caching with cache_method_result
class UserService:
    """Service for user-related operations."""
    
    @cache_method_result(timeout=CACHE_TIMEOUT, prefix="user_service")
    def get_user_data(self, user_id: int) -> Dict:
        """
        Get user data with caching.
        
        This method will cache the result for the specified timeout.
        The cache key will include the user_id parameter and the instance ID.
        
        Args:
            user_id: User ID
            
        Returns:
            User data dictionary
        """
        print(f"Cache miss for user_id={user_id}, fetching user data")
        
        # Simulate expensive operation
        time.sleep(0.1)
        
        # Generate user data
        return {
            "id": user_id,
            "username": f"user_{user_id}",
            "email": f"user_{user_id}@example.com",
            "is_active": True,
            "created_at": datetime.now().isoformat(),
        }


def test_function_caching():
    """Test function caching with cache_function."""
    print("\n=== Testing Function Caching with cache_function ===")
    
    # Test with multiple calls to the same function
    for i in range(1, 6):
        print(f"\nCall {i} to get_test_data(1):")
        start_time = time.time()
        data = get_test_data(1)
        duration = time.time() - start_time
        print(f"Duration: {duration:.4f} seconds")
        print(f"Data: {data}")
    
    # Test with different parameters
    print("\nTesting with different parameters:")
    for data_id in range(1, 4):
        print(f"\nCall to get_test_data({data_id}):")
        start_time = time.time()
        data = get_test_data(data_id)
        duration = time.time() - start_time
        print(f"Duration: {duration:.4f} seconds")
        print(f"Data: {data}")


def test_api_response_caching():
    """Test API response caching with cache_api_response."""
    print("\n=== Testing API Response Caching with cache_api_response ===")
    
    # Create a mock request
    class MockRequest:
        def __init__(self, user_id):
            self.GET = {'user_id': str(user_id)}
            self.method = 'GET'
    
    # Test with multiple calls to the same endpoint
    for i in range(1, 6):
        request = MockRequest(1)
        print(f"\nCall {i} to get_user_profile_api(user_id=1):")
        start_time = time.time()
        response = get_user_profile_api(request)
        duration = time.time() - start_time
        print(f"Duration: {duration:.4f} seconds")
        print(f"Response: {response.content.decode('utf-8')[:100]}...")
    
    # Test with different parameters
    print("\nTesting with different parameters:")
    for user_id in range(1, 4):
        request = MockRequest(user_id)
        print(f"\nCall to get_user_profile_api(user_id={user_id}):")
        start_time = time.time()
        response = get_user_profile_api(request)
        duration = time.time() - start_time
        print(f"Duration: {duration:.4f} seconds")
        print(f"Response: {response.content.decode('utf-8')[:100]}...")


def test_method_caching():
    """Test method caching with cache_method_result."""
    print("\n=== Testing Method Caching with cache_method_result ===")
    
    # Create a service instance
    user_service = UserService()
    
    # Test with multiple calls to the same method
    for i in range(1, 6):
        print(f"\nCall {i} to user_service.get_user_data(1):")
        start_time = time.time()
        data = user_service.get_user_data(1)
        duration = time.time() - start_time
        print(f"Duration: {duration:.4f} seconds")
        print(f"Data: {data}")
    
    # Test with different parameters
    print("\nTesting with different parameters:")
    for user_id in range(1, 4):
        print(f"\nCall to user_service.get_user_data({user_id}):")
        start_time = time.time()
        data = user_service.get_user_data(user_id)
        duration = time.time() - start_time
        print(f"Duration: {duration:.4f} seconds")
        print(f"Data: {data}")


def test_model_caching():
    """Test model caching with RedisCachedModel."""
    print("\n=== Testing Model Caching with RedisCachedModel ===")
    
    # Test standalone model caching functions
    print("\nTesting standalone model caching functions:")
    
    # Create test data
    test_data = {
        "id": 1,
        "name": "Test Product",
        "price": "99.99",
        "description": "A test product",
        "created_at": timezone.now().isoformat(),
        "updated_at": timezone.now().isoformat(),
    }
    
    # Cache the model
    print("Caching model...")
    success = cache_model(TestProduct, 1, test_data)
    print(f"Cache success: {success}")
    
    # Get the model from cache
    print("Getting model from cache...")
    start_time = time.time()
    cached_model = get_cached_model(TestProduct, 1)
    duration = time.time() - start_time
    print(f"Duration: {duration:.4f} seconds")
    print(f"Cached model: {cached_model}")
    
    # Invalidate the model cache
    print("Invalidating model cache...")
    success = invalidate_model_cache(TestProduct, 1)
    print(f"Invalidation success: {success}")
    
    # Verify invalidation
    print("Verifying invalidation...")
    cached_model = get_cached_model(TestProduct, 1)
    print(f"Cached model after invalidation: {cached_model}")


def print_cache_stats():
    """Print cache statistics."""
    print("\n=== Cache Statistics ===")
    
    stats = get_cache_stats()
    print(f"Total keys: {stats.get('total_keys', 0)}")
    print(f"Memory used: {stats.get('memory_used_mb', 0):.2f} MB")
    print(f"Hit rate: {stats.get('hit_rate', 0):.2f}%")
    print(f"Hits: {stats.get('hits', 0)}")
    print(f"Misses: {stats.get('misses', 0)}")


def main():
    """Main function."""
    print("=== Standardized Redis Cache Testing ===")
    
    if not CACHE_ENABLED or not redis_client:
        print("Redis cache is not enabled or Redis client is not available.")
        print("Please check your Redis configuration and try again.")
        return
    
    # Print initial cache stats
    print("\n=== Initial Cache Statistics ===")
    print_cache_stats()
    
    # Run tests
    test_function_caching()
    test_api_response_caching()
    test_method_caching()
    test_model_caching()
    
    # Print final cache stats
    print("\n=== Final Cache Statistics ===")
    print_cache_stats()
    
    print("\n=== Testing Complete ===")
    print("All standardized Redis caching approaches have been tested.")
    print("See STANDARDIZED_REDIS_CACHING.md for documentation on the standardized approach.")


if __name__ == "__main__":
    main()

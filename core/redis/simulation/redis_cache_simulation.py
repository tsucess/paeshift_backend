"""
Redis Cache Simulation Script.

This script simulates real-world usage of the standardized Redis caching approaches:
1. Function Caching with cache_function
2. API Response Caching with cache_api_response
3. Model Caching with RedisCachedModel

It measures performance improvements, tracks cache hit/miss rates,
tests cache invalidation, and tests cache warming.
"""

import os
import sys
import time
import random
import json
import threading
import statistics
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

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
    warm_cache,
)

from core.redis.utils import (
    get_cached_data,
    set_cached_data,
    delete_cached_data,
    invalidate_cache_pattern,
)

# Simulation constants
SIMULATION_THREADS = 10
SIMULATION_ITERATIONS = 100
CACHE_TIMEOUT = 3600  # 1 hour

# Results storage
results = {
    "function_caching": {
        "cached": [],
        "uncached": [],
        "hit_rate": 0,
    },
    "api_caching": {
        "cached": [],
        "uncached": [],
        "hit_rate": 0,
    },
    "model_caching": {
        "cached": [],
        "uncached": [],
        "hit_rate": 0,
    },
}


# Define a test model that uses RedisCachedModel
class SimulatedProduct(models.Model, RedisCachedModel):
    """Simulated product model with Redis caching."""

    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Redis caching configuration
    redis_cache_enabled = True
    redis_cache_prefix = "simulated_product"
    redis_cache_timeout = CACHE_TIMEOUT
    redis_cache_related = []
    redis_cache_exclude = ["internal_notes"]

    class Meta:
        app_label = "test_app"

    def __str__(self):
        return self.name


# 1. Function to be cached
@cache_function(namespace='simulation_data', ttl=CACHE_TIMEOUT)
def get_simulation_data(data_id: int) -> Dict:
    """
    Get simulation data with caching.

    This function will cache the result for the specified TTL.
    The cache key will include the data_id parameter.

    Args:
        data_id: Data ID

    Returns:
        Simulation data dictionary
    """
    # Simulate expensive operation
    time.sleep(0.1)

    # Generate simulation data
    return {
        "id": data_id,
        "name": f"Simulation Data {data_id}",
        "value": random.randint(1, 1000),
        "created_at": datetime.now().isoformat(),
    }


# Uncached version for comparison
def get_simulation_data_uncached(data_id: int) -> Dict:
    """Uncached version of get_simulation_data for comparison."""
    # Simulate expensive operation
    time.sleep(0.1)

    # Generate simulation data
    return {
        "id": data_id,
        "name": f"Simulation Data {data_id}",
        "value": random.randint(1, 1000),
        "created_at": datetime.now().isoformat(),
    }


# 2. API Response to be cached
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


# Uncached version for comparison
def get_user_profile_api_uncached(request: HttpRequest) -> JsonResponse:
    """Uncached version of get_user_profile_api for comparison."""
    user_id = request.GET.get('user_id', '1')

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


# Simulation functions
def simulate_function_caching():
    """Simulate function caching with cache_function."""
    print("\n=== Simulating Function Caching with cache_function ===")

    # Clear previous results
    results["function_caching"]["cached"] = []
    results["function_caching"]["uncached"] = []

    # Warm up the cache
    for data_id in range(1, 6):
        get_simulation_data(data_id)

    # Simulate multiple threads accessing the same data
    def worker(thread_id: int):
        # Test cached function
        for i in range(SIMULATION_ITERATIONS):
            data_id = random.randint(1, 5)

            # Measure cached function
            start_time = time.time()
            data = get_simulation_data(data_id)
            duration = time.time() - start_time
            results["function_caching"]["cached"].append(duration)

            # Measure uncached function
            start_time = time.time()
            data = get_simulation_data_uncached(data_id)
            duration = time.time() - start_time
            results["function_caching"]["uncached"].append(duration)

    # Run workers in parallel
    with ThreadPoolExecutor(max_workers=SIMULATION_THREADS) as executor:
        executor.map(worker, range(SIMULATION_THREADS))

    # Calculate statistics
    cached_avg = statistics.mean(results["function_caching"]["cached"])
    uncached_avg = statistics.mean(results["function_caching"]["uncached"])
    improvement = (uncached_avg - cached_avg) / uncached_avg * 100

    print(f"Average time (cached): {cached_avg:.4f} seconds")
    print(f"Average time (uncached): {uncached_avg:.4f} seconds")
    print(f"Performance improvement: {improvement:.2f}%")

    # Get cache stats
    stats = get_cache_stats()
    hits = stats.get('hits', 0)
    misses = stats.get('misses', 0)
    total = hits + misses
    hit_rate = (hits / total * 100) if total > 0 else 0
    results["function_caching"]["hit_rate"] = hit_rate

    print(f"Cache hit rate: {hit_rate:.2f}%")


def simulate_api_caching():
    """Simulate API response caching with cache_api_response."""
    print("\n=== Simulating API Response Caching with cache_api_response ===")

    # Clear previous results
    results["api_caching"]["cached"] = []
    results["api_caching"]["uncached"] = []

    # Create a mock request
    class MockRequest:
        def __init__(self, user_id):
            self.GET = {'user_id': str(user_id)}
            self.method = 'GET'
            self.path = '/api/user/profile'

    # Warm up the cache
    for user_id in range(1, 6):
        request = MockRequest(user_id)
        get_user_profile_api(request)

    # Simulate multiple threads accessing the API
    def worker(thread_id: int):
        for i in range(SIMULATION_ITERATIONS):
            user_id = random.randint(1, 5)
            request = MockRequest(user_id)

            # Measure cached API
            start_time = time.time()
            response = get_user_profile_api(request)
            duration = time.time() - start_time
            results["api_caching"]["cached"].append(duration)

            # Measure uncached API
            start_time = time.time()
            response = get_user_profile_api_uncached(request)
            duration = time.time() - start_time
            results["api_caching"]["uncached"].append(duration)

    # Run workers in parallel
    with ThreadPoolExecutor(max_workers=SIMULATION_THREADS) as executor:
        executor.map(worker, range(SIMULATION_THREADS))

    # Calculate statistics
    cached_avg = statistics.mean(results["api_caching"]["cached"])
    uncached_avg = statistics.mean(results["api_caching"]["uncached"])
    improvement = (uncached_avg - cached_avg) / uncached_avg * 100

    print(f"Average time (cached): {cached_avg:.4f} seconds")
    print(f"Average time (uncached): {uncached_avg:.4f} seconds")
    print(f"Performance improvement: {improvement:.2f}%")

    # Get cache stats
    stats = get_cache_stats()
    hits = stats.get('hits', 0)
    misses = stats.get('misses', 0)
    total = hits + misses
    hit_rate = (hits / total * 100) if total > 0 else 0
    results["api_caching"]["hit_rate"] = hit_rate

    print(f"Cache hit rate: {hit_rate:.2f}%")


def simulate_model_caching():
    """Simulate model caching with RedisCachedModel."""
    print("\n=== Simulating Model Caching with RedisCachedModel ===")

    # Clear previous results
    results["model_caching"]["cached"] = []
    results["model_caching"]["uncached"] = []

    # Create test data for multiple products
    product_data = []
    for i in range(1, 6):
        product_data.append({
            "id": i,
            "name": f"Product {i}",
            "price": f"{random.randint(10, 1000)}.99",
            "description": f"Description for product {i}",
            "created_at": timezone.now().isoformat(),
            "updated_at": timezone.now().isoformat(),
        })

    # Cache the products
    for data in product_data:
        cache_model(SimulatedProduct, data["id"], data)

    # Simulate multiple threads accessing the models
    def worker(thread_id: int):
        for i in range(SIMULATION_ITERATIONS):
            product_id = random.randint(1, 5)

            # Measure cached model access
            start_time = time.time()
            product = get_cached_model(SimulatedProduct, product_id)
            duration = time.time() - start_time
            results["model_caching"]["cached"].append(duration)

            # Measure uncached model access (simulated DB query)
            start_time = time.time()
            # Simulate database query
            time.sleep(0.1)
            product = product_data[product_id - 1]
            duration = time.time() - start_time
            results["model_caching"]["uncached"].append(duration)

    # Run workers in parallel
    with ThreadPoolExecutor(max_workers=SIMULATION_THREADS) as executor:
        executor.map(worker, range(SIMULATION_THREADS))

    # Calculate statistics
    cached_avg = statistics.mean(results["model_caching"]["cached"])
    uncached_avg = statistics.mean(results["model_caching"]["uncached"])
    improvement = (uncached_avg - cached_avg) / uncached_avg * 100

    print(f"Average time (cached): {cached_avg:.4f} seconds")
    print(f"Average time (uncached): {uncached_avg:.4f} seconds")
    print(f"Performance improvement: {improvement:.2f}%")

    # Test cache invalidation
    print("\nTesting cache invalidation...")

    # Invalidate one product's cache
    start_time = time.time()
    invalidate_model_cache(SimulatedProduct, 1)
    duration = time.time() - start_time
    print(f"Cache invalidation time: {duration:.4f} seconds")

    # Verify invalidation
    cached_product = get_cached_model(SimulatedProduct, 1)
    print(f"Product 1 in cache after invalidation: {'Yes' if cached_product else 'No'}")

    # Re-cache the product
    cache_model(SimulatedProduct, 1, product_data[0])

    # Get cache stats
    stats = get_cache_stats()
    hits = stats.get('hits', 0)
    misses = stats.get('misses', 0)
    total = hits + misses
    hit_rate = (hits / total * 100) if total > 0 else 0
    results["model_caching"]["hit_rate"] = hit_rate

    print(f"Cache hit rate: {hit_rate:.2f}%")

    # Test cache warming
    print("\nTesting cache warming...")

    # Clear all product caches
    for i in range(1, 6):
        invalidate_model_cache(SimulatedProduct, i)

    # Measure time to warm the cache
    start_time = time.time()
    for i in range(1, 6):
        cache_model(SimulatedProduct, i, product_data[i-1])
    warm_time = time.time() - start_time

    print(f"Cache warming time for 5 products: {warm_time:.4f} seconds")


def main():
    """Main simulation function."""
    print("=== Redis Cache Simulation ===")

    if not CACHE_ENABLED or not redis_client:
        print("Redis cache is not enabled or Redis client is not available.")
        print("Please check your Redis configuration and try again.")
        return

    # Print initial cache stats
    print("\n=== Initial Cache Statistics ===")
    print_cache_stats()

    # Run simulations
    simulate_function_caching()
    simulate_api_caching()
    simulate_model_caching()

    # Print final cache stats
    print("\n=== Final Cache Statistics ===")
    print_cache_stats()

    # Print summary
    print("\n=== Simulation Summary ===")
    print_simulation_summary()

    print("\n=== Simulation Complete ===")
    print("All standardized Redis caching approaches have been simulated.")
    print("See STANDARDIZED_REDIS_CACHING.md for documentation on the standardized approach.")


def print_cache_stats():
    """Print cache statistics."""
    stats = get_cache_stats()
    print(f"Total keys: {stats.get('total_keys', 0)}")
    print(f"Memory used: {stats.get('memory_used_mb', 0):.2f} MB")
    print(f"Hit rate: {stats.get('hit_rate', 0):.2f}%")
    print(f"Hits: {stats.get('hits', 0)}")
    print(f"Misses: {stats.get('misses', 0)}")


def print_simulation_summary():
    """Print simulation summary."""
    for cache_type, data in results.items():
        if data["cached"] and data["uncached"]:
            cached_avg = statistics.mean(data["cached"])
            uncached_avg = statistics.mean(data["uncached"])
            improvement = (uncached_avg - cached_avg) / uncached_avg * 100

            print(f"\n{cache_type.replace('_', ' ').title()}:")
            print(f"  Average time (cached): {cached_avg:.4f} seconds")
            print(f"  Average time (uncached): {uncached_avg:.4f} seconds")
            print(f"  Performance improvement: {improvement:.2f}%")
            print(f"  Cache hit rate: {data['hit_rate']:.2f}%")


if __name__ == "__main__":
    main()

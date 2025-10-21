# Redis Caching Cheat Sheet

This cheat sheet provides quick reference for implementing Redis caching in your application.

## Quick Decision Guide

| If you need to cache... | Use this approach |
|-------------------------|-------------------|
| Function results | `@cache_function` |
| API responses | `@cache_api_response` |
| Model instances | `RedisCachedModel` mixin |
| Method results | `@cache_method_result` |

## 1. Function Caching

```python
from core.redis import cache_function

@cache_function(namespace='user_data', ttl=3600)
def get_user_data(user_id):
    # Expensive computation...
    return data
```

### Common Parameters

- `namespace`: Logical grouping (e.g., 'user_data', 'job', 'profile')
- `ttl`: Time-to-live in seconds
- `cache_none`: Whether to cache None results (default: False)
- `version`: Cache version for invalidation

### Invalidation

```python
# Invalidate specific function call
get_user_data.invalidate_cache(user_id=123)

# Invalidate all calls to the function
from core.redis.utils import invalidate_cache_pattern
invalidate_cache_pattern("user_data:*")
```

## 2. API Response Caching

```python
from core.redis import cache_api_response

@cache_api_response(timeout=900, vary_on_query_params=['user_id'])
def get_user_profile(request, user_id):
    # API logic...
    return JsonResponse(data)
```

### Common Parameters

- `timeout`: Cache timeout in seconds
- `vary_on_query_params`: List of query parameters to include in cache key
- `vary_on_headers`: List of HTTP headers to include in cache key
- `vary_on_cookies`: List of cookies to include in cache key
- `key_params`: List of URL parameters to include in cache key

### When to Use

- GET requests (POST, PUT, DELETE are not cached)
- Responses that depend on request parameters
- Frequently accessed endpoints

## 3. Model Caching

```python
from django.db import models
from core.redis import RedisCachedModel

class Product(models.Model, RedisCachedModel):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Redis caching configuration
    redis_cache_enabled = True
    redis_cache_prefix = "product"
    redis_cache_timeout = 86400  # 24 hours
    redis_cache_related = ["category"]
    redis_cache_exclude = ["internal_notes"]
```

### Configuration Options

- `redis_cache_enabled`: Enable/disable caching (default: True)
- `redis_cache_prefix`: Custom key prefix (default: model name)
- `redis_cache_timeout`: Custom timeout (default: model default or global default)
- `redis_cache_related`: Related fields to include (default: [])
- `redis_cache_exclude`: Fields to exclude (default: [])

### Standalone Functions

```python
from core.redis import cache_model, get_cached_model, invalidate_model_cache

# Cache a model instance
cache_model(product_instance)

# Get a cached model instance
product = get_cached_model(Product, product_id)

# Invalidate a model's cache
invalidate_model_cache(product_instance)
```

## 4. Method Caching

```python
from core.redis import cache_method_result

class UserService:
    @cache_method_result(timeout=3600, prefix="user_service")
    def get_user_data(self, user_id):
        # Expensive operation...
        return data
```

### Parameters

- `timeout`: Cache timeout in seconds
- `prefix`: Cache key prefix
- `include_args`: Whether to include method args in cache key (default: True)
- `include_self`: Whether to include instance ID in cache key (default: True)

## Cache Warming

```python
from core.redis import warm_cache, warm_model_cache, warm_critical_models

# Warm the entire cache
warm_cache()

# Warm critical models
warm_critical_models()

# Warm a specific model
warm_model_cache(Product)
```

## Cache Invalidation Strategies

### 1. Automatic Invalidation

- `RedisCachedModel` instances are automatically invalidated on save/delete
- Cache entries expire based on their TTL

### 2. Manual Invalidation

```python
# For RedisCachedModel instances
instance.invalidate_cache()

# For any model instance
from core.redis import invalidate_model_cache
invalidate_model_cache(instance)

# For function results
from core.redis.utils import delete_cached_data
delete_cached_data(cache_key)

# For patterns
from core.redis.utils import invalidate_cache_pattern
invalidate_cache_pattern("user:*")
```

### 3. Version-Based Invalidation

```python
# In settings.py
CACHE_VERSION = "1.1"  # Increment to invalidate all caches

# For a specific model
class Product(models.Model, RedisCachedModel):
    redis_cache_version = "2.0"  # Increment to invalidate this model's cache
```

## Best Practices

1. **Set appropriate timeouts** for your cached data:
   - Short timeouts (minutes) for frequently changing data
   - Longer timeouts (hours/days) for relatively static data

2. **Use cache versioning** to handle schema changes:
   - Increment `CACHE_VERSION` when data schema changes
   - Use version parameter in decorators for fine-grained control

3. **Don't cache sensitive data**:
   - Passwords, payment details, personal identification information
   - Use `redis_cache_exclude` to exclude sensitive fields

4. **Handle cache misses gracefully**:
   - Always have a fallback for when the cache is empty or unavailable
   - Use `CACHE_FALLBACK_TO_DB` setting to control fallback behavior

5. **Monitor cache performance**:
   - Check hit rate to ensure caching is effective
   - Watch memory usage to avoid Redis running out of memory

## Troubleshooting

### Common Issues

1. **Cache misses when expecting hits**
   - Check that `CACHE_ENABLED` is True
   - Verify cache key generation is consistent
   - Check TTL settings

2. **Stale data in cache**
   - Ensure invalidation is working correctly
   - Check that TTL is appropriate for data volatility
   - Implement timestamp validation for critical data

3. **High memory usage**
   - Reduce TTL for less critical data
   - Use selective caching (only cache what's needed)
   - Implement cache eviction policies

4. **Slow cache performance**
   - Check Redis server load
   - Optimize cache key generation
   - Use connection pooling

### Debugging Tools

```python
from core.redis import get_cache_stats, redis_client

# Get cache statistics
stats = get_cache_stats()
print(f"Hit rate: {stats.get('hit_rate', 0):.2f}%")

# Check if a key exists
key_exists = redis_client.exists("my_cache_key")

# Get TTL for a key
ttl = redis_client.ttl("my_cache_key")
```

## Testing Cache Functionality

Use the provided test scripts to verify caching functionality:

```bash
# Run the standardized Redis cache test
python core/tests/standardized_redis_cache_test.py

# Run the Redis cache simulation
python core/redis/simulation/redis_cache_simulation.py
```

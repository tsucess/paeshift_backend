# Redis Caching System Guide

This guide explains the Redis caching system used in the application, including the consolidated modules and when to use each caching approach.

## Overview

The Redis caching system provides a robust way to cache data and improve application performance. The system has been consolidated to eliminate redundancy and provide a clear, standardized approach to caching.

## Consolidated Modules

The following modules have been consolidated:

1. **redis_decorators.py**: Enhanced with additional functionality that would have been in a separate v2 file
2. **redis_model_mixins.py**: Combines functionality from `redis_model_mixin.py`, `redis_sync.py`, and `model_mixins.py`
3. **redis_warming.py**: Enhanced with additional cache warming functionality
4. **redis_timestamp_validation.py**: Enhanced with timestamp validation decorators

## When to Use Each Caching Approach

### 1. Model Caching

Use `RedisCachedModel` from `redis_model_mixins.py` when you need to cache Django model instances:

```python
from core.redis_model_mixins import RedisCachedModel

class MyModel(RedisCachedModel):
    # Define cache settings
    redis_cache_enabled = True
    redis_cache_timeout = 3600  # 1 hour
    redis_cache_prefix = 'my_model'
    redis_cache_version = '1'
    redis_cache_fields = ['id', 'name', 'description']  # Fields to cache
    redis_cache_exclude = ['password', 'secret_key']  # Fields to exclude

    # Model fields
    name = models.CharField(max_length=100)
    description = models.TextField()
    # ...
```

This approach provides:
- Automatic cache invalidation on save/delete
- Customizable cache key generation
- Configurable cache timeout
- Selective field caching
- Cache versioning

### 2. Function/Method Caching

Use decorators from `redis_decorators.py` when you need to cache function or method results:

```python
from core.redis_decorators import cache_function, cache_api_response

# Cache a regular function
@cache_function(namespace='user_data', ttl=3600)
def get_user_data(user_id):
    # Expensive operation
    return data

# Cache an API response
@cache_api_response(timeout=900, key_params=['user_id'])
def api_view(request, user_id):
    # API logic
    return response
```

### 3. Timestamp-Based Validation

Use decorators from `redis_timestamp_validation.py` when you need to invalidate cache based on timestamps:

```python
from core.redis_timestamp_validation import validate_with_timestamp, invalidate_on_timestamp_change

# Validate with timestamp
@validate_with_timestamp(cache_key_prefix='user_profile', timeout=3600)
def get_user_profile(user_id):
    # Expensive operation
    return profile

# Invalidate on timestamp change
@invalidate_on_timestamp_change(model_class=User, cache_key_prefix='user_data')
def get_user_data(user):
    # Expensive operation
    return data
```

### 4. Cache Warming

Use functions from `redis_warming.py` when you need to pre-populate the cache:

```python
from core.redis_warming import warm_model_cache, warm_critical_models

# Warm cache for a specific model
warm_model_cache(User, strategy='recent', limit=1000)

# Warm cache for critical models
warm_critical_models()
```

## Best Practices

1. **Choose the Right Approach**: Use model caching for Django models, function caching for expensive operations, and timestamp validation for data that changes frequently.

2. **Set Appropriate Timeouts**: Use shorter timeouts for frequently changing data and longer timeouts for static data.

3. **Be Selective**: Only cache data that is expensive to compute or frequently accessed.

4. **Monitor Cache Performance**: Use the monitoring tools to track cache hit rates and memory usage.

5. **Warm the Cache**: Use cache warming for critical data to prevent cache misses during high traffic periods.

## Troubleshooting

1. **Cache Not Being Invalidated**: Ensure that your model inherits from `RedisCachedModel` and that `redis_cache_enabled` is set to `True`.

2. **Stale Data**: Check if you're using the appropriate timestamp validation approach for your use case.

3. **Memory Issues**: Be selective about what you cache and set appropriate timeouts to prevent memory exhaustion.

4. **Performance Issues**: Use the monitoring tools to identify bottlenecks and optimize your caching strategy.

## Conclusion

The consolidated Redis caching system provides a powerful and flexible way to improve application performance. By choosing the right caching approach for each use case, you can significantly reduce database load and improve response times.

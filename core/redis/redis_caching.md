# Redis Caching Implementation

This document outlines the Redis caching system implemented across the Payshift platform.

## Overview

The Redis caching system provides a consistent and efficient way to cache data across all applications in the platform. It reduces database load, improves response times, and ensures data consistency.

## Key Features

1. **Consistent Caching Interface**: A unified API for caching across all applications
2. **Automatic Serialization**: Handles complex Django models and QuerySets
3. **Cache Versioning**: Ensures cache invalidation when data schemas change
4. **Multiple Caching Strategies**: Function results, API responses, and model instances
5. **Cache Monitoring**: Detailed statistics and monitoring endpoints
6. **Cache Eviction Policies**: Prevents memory issues in production

## Usage Examples

### 1. Caching Model Instances

```python
from core.cache import cache_model_instance, get_cached_model_instance, invalidate_model_instance

# Cache a user's data
user_data = get_user_response(user)
cache_model_instance("user", user.id, user_data)

# Retrieve cached user data
cached_user = get_cached_model_instance("user", user_id)
if cached_user:
    return cached_user
    
# Invalidate cache when user data changes
invalidate_model_instance("user", user.id)
```

### 2. Caching Function Results

```python
from core.cache import cache_function_result

@cache_function_result(timeout=60*60*24, key_prefix="industry:")  # Cache for 24 hours
def get_all_industries():
    return list(JobIndustry.objects.all())
```

### 3. Caching API Responses

```python
from core.cache import cache_api_response

@cache_api_response(timeout=60*15, key_prefix="alljobs:")  # Cache for 15 minutes
def get_all_jobs(request):
    jobs = Job.objects.select_related("client__profile").all()
    serialized = [serialize_job(job) for job in jobs]
    return {"jobs": serialized}
```

## Cache Timeouts

Different types of data have different cache timeouts:

| Data Type | Timeout | Description |
|-----------|---------|-------------|
| User | 24 hours | User profile data |
| Job | 2 hours | Job listings |
| Application | 30 minutes | Job applications |
| Profile | 12 hours | User profiles |
| Industry | 7 days | Job industries (rarely changes) |
| Subcategory | 7 days | Job subcategories (rarely changes) |
| Whoami | 15 minutes | Current user data |

## Cache Invalidation

Cache invalidation happens automatically when data is updated:

1. **Model Updates**: When a model is updated, its cache is invalidated
2. **User Actions**: Actions like logout invalidate relevant caches
3. **Admin Actions**: Admins can manually clear caches through the monitoring interface

## Monitoring

The caching system includes monitoring endpoints:

- `/core/monitoring/cache-stats/`: View detailed cache statistics
- `/core/monitoring/clear-cache/`: Clear specific or all caches
- `/core/monitoring/system-health/`: Check system health including Redis

## Implementation Details

### Core Components

1. **Cache Keys**: Generated with versioning to handle schema changes
2. **Serialization**: Custom JSON encoder for Django models and complex objects
3. **Cache Limits**: Memory and entry count limits with eviction policies
4. **Statistics**: Hit/miss rates, memory usage, and age distribution

### Cache Eviction Policies

Three eviction policies are available:

1. **LRU (Least Recently Used)**: Removes least recently accessed entries
2. **Random**: Removes random entries when limits are reached
3. **TTL (Time To Live)**: Removes entries with shortest remaining TTL

## Best Practices

1. **Cache Appropriate Data**: Cache data that is expensive to compute or retrieve
2. **Set Appropriate Timeouts**: Use shorter timeouts for frequently changing data
3. **Invalidate Proactively**: Invalidate cache when data changes
4. **Monitor Cache Usage**: Watch for memory issues and adjust limits as needed
5. **Use Cache Decorators**: Prefer decorators for consistent caching behavior

## Implemented Endpoints

The following endpoints now use Redis caching:

1. **Accounts App**:
   - `/accountsapp/whoami/{user_id}`: User details and activity stats
   - Profile updates invalidate relevant caches

2. **Jobs App**:
   - `/jobs/{job_id}`: Job details
   - `/jobs/alljobs`: All jobs
   - `/jobs/job-industries/`: Job industries
   - `/jobs/job-subcategories/`: Job subcategories

## Future Improvements

1. **Cache Warming**: Preload frequently accessed data
2. **Cache Partitioning**: Separate caches for different data types
3. **Cache Analytics**: More detailed analytics on cache usage
4. **Distributed Caching**: Support for multiple Redis instances
5. **Cache Prefetching**: Predictive loading of related data

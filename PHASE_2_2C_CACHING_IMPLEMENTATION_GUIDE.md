# Phase 2.2c: Caching Implementation Guide

**Status**: Ready to Implement  
**Estimated Duration**: 2-3 hours  
**Expected Impact**: 80%+ cache hit rate, 50-75% response time reduction

---

## 🎯 Caching Strategy

### Three-Tier Caching Approach

1. **Query Result Caching** (Redis)
   - Cache expensive database queries
   - TTL: 5-30 minutes
   - Invalidate on data changes

2. **API Response Caching** (Redis)
   - Cache entire API responses
   - TTL: 5-60 minutes
   - Invalidate on POST/PUT/DELETE

3. **Model Instance Caching** (Redis)
   - Cache individual model instances
   - TTL: 1-24 hours
   - Invalidate on save/delete

---

## 📋 Implementation Checklist

### Phase 2.2c.1: Query Result Caching

**Endpoints to Cache**:
1. `GET /reviews/{user_id}` - User reviews
2. `GET /ratings/reviewer_{user_id}/` - Reviews by user
3. `GET /users/{user_id}/payments` - User payments
4. `GET /get-profile/{user_id}` - User profile
5. `GET /jobs/{job_id}` - Job details
6. `GET /clientjobs/{user_id}` - Client jobs

**Implementation Pattern**:
```python
from django.core.cache import cache

def get_user_reviews(user_id, filter_type="all"):
    cache_key = f"reviews:user:{user_id}:{filter_type}"
    
    # Try cache first
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    # Query database
    reviews = Review.objects.filter(reviewed_id=user_id)
    
    # Cache for 30 minutes
    cache.set(cache_key, reviews, 60 * 30)
    return reviews
```

### Phase 2.2c.2: Cache Invalidation

**Invalidation Triggers**:
- User profile updated → Invalidate profile cache
- Review created → Invalidate user reviews cache
- Payment created → Invalidate user payments cache
- Job updated → Invalidate job cache

**Implementation Pattern**:
```python
from django.db.models.signals import post_save, post_delete

@receiver(post_save, sender=Review)
def invalidate_review_cache(sender, instance, **kwargs):
    # Invalidate reviewed user's reviews cache
    cache.delete(f"reviews:user:{instance.reviewed_id}:all")
    cache.delete(f"reviews:user:{instance.reviewed_id}:recent")
    cache.delete(f"reviews:user:{instance.reviewed_id}:unread")
    
    # Invalidate reviewer's reviews cache
    cache.delete(f"reviews:reviewer:{instance.reviewer_id}:all")
```

### Phase 2.2c.3: API Response Caching

**Decorator Pattern**:
```python
from functools import wraps
from django.core.cache import cache

def cache_api_response(timeout=300):
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            # Generate cache key from request
            cache_key = f"api:{func.__name__}:{request.path}:{request.GET.urlencode()}"
            
            # Try cache
            cached = cache.get(cache_key)
            if cached:
                return cached
            
            # Execute function
            response = func(request, *args, **kwargs)
            
            # Cache response
            cache.set(cache_key, response, timeout)
            return response
        return wrapper
    return decorator
```

**Usage**:
```python
@cache_api_response(timeout=600)  # 10 minutes
@core_router.get("/reviews/{user_id}")
def get_user_ratings_and_reviews(request, user_id: int):
    # ... endpoint code ...
```

### Phase 2.2c.4: Cache Monitoring

**Metrics to Track**:
- Cache hit rate (target: 80%+)
- Cache miss rate (target: <20%)
- Average response time
- Database query count

**Implementation**:
```python
from django.core.cache import cache

class CacheStats:
    @staticmethod
    def get_stats():
        return {
            'hits': cache.get('cache_hits', 0),
            'misses': cache.get('cache_misses', 0),
            'hit_rate': cache.get('cache_hit_rate', 0),
        }
    
    @staticmethod
    def record_hit():
        hits = cache.get('cache_hits', 0) + 1
        cache.set('cache_hits', hits)
    
    @staticmethod
    def record_miss():
        misses = cache.get('cache_misses', 0) + 1
        cache.set('cache_misses', misses)
```

---

## 🔧 Configuration

### Redis Configuration (Already Set Up)
```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            'IGNORE_EXCEPTIONS': True,
        }
    }
}
```

### Cache TTL Strategy
| Data Type | TTL | Reason |
|-----------|-----|--------|
| User Profile | 1 hour | Changes infrequently |
| Job Details | 30 minutes | May be updated |
| Reviews | 30 minutes | May be updated |
| Payments | 5 minutes | Frequently updated |
| Job List | 5 minutes | Frequently updated |

---

## 📊 Expected Results

### Before Caching
- Average response time: 500-2000ms
- Database queries: 10-50 per endpoint
- Cache hit rate: 0%

### After Caching
- Average response time: 50-200ms
- Database queries: 1-3 per endpoint
- Cache hit rate: 80%+
- **Overall improvement: 75-90% faster**

---

## 🚀 Implementation Order

1. **Step 1**: Implement query result caching (1 hour)
2. **Step 2**: Implement cache invalidation (30 minutes)
3. **Step 3**: Implement API response caching (30 minutes)
4. **Step 4**: Add cache monitoring (30 minutes)
5. **Step 5**: Test and validate (30 minutes)

---

## ✅ Success Criteria

- [ ] Cache hit rate ≥ 80%
- [ ] Response time reduced by 75-90%
- [ ] Database queries reduced to 1-3 per endpoint
- [ ] All tests passing
- [ ] No cache invalidation issues
- [ ] Monitoring dashboard working

---

**Next**: Phase 2.2c - Caching Implementation


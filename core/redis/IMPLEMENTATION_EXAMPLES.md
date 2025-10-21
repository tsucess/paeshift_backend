# Redis Caching Implementation Examples

This document provides practical examples of how to implement Redis caching in different scenarios using our standardized approach.

## Table of Contents

1. [Function Caching Examples](#1-function-caching-examples)
2. [API Response Caching Examples](#2-api-response-caching-examples)
3. [Model Caching Examples](#3-model-caching-examples)
4. [Cache Invalidation Examples](#4-cache-invalidation-examples)
5. [Cache Warming Examples](#5-cache-warming-examples)
6. [Advanced Caching Patterns](#6-advanced-caching-patterns)

## 1. Function Caching Examples

### Basic Function Caching

```python
from core.redis import cache_function

@cache_function(namespace='user_data', ttl=3600)  # 1 hour cache
def get_user_data(user_id):
    """Get user data from database."""
    # Expensive database query
    return User.objects.get(id=user_id).to_dict()
```

### Caching with Dynamic TTL

```python
from core.redis import cache_function

@cache_function(namespace='product_data')
def get_product_data(product_id, ttl=None):
    """
    Get product data with dynamic TTL.
    
    High-traffic products get shorter TTL, low-traffic get longer TTL.
    """
    product = Product.objects.get(id=product_id)
    
    # Set TTL based on product popularity
    if ttl is None:
        if product.popularity > 8:
            # Popular products change frequently, cache for 5 minutes
            ttl = 300
        elif product.popularity > 5:
            # Medium popularity, cache for 30 minutes
            ttl = 1800
        else:
            # Low popularity, cache for 2 hours
            ttl = 7200
    
    # The decorator will use the ttl parameter if provided
    return product.to_dict()
```

### Caching Expensive Calculations

```python
from core.redis import cache_function

@cache_function(namespace='analytics', ttl=86400)  # 24 hours
def calculate_user_metrics(user_id):
    """Calculate user metrics (expensive operation)."""
    # Expensive calculations
    login_count = UserLogin.objects.filter(user_id=user_id).count()
    avg_session_time = UserSession.objects.filter(user_id=user_id).aggregate(Avg('duration'))
    purchase_total = Order.objects.filter(user_id=user_id).aggregate(Sum('amount'))
    
    return {
        'login_count': login_count,
        'avg_session_time': avg_session_time['duration__avg'] or 0,
        'purchase_total': purchase_total['amount__sum'] or 0,
    }
```

### Caching Database Aggregations

```python
from core.redis import cache_function
from django.db.models import Count, Sum, Avg

@cache_function(namespace='job_stats', ttl=3600)
def get_job_statistics(job_type=None):
    """Get job statistics with optional filtering."""
    # Start with all jobs
    jobs = Job.objects.all()
    
    # Apply filter if provided
    if job_type:
        jobs = jobs.filter(job_type=job_type)
    
    # Perform expensive aggregation
    stats = jobs.aggregate(
        total=Count('id'),
        avg_pay=Avg('hourly_rate'),
        total_hours=Sum('hours'),
    )
    
    return stats
```

## 2. API Response Caching Examples

### Basic API Response Caching

```python
from core.redis import cache_api_response
from django.http import JsonResponse

@cache_api_response(timeout=900)  # 15 minutes
def get_products_api(request):
    """API endpoint to get all products."""
    products = Product.objects.all().values('id', 'name', 'price')
    return JsonResponse({'products': list(products)})
```

### Caching with Query Parameters

```python
from core.redis import cache_api_response
from django.http import JsonResponse

@cache_api_response(timeout=900, vary_on_query_params=['category', 'sort'])
def get_filtered_products_api(request):
    """API endpoint to get filtered products."""
    # Get query parameters
    category = request.GET.get('category')
    sort = request.GET.get('sort', 'name')
    
    # Start with all products
    products = Product.objects.all()
    
    # Apply category filter if provided
    if category:
        products = products.filter(category=category)
    
    # Apply sorting
    if sort == 'price_asc':
        products = products.order_by('price')
    elif sort == 'price_desc':
        products = products.order_by('-price')
    else:
        products = products.order_by('name')
    
    return JsonResponse({
        'products': list(products.values('id', 'name', 'price', 'category')),
        'count': products.count(),
    })
```

### Caching User-Specific Responses

```python
from core.redis import cache_api_response
from django.http import JsonResponse

@cache_api_response(timeout=900, vary_on_query_params=['user_id'])
def get_user_dashboard_api(request):
    """API endpoint to get user dashboard data."""
    user_id = request.GET.get('user_id')
    
    if not user_id:
        return JsonResponse({'error': 'User ID is required'}, status=400)
    
    # Get user data
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    
    # Get user's recent activity
    recent_jobs = Job.objects.filter(user_id=user_id).order_by('-created_at')[:5]
    recent_payments = Payment.objects.filter(user_id=user_id).order_by('-date')[:5]
    
    return JsonResponse({
        'user': {
            'id': user.id,
            'name': user.name,
            'email': user.email,
        },
        'recent_jobs': list(recent_jobs.values('id', 'title', 'status', 'created_at')),
        'recent_payments': list(recent_payments.values('id', 'amount', 'status', 'date')),
    })
```

## 3. Model Caching Examples

### Basic Model Caching

```python
from django.db import models
from core.redis import RedisCachedModel

class Product(models.Model, RedisCachedModel):
    """Product model with Redis caching."""
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey('Category', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Redis caching configuration
    redis_cache_enabled = True
    redis_cache_prefix = "product"
    redis_cache_timeout = 86400  # 24 hours
    redis_cache_related = ["category"]
    redis_cache_exclude = ["internal_notes"]
```

### Using Standalone Model Caching Functions

```python
from core.redis import cache_model, get_cached_model, invalidate_model_cache

def get_product_details(product_id):
    """Get product details with caching."""
    # Try to get from cache first
    product = get_cached_model(Product, product_id)
    
    if not product:
        # Cache miss, get from database
        try:
            product = Product.objects.get(id=product_id)
            # Cache the product
            cache_model(product)
        except Product.DoesNotExist:
            return None
    
    return product

def update_product_price(product_id, new_price):
    """Update product price and invalidate cache."""
    try:
        product = Product.objects.get(id=product_id)
        product.price = new_price
        product.save()
        
        # Invalidate cache manually (although save() would do this automatically)
        invalidate_model_cache(product)
        
        return True
    except Product.DoesNotExist:
        return False
```

## 4. Cache Invalidation Examples

### Automatic Invalidation with RedisCachedModel

```python
# RedisCachedModel automatically invalidates cache on save() and delete()
product = Product.objects.get(id=1)
product.price = 99.99
product.save()  # Cache is automatically invalidated
```

### Manual Invalidation

```python
from core.redis import invalidate_model_cache
from core.redis.utils import delete_cached_data, invalidate_cache_pattern

# Invalidate a specific model instance
product = Product.objects.get(id=1)
invalidate_model_cache(product)

# Invalidate by model and ID
invalidate_model_cache(Product, 1)

# Invalidate a specific cache key
delete_cached_data("product:1")

# Invalidate all products
invalidate_cache_pattern("product:*")

# Invalidate all caches for a specific user
invalidate_cache_pattern("user:123:*")
```

### Version-Based Invalidation

```python
# In settings.py
CACHE_VERSION = "1.1"  # Increment to invalidate all caches

# For a specific model
class Product(models.Model, RedisCachedModel):
    # ...
    redis_cache_version = "2.0"  # Increment to invalidate this model's cache
```

## 5. Cache Warming Examples

### Warming Critical Models

```python
from core.redis import warm_model_cache, warm_critical_models
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Warm the Redis cache for critical models'
    
    def handle(self, *args, **options):
        self.stdout.write('Warming cache for critical models...')
        
        # Warm all critical models
        warm_critical_models()
        
        # Or warm specific models
        warm_model_cache(Product)
        warm_model_cache(User)
        
        self.stdout.write(self.style.SUCCESS('Cache warming complete!'))
```

### Scheduled Cache Warming

```python
from core.redis import warm_model_cache
from django_q.tasks import schedule
from django_q.models import Schedule

def setup_cache_warming_schedule():
    """Set up scheduled cache warming tasks."""
    # Warm product cache every hour
    schedule(
        'core.redis.warming.warm_model_cache',
        'Product',
        schedule_type=Schedule.HOURLY,
        repeats=-1,  # Repeat indefinitely
        name='warm_product_cache',
    )
    
    # Warm user cache every day at midnight
    schedule(
        'core.redis.warming.warm_model_cache',
        'User',
        schedule_type=Schedule.DAILY,
        next_run=timezone.now().replace(hour=0, minute=0, second=0),
        repeats=-1,  # Repeat indefinitely
        name='warm_user_cache',
    )
```

## 6. Advanced Caching Patterns

### Tiered Caching

```python
from core.redis import cache_function
from django.core.cache import cache as local_cache

def get_user_with_tiered_cache(user_id):
    """
    Get user with tiered caching.
    
    1. Check local memory cache (fastest)
    2. Check Redis cache (fast)
    3. Query database (slow)
    """
    # Local cache key
    local_key = f"local_user_{user_id}"
    
    # Try local memory cache first (fastest)
    user = local_cache.get(local_key)
    if user:
        return user, "local_cache"
    
    # Try Redis cache next
    @cache_function(namespace='user', ttl=3600)
    def get_user_from_db(user_id):
        try:
            return User.objects.get(id=user_id).to_dict()
        except User.DoesNotExist:
            return None
    
    user = get_user_from_db(user_id)
    
    if user:
        # Store in local cache for 60 seconds
        local_cache.set(local_key, user, 60)
        return user, "redis_cache"
    
    return None, "database_miss"
```

### Cache Stampede Prevention

```python
from core.redis import cache_function
import random

@cache_function(namespace='expensive_report', ttl=3600)
def generate_expensive_report(report_id):
    """
    Generate an expensive report with cache stampede prevention.
    
    Uses probabilistic early expiration to prevent cache stampedes.
    """
    # Actual TTL is 1 hour, but we'll start regenerating earlier
    # to prevent multiple simultaneous regenerations when the cache expires
    
    # Add jitter to TTL to prevent synchronized expiration
    actual_ttl = 3600 + random.randint(-60, 60)
    
    # Expensive report generation
    # ...
    
    return report_data
```

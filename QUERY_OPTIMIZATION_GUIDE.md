# Query Optimization Guide - Paeshift

**Date**: October 20, 2025  
**Status**: Phase 2.2 - Database Optimization  
**Goal**: Eliminate N+1 queries and optimize database performance

---

## 🎯 Query Optimization Patterns

### Pattern 1: Single Related Object (ForeignKey)
Use `select_related()` for ForeignKey and OneToOne relationships.

```python
# ❌ BAD: N+1 queries (1 + N queries)
jobs = Job.objects.all()
for job in jobs:
    print(job.client.username)  # N additional queries

# ✅ GOOD: Single query
jobs = Job.objects.select_related('client', 'industry', 'subcategory')
for job in jobs:
    print(job.client.username)  # No additional queries
```

### Pattern 2: Multiple Related Objects (ManyToOne)
Use `prefetch_related()` for reverse ForeignKey and ManyToMany relationships.

```python
# ❌ BAD: N+1 queries
jobs = Job.objects.all()
for job in jobs:
    apps = job.applications.all()  # N additional queries
    print(f"Job has {apps.count()} applications")

# ✅ GOOD: Single query
jobs = Job.objects.prefetch_related('applications')
for job in jobs:
    apps = job.applications.all()  # No additional queries
    print(f"Job has {apps.count()} applications")
```

### Pattern 3: Nested Relationships
Combine `select_related()` and `prefetch_related()`.

```python
# ❌ BAD: Multiple queries
applications = Application.objects.all()
for app in applications:
    print(app.job.client.username)  # Multiple queries per app
    print(app.applicant.profile.rating)  # Multiple queries per app

# ✅ GOOD: Single query
applications = Application.objects.select_related(
    'job__client__profile',
    'applicant__profile'
)
for app in applications:
    print(app.job.client.username)  # No additional queries
    print(app.applicant.profile.rating)  # No additional queries
```

### Pattern 4: Filtering with Aggregation
Use `annotate()` to avoid N+1 queries.

```python
# ❌ BAD: N+1 queries
jobs = Job.objects.all()
for job in jobs:
    count = job.applications.count()  # N additional queries
    print(f"Job {job.id} has {count} applications")

# ✅ GOOD: Single query
from django.db.models import Count
jobs = Job.objects.annotate(
    applications_count=Count('applications')
)
for job in jobs:
    print(f"Job {job.id} has {job.applications_count} applications")
```

### Pattern 5: Limiting Fields
Use `only()` and `defer()` to reduce data transfer.

```python
# ❌ BAD: Fetches all fields
jobs = Job.objects.all()

# ✅ GOOD: Fetch only needed fields
jobs = Job.objects.only('id', 'title', 'client_id', 'date')

# ✅ ALSO GOOD: Defer heavy fields
jobs = Job.objects.defer('description', 'metadata')
```

---

## 📊 Current Optimizations in Paeshift

### ✅ Already Optimized Endpoints

1. **GET /alljobs** (jobs/api.py:143)
   ```python
   jobs = Job.objects.select_related(
       "client__profile",
       "industry",
       "subcategory"
   ).prefetch_related("applications")
   ```

2. **GET /saved-jobs** (jobs/api.py:757)
   ```python
   saved_jobs = SavedJob.objects.select_related("job__industry")
       .filter(user_id=user_id)
       .only("id", "saved_at", "job__id", "job__title", ...)
   ```

---

## 🔧 Optimization Opportunities

### 1. Application Queries
**Current Issue**: Applications fetched without related data

**Optimization**:
```python
# In jobs/api.py or applicant.py
applications = Application.objects.select_related(
    'job__client__profile',
    'job__industry',
    'job__subcategory',
    'applicant__profile'
).filter(...)
```

### 2. Payment Queries
**Current Issue**: Payments fetched without related data

**Optimization**:
```python
# In payment/api.py
payments = Payment.objects.select_related(
    'payer__profile',
    'recipient__profile',
    'job'
).filter(...)
```

### 3. Review Queries
**Current Issue**: Reviews fetched without related data

**Optimization**:
```python
# In rating/api.py
reviews = Review.objects.select_related(
    'reviewer__profile',
    'reviewed__profile',
    'job'
).filter(...)
```

### 4. User Profile Queries
**Current Issue**: User profiles fetched separately

**Optimization**:
```python
# In accounts/api.py
users = CustomUser.objects.select_related('profile').filter(...)
```

---

## 📈 Performance Metrics

### Before Optimization
- Query count per endpoint: 10-50 queries
- Response time: 500-2000ms
- Database CPU: High
- Cache hit rate: 0%

### After Optimization (Target)
- Query count per endpoint: 1-3 queries
- Response time: 50-200ms
- Database CPU: Low
- Cache hit rate: 80%+

---

## 🛠️ Implementation Checklist

### Phase 2.2a: Query Optimization
- [x] Add database indexes (COMPLETE)
- [ ] Optimize jobs/api.py endpoints
- [ ] Optimize payment/api.py endpoints
- [ ] Optimize rating/api.py endpoints
- [ ] Optimize accounts/api.py endpoints
- [ ] Add query analysis logging
- [ ] Run performance tests

### Phase 2.2b: Caching Implementation
- [ ] Setup Redis caching
- [ ] Implement query result caching
- [ ] Implement API response caching
- [ ] Setup cache invalidation
- [ ] Monitor cache hit rates

### Phase 2.2c: Performance Testing
- [ ] Setup Django Debug Toolbar
- [ ] Measure query counts
- [ ] Measure response times
- [ ] Identify remaining bottlenecks
- [ ] Document improvements

---

## 🔍 Query Analysis Tools

### Django Debug Toolbar
```bash
pip install django-debug-toolbar
```

Add to settings.py:
```python
INSTALLED_APPS = [
    'debug_toolbar',
    ...
]

MIDDLEWARE = [
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    ...
]

INTERNAL_IPS = ['127.0.0.1']
```

### Django Silk
```bash
pip install django-silk
```

### Query Logging
```python
from django.db import connection
from django.test.utils import CaptureQueriesContext

with CaptureQueriesContext(connection) as context:
    # Your code here
    pass

print(f"Queries executed: {len(context)}")
for query in context:
    print(query['sql'])
```

---

## 📚 Best Practices

1. **Always use select_related() for ForeignKey**
2. **Always use prefetch_related() for reverse relationships**
3. **Use only() to limit fields when possible**
4. **Use annotate() for aggregations**
5. **Cache expensive queries**
6. **Monitor query counts in tests**
7. **Use database indexes for frequently queried fields**
8. **Batch operations when possible**

---

## 🎯 Success Criteria

- ✅ All endpoints use select_related/prefetch_related
- ✅ Query count reduced by 80%+
- ✅ Response time reduced by 70%+
- ✅ Database CPU usage reduced by 50%+
- ✅ All tests passing
- ✅ Documentation updated



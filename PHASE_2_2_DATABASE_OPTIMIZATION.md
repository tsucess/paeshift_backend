# Phase 2.2: Database Optimization Implementation

**Date**: October 20, 2025  
**Status**: IN PROGRESS  
**Goal**: Optimize database queries, add indexes, implement caching

---

## 🎯 Phase 2.2 Objectives

1. **Analyze Current Queries** - Identify N+1 queries and slow operations
2. **Add Database Indexes** - Speed up frequently queried fields
3. **Optimize Query Patterns** - Use select_related() and prefetch_related()
4. **Implement Caching** - Cache expensive queries and API responses
5. **Performance Testing** - Measure improvements

---

## 📊 Step 1: Query Analysis

### Current Database Schema Analysis

#### Accounts App
- **User Model**: 
  - Frequently queried by: email, username, id
  - Relationships: Profile (OneToOne), Wallet (OneToOne)
  - **Recommended Indexes**: email, username

- **Profile Model**:
  - Frequently queried by: user_id, role
  - Relationships: User (OneToOne)
  - **Recommended Indexes**: user_id, role

- **Wallet Model**:
  - Frequently queried by: user_id
  - Relationships: User (OneToOne)
  - **Recommended Indexes**: user_id

#### Jobs App
- **Job Model**:
  - Frequently queried by: status, date, client_id, created_by_id
  - Relationships: client (FK), created_by (FK), industry (FK), subcategory (FK)
  - **Recommended Indexes**: status, date, client_id, created_by_id, (status, date)

- **Application Model**:
  - Frequently queried by: job_id, applicant_id, status
  - Relationships: job (FK), applicant (FK), employer (FK)
  - **Recommended Indexes**: job_id, applicant_id, status, (job_id, status)

- **SavedJob Model**:
  - Frequently queried by: user_id, job_id
  - Relationships: user (FK), job (FK)
  - **Recommended Indexes**: user_id, job_id, (user_id, saved_at)

#### Payment App
- **Payment Model**:
  - Frequently queried by: status, payer_id, recipient_id, job_id
  - Relationships: payer (FK), recipient (FK), job (FK)
  - **Recommended Indexes**: status, payer_id, recipient_id, job_id

- **Wallet Model**:
  - Frequently queried by: user_id
  - **Recommended Indexes**: user_id

#### Rating App
- **Review Model**:
  - Frequently queried by: reviewed_id, reviewer_id, job_id
  - Relationships: reviewed (FK), reviewer (FK), job (FK)
  - **Recommended Indexes**: reviewed_id, reviewer_id, job_id, (reviewer_id, reviewed_id, job_id)

---

## 🔧 Step 2: Add Database Indexes

### Indexes to Add

```python
# accounts/models.py
class User(AbstractBaseUser):
    class Meta:
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['username']),
        ]

class Profile(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['user_id']),
            models.Index(fields=['role']),
        ]

# jobs/models.py
class Job(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['date']),
            models.Index(fields=['client_id']),
            models.Index(fields=['created_by_id']),
            models.Index(fields=['status', 'date']),
        ]

class Application(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['job_id']),
            models.Index(fields=['applicant_id']),
            models.Index(fields=['status']),
            models.Index(fields=['job_id', 'status']),
        ]

# payment/models.py
class Payment(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['payer_id']),
            models.Index(fields=['recipient_id']),
            models.Index(fields=['job_id']),
        ]

# rating/models.py
class Review(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['reviewed_id']),
            models.Index(fields=['reviewer_id']),
            models.Index(fields=['job_id']),
            models.Index(fields=['reviewer_id', 'reviewed_id', 'job_id']),
        ]
```

---

## 🚀 Step 3: Optimize Query Patterns

### Common N+1 Query Patterns to Fix

#### Pattern 1: Job List with Client Info
```python
# ❌ BAD: N+1 queries
jobs = Job.objects.all()
for job in jobs:
    print(job.client.username)  # N queries

# ✅ GOOD: Single query
jobs = Job.objects.select_related('client', 'industry', 'subcategory')
```

#### Pattern 2: Applications with Job and User Info
```python
# ❌ BAD: N+1 queries
apps = Application.objects.all()
for app in apps:
    print(app.job.title, app.applicant.username)  # N queries

# ✅ GOOD: Single query
apps = Application.objects.select_related('job', 'applicant', 'employer')
```

#### Pattern 3: User with Reviews
```python
# ❌ BAD: N+1 queries
users = User.objects.all()
for user in users:
    reviews = user.reviews_received.all()  # N queries

# ✅ GOOD: Single query
users = User.objects.prefetch_related('reviews_received')
```

---

## 💾 Step 4: Implement Caching

### Cache Strategy

1. **Query Result Caching**
   - Cache expensive queries (user ratings, job counts)
   - TTL: 1 hour for user data, 30 minutes for job data

2. **API Response Caching**
   - Cache GET endpoints
   - Invalidate on POST/PUT/DELETE

3. **Computed Value Caching**
   - Cache user ratings (computed from reviews)
   - Cache job statistics

### Implementation

```python
# core/cache.py
from django.core.cache import cache

def get_user_rating(user_id):
    cache_key = f'user_rating_{user_id}'
    rating = cache.get(cache_key)
    
    if rating is None:
        rating = Review.get_average_rating(user_id)
        cache.set(cache_key, rating, 3600)  # 1 hour
    
    return rating

def invalidate_user_cache(user_id):
    cache.delete(f'user_rating_{user_id}')
```

---

## 📈 Step 5: Performance Metrics

### Metrics to Track

1. **Query Count**: Reduce from N to 1-2 per endpoint
2. **Query Time**: Target < 100ms per query
3. **Response Time**: Target < 200ms per endpoint
4. **Cache Hit Rate**: Target > 80%
5. **Database Load**: Reduce CPU usage by 50%+

### Measurement Tools

- Django Debug Toolbar (development)
- django-silk (production)
- New Relic (APM)
- Prometheus (metrics)

---

## ✅ Implementation Checklist

- [ ] Add database indexes to all models
- [ ] Create migration for new indexes
- [ ] Update API endpoints with select_related()
- [ ] Update API endpoints with prefetch_related()
- [ ] Implement query result caching
- [ ] Implement API response caching
- [ ] Setup cache invalidation
- [ ] Run performance tests
- [ ] Document optimization results
- [ ] Update API documentation

---

## 🎯 Success Criteria

- ✅ All N+1 queries eliminated
- ✅ Query time reduced by 50%+
- ✅ Response time < 200ms
- ✅ Cache hit rate > 80%
- ✅ Database CPU usage reduced by 50%+
- ✅ All tests passing
- ✅ Documentation updated

---

## 📚 Related Files

- `PHASE_2_ACTION_PLAN.md` - Overall action plan
- `PHASE_2_SUMMARY.md` - Phase 2.1 summary
- `QUICK_REFERENCE.md` - Quick reference guide



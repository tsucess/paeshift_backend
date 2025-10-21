# Cache Consistency Improvements

This document outlines the cache consistency improvements implemented in the Payshift application.

## Overview

The cache consistency improvements ensure that data in Redis cache stays in sync with the database, preventing stale or inconsistent data while maintaining the performance benefits of caching.

## Key Features

1. **Version-based Consistency**: Track data versions to detect changes
2. **Timestamp Validation**: Compare timestamps to determine which data is newer
3. **Atomic Updates**: Use transactions and locks to prevent race conditions
4. **Cache Reconciliation**: Periodically reconcile cache with database
5. **Enhanced Logging**: Comprehensive logging for cache operations
6. **Consistency Monitoring**: Tools to monitor and report cache consistency

## Implementation Details

### 1. Version-based Consistency

Models that need strong consistency should include a version field:

```python
class VersionedModel(models.Model):
    version = models.IntegerField(default=1)
    last_updated = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        self.version += 1
        super().save(*args, **kwargs)
    
    class Meta:
        abstract = True
```

When caching, the version is included in the cached data. When retrieving from cache, the version is compared to ensure consistency.

### 2. Timestamp Validation

All cacheable models should include a standard timestamp field:

```python
last_updated = models.DateTimeField(auto_now=True)
```

When syncing between cache and database, timestamps are compared to determine which data is newer.

### 3. Atomic Updates

Database updates are performed within transactions, and Redis operations use locks to prevent race conditions:

```python
with redis_lock(f"lock:{model_name}:{instance_id}"):
    with transaction.atomic():
        # Update database
        
        # Update cache
```

### 4. Cache Reconciliation

A management command is provided to reconcile cache with database:

```bash
python manage.py reconcile_cache
```

Options:
- `--model app_label.model_name`: Reconcile specific model
- `--force`: Force reconciliation even if timestamps suggest DB is older
- `--batch-size`: Number of instances to process in each batch
- `--max-instances`: Maximum number of instances to process per model
- `--check-only`: Only check for inconsistencies without fixing them
- `--verbose`: Show detailed output

### 5. Enhanced Logging

Comprehensive logging is implemented for all cache operations:

```python
logger.info(f"Synced {model_name} {instance_id} to DB")
logger.warning(f"Missing timestamps for comparison: {key}")
logger.error(f"Error syncing key {key} to DB: {str(e)}")
```

### 6. Consistency Monitoring

A function is provided to check cache consistency:

```python
from godmode.cache_sync import check_cache_consistency

stats = check_cache_consistency(User)
print(f"Consistent: {stats['consistent']}, Inconsistent: {stats['inconsistent']}, Missing: {stats['missing']}")
```

## Usage Examples

### Adding Version-based Consistency to a Model

```python
from django.db import models

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(blank=True)
    version = models.IntegerField(default=1)
    last_updated = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        self.version += 1
        super().save(*args, **kwargs)
```

### Reconciling Cache for a Specific Model

```bash
python manage.py reconcile_cache --model accounts.User --force
```

### Checking Cache Consistency

```bash
python manage.py reconcile_cache --model accounts.User --check-only --verbose
```

### Scheduling Regular Reconciliation

Add to your crontab or scheduler:

```
0 3 * * * cd /path/to/project && python manage.py reconcile_cache --batch-size 500 --max-instances 10000
```

## Best Practices

1. **Add Standard Timestamp Fields**: Ensure all cacheable models have a `last_updated` field
2. **Use Version Fields for Critical Models**: Add version fields to models where strong consistency is required
3. **Atomic Updates**: Use transactions and locks for critical operations
4. **Regular Reconciliation**: Schedule regular cache reconciliation jobs
5. **Monitor Consistency**: Regularly check cache consistency and address issues
6. **Comprehensive Logging**: Implement detailed logging for cache operations

## Troubleshooting

### Common Issues

1. **Stale Data**: If you're seeing stale data, check that the model has proper timestamp fields and that cache invalidation is working correctly.

2. **Race Conditions**: If you're experiencing race conditions, ensure that critical operations use transactions and locks.

3. **Missing Cache Entries**: If cache entries are missing, check that the model is properly registered for caching and that cache warming is working.

4. **Inconsistent Data**: If data is inconsistent between cache and database, run the reconciliation command with the `--check-only` option to identify issues.

### Debugging

Use the following command to check cache consistency:

```bash
python manage.py reconcile_cache --model app_label.model_name --check-only --verbose
```

This will show detailed information about inconsistencies between cache and database.

## Future Enhancements

1. **Real-time Monitoring**: Implement real-time monitoring of cache consistency
2. **Automatic Reconciliation**: Automatically reconcile cache when inconsistencies are detected
3. **Distributed Locking**: Enhance locking mechanism for distributed environments
4. **Cache Warming**: Implement intelligent cache warming based on access patterns
5. **Telemetry**: Add detailed telemetry for cache operations

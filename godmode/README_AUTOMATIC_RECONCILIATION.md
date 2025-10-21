# Automatic Cache Reconciliation

This document outlines the automatic cache reconciliation system implemented in the Payshift application.

## Overview

The automatic cache reconciliation system ensures that data in Redis cache stays in sync with the database by:

1. **Continuously Monitoring**: Randomly sampling cached models during normal application operation
2. **Detecting Inconsistencies**: Comparing cache data with database data to identify inconsistencies
3. **Automatic Reconciliation**: Triggering reconciliation when inconsistencies exceed a threshold
4. **Scheduled Checks**: Running comprehensive consistency checks on a schedule
5. **Dashboard Monitoring**: Providing a dashboard to monitor cache consistency

## Key Components

### 1. Cache Consistency Middleware

The `CacheConsistencyMiddleware` randomly samples cached models during normal application operation to detect inconsistencies. When inconsistencies exceed a threshold, it automatically triggers reconciliation.

```python
# godmode/middleware/cache_consistency.py
class CacheConsistencyMiddleware:
    """
    Middleware that automatically detects cache inconsistencies and triggers reconciliation.
    """
```

### 2. Scheduled Tasks

Scheduled tasks run comprehensive consistency checks and reconciliation on a regular basis:

```python
# godmode/tasks/scheduled.py
def setup_scheduled_tasks():
    """
    Set up scheduled tasks for Django Q.
    """
    # Schedule cache consistency check
    schedule(
        'godmode.tasks.cache_tasks.scheduled_consistency_check',
        schedule_type=Schedule.DAILY,
        name='daily_cache_consistency_check',
        repeats=-1,  # Repeat indefinitely
    )
    
    # Schedule cache reconciliation for all models
    schedule(
        'godmode.cache_sync.reconcile_all_caches',
        schedule_type=Schedule.WEEKLY,
        name='weekly_cache_reconciliation',
        repeats=-1,  # Repeat indefinitely
    )
```

### 3. Cache Consistency Dashboard

The cache consistency dashboard provides a visual interface to monitor cache consistency and manually trigger reconciliation:

```
/godmode/cache-consistency/
```

### 4. Consistency Check Functions

Functions to check cache consistency and trigger reconciliation:

```python
# godmode/cache_sync.py
def check_cache_consistency(model_class, sample_size=100):
    """
    Check cache consistency for a sample of model instances.
    """

def reconcile_cache_for_model(model_class, force=False, batch_size=100, max_instances=1000):
    """
    Reconcile cache with database for a specific model.
    """
```

## Configuration

The automatic cache reconciliation system can be configured through settings:

```python
# settings.py
CACHE_CONSISTENCY_CHECK_PROBABILITY = 0.01  # 1% chance of checking on each request
CACHE_CONSISTENCY_CHECK_INTERVAL = 3600  # 1 hour between checks for the same model
CACHE_CONSISTENCY_THRESHOLD = 0.9  # 90% consistency required
CACHE_AUTO_RECONCILE_THRESHOLD = 0.7  # Auto-reconcile if below 70%
CACHE_CONSISTENCY_SAMPLE_SIZE = 50  # Check 50 instances
```

## How It Works

### Continuous Monitoring

1. For each authenticated request, the middleware has a small chance (default: 1%) of checking a random model's cache consistency
2. The middleware selects a random model and checks a sample of instances
3. If the consistency ratio falls below the threshold, reconciliation is triggered

### Scheduled Checks

1. Daily consistency checks run for all models
2. Weekly reconciliation runs for all models
3. Results are logged and stored for monitoring

### Manual Checks

1. Administrators can view the cache consistency dashboard
2. The dashboard shows consistency ratios for all models
3. Administrators can manually trigger consistency checks and reconciliation

## Reconciliation Process

When reconciliation is triggered, the system:

1. Checks for missing cache entries and creates them
2. Checks for stale cache entries and updates them
3. Checks for orphaned cache entries and removes them

## Dashboard Features

The cache consistency dashboard provides:

1. Overall consistency statistics
2. Per-model consistency ratios
3. Detailed information about inconsistencies
4. Buttons to manually trigger checks and reconciliation
5. Visual indicators for critical, warning, and good consistency levels

## Best Practices

1. **Monitor the Dashboard**: Regularly check the cache consistency dashboard
2. **Adjust Thresholds**: Adjust thresholds based on your application's needs
3. **Schedule Reconciliation**: Schedule reconciliation during low-traffic periods
4. **Investigate Patterns**: Look for patterns in inconsistencies to identify root causes
5. **Optimize Sample Size**: Adjust sample size based on model size and importance

## Troubleshooting

### Common Issues

1. **High Inconsistency Rates**: If you see high inconsistency rates, check for:
   - Missing signal handlers for model changes
   - Direct database updates bypassing the ORM
   - Race conditions in high-concurrency operations

2. **Performance Impact**: If the middleware is impacting performance:
   - Reduce the check probability
   - Increase the check interval
   - Decrease the sample size

3. **Frequent Reconciliation**: If reconciliation is triggered too frequently:
   - Increase the auto-reconcile threshold
   - Investigate the root cause of inconsistencies
   - Improve the cache invalidation mechanism

## Future Enhancements

1. **Machine Learning**: Use machine learning to predict which models are likely to have inconsistencies
2. **Adaptive Sampling**: Adjust sample size and check frequency based on historical consistency data
3. **Distributed Reconciliation**: Distribute reconciliation across multiple workers
4. **Real-time Alerts**: Send real-time alerts for critical consistency issues
5. **Detailed Analytics**: Provide more detailed analytics on cache consistency patterns

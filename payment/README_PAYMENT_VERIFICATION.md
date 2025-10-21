# Payment Verification System

This document describes the payment verification system implemented for Payshift, which automatically verifies payment status from Paystack and Flutterwave every 10 minutes.

## Overview

The payment verification system ensures that all payments are properly tracked and verified, even if webhooks fail to deliver. It uses Django Q to schedule regular verification tasks that check the status of pending payments directly with the payment gateways.

## Features

- **Scheduled Verification**: Automatically checks pending payments every 10 minutes
- **Multiple Payment Gateways**: Supports both Paystack and Flutterwave
- **Comprehensive Logging**: Detailed logs of all verification attempts
- **Redis Caching**: Caches verification results with short timeouts
- **Fallback Mechanism**: Uses Django Q as a fallback for Celery tasks
- **Monitoring Tools**: Commands to monitor verification performance

## Implementation Details

### 1. Scheduled Task

The system uses Django Q to schedule a task that runs every 10 minutes:

```python
# Schedule the task
schedule(
    "payment.tasks.check_pending_payments",
    name="payment_verification",
    schedule_type=Schedule.MINUTES,
    minutes=10,
    next_run=datetime.now() + timedelta(minutes=1),
)
```

### 2. Verification Process

The verification process follows these steps:

1. Find all pending payments from the last 48 hours
2. For each payment, queue a verification task
3. The verification task checks the payment status with the appropriate gateway
4. If the payment is successful, update the status and notify the user
5. Log all verification attempts for auditing

### 3. Redis Caching

Payment data is cached with short timeouts to improve performance:

```python
# Cache the verification result
from payment.redis_cache import cache_payment
payment_data = payment.to_dict()
cache_payment(payment_data)
```

The cache timeout is set to 15 minutes to ensure data freshness while reducing database load.

## Usage

### Setting Up the Verification Schedule

To set up the payment verification schedule:

```bash
python setup_payment_verification.py
```

### Manually Verifying Payments

To manually verify pending payments:

```bash
python manage.py verify_pending_payments
```

Options:
- `--hours=48`: Verify payments from the last N hours
- `--sync`: Run verification synchronously
- `--limit=10`: Limit the number of payments to verify

### Monitoring Verification Performance

To monitor verification performance:

```bash
python manage.py monitor_payment_verification
```

Options:
- `--hours=24`: Show statistics from the last N hours
- `--verbose`: Show detailed information

## Best Practices

1. **Don't Cache Payment Data Long-Term**: Payment statuses change frequently, so use short cache timeouts
2. **Maintain Comprehensive Logs**: Keep detailed logs of all payment verification attempts
3. **Use Both Webhooks and Scheduled Verification**: Webhooks for immediate updates, scheduled verification as a backup
4. **Monitor Verification Performance**: Regularly check verification statistics to identify issues

## Troubleshooting

### Common Issues

1. **Pending Payments Not Being Verified**:
   - Check if Django Q is running: `python manage.py qmonitor`
   - Verify the schedule exists: `python manage.py qinfo`

2. **Verification Failures**:
   - Check payment gateway API credentials
   - Verify network connectivity to payment gateways
   - Check logs for specific error messages

3. **High Database Load**:
   - Adjust verification frequency (increase minutes between runs)
   - Optimize database queries in verification tasks

## Conclusion

The payment verification system provides a robust mechanism for ensuring payment statuses are accurately tracked. By combining webhooks with scheduled verification, it offers redundancy and reliability for critical payment processing.

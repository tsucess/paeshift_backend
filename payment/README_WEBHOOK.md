# Payment Webhook Implementation

This document provides an overview of the payment webhook implementation for the Payshift application.

## Overview

The payment webhook system is designed to handle callbacks from payment gateways (Paystack and Flutterwave) when a payment status changes. The system includes:

1. Webhook endpoints for receiving notifications
2. Signature verification for security
3. Asynchronous processing with Celery
4. Fallback to Django Q for reliability
5. Periodic checking of pending payments

## Components

### 1. Webhook Endpoints

Two webhook endpoints are exposed:

- `/payment/webhooks/paystack/` - For Paystack callbacks
- `/payment/webhooks/flutterwave/` - For Flutterwave callbacks

These endpoints are defined in `payment/urls.py` and implemented in `payment/webhooks.py`.

### 2. Webhook Handlers

The webhook handlers:

- Verify the signature of incoming requests
- Extract payment reference and status
- Queue asynchronous tasks for processing
- Return appropriate HTTP responses

### 3. Asynchronous Processing

Payment processing is handled asynchronously using Celery tasks:

- `process_payment_webhook` - Processes webhook notifications
- `check_pending_payments` - Periodically checks pending payments
- `process_refund_task` - Processes refund requests

### 4. Django Q Fallback

If Celery tasks fail after multiple retries, the system falls back to Django Q:

- `process_payment_webhook_q` - Django Q version of the webhook processor
- `verify_payment_status` - Django Q task for verifying payment status

## Security

The webhook implementation includes several security measures:

1. **Signature Verification**: Validates that requests come from legitimate payment gateways
2. **CSRF Exemption**: Webhooks are exempt from CSRF protection as they use their own verification
3. **Transaction Isolation**: Database operations are wrapped in transactions
4. **Error Handling**: Comprehensive error handling and logging

## Configuration

The following settings are required in `settings.py`:

```python
# Paystack Configuration
PAYSTACK_SECRET_KEY = 'your_paystack_secret_key'
PAYSTACK_PUBLIC_KEY = 'your_paystack_public_key'

# Flutterwave Configuration
FLUTTERWAVE_SECRET_KEY = 'your_flutterwave_secret_key'
FLUTTERWAVE_PUBLIC_KEY = 'your_flutterwave_public_key'
FLUTTERWAVE_WEBHOOK_HASH = 'your_flutterwave_webhook_hash'

# Celery Configuration
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
```

## Flow Diagram

```
Payment Gateway ──> Webhook Endpoint ──> Signature Verification
                                              │
                                              ▼
                                        Celery Task
                                              │
                                              ▼
                                    Payment Verification
                                              │
                                              ▼
                                    Database Update
                                              │
                                              ▼
                                    Notification Creation
```

## Error Handling

The system includes comprehensive error handling:

1. **Retry Mechanism**: Failed tasks are retried with exponential backoff
2. **Fallback System**: If Celery fails, Django Q is used as a fallback
3. **Logging**: Detailed logging for debugging and monitoring
4. **Periodic Checks**: Regular checks for pending payments that might have been missed

## Testing

You can test the webhook implementation using the `test_webhook` management command:

```bash
python manage.py test_webhook --payment-method=paystack
```

This simulates a webhook callback without requiring an actual payment gateway.

## Monitoring

The system logs all webhook activities to `payment.log`. You can monitor this file for debugging and auditing purposes.

## Extending

To add support for additional payment gateways:

1. Create a new webhook handler in `payment/webhooks.py`
2. Add the endpoint to `payment/urls.py`
3. Implement the gateway-specific verification in `payment/services.py`
4. Update the Celery tasks to handle the new gateway

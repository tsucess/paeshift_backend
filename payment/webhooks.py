"""
Payment webhook handlers for Paystack and Flutterwave.

This module provides webhook endpoints for payment gateways to notify the system
about payment status changes. It includes:

1. Webhook handlers for Paystack and Flutterwave
2. Enhanced signature verification and security measures
3. Integration with Redis queue for asynchronous batch processing
4. Telemetry and monitoring for webhook performance
5. Protection against replay attacks
6. IP whitelisting
"""

import json
import logging
import time
from typing import Dict, Any, Optional

from django.conf import settings
from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from godmode.audit import log_security_event
from godmode.data_masking import mask_sensitive_data

from .models import Payment
from .tasks import process_payment_webhook
from .webhook_queue import enqueue_webhook, PRIORITY_HIGH, PRIORITY_NORMAL, PRIORITY_LOW
from .webhook_verification import verify_webhook_signature, get_client_ip

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
@verify_webhook_signature(gateway="paystack")
def paystack_webhook(request):
    """
    Handle Paystack webhook notifications.

    Verifies the signature and enqueues the webhook for batch processing.
    """
    start_time = time.time()
    client_ip = get_client_ip(request)

    # Parse payload
    try:
        payload = request.body
        event_data = json.loads(payload)
        event = event_data.get("event")

        # Only process charge.success events
        if event == "charge.success":
            data = event_data.get("data", {})
            reference = data.get("reference")

            if not reference:
                logger.error("Paystack webhook missing reference")
                log_security_event(
                    request=request,
                    action="Paystack webhook missing reference",
                    severity="medium",
                    details={
                        "ip_address": client_ip,
                        "event": event,
                    },
                )
                return HttpResponse(status=400)

            # Mask sensitive data for logging
            masked_data = mask_sensitive_data(event_data)

            # Enqueue webhook for batch processing
            webhook_id = enqueue_webhook(
                payment_method="paystack",
                reference=reference,
                status="success",
                raw_data=event_data,
                priority=PRIORITY_HIGH,  # High priority for payment success
            )

            # Calculate processing time
            processing_time = (time.time() - start_time) * 1000  # ms

            logger.info(
                f"Paystack webhook received for reference {reference}, "
                f"enqueued as {webhook_id} in {processing_time:.2f}ms"
            )

            # Also send to Celery for backward compatibility during transition
            # This can be removed once the new system is fully tested
            process_payment_webhook.delay(
                reference=reference,
                payment_method="paystack",
                status="success",
                raw_data=event_data,
            )

            return HttpResponse(status=200)

        # Acknowledge other events but don't process them
        return HttpResponse(status=200)

    except json.JSONDecodeError:
        logger.exception("Failed to parse Paystack webhook payload")
        log_security_event(
            request=request,
            action="Failed to parse Paystack webhook payload",
            severity="medium",
            details={
                "ip_address": client_ip,
            },
        )
        return HttpResponse(status=400)
    except Exception as e:
        logger.exception(f"Error processing Paystack webhook: {str(e)}")
        log_security_event(
            request=request,
            action="Error processing Paystack webhook",
            severity="high",
            details={
                "ip_address": client_ip,
                "error": str(e),
            },
        )
        return HttpResponse(status=500)


@csrf_exempt
@require_POST
@verify_webhook_signature(gateway="flutterwave")
def flutterwave_webhook(request):
    """
    Handle Flutterwave webhook notifications.

    Verifies the signature and enqueues the webhook for batch processing.
    """
    start_time = time.time()
    client_ip = get_client_ip(request)

    # Parse payload
    try:
        payload = json.loads(request.body)
        event = payload.get("event")

        # Only process successful charge events
        if event == "charge.completed":
            data = payload.get("data", {})
            tx_ref = data.get("tx_ref")
            status = data.get("status")

            if not tx_ref:
                logger.error("Flutterwave webhook missing tx_ref")
                log_security_event(
                    request=request,
                    action="Flutterwave webhook missing tx_ref",
                    severity="medium",
                    details={
                        "ip_address": client_ip,
                        "event": event,
                    },
                )
                return HttpResponse(status=400)

            # Mask sensitive data for logging
            masked_data = mask_sensitive_data(payload)

            # Determine webhook priority based on status
            priority = PRIORITY_HIGH if status == "successful" else PRIORITY_NORMAL

            # Enqueue webhook for batch processing
            webhook_id = enqueue_webhook(
                payment_method="flutterwave",
                reference=tx_ref,
                status="success" if status == "successful" else "failed",
                raw_data=payload,
                priority=priority,
            )

            # Calculate processing time
            processing_time = (time.time() - start_time) * 1000  # ms

            logger.info(
                f"Flutterwave webhook received for tx_ref {tx_ref}, "
                f"enqueued as {webhook_id} in {processing_time:.2f}ms"
            )

            # Also send to Celery for backward compatibility during transition
            # This can be removed once the new system is fully tested
            process_payment_webhook.delay(
                reference=tx_ref,
                payment_method="flutterwave",
                status="success" if status == "successful" else "failed",
                raw_data=payload,
            )

            return HttpResponse(status=200)

        # Acknowledge other events but don't process them
        return HttpResponse(status=200)

    except json.JSONDecodeError:
        logger.exception("Failed to parse Flutterwave webhook payload")
        log_security_event(
            request=request,
            action="Failed to parse Flutterwave webhook payload",
            severity="medium",
            details={
                "ip_address": client_ip,
            },
        )
        return HttpResponse(status=400)
    except Exception as e:
        logger.exception(f"Error processing Flutterwave webhook: {str(e)}")
        log_security_event(
            request=request,
            action="Error processing Flutterwave webhook",
            severity="high",
            details={
                "ip_address": client_ip,
                "error": str(e),
            },
        )
        return HttpResponse(status=500)

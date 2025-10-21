from datetime import timedelta
from django.http import HttpResponse

from django.shortcuts import render
from django.utils import timezone
from .tasks import process_payment_webhook

from django.http import HttpResponse
from .tasks import process_payment_webhook
import json

def paystack_webhook(request):
    if request.method != "POST":
        return HttpResponse(status=405)  # Method not allowed

    try:
        payload = json.loads(request.body)
        reference = payload.get('data', {}).get('reference')
        status = payload.get('data', {}).get('status')
    except Exception:
        return HttpResponse(status=400)  # Bad request

    if not reference or not status:
        return HttpResponse(status=400)

    process_payment_webhook.delay(reference, 'paystack', status, payload)

    return HttpResponse(status=200)

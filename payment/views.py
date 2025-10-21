import json
import logging
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt

from .models import Payment
from .tasks import process_payment_webhook
from .services import PaystackService, FlutterwaveService

logger = logging.getLogger(__name__)

# ====================================
# 🔹 1️⃣ Paystack Webhook (server-to-server)
# ====================================
@csrf_exempt
def paystack_webhook(request):
    """Handle Paystack webhook events (sent from Paystack server)."""
    if request.method != "POST":
        return HttpResponse(status=405)

    try:
        payload = json.loads(request.body)
        reference = payload.get('data', {}).get('reference')
        status = payload.get('data', {}).get('status')
    except Exception as e:
        logger.error(f"Invalid Paystack webhook payload: {e}")
        return HttpResponse(status=400)

    if not reference or not status:
        logger.warning("Paystack webhook missing reference or status")
        return HttpResponse(status=400)

    # Queue background task for safety and async processing
    process_payment_webhook.delay(reference, 'paystack', status, payload)

    logger.info(f"✅ Paystack webhook received for {reference} ({status})")
    return HttpResponse(status=200)


# ====================================
# 🔹 2️⃣ User Redirect Verification (browser callback)
# ====================================
@csrf_exempt
def verify_payment_view(request):
    """
    Called when the user returns from Paystack/Flutterwave.
    Verifies payment → marks as successful → updates job → redirects to dashboard.
    """
    reference = request.GET.get("reference") or request.GET.get("tx_ref")
    gateway = request.GET.get("gateway") or "flutterwave"

    if not reference:
        return JsonResponse({"status": "error", "message": "Missing payment reference"}, status=400)

    try:
        payment = Payment.objects.select_related("job").get(pay_code=reference)
    except Payment.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Payment not found"}, status=404)

    # Pick correct gateway service
    service = PaystackService() if "paystack" in gateway.lower() else FlutterwaveService()

    try:
        verification = service.verify_payment(reference)
        verified_status = verification.get("status")
    except Exception as e:
        logger.error(f"❌ Payment verification failed for {reference}: {e}")
        return redirect(f"{settings.FRONTEND_URL}/dashboard?payment=failed")

    if verified_status == "success":
        try:
            payment.mark_as_successful()
            payment.save(update_fields=["status"])
            logger.info(f"✅ Payment verified successfully: {reference}")
            return redirect(f"{settings.FRONTEND_URL}/dashboard?payment=success")
        except Exception as e:
            logger.error(f"❌ Error marking payment successful: {e}")
            return JsonResponse({"status": "error", "message": str(e)}, status=500)

    else:
        payment.status = "failed"
        payment.save(update_fields=["status"])
        logger.warning(f"❌ Payment verification failed for {reference}")
        return redirect(f"{settings.FRONTEND_URL}/dashboard?payment=failed")

import time
import logging
from typing import Dict, Any
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

def initialize_payment(amount: float, email: str, callback_url: str) -> Dict[str, Any]:
    """Initialize a new payment with Flutterwave"""
    if not settings.FLW_SECRET_KEY:
        raise ValueError("Flutterwave secret key not configured")

    headers = {
        'Authorization': f'Bearer {settings.FLW_SECRET_KEY}',
        'Content-Type': 'application/json',
    }
    
    payload = {
        "tx_ref": f"payshift_{int(time.time())}",
        "amount": str(amount),
        "currency": "NGN",
        "redirect_url": callback_url,
        "customer": {
            "email": email
        },
        "customizations": {
            "title": "Payshift Payment",
            "description": "Payment for service"
        }
    }

    try:
        logger.info(f"Initializing payment for {email} - Amount: {amount}")
        response = requests.post(
            "https://api.flutterwave.com/v3/payments",
            json=payload,
            headers=headers
        )
        response.raise_for_status()
        result = response.json()
        logger.info(f"Payment initialization successful: {result.get('data', {}).get('reference', 'No reference')}")
        return result
    except requests.exceptions.RequestException as e:
        logger.error(f"Payment processing failed: {str(e)}")
        raise ValueError(f"Payment processing failed: {str(e)}")

def verify_payment(transaction_id: str) -> Dict[str, Any]:
    """Verify a payment with Flutterwave"""
    if not settings.FLW_SECRET_KEY:
        raise ValueError("Flutterwave secret key not configured")

    headers = {
        'Authorization': f'Bearer {settings.FLW_SECRET_KEY}',
        'Content-Type': 'application/json',
    }

    try:
        logger.info(f"Verifying payment: {transaction_id}")
        response = requests.get(
            f"https://api.flutterwave.com/v3/transactions/{transaction_id}/verify",
            headers=headers
        )
        response.raise_for_status()
        result = response.json()
        logger.info(f"Payment verification result: {result.get('status', 'unknown')}")
        return result
    except requests.exceptions.RequestException as e:
        logger.error(f"Payment verification failed: {str(e)}")
        raise ValueError(f"Payment verification failed: {str(e)}")

def paystack_transfer(bank_details: dict, amount: float) -> dict:
    """
    Initiate a transfer to a Nigerian bank account using Paystack API.
    bank_details: dict with keys like 'account_number', 'bank_code', 'bank_name', etc.
    amount: amount in Naira (float or Decimal)
    Returns a dict with at least a 'status' key: 'success' or 'failed', and optionally 'message'.
    """
    import requests
    from django.conf import settings
    import logging
    logger = logging.getLogger(__name__)

    PAYSTACK_SECRET_KEY = getattr(settings, 'PAYSTACK_SECRET_KEY', None)
    if not PAYSTACK_SECRET_KEY:
        logger.error("Paystack secret key not configured in settings.")
        return {'status': 'failed', 'message': 'Paystack secret key not configured.'}

    # Paystack expects amount in kobo (Naira * 100)
    try:
        amount_kobo = int(float(amount) * 100)
    except Exception:
        logger.error(f"Invalid amount for paystack_transfer: {amount}")
        return {'status': 'failed', 'message': 'Invalid amount.'}

    # Step 1: Create transfer recipient
    recipient_url = "https://api.paystack.co/transferrecipient"
    recipient_payload = {
        "type": "nuban",
        "name": bank_details.get("account_name", "Payshift User"),
        "account_number": bank_details["account_number"],
        "bank_code": bank_details.get("bank_code"),
        "currency": "NGN"
    }
    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    try:
        recipient_resp = requests.post(recipient_url, json=recipient_payload, headers=headers, timeout=15)
        recipient_resp.raise_for_status()
        recipient_data = recipient_resp.json()
        if not recipient_data.get("status"):
            logger.error(f"Paystack recipient creation failed: {recipient_data}")
            return {'status': 'failed', 'message': recipient_data.get('message', 'Recipient creation failed.')}
        recipient_code = recipient_data["data"]["recipient_code"]
    except Exception as e:
        logger.error(f"Paystack recipient creation error: {e}")
        return {'status': 'failed', 'message': str(e)}

    # Step 2: Initiate transfer
    transfer_url = "https://api.paystack.co/transfer"
    transfer_payload = {
        "source": "balance",
        "amount": amount_kobo,
        "recipient": recipient_code,
        "reason": bank_details.get("transfer_reason", "Wallet withdrawal")
    }
    try:
        transfer_resp = requests.post(transfer_url, json=transfer_payload, headers=headers, timeout=15)
        transfer_resp.raise_for_status()
        transfer_data = transfer_resp.json()
        if transfer_data.get("status"):
            logger.info(f"Paystack transfer successful: {transfer_data}")
            return {'status': 'success', 'data': transfer_data.get('data', {}), 'message': transfer_data.get('message', '')}
        else:
            logger.error(f"Paystack transfer failed: {transfer_data}")
            return {'status': 'failed', 'message': transfer_data.get('message', 'Transfer failed.')}
    except Exception as e:
        logger.error(f"Paystack transfer error: {e}")
        return {'status': 'failed', 'message': str(e)}

def flutterwave_transfer(bank_details: dict, amount: float) -> dict:
    """
    Initiate a transfer to a Nigerian bank account using Flutterwave API.
    bank_details: dict with keys like 'account_number', 'bank_code', 'bank_name', etc.
    amount: amount in Naira (float or Decimal)
    Returns a dict with at least a 'status' key: 'success' or 'failed', and optionally 'message'.
    """
    import requests
    from django.conf import settings
    import logging
    logger = logging.getLogger(__name__)

    FLW_SECRET_KEY = getattr(settings, 'FLW_SECRET_KEY', None)
    if not FLW_SECRET_KEY:
        logger.error("Flutterwave secret key not configured in settings.")
        return {'status': 'failed', 'message': 'Flutterwave secret key not configured.'}

    # Flutterwave expects amount in Naira
    try:
        amount_naira = float(amount)
    except Exception:
        logger.error(f"Invalid amount for flutterwave_transfer: {amount}")
        return {'status': 'failed', 'message': 'Invalid amount.'}

    # Step 1: Initiate transfer
    transfer_url = "https://api.flutterwave.com/v3/transfers"
    transfer_payload = {
        "account_bank": bank_details.get("bank_code"),
        "account_number": bank_details["account_number"],
        "amount": amount_naira,
        "currency": "NGN",
        "beneficiary_name": bank_details.get("account_name", "Payshift User"),
        "narration": bank_details.get("transfer_reason", "Wallet withdrawal"),
        "reference": f"payshift_{int(time.time())}"
    }
    headers = {
        "Authorization": f"Bearer {FLW_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    try:
        transfer_resp = requests.post(transfer_url, json=transfer_payload, headers=headers, timeout=15)
        transfer_resp.raise_for_status()
        transfer_data = transfer_resp.json()
        if transfer_data.get("status") == "success":
            logger.info(f"Flutterwave transfer successful: {transfer_data}")
            return {'status': 'success', 'data': transfer_data.get('data', {}), 'message': transfer_data.get('message', '')}
        else:
            logger.error(f"Flutterwave transfer failed: {transfer_data}")
            return {'status': 'failed', 'message': transfer_data.get('message', 'Transfer failed.')}
    except Exception as e:
        logger.error(f"Flutterwave transfer error: {e}")
        return {'status': 'failed', 'message': str(e)}

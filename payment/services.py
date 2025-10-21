import logging
from decimal import Decimal

import requests
from django.conf import settings
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class PaystackService:
    """Service for handling Paystack payment operations"""

    def __init__(self):
        self.base_url = "https://api.paystack.co"
        self.secret_key = settings.PAYSTACK_SECRET_KEY
        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

    def initialize_payment(self, email, amount, metadata=None):
        """Initialize a payment transaction."""
        from .models import Payment  # Lazy import

        url = f"{self.base_url}/transaction/initialize"
        data = {
            "email": email,
            "amount": int(amount * 100),  # Convert to kobo
            "metadata": metadata or {},
        }

        response = requests.post(url, headers=self.headers, json=data)
        response_data = response.json()

        if not response_data.get("status"):
            raise ValidationError(
                response_data.get("message", "Payment initialization failed")
            )

        return response_data["data"]

    def verify_payment(self, reference):
        """Verify a payment transaction."""
        from .models import Payment  # Lazy import

        url = f"{self.base_url}/transaction/verify/{reference}"
        response = requests.get(url, headers=self.headers)
        response_data = response.json()

        if not response_data.get("status"):
            raise ValidationError(
                response_data.get("message", "Payment verification failed")
            )

        return response_data["data"]

    def create_transfer_recipient(self, name, account_number, bank_code):
        """Create a transfer recipient."""
        url = f"{self.base_url}/transferrecipient"
        data = {
            "type": "nuban",
            "name": name,
            "account_number": account_number,
            "bank_code": bank_code,
        }

        response = requests.post(url, headers=self.headers, json=data)
        response_data = response.json()

        if not response_data.get("status"):
            raise ValidationError(
                response_data.get("message", "Recipient creation failed")
            )

        return response_data["data"]

    def initiate_transfer(self, recipient_code, amount, reason):
        """Initiate a transfer to a recipient."""
        url = f"{self.base_url}/transfer"
        data = {
            "source": "balance",
            "reason": reason,
            "amount": int(amount * 100),  # Convert to kobo
            "recipient": recipient_code,
        }

        response = requests.post(url, headers=self.headers, json=data)
        response_data = response.json()

        if not response_data.get("status"):
            raise ValidationError(
                response_data.get("message", "Transfer initiation failed")
            )

        return response_data["data"]

    def verify_transfer(self, transfer_code):
        """Verify a transfer status."""
        url = f"{self.base_url}/transfer/{transfer_code}"
        response = requests.get(url, headers=self.headers)
        response_data = response.json()

        if not response_data.get("status"):
            raise ValidationError(
                response_data.get("message", "Transfer verification failed")
            )

        return response_data["data"]


class FlutterwaveService:
    """Service for handling Flutterwave payment operations"""

    def __init__(self):
        self.base_url = "https://api.flutterwave.com/v3"
        self.secret_key = settings.FLUTTERWAVE_SECRET_KEY
        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

    def initialize_payment(self, email, amount, metadata=None, redirect_url=None):
        """Initialize a payment transaction."""
        url = f"{self.base_url}/payments"
        data = {
            "tx_ref": f"fw-{int(Decimal(str(amount)) * 100)}-{email.split('@')[0]}",
            "amount": str(amount),
            "currency": "NGN",
            "redirect_url": redirect_url or f"{settings.FRONTEND_URL}/payment/callback",
            "customer": {
                "email": email,
            },
            "meta": metadata or {},
        }

        logger.info(f"Initializing Flutterwave payment for {email}: {amount}")

        try:
            response = requests.post(url, headers=self.headers, json=data)
            response.raise_for_status()
            response_data = response.json()

            if not response_data.get("status") == "success":
                error_msg = response_data.get(
                    "message", "Payment initialization failed"
                )
                logger.error(f"Flutterwave payment initialization failed: {error_msg}")
                raise ValidationError(error_msg)

            logger.info(
                f"Flutterwave payment initialized successfully: {response_data['data']['tx_ref']}"
            )
            return response_data["data"]

        except requests.exceptions.RequestException as e:
            logger.error(f"Flutterwave API request error: {str(e)}")
            raise ValidationError(f"Payment service unavailable: {str(e)}")

    def verify_payment(self, reference):
        """Verify a payment transaction."""
        # Flutterwave allows verification by transaction ID or reference
        url = f"{self.base_url}/transactions/verify_by_reference?tx_ref={reference}"

        logger.info(f"Verifying Flutterwave payment: {reference}")

        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            response_data = response.json()

            if not response_data.get("status") == "success":
                error_msg = response_data.get("message", "Payment verification failed")
                logger.error(f"Flutterwave payment verification failed: {error_msg}")
                raise ValidationError(error_msg)

            # Check if the transaction was successful
            if response_data["data"]["status"] != "successful":
                logger.warning(
                    f"Flutterwave payment not successful: {response_data['data']['status']}"
                )
                return {
                    "status": "failed",
                    "message": f"Payment status: {response_data['data']['status']}",
                    "data": response_data["data"],
                }

            logger.info(f"Flutterwave payment verified successfully: {reference}")
            return {"status": "success", "data": response_data["data"]}

        except requests.exceptions.RequestException as e:
            logger.error(f"Flutterwave API request error: {str(e)}")
            raise ValidationError(f"Payment verification service unavailable: {str(e)}")

    def process_refund(self, transaction_id, amount=None):
        """Process a refund for a transaction."""
        url = f"{self.base_url}/transactions/{transaction_id}/refund"
        data = {}

        if amount:
            data["amount"] = str(amount)

        logger.info(f"Processing Flutterwave refund for transaction {transaction_id}")

        try:
            response = requests.post(url, headers=self.headers, json=data)
            response.raise_for_status()
            response_data = response.json()

            if not response_data.get("status") == "success":
                error_msg = response_data.get("message", "Refund processing failed")
                logger.error(f"Flutterwave refund failed: {error_msg}")
                raise ValidationError(error_msg)

            logger.info(f"Flutterwave refund processed successfully: {transaction_id}")
            return response_data["data"]

        except requests.exceptions.RequestException as e:
            logger.error(f"Flutterwave API request error: {str(e)}")
            raise ValidationError(f"Refund service unavailable: {str(e)}")

    def get_transaction(self, transaction_id):
        """Get details of a transaction."""
        url = f"{self.base_url}/transactions/{transaction_id}"

        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            response_data = response.json()

            if not response_data.get("status") == "success":
                error_msg = response_data.get("message", "Transaction retrieval failed")
                logger.error(f"Flutterwave transaction retrieval failed: {error_msg}")
                raise ValidationError(error_msg)

            return response_data["data"]

        except requests.exceptions.RequestException as e:
            logger.error(f"Flutterwave API request error: {str(e)}")
            raise ValidationError(f"Transaction service unavailable: {str(e)}")

"""
Unit tests for payment API endpoints.
"""
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from ninja.testing import TestClient

from payment.api import payments_router
from payment.models import Payment, Wallet, Transaction

User = get_user_model()


@pytest.mark.django_db
class TestPaymentAPI:
    """Test suite for payment API endpoints."""

    def setup_method(self):
        """Setup test client."""
        self.client = TestClient(payments_router)

    def test_initiate_payment_success(self, client_user, applicant_user, job):
        """Test successful payment initiation."""
        payload = {
            'user_id': client_user.id,
            'job_id': job.id,
            'total': '100.00',
            'payment_method': 'paystack',
            'first_name': client_user.first_name,
            'last_name': client_user.last_name
        }
        with patch('payment.api._process_paystack') as mock_paystack:
            mock_paystack.return_value = 'https://checkout.paystack.com/test'
            response = self.client.post('/payments', json=payload)
            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'success'
            assert 'authorization_url' in data['data']

    def test_initiate_payment_invalid_method(self, client_user, job):
        """Test payment with invalid method."""
        payload = {
            'user_id': client_user.id,
            'job_id': job.id,
            'total': '100.00',
            'payment_method': 'invalid_method',
            'first_name': client_user.first_name,
            'last_name': client_user.last_name
        }
        response = self.client.post('/payments', json=payload)
        assert response.status_code == 400

    def test_initiate_payment_invalid_amount(self, client_user, job):
        """Test payment with invalid amount."""
        payload = {
            'user_id': client_user.id,
            'job_id': job.id,
            'total': '-100.00',
            'payment_method': 'paystack',
            'first_name': client_user.first_name,
            'last_name': client_user.last_name
        }
        response = self.client.post('/payments', json=payload)
        assert response.status_code == 400

    def test_initiate_payment_nonexistent_user(self, job):
        """Test payment with nonexistent user."""
        payload = {
            'user_id': 99999,
            'job_id': job.id,
            'total': '100.00',
            'payment_method': 'paystack',
            'first_name': 'John',
            'last_name': 'Doe'
        }
        response = self.client.post('/payments', json=payload)
        assert response.status_code == 404

    def test_verify_payment_success(self, payment):
        """Test successful payment verification."""
        payload = {
            'reference': payment.pay_code,
            'status': 'success'
        }
        with patch('payment.api.verify_paystack_payment') as mock_verify:
            mock_verify.return_value = True
            response = self.client.post('/verify', json=payload)
            assert response.status_code == 200

    def test_verify_payment_failed(self, payment):
        """Test failed payment verification."""
        payload = {
            'reference': payment.pay_code,
            'status': 'failed'
        }
        response = self.client.post('/verify', json=payload)
        assert response.status_code == 400

    def test_get_wallet_balance(self, client_user):
        """Test getting wallet balance."""
        response = self.client.get(f'/users/{client_user.id}/wallet/balance')
        assert response.status_code == 200
        data = response.json()
        assert 'balance' in data

    def test_get_wallet_transactions(self, client_user):
        """Test getting wallet transactions."""
        response = self.client.get(f'/users/{client_user.id}/wallet/transactions')
        assert response.status_code == 200
        data = response.json()
        assert 'transactions' in data

    def test_withdraw_funds_success(self, client_user):
        """Test successful fund withdrawal."""
        # Create wallet with balance
        wallet, _ = Wallet.objects.get_or_create(user=client_user)
        wallet.balance = Decimal('500.00')
        wallet.save()

        payload = {
            'user_id': client_user.id,
            'amount': '100.00',
            'bank_account': '1234567890',
            'bank_code': '001'
        }
        response = self.client.post('/withdraw', json=payload)
        assert response.status_code == 200

    def test_withdraw_insufficient_funds(self, client_user):
        """Test withdrawal with insufficient funds."""
        # Create wallet with low balance
        wallet, _ = Wallet.objects.get_or_create(user=client_user)
        wallet.balance = Decimal('10.00')
        wallet.save()

        payload = {
            'user_id': client_user.id,
            'amount': '100.00',
            'bank_account': '1234567890',
            'bank_code': '001'
        }
        response = self.client.post('/withdraw', json=payload)
        assert response.status_code == 400

    def test_get_payment_history(self, client_user, payment):
        """Test getting payment history."""
        response = self.client.get(f'/users/{client_user.id}/payments')
        assert response.status_code == 200
        data = response.json()
        assert 'payments' in data

    def test_refund_payment_success(self, payment, client_user):
        """Test successful payment refund."""
        payment.status = 'completed'
        payment.save()

        payload = {
            'user_id': client_user.id,
            'reason': 'Customer request'
        }
        response = self.client.post(f'/payments/{payment.id}/refund', json=payload)
        assert response.status_code == 200

    def test_refund_nonexistent_payment(self, client_user):
        """Test refunding nonexistent payment."""
        payload = {
            'user_id': client_user.id,
            'reason': 'Customer request'
        }
        response = self.client.post('/payments/99999/refund', json=payload)
        assert response.status_code == 404

    def test_get_payment_status(self, payment):
        """Test getting payment status."""
        response = self.client.get(f'/payments/{payment.id}/status')
        assert response.status_code == 200
        data = response.json()
        assert 'status' in data
        assert data['status'] == payment.status


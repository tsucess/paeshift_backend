from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from jobs.models import Job
from payment.models import Payment, Transaction

User = get_user_model()


class PaymentIntegrationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", email="test@test.com", password="testpass123"
        )
        self.job = Job.objects.create(
            title="Test Job",
            description="Test Description",
            client=self.user,
            job_type=Job.JobType.SINGLE_DAY,
            shift_type=Job.ShiftType.MORNING,
            date=timezone.now().date(),
            start_time=timezone.now().time(),
            end_time=(timezone.now() + timezone.timedelta(hours=8)).time(),
            rate=Decimal("100.00"),
            location="Test Location",
        )
        self.client.force_authenticate(user=self.user)

    @patch("payment.services.PaystackService.initialize_transaction")
    def test_initialize_payment(self, mock_initialize):
        mock_initialize.return_value = {
            "status": True,
            "data": {
                "authorization_url": "https://checkout.paystack.com/test",
                "access_code": "test_access_code",
                "reference": "test_reference",
            },
        }

        url = reverse("api:payment-initialize")
        data = {"job_id": self.job.id, "amount": "100.00", "payment_method": "paystack"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("authorization_url", response.data)
        self.assertIn("reference", response.data)

    @patch("payment.services.PaystackService.verify_transaction")
    def test_verify_payment(self, mock_verify):
        # Create a test payment
        payment = Payment.objects.create(
            user=self.user,
            job=self.job,
            amount=Decimal("100.00"),
            reference="test_reference",
        )

        mock_verify.return_value = {
            "status": True,
            "data": {
                "status": "success",
                "amount": 10000,  # Amount in kobo
                "reference": "test_reference",
            },
        }

        url = reverse("api:payment-verify")
        data = {"reference": "test_reference"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")

        # Verify payment was updated
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.COMPLETED)

    def test_payment_history(self):
        # Create some test payments
        Payment.objects.create(
            user=self.user,
            job=self.job,
            amount=Decimal("100.00"),
            reference="test_ref_1",
            status=Payment.Status.COMPLETED,
        )
        Payment.objects.create(
            user=self.user,
            job=self.job,
            amount=Decimal("150.00"),
            reference="test_ref_2",
            status=Payment.Status.PENDING,
        )

        url = reverse("api:payment-history")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)


class TransactionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", email="test@test.com", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

    def test_create_transaction(self):
        transaction = Transaction.objects.create(
            user=self.user,
            amount=Decimal("100.00"),
            transaction_type=Transaction.Type.CREDIT,
            description="Test transaction",
        )
        self.assertEqual(transaction.amount, Decimal("100.00"))
        self.assertEqual(transaction.transaction_type, Transaction.Type.CREDIT)

    def test_transaction_history(self):
        # Create test transactions
        Transaction.objects.create(
            user=self.user,
            amount=Decimal("100.00"),
            transaction_type=Transaction.Type.CREDIT,
            description="Credit transaction",
        )
        Transaction.objects.create(
            user=self.user,
            amount=Decimal("50.00"),
            transaction_type=Transaction.Type.DEBIT,
            description="Debit transaction",
        )

        url = reverse("api:transaction-history")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_balance_calculation(self):
        # Add credits and debits
        Transaction.objects.create(
            user=self.user,
            amount=Decimal("100.00"),
            transaction_type=Transaction.Type.CREDIT,
            description="Credit 1",
        )
        Transaction.objects.create(
            user=self.user,
            amount=Decimal("50.00"),
            transaction_type=Transaction.Type.DEBIT,
            description="Debit 1",
        )
        Transaction.objects.create(
            user=self.user,
            amount=Decimal("75.00"),
            transaction_type=Transaction.Type.CREDIT,
            description="Credit 2",
        )

        url = reverse("api:balance")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["balance"], "125.00")


from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from jobs.models import Job
from payment.models import Payment, Transaction

User = get_user_model()


class PaymentIntegrationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", email="test@test.com", password="testpass123"
        )
        self.job = Job.objects.create(
            title="Test Job",
            description="Test Description",
            client=self.user,
            job_type=Job.JobType.SINGLE_DAY,
            shift_type=Job.ShiftType.MORNING,
            date=timezone.now().date(),
            start_time=timezone.now().time(),
            end_time=(timezone.now() + timezone.timedelta(hours=8)).time(),
            rate=Decimal("100.00"),
            location="Test Location",
        )
        self.client.force_authenticate(user=self.user)

    @patch("payment.services.PaystackService.initialize_transaction")
    def test_initialize_payment(self, mock_initialize):
        mock_initialize.return_value = {
            "status": True,
            "data": {
                "authorization_url": "https://checkout.paystack.com/test",
                "access_code": "test_access_code",
                "reference": "test_reference",
            },
        }

        url = reverse("api:payment-initialize")
        data = {"job_id": self.job.id, "amount": "100.00", "payment_method": "paystack"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("authorization_url", response.data)
        self.assertIn("reference", response.data)

    @patch("payment.services.PaystackService.verify_transaction")
    def test_verify_payment(self, mock_verify):
        # Create a test payment
        payment = Payment.objects.create(
            user=self.user,
            job=self.job,
            amount=Decimal("100.00"),
            reference="test_reference",
        )

        mock_verify.return_value = {
            "status": True,
            "data": {
                "status": "success",
                "amount": 10000,  # Amount in kobo
                "reference": "test_reference",
            },
        }

        url = reverse("api:payment-verify")
        data = {"reference": "test_reference"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")

        # Verify payment was updated
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.COMPLETED)

    def test_payment_history(self):
        # Create some test payments
        Payment.objects.create(
            user=self.user,
            job=self.job,
            amount=Decimal("100.00"),
            reference="test_ref_1",
            status=Payment.Status.COMPLETED,
        )
        Payment.objects.create(
            user=self.user,
            job=self.job,
            amount=Decimal("150.00"),
            reference="test_ref_2",
            status=Payment.Status.PENDING,
        )

        url = reverse("api:payment-history")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)


class TransactionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", email="test@test.com", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

    def test_create_transaction(self):
        transaction = Transaction.objects.create(
            user=self.user,
            amount=Decimal("100.00"),
            transaction_type=Transaction.Type.CREDIT,
            description="Test transaction",
        )
        self.assertEqual(transaction.amount, Decimal("100.00"))
        self.assertEqual(transaction.transaction_type, Transaction.Type.CREDIT)

    def test_transaction_history(self):
        # Create test transactions
        Transaction.objects.create(
            user=self.user,
            amount=Decimal("100.00"),
            transaction_type=Transaction.Type.CREDIT,
            description="Credit transaction",
        )
        Transaction.objects.create(
            user=self.user,
            amount=Decimal("50.00"),
            transaction_type=Transaction.Type.DEBIT,
            description="Debit transaction",
        )

        url = reverse("api:transaction-history")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_balance_calculation(self):
        # Add credits and debits
        Transaction.objects.create(
            user=self.user,
            amount=Decimal("100.00"),
            transaction_type=Transaction.Type.CREDIT,
            description="Credit 1",
        )
        Transaction.objects.create(
            user=self.user,
            amount=Decimal("50.00"),
            transaction_type=Transaction.Type.DEBIT,
            description="Debit 1",
        )
        Transaction.objects.create(
            user=self.user,
            amount=Decimal("75.00"),
            transaction_type=Transaction.Type.CREDIT,
            description="Credit 2",
        )

        url = reverse("api:balance")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["balance"], "125.00")

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from jobs.models import Job
from payment.models import Payment


class PaymentModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        from datetime import datetime, timedelta

        from django.utils import timezone

        # Create industry and subcategory
        from jobs.models import JobIndustry, JobSubCategory

        industry = JobIndustry.objects.create(name="Test Industry")
        subcategory = JobSubCategory.objects.create(
            name="Test Subcategory", industry=industry
        )

        self.job = Job.objects.create(
            title="Test Job",
            description="Test job description",
            client=self.user,
            created_by=self.user,
            industry=industry,
            subcategory=subcategory,
            job_type=Job.JobType.SINGLE_DAY,
            shift_type=Job.ShiftType.MORNING,
            date=timezone.now().date() + timedelta(days=7),
            start_time=datetime.strptime("09:00", "%H:%M").time(),
            end_time=datetime.strptime("17:00", "%H:%M").time(),
            applicants_needed=1,
            rate=Decimal("100.00"),
            location="Test Location",
            latitude=Decimal("40.7128"),
            longitude=Decimal("-74.0060"),
        )

    def test_create_payment(self):
        payment = Payment.objects.create(
            job=self.job,
            payer=self.user,
            original_amount=Decimal("100.00"),
            service_fee=Decimal("5.00"),
            final_amount=Decimal("95.00"),
            pay_code="TEST123456",
            status="Pending",
        )
        self.assertEqual(payment.original_amount, Decimal("100.00"))
        self.assertEqual(payment.status, "Pending")

    def test_payment_calculation(self):
        payment = Payment.objects.create(
            job=self.job,
            payer=self.user,
            original_amount=Decimal("100.00"),
            service_fee=Decimal("0.00"),
            final_amount=Decimal("0.00"),
            pay_code="TEST654321",
            status="Pending",
        )
        payment.calculate_fees()
        self.assertEqual(payment.service_fee, Decimal("5.00"))
        self.assertEqual(payment.final_amount, Decimal("95.00"))


# Transaction model has been removed, so we don't need these tests
# class TransactionTests(TestCase):
#     def test_transaction_creation(self):
#         # Add transaction-specific tests
#         pass

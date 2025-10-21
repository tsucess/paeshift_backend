# payments/models.py
from django.core.exceptions import ValidationError

import logging
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django_fsm import FSMField, transition
# TEMPORARILY COMMENTED OUT FOR SYSTEMATIC TESTING - jobs app not yet added
from jobs.models import Job
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
# from auditlog.registry import auditlog  # Temporarily commented out for deployment

logger = logging.getLogger(__name__)






class PaymentStatusEnum(models.TextChoices):
    SUCCESS = "success", _("Success")
    SUCCESSFUL = "successful", _("Successful")
    FAILED = "failed", _("Failed")
    ABANDONED = "abandoned", _("Abandoned")
    PENDING = "pending", _("Pending")
    REVERSED = "reversed", _("Reversed")
    CANCELLED = "cancelled", _("Cancelled")
    REFUNDED = "refunded", _("Refunded")
    COMPLETED = "completed", _("Completed")


class PaymentMethodEnum(models.TextChoices):
    PAYSTACK = "paystack", _("Paystack")
    FLUTTERWAVE = "flutterwave", _("Flutterwave")
    WALLET = "wallet", _("Wallet")
    BANK_TRANSFER = "bank_transfer", _("Bank Transfer")
    CARD = "card", _("Card")


class Payment(models.Model):
    """
    Payment model for tracking payments between users
    """
    pay_code = models.CharField(max_length=20, unique=True)
    payer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payments_made",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payments_received",
        null=True,
        blank=True,
    )
    job = models.ForeignKey(Job, on_delete=models.SET_NULL, null=True, blank=True)
    original_amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    service_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    final_amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethodEnum.choices,
        default=PaymentMethodEnum.PAYSTACK,
    )
    status = FSMField(
        default=PaymentStatusEnum.PENDING, choices=PaymentStatusEnum.choices
    )
    paystack_reference = models.CharField(max_length=100, blank=True, null=True)
    flutterwave_reference = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['payer_id']),
            models.Index(fields=['recipient_id']),
            models.Index(fields=['job_id']),
            models.Index(fields=['created_at']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"Payment {self.pay_code} - {self.payer.email} to {self.recipient.email if self.recipient else 'N/A'}"

    def save(self, *args, **kwargs):
        if not self.pay_code:
            self.pay_code = self.generate_pay_code()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_pay_code():
        """Generate unique payment code"""
        import uuid
        return f"PAY_{uuid.uuid4().hex[:8].upper()}"

    def to_dict(self):
        """Convert payment to dictionary for API responses"""
        return {
            "id": self.id,
            "pay_code": self.pay_code,
            "payer_id": self.payer_id,
            "recipient_id": self.recipient_id if self.recipient else None,
            "job_id": self.job_id if self.job else None,
            "original_amount": str(self.original_amount),
            "service_fee": str(self.service_fee),
            "final_amount": str(self.final_amount),
            "payment_method": self.payment_method,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

  
    @transition(field=status, source=[PaymentStatusEnum.PENDING, PaymentStatusEnum.FAILED], target=PaymentStatusEnum.SUCCESSFUL)
    def mark_as_successful(self):
        """
        Mark payment as successful and update linked job record.
        This runs automatically when transitioning from pending/failed to successful.
        """
        if not self.job:
            logger.info(f"Payment {self.pay_code} has no linked job to update.")
            return

        from jobs.models import Job

        try:
            job = Job.objects.get(pk=self.job.pk)
            previous_status = job.status

            # Update job payment status
            job.payment_status = Job.PaymentStatus.PAID

            # Auto-transition job status if needed
            if job.status == Job.Status.PENDING:
                job.status = Job.Status.UPCOMING

            job.save(update_fields=["payment_status", "status"])
            logger.info(
                f"✅ Payment {self.pay_code} marked successful. "
                f"Job {job.pk} moved from {previous_status} → {job.status}."
            )

        except Job.DoesNotExist:
            logger.error(f"❌ Job linked to payment {self.pay_code} not found.")
        except Exception as e:
            logger.error(f"❌ Error updating job for payment {self.pay_code}: {e}")



    @transition(field=status, source=[PaymentStatusEnum.PENDING, PaymentStatusEnum.SUCCESSFUL], target=PaymentStatusEnum.FAILED)
    def mark_as_failed(self):
        """Mark payment as failed"""
        pass

    @transition(field=status, source="*", target=PaymentStatusEnum.PENDING)
    def reset_to_pending(self):
        """Reset payment back to pending"""
        pass





class Wallet(models.Model):
    """
    User wallet for storing funds
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wallet"
    )
    balance = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Wallet"
        verbose_name_plural = "Wallets"

    def __str__(self):
        return f"{self.user.email} - Balance: {self.balance}"

    def add_funds(self, amount):
        """Add funds to wallet"""
        if amount <= 0:
            raise ValueError("Amount must be positive")
        self.balance += amount
        self.save()

    def deduct_funds(self, amount):
        """Deduct funds from wallet"""
        if amount <= 0:
            raise ValueError("Amount must be positive")
        if self.balance < amount:
            raise ValueError("Insufficient funds")
        self.balance -= amount
        self.save()

    def has_sufficient_funds(self, amount):
        """Check if wallet has sufficient funds"""
        return self.balance >= amount


class Transaction(models.Model):
    """
    Transaction model for tracking all wallet transactions
    """
    class Type(models.TextChoices):
        CREDIT = "credit", _("Credit")
        DEBIT = "debit", _("Debit")

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        COMPLETED = "completed", _("Completed")
        FAILED = "failed", _("Failed")
        CANCELLED = "cancelled", _("Cancelled")

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="transactions")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=Type.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    reference = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Transaction"
        verbose_name_plural = "Transactions"

    def __str__(self):
        return f"{self.wallet.user.email} - {self.transaction_type} - {self.amount}"

    @staticmethod
    def generate_reference():
        """Generate unique transaction reference"""
        import uuid
        return f"TXN_{uuid.uuid4().hex[:12].upper()}"


# class Payment(models.Model):
#     """
#     Payment model for tracking payments between users
#     """
#     pay_code = models.CharField(max_length=20, unique=True)
#     payer = models.ForeignKey(
#         settings.AUTH_USER_MODEL,
#         on_delete=models.CASCADE,
#         related_name="payments_made",
#     )
#     recipient = models.ForeignKey(
#         settings.AUTH_USER_MODEL,
#         on_delete=models.CASCADE,
#         related_name="payments_received",
#         null=True,
#         blank=True,
#     )
#     # TEMPORARILY COMMENTED OUT FOR SYSTEMATIC TESTING - jobs app not yet added
#     job = models.ForeignKey(Job, on_delete=models.SET_NULL, null=True, blank=True)
#     original_amount = models.DecimalField(
#         max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
#     )
#     service_fee = models.DecimalField(
#         max_digits=10, 
#         decimal_places=2, 
#         default=Decimal("0.00")
#     )
#     final_amount = models.DecimalField(
#         max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
#     )
#     payment_method = models.CharField(
#         max_length=20, choices=PaymentMethodEnum.choices, default=PaymentMethodEnum.PAYSTACK
#     )
#     status = FSMField(
#         default=PaymentStatusEnum.PENDING, choices=PaymentStatusEnum.choices
#     )
#     paystack_reference = models.CharField(max_length=100, blank=True, null=True)
#     flutterwave_reference = models.CharField(max_length=100, blank=True, null=True)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         ordering = ["-created_at"]
#         verbose_name = "Payment"
#         verbose_name_plural = "Payments"

#     def __str__(self):
#         return f"Payment {self.pay_code} - {self.payer.email} to {self.recipient.email if self.recipient else 'N/A'}"

#     def save(self, *args, **kwargs):
#         if not self.pay_code:
#             self.pay_code = self.generate_pay_code()
#         super().save(*args, **kwargs)

#     @staticmethod
#     def generate_pay_code():
#         """Generate unique payment code"""
#         import uuid
#         return f"PAY_{uuid.uuid4().hex[:8].upper()}"

#     def to_dict(self):
#         """Convert payment to dictionary for API responses"""
#         return {
#             "id": self.id,
#             "pay_code": self.pay_code,
#             "payer_id": self.payer_id,
#             "recipient_id": self.recipient_id if self.recipient else None,
#             # "job_id": self.job_id if self.job else None,  # Commented out - no job field
#             "original_amount": str(self.original_amount),
#             "service_fee": str(self.service_fee),
#             "final_amount": str(self.final_amount),
#             "payment_method": self.payment_method,
#             "status": self.status,
#             "created_at": self.created_at.isoformat(),
#             "updated_at": self.updated_at.isoformat(),
#         }


# from django_fsm import transition



# class Payment(models.Model):
#     pay_code = models.CharField(max_length=20, unique=True)
#     payer = models.ForeignKey(
#         settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payments_made"
#     )
#     recipient = models.ForeignKey(
#         settings.AUTH_USER_MODEL,
#         on_delete=models.CASCADE,
#         related_name="payments_received",
#         null=True,
#         blank=True,
#     )
#     job = models.ForeignKey(Job, on_delete=models.SET_NULL, null=True, blank=True)
#     original_amount = models.DecimalField(
#         max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
#     )
#     service_fee = models.DecimalField(
#         max_digits=10, decimal_places=2, default=Decimal("0.00")
#     )
#     final_amount = models.DecimalField(
#         max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
#     )
#     payment_method = models.CharField(
#         max_length=20, choices=PaymentMethodEnum.choices, default=PaymentMethodEnum.PAYSTACK
#     )
#     status = FSMField(default=PaymentStatusEnum.PENDING, choices=PaymentStatusEnum.choices)
#     paystack_reference = models.CharField(max_length=100, blank=True, null=True)
#     flutterwave_reference = models.CharField(max_length=100, blank=True, null=True)
#     verified_at = models.DateTimeField(null=True, blank=True)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         ordering = ["-created_at"]

#     def __str__(self):
#         return f"Payment {self.pay_code} ({self.status})"

#     def save(self, *args, **kwargs):
#         if not self.pay_code:
#             self.pay_code = self.generate_pay_code()
#         super().save(*args, **kwargs)

#     @staticmethod
#     def generate_pay_code():
#         import uuid
#         return f"PAY_{uuid.uuid4().hex[:8].upper()}"

#     # ✅ Only marks as successful when verified (not when initialized)
#     @transition(field=status, source=PaymentStatusEnum.PENDING, target=PaymentStatusEnum.SUCCESSFUL)
#     def mark_as_successful(self):
#         """Mark payment as successful and update linked job"""
#         self.verified_at = timezone.now()
#         if self.job:
#             from jobs.models import Job  # avoid circular import
#             with transaction.atomic():
#                 Job.objects.filter(pk=self.job.pk).update(
#                     payment_status=Job.PaymentStatus.PAID,
#                     status=Job.Status.UPCOMING if self.job.status == Job.Status.PENDING else self.job.status
#                 )
#                 logger.info(f"✅ Job {self.job.pk} marked as PAID (via {self.pay_code})")

#     @transition(field=status, source="*", target=PaymentStatusEnum.FAILED)
#     def mark_as_failed(self):
#         logger.warning(f"❌ Payment {self.pay_code} marked as failed")











class EscrowPayment(models.Model):
    """
    Escrow payment model for holding payments until conditions are met
    """
    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        FUNDED = "funded", _("Funded")
        RELEASED = "released", _("Released")
        REFUNDED = "refunded", _("Refunded")
        DISPUTED = "disputed", _("Disputed")
        CANCELLED = "cancelled", _("Cancelled")

    payment = models.OneToOneField(
        Payment,
        on_delete=models.CASCADE,
        related_name="escrow"
    )
    escrow_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))]
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    funded_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    release_conditions = models.TextField(
        blank=True,
        help_text="Conditions that must be met to release escrow"
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Escrow Payment"
        verbose_name_plural = "Escrow Payments"

    def __str__(self):
        return f"Escrow {self.payment.pay_code} - {self.escrow_amount} ({self.status})"

    def fund_escrow(self):
        """Mark escrow as funded"""
        if self.status == self.Status.PENDING:
            self.status = self.Status.FUNDED
            self.funded_at = timezone.now()
            self.save()

    def release_escrow(self):
        """Release escrow to recipient"""
        if self.status == self.Status.FUNDED:
            self.status = self.Status.RELEASED
            self.released_at = timezone.now()
            self.save()

    def refund_escrow(self):
        """Refund escrow to payer"""
        if self.status in [self.Status.FUNDED, self.Status.DISPUTED]:
            self.status = self.Status.REFUNDED
            self.refunded_at = timezone.now()
            self.save()

    def dispute_escrow(self):
        """Mark escrow as disputed"""
        if self.status == self.Status.FUNDED:
            self.status = self.Status.DISPUTED
            self.save()


# Register models for audit logging - temporarily commented out for deployment
# auditlog.register(Payment)
# auditlog.register(Wallet)
# auditlog.register(Transaction)
# auditlog.register(EscrowPayment)

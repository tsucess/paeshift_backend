# Standard Library Imports
import logging
import os
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

# Django Imports
import django
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import (AbstractBaseUser, BaseUserManager,
                                        PermissionsMixin)
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.core.validators import (FileExtensionValidator, MaxLengthValidator,
                                    MaxValueValidator, MinLengthValidator,
                                    MinValueValidator, RegexValidator)
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
# Third Party Imports
from geopy.exc import GeocoderTimedOut
from geopy.geocoders import Nominatim

# Local App Imports
from rating.models import Review
## Removed RedisCachedModelMixin import to eliminate Redis dependency

# Initialize logger
logger = logging.getLogger(__name__)

# Get user model
User = get_user_model()


# File Storage Configuration (if needed)
def user_profile_pic_path(instance, filename):
    """Generates upload path for user profile pictures"""
    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(
        "profile_pics", f"user_{instance.user.id}", f"{timestamp}_{filename}"
    )


# Your models will follow below these imports

# ------------------------------------------------------
# 1️⃣ Job Industry & Subcategory Models (Optimized)
# ------------------------------------------------------


class JobIndustry(models.Model):
    """Represents a top-level job industry (e.g., IT, Healthcare, Construction)."""

    # Redis caching configuration
    cache_enabled = True
    cache_exclude = []

    name = models.CharField(
        max_length=255,
        unique=True,
        blank=True,
        null=True,
        validators=[
            MinLengthValidator(
                2, message="Industry name must be at least 2 characters"
            ),
            MaxLengthValidator(255),
        ],
    )
    timestamp = models.DateTimeField(
        default=timezone.now, db_index=True  # Added for faster filtering
    )

    class Meta:
        verbose_name = "Job Industry"
        verbose_name_plural = "Job Industries"
        indexes = [
            models.Index(fields=["name"]),  # Faster name lookups
        ]
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} (Created on {self.timestamp.date()})"

    def clean(self):
        """Additional validation at model level"""
        super().clean()
        if self.name and len(self.name.strip()) < 2:
            raise ValidationError("Industry name cannot be just whitespace")


class JobSubCategory(models.Model):
    """Represents a subcategory under a JobIndustry"""

    # Redis caching configuration
    cache_enabled = True
    cache_related = ["industry"]
    cache_exclude = []

    industry = models.ForeignKey(
        JobIndustry,
        on_delete=models.CASCADE,
        related_name="subcategories",
        db_index=True,  # Added for faster joins
    )
    name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        validators=[MinLengthValidator(2), MaxLengthValidator(255)]
    )
    saved_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["name"]
        unique_together = [["industry", "name"]]
        indexes = [
            models.Index(fields=["industry", "name"]),  # Composite index
            models.Index(fields=["name"]),  # Additional single column index
        ]
        verbose_name = "Job Subcategory"
        verbose_name_plural = "Job Subcategories"

    def __str__(self):
        return f"{self.name} (under {self.industry.name})"

    @property
    def full_info(self):
        return f"{self.name} | Industry created: {self.industry.timestamp.date()}"

    def clean(self):
        """Validate subcategory name"""
        super().clean()
        if self.name and len(self.name.strip()) < 2:
            raise ValidationError("Subcategory name cannot be just whitespace")


class Job(models.Model):
    """
    Optimized Job model with all fixes applied.
    Preserves all original fields while adding improvements.

    Includes Redis caching for improved performance.
    Uses RedisSyncMixin to automatically sync with Redis when saved or deleted.
    """

    # Redis caching configuration
    cache_enabled = True
    cache_related = ["industry", "subcategory"]
    cache_exclude = []

    # Redis sync configuration
    redis_cache_prefix = "job"
    redis_cache_timeout = 60 * 60 * 6  # 6 hours
    redis_cache_permanent = False

    # --- Choice Classes ---
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        UPCOMING = "upcoming", "Upcoming"
        ONGOING = "ongoing", "Ongoing"
        COMPLETED = "completed", "Completed"
        CANCELED = "canceled", "Canceled"

    class JobType(models.TextChoices):
        SINGLE_DAY = "single_day", "Single Day"
        MULTIPLE_DAYS = "multiple_days", "Multiple Days"
        TEMPORARY = "temporary", "Temporary"
        PART_TIME = "part_time", "Part Time"
        FULL_TIME = "full_time", "Full Time"

    class ShiftType(models.TextChoices):
        MORNING = "morning", "Morning"
        AFTERNOON = "afternoon", "Afternoon"
        EVENING = "evening", "Evening"
        NIGHT = "night", "Night"
        DAY = "day", "Day"
        Flexible = "flexible", "Flexible"

    class PaymentStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        HELD = "held", "Held in Escrow"
        PARTIAL = "partial", "Partially Paid"
        PAID = "paid", "Paid"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    # --- Core Fields ---
    title = models.CharField(max_length=255, validators=[MinLengthValidator(3)])
    description = models.TextField(
        default="No description provided", validators=[MaxLengthValidator(5000)]
    )
    is_active = models.BooleanField(default=True, db_index=True)

    # --- Relationship Fields ---
    client = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="jobs_as_client",
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="jobs",
        null=True,
        db_index=True,
    )
    industry = models.ForeignKey(
        "JobIndustry", on_delete=models.SET_NULL, null=True, blank=True, db_index=True
    )
    subcategory = models.ForeignKey(
        "JobSubCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_index=True,
    )
    selected_applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_jobs",
        db_index=True,
    )

    # --- Scheduling Fields ---
    job_type = models.CharField(
        max_length=20,
        choices=JobType.choices,
        default=JobType.SINGLE_DAY,
        db_index=True,
    )
    shift_type = models.CharField(
        max_length=20, choices=ShiftType.choices, db_index=True
    )
    date = models.DateField(db_index=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    recurring_days = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Comma-separated days (e.g., Monday,Wednesday,Friday)",
        validators=[
            RegexValidator(
                regex=r"^[a-zA-Z, ]+$", message="Only letters and commas allowed"
            )
        ],
    )
    applicants_needed = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1)]
    )

    # --- Financial Fields ---
    rate = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)]
    )
    service_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00, validators=[MinValueValidator(0)]
    )
    total_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00, validators=[MinValueValidator(0)]
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        db_index=True,
    )

    # --- Location Fields ---
    location = models.CharField(max_length=255)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )

    # --- Status Tracking ---
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )

    # --- Time Tracking ---
    actual_shift_start = models.DateTimeField(null=True, blank=True, db_index=True)
    actual_shift_end = models.DateTimeField(null=True, blank=True, db_index=True)
    last_location_update = models.DateTimeField(null=True, blank=True)

    # --- Timestamps ---
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        indexes = [
            models.Index(fields=["status", "payment_status"]),
            models.Index(fields=["latitude", "longitude"]),
            models.Index(fields=["date", "start_time"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["job_type", "shift_type"]),
        ]
        verbose_name = "Job"
        verbose_name_plural = "Jobs"
        db_table = "jobs_job"

    @property
    def is_shift_ongoing(self):
        """Check if the shift is currently ongoing."""
        now = timezone.now()
        if self.actual_shift_start and not self.actual_shift_end:
            return True
        if self.date == now.date():
            current_time = now.time()
            return self.start_time <= current_time <= self.end_time
        return False

    @property
    def location_coordinates(self):
        """Return latitude and longitude as a tuple if both exist."""
        if self.latitude and self.longitude:
            return (float(self.latitude), float(self.longitude))
        return None

    @property
    def duration_hours(self):
        if not all([self.start_time, self.end_time, self.date]):
            return 0.0

        start_dt = datetime.combine(self.date, self.start_time)
        end_dt = datetime.combine(self.date, self.end_time)

        # Handle overnight shifts
        if end_dt < start_dt:
            end_dt += timedelta(days=1)

        duration = end_dt - start_dt
        return round(duration.total_seconds() / 3600, 2)


    def clean(self):
        """Validate model-level business rules"""
        super().clean()

        if self.pk:
            old = Job.objects.get(pk=self.pk)
            allowed_transitions = {
                self.PaymentStatus.PENDING: [
                    self.PaymentStatus.PAID,  # Explicitly allow this
                    self.PaymentStatus.HELD,
                    self.PaymentStatus.FAILED,
                    self.PaymentStatus.PARTIAL
                ],
                self.PaymentStatus.HELD: [
                    self.PaymentStatus.PAID,  # Allow direct transition
                    self.PaymentStatus.COMPLETED,
                    self.PaymentStatus.REFUNDED
                ],
                # ... keep other transitions ...
            }
            if old.payment_status != self.payment_status:
                if self.payment_status not in allowed_transitions.get(old.payment_status, []):
                    raise ValidationError(
                        f"Invalid payment status transition: {old.payment_status} → {self.payment_status}"
                    )



    def start_shift(self):
        """Mark the shift as started with validation and update accepted applications to ongoing."""
        if self.status not in [self.Status.PENDING, self.Status.UPCOMING]:
            raise ValidationError("Cannot start a job that isn't pending or upcoming")

        with transaction.atomic():
            self.actual_shift_start = timezone.now()
            self.status = self.Status.ONGOING
            self.save(update_fields=["actual_shift_start", "status"])

            # Update all accepted applications to ongoing status
            from jobs.models import Application
            accepted_applications = self.applications.filter(status=Application.Status.ACCEPTED)
            for application in accepted_applications:
                application.update_status(Application.Status.ONGOING)

    def end_shift(self):
        """Mark the shift as ended with validation and distribute payment to applicants if no open dispute."""
        if self.status != self.Status.ONGOING:
            raise ValidationError("Cannot end a job that isn't ongoing")

        from payment.models import Wallet, Transaction
        from decimal import Decimal
        from django.utils import timezone
        from disputes.models import Dispute
        from django.db import transaction as db_transaction

        with transaction.atomic():
            self.actual_shift_end = timezone.now()
            self.status = self.Status.COMPLETED
            self.save(update_fields=["actual_shift_end", "status"])

            # Check for open dispute
            open_dispute = Dispute.objects.filter(job=self, status=Dispute.Status.OPEN).exists()
            if open_dispute:
                # Payment held in escrow, do not distribute
                return

            # Distribute payment to ongoing applicants (who were working the shift)
            from jobs.models import Application
            ongoing_apps = self.applications.filter(status=Application.Status.ONGOING)
            num_ongoing = ongoing_apps.count()
            if num_ongoing > 0 and self.total_amount > 0:
                share = (self.total_amount / num_ongoing).quantize(Decimal("0.01"))
                for app in ongoing_apps:
                    applicant = app.applicant
                    if not applicant:
                        continue
                    try:
                        with db_transaction.atomic():
                            wallet, _ = Wallet.objects.get_or_create(user=applicant)
                            wallet.add_funds(share)
                            Transaction.objects.create(
                                wallet=wallet,
                                amount=share,
                                transaction_type=Transaction.Type.CREDIT,
                                status=Transaction.Status.COMPLETED,
                                reference=f"job_{self.id}_pay_{applicant.id}_{timezone.now().timestamp()}",
                                description=f"Payment for job '{self.title}' (ID: {self.id})",
                                metadata={"job_id": self.id, "applicant_id": applicant.id}
                            )
                    except Exception as e:
                        logger.error(f"Failed to credit wallet for applicant {applicant.id}: {e}")

            # Update ongoing applications to accepted status (shift completed)
            for app in ongoing_apps:
                app.update_status(Application.Status.ACCEPTED)

    def deactivate(self):
        """Cancel the job with validation."""
        if self.status in [self.Status.COMPLETED, self.Status.CANCELED]:
            raise ValidationError("Cannot cancel already completed or canceled job")

        with transaction.atomic():
            self.is_active = False
            self.status = self.Status.CANCELED
            self.save(update_fields=["is_active", "status"])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_location = self.location

    def calculate_service_fee_and_total(self):
        """
        Calculate service fee (15% of total) and total amount based on rate and duration.

        This method calculates the service fee as 15% of the total amount,
        which is determined by multiplying the hourly rate by the job duration.
        """
        from decimal import ROUND_HALF_UP, Decimal

        # Calculate total amount based on rate and duration
        if self.rate and self.duration_hours:
            # Calculate total with proper decimal precision
            total = (self.rate * Decimal(str(self.duration_hours))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

            # Calculate service fee (15% of total)
            service_fee = (total * Decimal("0.15")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

            self.total_amount = total
            self.service_fee = service_fee
            return True
        return False


    def mark_as_paid(self):
        """Atomic payment completion handler"""
        with transaction.atomic():
            if self.payment_status not in [self.PaymentStatus.PENDING, self.PaymentStatus.HELD]:
                raise ValidationError("Only pending/held jobs can be marked paid")
            
            self.payment_status = self.PaymentStatus.PAID
            if self.status == self.Status.PENDING:
                self.status = self.Status.UPCOMING
            self.save(update_fields=["payment_status", "status"])


    def save(self, *args, **kwargs):
        # Skip geocoding during initial save to avoid API rate limits
        skip_geocoding = kwargs.pop("skip_geocoding", False)

        needs_geocoding = False
        if self.pk is None:
            needs_geocoding = True
        elif self.pk:
            try:
                old_job = Job.objects.get(pk=self.pk)
                needs_geocoding = self.location != old_job.location
            except Job.DoesNotExist:
                needs_geocoding = True

        # Calculate service fee and total amount for new jobs or when rate/times change
        is_new = self.pk is None

        self.full_clean()  # Ensure validation runs on every save

        # For new jobs, calculate service fee and total amount
        if is_new and self.rate and self.start_time and self.end_time:
            self.calculate_service_fee_and_total()

        # Store client ID before save for cache invalidation
        client_id = None
        if self.pk and hasattr(self, 'client') and self.client:
            client_id = self.client.id

        with transaction.atomic():
            super().save(*args, **kwargs)

            # Only attempt geocoding if not explicitly skipped
            if not skip_geocoding and needs_geocoding and self.location:
                try:
                    from django_q.tasks import async_task

                    # Queue geocoding as a background task instead of doing it synchronously
                    async_task(
                        "jobs.tasks.geocode_job",
                        self.id,
                        hook="jobs.hooks.handle_geocode_result",
                    )
                    logger.info(f"Queued geocoding task for job {self.id}")
                except Exception as e:
                    logger.error(
                        f"Failed to queue geocoding task for job {self.id}: {str(e)}"
                    )

            # Invalidate client jobs cache
            try:
                from core.redis.utils import invalidate_cache_pattern

                # Invalidate cache for this specific job
                invalidate_cache_pattern(f"job:{self.id}")
                invalidate_cache_pattern(f"model:job:{self.id}")

                # Invalidate client jobs cache for this client
                if hasattr(self, 'client') and self.client:
                    invalidate_cache_pattern(f"clientjobs:*:u:{self.client.id}")
                    logger.debug(f"Invalidated client jobs cache for client {self.client.id}")

                # If client changed, invalidate cache for previous client too
                if client_id and client_id != self.client.id:
                    invalidate_cache_pattern(f"clientjobs:*:u:{client_id}")
                    logger.debug(f"Invalidated client jobs cache for previous client {client_id}")
            except Exception as e:
                logger.error(f"Failed to invalidate cache for job {self.id}: {str(e)}")

        # Ensure the job is cached after save
        if hasattr(self, 'cache'):
            self.cache()

        return self

    def delete(self, *args, **kwargs):
        """
        Override delete method to invalidate cache before deletion.
        """
        # Store client ID for cache invalidation
        client_id = None
        if hasattr(self, 'client') and self.client:
            client_id = self.client.id

        # Additional cache invalidation for client jobs
        try:
            from core.redis.utils import invalidate_cache_pattern

            # Invalidate cache for this specific job
            invalidate_cache_pattern(f"job:{self.id}")
            invalidate_cache_pattern(f"model:job:{self.id}")

            # Invalidate client jobs cache for this client
            if client_id:
                invalidate_cache_pattern(f"clientjobs:*:u:{client_id}")
                logger.debug(f"Invalidated client jobs cache for client {client_id} after job deletion")
        except Exception as e:
            logger.error(f"Failed to invalidate cache after job deletion: {str(e)}")

        # Call parent's delete method
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"



class Application(models.Model):
    """
    Optimized Application model with all fixes and enhancements.

    Uses RedisSyncMixin to automatically sync with Redis when saved or deleted.
    """

    # # Redis caching configuration
    # cache_enabled = True
    # cache_related = ["job", "applicant", "industry"]
    # cache_exclude = []

    # # Redis sync configuration
    # redis_cache_prefix = "application"
    # redis_cache_timeout = 60 * 60 * 3  # 3 hours
    # redis_cache_permanent = False

    class Status(models.TextChoices):
        PENDING = "Pending", "Pending"
        APPLIED = "Applied", "Applied"
        REJECTED = "Rejected", "Rejected"
        ACCEPTED = "Accepted", "Accepted"
        ONGOING = "Ongoing", "Ongoing"
        WITHDRAWN = "Withdrawn", "Withdrawn"

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )

    # Core Fields
    job = models.ForeignKey(
        "Job", on_delete=models.CASCADE, related_name="applications", db_index=True
    )
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        default=None,
        db_index=True,
    )

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    applied_at = models.DateTimeField(auto_now_add=True, db_index=True)
    status_changed_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # Performance Tracking
    is_shown_up = models.BooleanField(default=False, db_index=True)
    manual_rating = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(1.0), MaxValueValidator(5.0)],
    )
    feedback = models.TextField(blank=True, validators=[MaxLengthValidator(2000)])

    # Location Tracking (standardized to Decimal)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal("-90.0")),
            MaxValueValidator(Decimal("90.0")),
        ],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal("-180.0")),
            MaxValueValidator(Decimal("180.0")),
        ],
    )

    # Related Fields
    industry = models.ForeignKey(
        "JobIndustry", on_delete=models.SET_NULL, null=True, blank=True, db_index=True
    )
    def employer(self):
        return self.job.client
    class Meta:
        unique_together = ("job", "applicant")
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["applied_at"]),
            models.Index(fields=["is_shown_up"]),
            models.Index(fields=["job", "applicant", "status"]),  # Composite index
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.applicant} - {self.job.title} ({self.get_status_display()})"

    @property
    def employer(self):
        """Derived from job.client to remove redundancy"""
        return self.job.client

    @property
    def location_coordinates(self):
        """Return latitude and longitude as a tuple if both exist."""
        if self.latitude is not None and self.longitude is not None:
            return (float(self.latitude), float(self.longitude))
        return None

    @property
    def rating(self):
        """
        Calculate average rating for the applicant with better error handling.
        Falls back to manual_rating if review system is unavailable.
        """
        try:
            from rating.models import Review

            rating = Review.get_average_rating(self.applicant)
            return rating if rating is not None else self.manual_rating
        except Exception as e:
            logger.error(
                f"Rating calculation failed for applicant {self.applicant_id}: {str(e)}"
            )
            return self.manual_rating

    @rating.setter
    def rating(self, value):
        """Set manual rating with validation."""
        if value is not None:
            try:
                value = Decimal(str(value)).quantize(Decimal("0.1"))
                if not (Decimal("1.0") <= value <= Decimal("5.0")):
                    raise ValidationError("Rating must be between 1.0 and 5.0")
                self.manual_rating = float(value)
            except (ValueError, TypeError) as e:
                raise ValidationError(f"Invalid rating value: {str(e)}")

    def update_status(self, new_status):
        """
        Atomic status update with comprehensive validation.
        """
        if new_status not in dict(self.Status.choices):
            raise ValidationError(f"Invalid status: {new_status}")

        if self.status == new_status:
            return False

        with transaction.atomic():
            old_status = self.status
            self.status = new_status
            self.status_changed_at = timezone.now()
            self.save(update_fields=["status", "status_changed_at"])

            ApplicationStatusLog.objects.create(
                application=self, old_status=old_status, new_status=new_status
            )
        return True

    @transaction.atomic
    def accept(self):
        """Accept application with race condition protection for multiple applicants."""
        if self.status == self.Status.ACCEPTED:
            return False

        # Lock related job row to prevent race conditions
        job = Job.objects.select_for_update().get(pk=self.job.id)

        # Count currently accepted applications
        accepted_count = job.applications.filter(status=self.Status.ACCEPTED).count()
        if accepted_count >= job.applicants_needed:
            raise ValidationError(f"This job already has the maximum number of accepted applicants ({job.applicants_needed}).")

        self.update_status(self.Status.ACCEPTED)

        # Only update selected_applicant if needed, do NOT change job status automatically
        accepted_count += 1
        if job.applicants_needed == 1:
            job.selected_applicant = self.applicant
            job.save(update_fields=["selected_applicant"])
        else:
            # If not yet filled, do not change job status
            job.save(update_fields=[])
        return True

    def reject(self):
        """Reject this application atomically."""
        return self.update_status(self.Status.REJECTED)

    def withdraw(self):
        """Withdraw application with proper validation."""
        if self.status in [self.Status.ACCEPTED, self.Status.REJECTED]:
            raise ValidationError("Cannot withdraw accepted or rejected applications.")
        return self.update_status(self.Status.WITHDRAWN)

    def clean(self):
        """Comprehensive model validation."""
        super().clean()

        # Validate new instances
        if not self.pk and self.applicant and self.job:
            if not (self.applicant.pk and self.job.pk):
                raise ValidationError(
                    "Applicant and Job must be saved before creating an Application."
                )

            if Application.objects.filter(
                applicant=self.applicant, job=self.job
            ).exists():
                raise ValidationError("Duplicate application is not allowed.")

        # Validate rating
        if self.manual_rating is not None and not (
            1.0 <= float(self.manual_rating) <= 5.0
        ):
            raise ValidationError("Manual rating must be between 1.0 and 5.0")

    def save(self, *args, **kwargs):
        """Enhanced save with validation and optimized updates."""
        self.full_clean()

        # Track status changes efficiently
        if self.pk:
            old_status = Application.objects.values_list("status", flat=True).get(
                pk=self.pk
            )
            if old_status != self.status:
                self.status_changed_at = timezone.now()
                if "update_fields" in kwargs:
                    kwargs["update_fields"].extend(["status_changed_at"])

        super().save(*args, **kwargs)



class ApplicationStatusLog(models.Model):
    """
    Model for tracking application status changes without caching.
    """

    application = models.ForeignKey(
        'Application',
        on_delete=models.CASCADE,
        related_name="status_logs",
        db_index=True,
    )
    old_status = models.CharField(
        max_length=20,
        choices=Application.Status.choices,
        db_index=True,
    )
    new_status = models.CharField(
        max_length=20,
        choices=Application.Status.choices,
        db_index=True,
    )
    changed_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="User who initiated the status change",
    )

    class Meta:
        ordering = ["-changed_at"]
        indexes = [
            models.Index(fields=["application", "changed_at"]),
            models.Index(fields=["new_status", "changed_at"]),
        ]
        verbose_name = "Application Status Log"
        verbose_name_plural = "Application Status Logs"

    def __str__(self):
        return (
            f"Application {self.application_id}: "
            f"{self.old_status} → {self.new_status} "
            f"({self.changed_at})"
        )

    def clean(self):
        """Validate status transitions"""
        super().clean()
        if self.old_status == self.new_status:
            raise ValidationError("Old and new status cannot be the same")

    @classmethod
    def log_status_change(cls, application, old_status, new_status, changed_by=None):
        """Helper method to create logs atomically"""
        with transaction.atomic():
            return cls.objects.create(
                application=application,
                old_status=old_status,
                new_status=new_status,
                changed_by=changed_by,
            )

    def to_dict(self):
        """Convert to dict for serialization or other uses"""
        return {
            "id": self.id,
            "application_id": self.application_id,
            "old_status": self.old_status,
            "new_status": self.new_status,
            "changed_at": self.changed_at.isoformat() if self.changed_at else None,
            "changed_by_id": self.changed_by_id,
            "changed_by_username": self.changed_by.username if self.changed_by else None,
            "job_id": getattr(self.application, 'job_id', None),
            "applicant_id": getattr(self.application, 'applicant_id', None),
        }


class SavedJob(models.Model):
    """
    Optimized model for tracking user-saved jobs with Redis synchronization.

    This model uses RedisSyncMixin to automatically keep Redis cache in sync
    with database changes. When a SavedJob is created, updated, or deleted,
    the Redis cache is automatically updated to reflect the changes.
    """

    # Redis sync settings
    redis_cache_prefix = "savedjob"
    redis_cache_timeout = 60 * 30  # 30 minutes
    redis_cache_permanent = False

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_jobs",
        db_index=True,  # Added for faster user lookups
    )
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="saved_by_users",
        db_index=True,  # Added for faster job lookups
    )
    saved_at = models.DateTimeField(
        auto_now_add=True, db_index=True  # Added for chronological sorting
    )
    notes = models.TextField(
        blank=True,
        null=True,
        max_length=500,
        help_text="Optional notes about why this job was saved",
    )

    class Meta:
        unique_together = ("user", "job")
        indexes = [
            # Composite index for common access patterns
            models.Index(fields=["user", "saved_at"]),
            models.Index(fields=["job", "saved_at"]),
        ]
        verbose_name = "Saved Job"
        verbose_name_plural = "Saved Jobs"
        ordering = ["-saved_at"]

    def __str__(self):
        return f"{self.user.email} saved {self.job.title} on {self.saved_at.date()}"

    def clean(self):
        """Additional validation"""
        super().clean()
        if self.notes and len(self.notes.strip()) == 0:
            self.notes = None  # Convert empty strings to None

    @classmethod
    def create_saved_job(cls, user, job, notes=None):
        """Atomic creation with validation"""
        with transaction.atomic():
            if cls.objects.filter(user=user, job=job).exists():
                raise ValidationError("This job is already saved by the user")
            saved_job = cls.objects.create(user=user, job=job, notes=notes)

            # Sync to Redis (handled automatically by RedisSyncMixin)
            return saved_job

    @property
    def job_details(self):
        """Quick access to frequently needed job information"""
        return {
            "title": self.job.title,
            "status": self.job.status,
            "date": self.job.date,
            "location": self.job.location,
        }

    def to_dict(self):
        """
        Convert SavedJob to dictionary for caching.

        This method is used by RedisSyncMixin to serialize the model
        for Redis caching.
        """
        return {
            "id": self.id,
            "user_id": self.user_id,
            "job_id": self.job_id,
            "saved_at": self.saved_at.isoformat() if self.saved_at else None,
            "notes": self.notes,
            "job_details": {
                "title": self.job.title,
                "status": self.job.status,
                "date": self.job.date.isoformat() if hasattr(self.job, 'date') and self.job.date else None,
                "location": self.job.location,
                "industry": self.job.industry.name if self.job.industry else None,
            }
        }

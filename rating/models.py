from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from jobs.models import *
# Local Imports
# from jobs.models import Job  


class Review(models.Model):
    """
    Enhanced user ratings and reviews with verification with Redis caching
    """

    # Redis caching configuration
    cache_enabled = True
    cache_related = ["reviewer", "reviewed"]
    cache_exclude = []
    job = models.ForeignKey("jobs.Job", on_delete=models.CASCADE, related_name="reviews")

    # job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="reviews")
    reviewed = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews_received",
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews_given"
    )
    review = models.CharField(max_length=20, blank=True, null=True)
    rating = models.DecimalField(
        max_digits=2,
        decimal_places=1,
        validators=[MinValueValidator(1.0), MaxValueValidator(5.0)],
    )
    feedback = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)
    response = models.TextField(blank=True, null=True)
    response_date = models.DateTimeField(blank=True, null=True)
    sentiment = models.CharField(max_length=20, blank=True, null=True)
    is_read = models.BooleanField(default=False)
    class Meta:
        unique_together = ('reviewer', 'reviewed', 'job')
        constraints = [
            models.CheckConstraint(
                check=models.Q(rating__gte=1.0) & models.Q(rating__lte=5.0),
                name="rating_range",
            ),
            models.UniqueConstraint(
                fields=["reviewer", "reviewed", "job"],  # add job here
                name="unique_rating_per_user_per_job",
            ),
        ]
        ordering = ["-created_at"]
        verbose_name = _("Review")
        verbose_name_plural = _("Reviews")
        indexes = [
            models.Index(fields=['reviewed_id']),
            models.Index(fields=['reviewer_id']),
            models.Index(fields=['job_id']),
            models.Index(fields=['created_at']),
            models.Index(fields=['reviewer_id', 'reviewed_id', 'job_id']),
        ]




    @classmethod
    def get_average_rating(cls, user):
        """
        Calculate the average rating for a user from all reviews.
        Returns a decimal rounded to 2 decimal places.
        """
        avg = cls.objects.filter(reviewed=user).aggregate(
            avg_rating=models.Avg("rating")
        )["avg_rating"]

        if avg is None:
            return Decimal("0.00")

        return Decimal(str(avg)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def __str__(self):
        return f"{self.reviewer.username} -> {self.reviewed.username} ({self.rating})"










class Feedback(models.Model):
    """
    Enhanced feedback system with categories with Redis caching
    """

    # Redis caching configuration
    cache_enabled = True
    cache_related = ["user"]
    cache_exclude = []

    class FeedbackCategory(models.TextChoices):
        GENERAL = "general", _("General")
        BUG = "bug", _("Bug Report")
        FEATURE = "feature", _("Feature Request")
        UI = "ui", _("User Interface")
        OTHER = "other", _("Other")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="feedbacks",
        null=True,
        blank=True,
    )
    category = models.CharField(
        max_length=10,
        choices=FeedbackCategory.choices,
        default=FeedbackCategory.GENERAL,
    )
    message = models.TextField()
    rating = models.IntegerField(
        default=5, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)
    admin_notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Feedback")
        verbose_name_plural = _("Feedbacks")

    def __str__(self):
        return f"{self.category} feedback from {self.user.username if self.user else 'Anonymous'}"

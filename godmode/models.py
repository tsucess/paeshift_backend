import json
import logging

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Avg, Count, Sum
from django.utils import timezone

User = get_user_model()
logger = logging.getLogger(__name__)


class SimulationRun(models.Model):
    """
    Model to track simulation runs initiated from the God Mode interface.
    """

    SIMULATION_TYPES = [
        ("admin", "Admin Registration"),
        ("client", "Client Registration"),
        ("applicant", "Applicant Registration"),
        ("job", "Job Creation"),
        ("application", "Job Application"),
        ("payment", "Payment Processing"),
        ("dispute", "Dispute Management"),
        ("location", "Location Streams"),
        ("webhook", "Payment Webhook"),
        ("full", "Full End-to-End Simulation"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    simulation_type = models.CharField(max_length=20, choices=SIMULATION_TYPES)
    parameters = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    result = models.JSONField(null=True, blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    initiated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="simulations"
    )

    def __str__(self):
        return f"{self.get_simulation_type_display()} - {self.started_at.strftime('%Y-%m-%d %H:%M')}"

    class Meta:
        ordering = ["-started_at"]
        verbose_name = "Simulation Run"
        verbose_name_plural = "Simulation Runs"


class UserActivityLog(models.Model):
    """
    Model to track detailed user activity for God Mode monitoring.
    This is separate from the gamification UserActivity model and provides more detailed tracking.
    """

    ACTION_TYPES = [
        ("login", "Login"),
        ("logout", "Logout"),
        ("view_profile", "View Profile"),
        ("update_profile", "Update Profile"),
        ("view_job", "View Job"),
        ("create_job", "Create Job"),
        ("apply_job", "Apply to Job"),
        ("payment", "Payment"),
        ("message", "Message"),
        ("location_update", "Location Update"),
        ("dispute", "Dispute Action"),
        ("admin_action", "Admin Action"),
        ("simulation", "Run Simulation"),
        ("other", "Other"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="godmode_activity_logs"
    )
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    timestamp = models.DateTimeField(default=timezone.now)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    details = models.JSONField(default=dict)

    def __str__(self):
        return f"{self.user.username} - {self.get_action_type_display()} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "User Activity Log"
        verbose_name_plural = "User Activity Logs"


class LocationVerification(models.Model):
    """
    Model to store location verification results for comparing claimed addresses with location history.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("verified", "Verified"),
        ("suspicious", "Suspicious"),
        ("invalid", "Invalid"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="location_verifications"
    )
    claimed_address = models.TextField()
    claimed_latitude = models.FloatField(null=True, blank=True)
    claimed_longitude = models.FloatField(null=True, blank=True)
    actual_locations = models.JSONField(default=list)  # List of location history points
    verification_status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending"
    )
    verification_details = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="verifications_performed",
    )

    def __str__(self):
        return f"Location Verification for {self.user.username} - {self.get_verification_status_display()}"

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Location Verification"
        verbose_name_plural = "Location Verifications"


class WebhookLog(models.Model):
    """
    Model to store logs of payment webhook calls for monitoring and debugging.
    """

    STATUS_CHOICES = [
        ("success", "Success"),
        ("failed", "Failed"),
        ("pending", "Pending"),
        ("error", "Error"),
    ]

    GATEWAY_CHOICES = [
        ("paystack", "Paystack"),
        ("flutterwave", "Flutterwave"),
        ("other", "Other"),
    ]

    reference = models.CharField(max_length=100)
    gateway = models.CharField(max_length=20, choices=GATEWAY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    request_data = models.JSONField(default=dict)
    response_data = models.JSONField(default=dict)
    error_message = models.TextField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Webhook {self.reference} - {self.get_status_display()}"

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Webhook Log"
        verbose_name_plural = "Webhook Logs"


class WorkAssignment(models.Model):
    """
    Model to track work assignments for admin staff.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("urgent", "Urgent"),
    ]

    TYPE_CHOICES = [
        ("dispute", "Dispute Resolution"),
        ("verification", "User Verification"),
        ("payment", "Payment Issue"),
        ("support", "Customer Support"),
        ("other", "Other"),
    ]

    admin = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="work_assignments"
    )
    assigned_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="assigned_work"
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    task_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    priority = models.CharField(
        max_length=20, choices=PRIORITY_CHOICES, default="medium"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    related_object_type = models.CharField(max_length=50, null=True, blank=True)
    related_object_id = models.IntegerField(null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.title} - {self.admin.username}"

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Work Assignment"
        verbose_name_plural = "Work Assignments"


class DataExportConfig(models.Model):
    """
    Model to store configurations for data exports.
    """

    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    model_name = models.CharField(max_length=100)
    fields = models.JSONField()
    filters = models.JSONField(default=dict)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="export_configs"
    )
    created_at = models.DateTimeField(default=timezone.now)
    last_used = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} - {self.model_name}"

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Data Export Configuration"
        verbose_name_plural = "Data Export Configurations"


class DataExport(models.Model):
    """
    Model to track data exports.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    config = models.ForeignKey(
        DataExportConfig, on_delete=models.SET_NULL, null=True, related_name="exports"
    )
    file_name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    row_count = models.IntegerField(default=0)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="data_exports"
    )
    created_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.file_name} - {self.get_status_display()}"

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Data Export"
        verbose_name_plural = "Data Exports"


class UserRanking(models.Model):
    """
    Model to store user rankings based on various metrics.
    """

    RANKING_TYPE_CHOICES = [
        ("points", "Gamification Points"),
        ("payments", "Total Payments"),
        ("jobs_created", "Jobs Created"),
        ("jobs_completed", "Jobs Completed"),
        ("applications", "Applications Submitted"),
        ("activity", "Activity Level"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="rankings")
    ranking_type = models.CharField(max_length=20, choices=RANKING_TYPE_CHOICES)
    rank = models.IntegerField()
    score = models.FloatField()
    percentile = models.FloatField(null=True, blank=True)
    previous_rank = models.IntegerField(null=True, blank=True)
    previous_score = models.FloatField(null=True, blank=True)
    updated_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.username} - {self.get_ranking_type_display()} - Rank {self.rank}"

    class Meta:
        ordering = ["ranking_type", "rank"]
        verbose_name = "User Ranking"
        verbose_name_plural = "User Rankings"
        unique_together = ("user", "ranking_type")


class MFASecret(models.Model):
    """
    Model to store MFA secrets for users.
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="mfa_secret")
    secret = models.CharField(max_length=255)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    last_used = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"MFA Secret for {self.user.username}"

    class Meta:
        verbose_name = "MFA Secret"
        verbose_name_plural = "MFA Secrets"

    def save(self, *args, **kwargs):
        """Override save to log MFA changes."""
        is_new = self.pk is None
        super().save(*args, **kwargs)

        if is_new:
            logger.info(f"MFA enabled for user {self.user.id}")

    def delete(self, *args, **kwargs):
        """Override delete to log MFA changes."""
        user_id = self.user.id
        super().delete(*args, **kwargs)
        logger.info(f"MFA disabled for user {user_id}")


class AuditLog(models.Model):
    """
    Model to store immutable audit logs for God Mode operations.
    """

    ACTION_TYPES = [
        ("login", "Login"),
        ("logout", "Logout"),
        ("view", "View Data"),
        ("create", "Create Data"),
        ("update", "Update Data"),
        ("delete", "Delete Data"),
        ("export", "Export Data"),
        ("import", "Import Data"),
        ("admin", "Admin Action"),
        ("security", "Security Event"),
        ("mfa", "MFA Event"),
        ("other", "Other"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="audit_logs"
    )
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    action = models.CharField(max_length=255)
    object_type = models.CharField(max_length=100, null=True, blank=True)
    object_id = models.CharField(max_length=100, null=True, blank=True)
    details = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.get_action_type_display()}: {self.action} by {self.user.username if self.user else 'Unknown'}"

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"

    def save(self, *args, **kwargs):
        """Override save to ensure immutability."""
        if self.pk:
            # Prevent updates to existing records
            logger.warning(f"Attempted to update immutable audit log {self.pk}")
            return

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Override delete to prevent deletion."""
        logger.warning(f"Attempted to delete immutable audit log {self.pk}")
        return


class IPWhitelist(models.Model):
    """
    Model to store IP whitelist for God Mode access.
    """

    ip_address = models.CharField(max_length=50, unique=True)
    description = models.CharField(max_length=255, null=True, blank=True)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="created_ip_whitelist"
    )
    last_used = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.ip_address} - {self.description or 'No description'}"

    class Meta:
        verbose_name = "IP Whitelist"
        verbose_name_plural = "IP Whitelist"
        ordering = ["ip_address"]

    def save(self, *args, **kwargs):
        """Override save to invalidate cache."""
        super().save(*args, **kwargs)

        # Invalidate cache
        from godmode.ip_restrictions import invalidate_ip_whitelist_cache
        invalidate_ip_whitelist_cache()

    def delete(self, *args, **kwargs):
        """Override delete to invalidate cache."""
        super().delete(*args, **kwargs)

        # Invalidate cache
        from godmode.ip_restrictions import invalidate_ip_whitelist_cache
        invalidate_ip_whitelist_cache()

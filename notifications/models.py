from django.conf import settings
from django.db import models


# =
# 🔹 ENUM CLASS: Notification Categories
# =
class NotificationCategory(models.TextChoices):
    NEW_JOB_ALERT = "new_job_alert", "New Job Alert"
    JOB_REMINDER = "job_reminder", "Job Reminder"
    JOB_ACCEPTANCE = "job_acceptance", "Job Request Acceptance"
    SETTINGS_CHANGES = "settings_changes", "Settings Changes"


# =
# 🔹 MODEL: User Notifications
# =
class Notification(models.Model):
    """
    Stores notifications for users.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    category = models.CharField(max_length=50, choices=NotificationCategory.choices)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(null=True, blank=True, help_text="Additional data for the notification")
    title = models.CharField(max_length=50, blank=True, null=True)
    navigate_url = models.CharField(max_length=300, default="/", blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]  # Sort notifications by newest first

    def __str__(self):
        return f"Notification for {self.user.username}: {self.category} - {self.message[:50]}"

    def mark_as_read(self):
        """Mark notification as read."""
        self.is_read = True
        self.save(update_fields=["is_read"])

    @property
    def viewed(self):
        return not self.is_read

    @viewed.setter
    def viewed(self, value):
        self.is_read = not value











# =
# 🔹 MODEL: Notification Preferences
# =
def default_push_preferences():
    """Return default push notification settings."""
    return {
        "new_job_alert": True,
        "job_reminder": True,
        "job_acceptance": True,
        "settings_changes": True,
    }


def default_email_preferences():
    """Return default email notification settings."""
    return {
        "new_job_alert": True,
        "job_reminder": True,
        "job_acceptance": True,
        "settings_changes": True,
    }


class NotificationPreference(models.Model):
    """
    Stores user preferences for email and push notifications.
    Uses JSON fields for flexibility and future expansion.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
    )

    # Push Notification Preferences
    push_preferences = models.JSONField(default=default_push_preferences)

    # Email Notification Preferences
    email_preferences = models.JSONField(default=default_email_preferences)

    class Meta:
        verbose_name = "Notification Preference"
        verbose_name_plural = "Notification Preferences"

    def __str__(self):
        return f"Notification Preferences for {self.user.username}"

    # =
    # 🔹 UPDATE NOTIFICATION PREFERENCES
    # =
    def update_preferences(self, preference_type: str, category: str, value: bool):
        """
        Update a specific notification preference.

        :param preference_type: "push" or "email"
        :param category: Notification category (e.g., "new_job_alert")
        :param value: True (enable) or False (disable)
        """
        if preference_type not in ["push", "email"]:
            raise ValueError("Preference type must be 'push' or 'email'")

        if category not in NotificationCategory.values:
            raise ValueError(f"Invalid notification category: {category}")

        if preference_type == "push":
            self.push_preferences[category] = value
        elif preference_type == "email":
            self.email_preferences[category] = value

        self.save(update_fields=[f"{preference_type}_preferences"])

    # =
    # 🔹 CHECK IF A USER WANTS NOTIFICATIONS
    # =
    def is_notification_enabled(self, preference_type: str, category: str) -> bool:
        """
        Check if a user has enabled a particular notification type.
        """
        if preference_type not in ["push", "email"]:
            return False  # Invalid preference type

        return (
            self.push_preferences.get(category, False)
            if preference_type == "push"
            else self.email_preferences.get(category, False)
        )

from datetime import datetime
from typing import Optional, Literal

from ninja import Schema
from pydantic import Field

from core.schema_utils import HashableSchema


# ==
# 📌 Notification Schemas
# ==
class NotificationSchema(HashableSchema):
    """Schema for notification data with read status"""

    id: int
    message: str = Field(..., min_length=5, max_length=500)
    is_read: bool = Field(default=False)
    created_at: datetime
    notification_type: str = Field(
        ...,
        description="Type of notification",
        examples=["job_alert", "payment", "system", "message"],
    )
    metadata: Optional[dict] = Field(
        None, description="Additional context data for the notification"
    )


class NotificationSettingsSchema(HashableSchema):
    """Schema for user notification preferences"""

    push_new_job_alert: bool = Field(default=True)
    push_job_reminder: bool = Field(default=True)
    push_job_acceptance: bool = Field(default=True)
    push_settings_changes: bool = Field(default=True)
    email_new_job_alert: bool = Field(default=False)
    email_job_reminder: bool = Field(default=False)
    email_job_acceptance: bool = Field(default=True)
    email_settings_changes: bool = Field(default=True)
    sms_urgent_alerts: bool = Field(
        default=False, description="Receive SMS for critical notifications"
    )


class NotificationUpdateSchema(HashableSchema):
    """Schema for marking notifications as read"""

    notification_ids: list[int] = Field(
        ..., min_items=1, description="List of notification IDs to update"
    )
    mark_as_read: bool = Field(
        default=True, description="True to mark as read, False to mark as unread"
    )


class NotificationCountResponse(HashableSchema):
    """Response schema for unread notification count"""

    total_unread: int = Field(..., ge=0)
    unread_by_type: dict[str, int] = Field(
        default_factory=dict, description="Count of unread notifications by type"
    )


class SinglePreferenceUpdateSchema(HashableSchema):
    """Schema for updating a single notification preference"""

    preference_type: Literal["push", "email"] = Field(
        ..., description="Type of notification preference (push or email)"
    )
    category: str = Field(
        ..., description="Category of notification (e.g., job_acceptance, new_job_alert)"
    )
    value: bool = Field(
        ..., description="Whether the notification is enabled (true) or disabled (false)"
    )

# Dispute/models.py

import os
from decimal import Decimal
from pathlib import Path

import django
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from geopy.geocoders import Nominatim

from accounts.models import CustomUser as User
from jobs.models import *


# Create your models here.
# ------------------------------------------------------
# 5️⃣ Dispute Model
# ------------------------------------------------------
class Dispute(models.Model):
    """Represents a dispute raised regarding a Job or Application."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ASSIGNED = "assigned", "Assigned"
        IN_REVIEW = "in_review", "In Review"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"
        ESCALATED = "escalated", "Escalated"

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="disputes")
    application = models.ForeignKey(
        "jobs.Application",
        on_delete=models.CASCADE,
        related_name="disputes",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="disputes_raised"
    )
    title = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True
    )
    assigned_admin = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="disputes_assigned",
    )
    reason = models.TextField(null=True, blank=True)
    resolution = models.TextField(blank=True, null=True)
    resolution_notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(blank=True, null=True)
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="disputes_resolved",
    )

    def __str__(self):
        return f"Dispute #{self.id} - {self.title} ({self.status})"

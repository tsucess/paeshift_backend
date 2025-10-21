# jobs/admin.py

from django.contrib import admin

from django.utils.html import format_html

from .models import *


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin for Ratings & Reviews."""

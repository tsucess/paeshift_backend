from django.contrib import admin

from .models import LocationHistory, Message


@admin.register(LocationHistory)
class LocationHistoryAdmin(admin.ModelAdmin):
    """Admin panel customization for tracking user locations."""

    list_display = ("user", "job", "latitude", "longitude", "timestamp")
    list_filter = ("job", "user", "timestamp")
    search_fields = ("user__username", "job__title")
    ordering = ("-timestamp",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """Admin panel customization for chat messages."""

    list_display = ("sender", "job", "content", "timestamp")
    list_filter = ("job", "sender", "timestamp")
    search_fields = ("sender__username", "job__title", "content")
    ordering = ("-timestamp",)

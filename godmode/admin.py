from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import (DataExport, DataExportConfig, LocationVerification,
                     SimulationRun, UserActivityLog, UserRanking, WebhookLog,
                     WorkAssignment)


@admin.register(SimulationRun)
class SimulationRunAdmin(admin.ModelAdmin):
    list_display = (
        "simulation_type_display",
        "status",
        "started_at",
        "completed_at",
        "initiated_by",
    )
    list_filter = ("simulation_type", "status", "started_at")
    search_fields = ("simulation_type", "initiated_by__username")
    readonly_fields = ("started_at", "completed_at")

    def simulation_type_display(self, obj):
        return obj.get_simulation_type_display()

    simulation_type_display.short_description = "Simulation Type"

    def has_delete_permission(self, request, obj=None):
        # Only allow deletion of failed simulations
        if obj and obj.status == "failed":
            return True
        return False


@admin.register(UserActivityLog)
class UserActivityLogAdmin(admin.ModelAdmin):
    list_display = ("user", "action_type_display", "timestamp", "ip_address")
    list_filter = ("action_type", "timestamp", "user__role")
    search_fields = ("user__username", "user__email", "ip_address")
    readonly_fields = ("timestamp",)

    def action_type_display(self, obj):
        return obj.get_action_type_display()

    action_type_display.short_description = "Action Type"


@admin.register(LocationVerification)
class LocationVerificationAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "claimed_address_short",
        "verification_status",
        "created_at",
        "verified_by",
    )
    list_filter = ("verification_status", "created_at")
    search_fields = ("user__username", "user__email", "claimed_address")
    readonly_fields = ("created_at",)

    def claimed_address_short(self, obj):
        if len(obj.claimed_address) > 50:
            return f"{obj.claimed_address[:50]}..."
        return obj.claimed_address

    claimed_address_short.short_description = "Claimed Address"


@admin.register(WebhookLog)
class WebhookLogAdmin(admin.ModelAdmin):
    list_display = ("reference", "gateway", "status", "created_at", "ip_address")
    list_filter = ("gateway", "status", "created_at")
    search_fields = ("reference", "error_message")
    readonly_fields = ("created_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(WorkAssignment)
class WorkAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "admin",
        "task_type",
        "priority",
        "status",
        "due_date",
        "created_at",
    )
    list_filter = ("task_type", "priority", "status", "created_at")
    search_fields = ("title", "description", "admin__username", "assigned_by__username")
    readonly_fields = ("created_at",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(admin=request.user)


@admin.register(DataExportConfig)
class DataExportConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "model_name", "created_by", "created_at", "last_used")
    list_filter = ("model_name", "created_at")
    search_fields = ("name", "description", "model_name", "created_by__username")
    readonly_fields = ("created_at", "last_used")


@admin.register(DataExport)
class DataExportAdmin(admin.ModelAdmin):
    list_display = (
        "file_name",
        "config",
        "status",
        "row_count",
        "created_by",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("file_name", "created_by__username")
    readonly_fields = ("created_at", "completed_at", "row_count")

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(UserRanking)
class UserRankingAdmin(admin.ModelAdmin):
    list_display = ("user", "ranking_type", "rank", "score", "percentile", "updated_at")
    list_filter = ("ranking_type", "updated_at")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

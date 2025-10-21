# jobs/admin.py

from django.conf import settings
from django.contrib import admin
from django.utils.html import format_html

from accounts.models import Profile
from jobs.models import Job, JobIndustry, JobSubCategory, SavedJob, Application
from rating.models import Review

from .models import *




@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    """Admin for Job Postings."""

    list_display = (
        "title",
        "client",
        "status",
        "payment_status",
        "industry",
        "subcategory",
        "rate",
        "applicants_needed",
        "job_type",
        "shift_type",
        "created_at",
    )

    readonly_fields = ("created_at", "updated_at")  # 🛠️ Fix: Make created_at read-only

    list_filter = (
    "title",
    "client",
    "status",
    "payment_status",
    "industry",
    "subcategory",
    "rate",
    "applicants_needed",
    "job_type",
    "shift_type",
    "created_at",
    )


@admin.register(JobIndustry)
class JobIndustryAdmin(admin.ModelAdmin):
    """Admin for Job Industries."""

    list_display = ("name",)
    search_fields = ("name",)
    list_per_page = 20


@admin.register(JobSubCategory)
class JobSubCategoryAdmin(admin.ModelAdmin):
    """Admin for Job Subcategories."""

    list_display = ("name", "industry")
    list_filter = ("industry",)
    search_fields = ("name", "industry__name")
    list_per_page = 20


@admin.register(SavedJob)
class SavedJobAdmin(admin.ModelAdmin):
    """Admin for Saved Jobs."""

    list_display = ("user", "job", "saved_at")
    search_fields = ("user__username", "job__title")
    readonly_fields = ("saved_at",)
    list_per_page = 20


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    """Admin for Job Applications."""
    list_display = ("applicant", "job", "status", "is_shown_up", "rating", "applied_at")
    list_filter = ("status", "is_shown_up")
    search_fields = ("applicant__username", "job__title")
    readonly_fields = ("applied_at",)
    list_per_page = 20


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    """Admin for Ratings & Reviews."""

    list_display = ("reviewer", "reviewed", "rating", "created_at")
    list_filter = ("rating",)
    search_fields = ("reviewer__username", "reviewed__username")
    readonly_fields = ("created_at",)
    list_per_page = 20


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """Admin for User Profiles."""

    list_display = ("user", "role", "balance", "profile_pic_preview")
    list_filter = ("role",)
    search_fields = ("user__username", "role")
    readonly_fields = ("profile_pic_preview",)
    list_per_page = 20

    def profile_pic_preview(self, obj):
        # Get the active profile picture
        pic = obj.pictures.filter(is_active=True).first()
        if pic and pic.image:
            return format_html(
                '<img src="{}" style="max-height: 50px; max-width: 50px;" />',
                pic.image.url,
            )
        return "-"

    profile_pic_preview.short_description = "Profile Picture"

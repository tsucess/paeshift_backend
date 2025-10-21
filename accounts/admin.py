from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .models import CustomUser, GoogleAuthSession
from .forms import CustomUserCreationForm, CustomUserChangeForm

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser
    list_display = ("email", "username", "is_staff", "is_active")
    list_filter = ("is_staff", "is_active")
    fieldsets = (
        (None, {"fields": ("email", "username", "password")} ),
        (_("Personal info"), {"fields": ("first_name", "last_name")} ),
        (_("Permissions"), {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")} ),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "username", "password1", "password2", "is_staff", "is_active"),
        }),
    )
    search_fields = ("email", "username")
    ordering = ("email",)

@admin.register(GoogleAuthSession)
class GoogleAuthSessionAdmin(admin.ModelAdmin):
    """Admin interface for Google Authentication Sessions."""
    list_display = ('user', 'google_email', 'is_active', 'created_at', 'last_used', 'ip_address')
    list_filter = ('is_active', 'created_at', 'last_used')
    search_fields = ('user__email', 'google_email', 'google_user_id')
    readonly_fields = ('created_at', 'last_used')
    date_hierarchy = 'created_at'

    fieldsets = (
        (None, {'fields': ('user', 'is_active')}),
        ('Google Account Information', {'fields': ('google_email', 'google_user_id')}),
        ('Session Information', {'fields': ('created_at', 'last_used', 'ip_address', 'user_agent')}),
        ('Token Information', {'fields': ('access_token', 'refresh_token', 'token_expiry'), 'classes': ('collapse',)}),
    )

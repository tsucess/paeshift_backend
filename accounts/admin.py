from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from django.db import transaction
from django.apps import apps
from django.contrib import messages
import logging

from .models import CustomUser, GoogleAuthSession
from .forms import CustomUserCreationForm, CustomUserChangeForm

logger = logging.getLogger(__name__)


def delete_users_with_cascade(modeladmin, request, queryset):
    """
    Custom delete action that properly handles cascading deletion for CustomUser.
    This is necessary for SQLite which enforces foreign key constraints.
    """
    # Convert queryset to list to avoid issues with queryset modification during iteration
    users_to_delete = list(queryset)
    total_users = len(users_to_delete)
    deleted_count = 0
    error_count = 0
    errors = []

    logger.info(f"Starting deletion of {total_users} user(s)")

    for user in users_to_delete:
        user_email = user.email
        user_id = user.id
        logger.info(f"Processing deletion for user: {user_email} (ID: {user_id})")

        try:
            with transaction.atomic():
                # Delete related objects in the correct order
                # 1. Delete notifications
                try:
                    from notifications.models import Notification, NotificationPreference
                    Notification.objects.filter(user=user).delete()
                    NotificationPreference.objects.filter(user=user).delete()
                except ImportError:
                    pass

                # 2. Delete job-related data
                try:
                    from jobs.models import Application, SavedJob, Job
                    Application.objects.filter(applicant=user).delete()
                    SavedJob.objects.filter(user=user).delete()
                    # Delete jobs created by or assigned to this user
                    Job.objects.filter(created_by=user).delete()
                    Job.objects.filter(selected_applicant=user).delete()
                except ImportError:
                    pass

                # 3. Delete payment data
                try:
                    from payment.models import Payment
                    Payment.objects.filter(payer=user).delete()
                    Payment.objects.filter(recipient=user).delete()
                except ImportError:
                    pass

                # 4. Delete rating/feedback data
                try:
                    from rating.models import Review, Feedback
                    Review.objects.filter(reviewer=user).delete()
                    Review.objects.filter(reviewed=user).delete()
                    Feedback.objects.filter(user=user).delete()
                except ImportError:
                    pass

                # 5. Delete chat messages and location history
                try:
                    from jobchat.models import Message, LocationHistory
                    Message.objects.filter(sender=user).delete()
                    LocationHistory.objects.filter(user=user).delete()
                except ImportError:
                    pass

                # 6. Delete gamification data
                try:
                    from gamification.models import UserActivity, UserReward, UserPoints
                    UserActivity.objects.filter(user=user).delete()
                    UserReward.objects.filter(user=user).delete()
                    UserPoints.objects.filter(user=user).delete()
                except ImportError:
                    pass

                # 7. Delete godmode data (rankings and MFA secrets)
                try:
                    from godmode.models import Ranking, MFASecret
                    Ranking.objects.filter(user=user).delete()
                    MFASecret.objects.filter(user=user).delete()
                except ImportError:
                    pass

                # 8. Delete allauth user sessions
                try:
                    from allauth.usersessions.models import UserSession
                    UserSession.objects.filter(user=user).delete()
                except (ImportError, Exception):
                    # Catch both ImportError and ImproperlyConfigured
                    pass

                # 9. Delete Google auth sessions
                GoogleAuthSession.objects.filter(user=user).delete()

                # 10. Delete OTP records
                from .models import OTP
                OTP.objects.filter(user=user).delete()

                # 11. Delete profile (has CASCADE, but delete explicitly to be safe)
                if hasattr(user, 'profile'):
                    user.profile.delete()

                # 12. Finally delete the user
                logger.info(f"About to delete user object: {user_email} (ID: {user_id})")
                user.delete()
                deleted_count += 1
                logger.info(f"[SUCCESS] Successfully deleted user: {user_email} (ID: {user_id})")

        except Exception as e:
            error_count += 1
            error_msg = f"Error deleting user {user_email} (ID: {user_id}): {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg, exc_info=True)

    # Show appropriate message to user
    logger.info(f"Deletion complete: {deleted_count} deleted, {error_count} failed")

    if deleted_count > 0:
        modeladmin.message_user(
            request,
            f"[SUCCESS] Successfully deleted {deleted_count} user(s) and all related data.",
            messages.SUCCESS
        )

    if error_count > 0:
        error_details = "\n".join(errors)
        modeladmin.message_user(
            request,
            f"[ERROR] Failed to delete {error_count} user(s):\n{error_details}",
            messages.ERROR
        )

    if deleted_count == 0 and error_count == 0:
        modeladmin.message_user(
            request,
            "[WARNING] No users were selected for deletion.",
            messages.WARNING
        )


delete_users_with_cascade.short_description = "Delete selected users and all related data"


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
    actions = [delete_users_with_cascade]

    def get_actions(self, request):
        """Override to remove Django's default delete_selected action"""
        actions = super().get_actions(request)
        # Remove the default delete_selected action
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def delete_model(self, request, obj):
        """Override delete_model to use our custom cascade deletion"""
        logger.info(f"Starting deletion of user: {obj.email} (ID: {obj.id})")
        try:
            with transaction.atomic():
                # Delete related objects in the correct order
                # 1. Delete notifications
                try:
                    from notifications.models import Notification, NotificationPreference
                    Notification.objects.filter(user=obj).delete()
                    NotificationPreference.objects.filter(user=obj).delete()
                except ImportError:
                    pass

                # 2. Delete job-related data
                try:
                    from jobs.models import Application, SavedJob, Job
                    Application.objects.filter(applicant=obj).delete()
                    SavedJob.objects.filter(user=obj).delete()
                    Job.objects.filter(created_by=obj).delete()
                    Job.objects.filter(selected_applicant=obj).delete()
                except ImportError:
                    pass

                # 3. Delete payment data
                try:
                    from payment.models import Payment
                    Payment.objects.filter(payer=obj).delete()
                    Payment.objects.filter(recipient=obj).delete()
                except ImportError:
                    pass

                # 4. Delete rating/feedback data
                try:
                    from rating.models import Review, Feedback
                    Review.objects.filter(reviewer=obj).delete()
                    Review.objects.filter(reviewed=obj).delete()
                    Feedback.objects.filter(user=obj).delete()
                except ImportError:
                    pass

                # 5. Delete chat messages and location history
                try:
                    from jobchat.models import Message, LocationHistory
                    Message.objects.filter(sender=obj).delete()
                    LocationHistory.objects.filter(user=obj).delete()
                except ImportError:
                    pass

                # 6. Delete gamification data
                try:
                    from gamification.models import UserActivity, UserReward, UserPoints
                    UserActivity.objects.filter(user=obj).delete()
                    UserReward.objects.filter(user=obj).delete()
                    UserPoints.objects.filter(user=obj).delete()
                except ImportError:
                    pass

                # 7. Delete godmode data
                try:
                    from godmode.models import Ranking, MFASecret
                    Ranking.objects.filter(user=obj).delete()
                    MFASecret.objects.filter(user=obj).delete()
                except ImportError:
                    pass

                # 8. Delete allauth user sessions
                try:
                    from allauth.usersessions.models import UserSession
                    UserSession.objects.filter(user=obj).delete()
                except (ImportError, Exception):
                    # Catch both ImportError and ImproperlyConfigured
                    pass

                # 9. Delete Google auth sessions
                GoogleAuthSession.objects.filter(user=obj).delete()

                # 10. Delete OTP records
                from .models import OTP
                OTP.objects.filter(user=obj).delete()

                # 11. Delete profile
                if hasattr(obj, 'profile'):
                    obj.profile.delete()

                # 12. Finally delete the user
                logger.info(f"About to delete user object: {obj.email}")
                obj.delete()
                logger.info(f"Successfully deleted user: {obj.email}")
        except Exception as e:
            logger.error(f"Error deleting user {obj.email}: {str(e)}", exc_info=True)
            raise

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

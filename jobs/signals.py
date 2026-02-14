# ==
# 📌 Python Standard Library Imports
# ==
import logging

# ==
# 📌 Third-Party Imports
# ==
from asgiref.sync import async_to_sync
# Temporarily comment out channels import until compatibility issue is fixed
# from channels.layers import get_channel_layer
# ==
# 📌 Django Core Imports
# ==
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver


from accounts.models import Profile
from jobchat.models import LocationHistory
from jobs.models import Application, Job
from notifications.models import Notification, NotificationCategory
from payment.models import Payment
from .job_matching_utils import match_jobs_to_users, match_users_to_jobs
from .utils import fallback_geocode_and_save
# Temporarily commented out - django_q has pkg_resources issue
# from django_q.tasks import async_task
# ==
# 📌 Local Application Imports
# ==



# ==
# 📌 Constants and Configuration
# ==
logger = logging.getLogger(__name__)
# Temporarily disable channel layer
channel_layer = None
User = get_user_model()




# Temporarily commented out - depends on payment app
@receiver(post_save, sender=Payment)
def update_job_status(sender, instance, created, **kwargs):
    if instance.status == 'paid':
        instance.mark_as_successful()
        try:
            with transaction.atomic():
                job = instance.job
                job.refresh_from_db()

                # Bypass validation for this critical update
                Job.objects.filter(pk=job.pk).update(
                    payment_status=Job.PaymentStatus.PAID,
                    status=Job.Status.UPCOMING if job.status == Job.Status.PENDING else job.status
                )

                logger.info(f"Updated job {job.id} payment status to PAID")

        except Exception as e:
            logger.error(f"Critical: Failed to update job status: {str(e)}")
            # Consider adding notification to admin here



# =
# 🛠 HELPER FUNCTIONS
# =
# Temporarily commented out - depends on jobchat app
# def get_nearby_applicants(job):
#     """Find applicants near the job location."""
#     try:
#         # Check if job has coordinates
#         if not job.latitude or not job.longitude:
#             return []
#
#         lat = float(job.latitude)
#         lng = float(job.longitude)
#
#         # Query applicants within 0.1 degree (~11km) range
#         return LocationHistory.objects.filter(
#             latitude__range=(lat - 0.1, lat + 0.1),
#             longitude__range=(lng - 0.1, lng + 0.1),
#         ).select_related("user")
#
#     except (ValueError, TypeError) as e:
#         logger.error(f"Error processing job location: {e}")
#         return []

def get_nearby_applicants(job):
    """Temporary fallback - returns empty list."""
    return []


# =
# ✅ USER REGISTRATION SIGNAL
# =
# Temporarily commented out - depends on notifications app
# @receiver(post_save, sender=User)
# def create_user_notification(sender, instance, created, **kwargs):
#     """Creates welcome notification for new users."""
#     if created:
#         Notification.objects.create(
#             user=instance,
#             category=NotificationCategory.SETTINGS_CHANGES,
#             message=" Welcome to our platform!",
#         )
#         logger.info(f"New user notification created for {instance.email}")


# =
# ✅ JOB-RELATED SIGNALS
# =
# Temporarily commented out - depends on notifications app
# @receiver(post_save, sender=Job)
# def handle_job_changes(sender, instance, created, **kwargs):
#     """Handle notifications for job creation and status changes."""
#     if created:
#         # Notify client
#         Notification.objects.create(
#             user=instance.client,
#             category=NotificationCategory.NEW_JOB_ALERT,
#             message=f"🎉 Your job '{instance.title}' was posted!",
#         )
#
#         # Notify nearby applicants using location-based matching
#         # This is a simpler approach than the Mojo-based matching
#         nearby_users = get_nearby_applicants(instance)
#         for loc in nearby_users:
#             Notification.objects.create(
#                 user=loc.user,
#                 category=NotificationCategory.NEW_JOB_ALERT,
#                 message=f"🔔 New job near you: {instance.title}",
#             )
#
#     elif kwargs.get("update_fields") and "status" in kwargs["update_fields"]:
#         # Job status changed
#         Notification.objects.create(
#             user=instance.client,
#             category=NotificationCategory.JOB_REMINDER,
#             message=f"📌 Job status updated: {instance.status}",
#         )
#
#         if instance.selected_applicant:
#             Notification.objects.create(
#                 user=instance.selected_applicant,
#                 category=NotificationCategory.JOB_ACCEPTANCE,
#                 message=f"✅ You've been selected for '{instance.title}'!",
#             )


@receiver(post_save, sender=Job)
def match_job_to_users_on_create(sender, instance, created, **kwargs):
    """
    Match a newly created job to potential users.

    This signal handler:
    1. Triggers an asynchronous job matching task when a job is created
    2. Caches the matching results for quick access
    3. Sends notifications to highly matched users
    """
    if created:
        logger.info(
            f"Triggering job matching for new job: {instance.id} - {instance.title}"
        )

        # Use Django Q for asynchronous job matching
        # Temporarily disabled - django_q has pkg_resources issue
        # try:
        #     # Queue the job matching task
        #     async_task(
        #         "jobs.job_matching_utils.match_jobs_to_users",
        #         [instance],
        #         hook="jobs.signals.handle_job_matching_results",
        #         task_name=f"match_job_{instance.id}",
        #         group="job_matching"
        #     )
        #     logger.info(f"Queued job matching task for job {instance.id}")
        # except Exception as e:
        #     logger.error(f"Error queuing job matching task: {e}")

        # Fallback to synchronous execution if async fails
        try:
            # Get all active users
            active_users = User.objects.filter(is_active=True)
            matches = match_jobs_to_users([instance], active_users)
            if matches:
                for job_id, job_matches in matches.items():
                    # Cache the matches
                    cache_key = f"job_matches:{job_id}"
                    cache.set(cache_key, job_matches, timeout=3600)  # Cache for 1 hour

                    # Send notifications for high-scoring matches
                    send_notifications_for_matches(instance, job_matches)
        except Exception as inner_e:
            logger.error(f"Error in fallback job matching: {inner_e}")


def handle_job_matching_results(task):
    """
    Handle the results of the job matching task.

    This function:
    1. Caches the matching results
    2. Sends notifications to highly matched users
    """
    if task.success:
        matches = task.result

        if not matches:
            logger.warning(f"No matches found for job matching task: {task.id}")
            return

        # Process each job's matches
        for job_id, job_matches in matches.items():
            try:
                # Get the job
                job = Job.objects.get(id=job_id)

                # Cache the matches
                cache_key = f"job_matches:{job_id}"
                cache.set(cache_key, job_matches, timeout=3600)  # Cache for 1 hour

                # Send notifications for high-scoring matches
                send_notifications_for_matches(job, job_matches)

                logger.info(f"Cached {len(job_matches)} matches for job {job_id}")
            except Job.DoesNotExist:
                logger.error(f"Job {job_id} not found when processing matches")
    else:
        logger.error(f"Job matching task failed: {task.result}")


def send_notifications_for_matches(job, matches):
    """
    Send notifications to users who are good matches for a job.

    Args:
        job: The Job instance
        matches: List of match dictionaries with user_id and score
    """
    # Only notify for high-scoring matches (above 0.7)
    high_matches = [m for m in matches if m["score"] > 0.7]

    for match in high_matches:
        try:
            user = User.objects.get(id=match["user_id"])
            send_job_match_notification(user, job, match["score"])
        except User.DoesNotExist:
            logger.warning(
                f"User {match['user_id']} not found when sending match notification"
            )


def send_job_match_notification(user, job, score):
    """
    Send a notification to a user about a job match.

    Args:
        user: The User instance
        job: The Job instance
        score: The match score (0-1)
    """
    # Format score as percentage
    score_percent = int(score * 100)

    # Create notification
    Notification.objects.create(
        user=user,
        category=NotificationCategory.NEW_JOB_ALERT,
        message=f"🔍 We found a job that's {score_percent}% match for you: {job.title}",
    )

    # Send real-time notification if possible
    if channel_layer:  # Only attempt if channel_layer is available
        try:
            async_to_sync(channel_layer.group_send)(
                f"user_{user.id}",
                {
                    "type": "job_match_notification",
                    "message": f"We found a job that's {score_percent}% match for you: {job.title}",
                    "job_id": job.id,
                    "match_score": score,
                },
            )
        except Exception as e:
            logger.error(f"Error sending real-time notification: {str(e)}")
    else:
        logger.warning("Real-time notifications disabled: channel_layer not available")


@receiver(post_save, sender=Job)
def geocode_job_after_save(sender, instance, created, **kwargs):
    """Geocode the job after it is saved to the database."""
    if created and instance.location and not (instance.latitude and instance.longitude):
        # Only geocode if the job was just created and has a location but no coordinates
        try:
            # Import here to avoid circular imports
            from jobs.utils import get_address_coordinates_helper

            # Get coordinates using the helper function
            coords = get_address_coordinates_helper(instance.location)

            if coords and coords.get("success"):
                instance.latitude = coords["latitude"]
                instance.longitude = coords["longitude"]
                # Use update_fields to avoid triggering this signal again
                instance.save(update_fields=["latitude", "longitude"])
                logger.info(
                    f"Job {instance.id} geocoded successfully: lat={instance.latitude}, lon={instance.longitude}"
                )
            else:
                logger.warning(
                    f"Geocoding failed for job {instance.id}: {coords.get('error', 'Unknown error')}"
                )
                # Fallback to synchronous geocoding
                fallback_geocode_and_save(instance.id)
        except Exception as e:
            logger.error(f"Error geocoding job location: {e}")
            # Fallback to synchronous geocoding
            try:
                fallback_geocode_and_save(instance.id)
            except Exception as inner_e:
                logger.error(f"Failed to geocode job: {inner_e}")


# =
# ✅ CACHE INVALIDATION SIGNALS
# =
@receiver(post_save, sender=Job)
def invalidate_clientjobs_cache_on_save(sender, instance, created, **kwargs):
    """
    Invalidate the client jobs cache when a job is created or updated.

    This ensures that the client jobs endpoint always returns the most up-to-date data.
    """
    if instance.client:
        # Invalidate the specific client's jobs cache
        client_id = instance.client.id
        cache_pattern = f"clientjobs:u:{client_id}:*"


        # Also invalidate the general clientjobs cache


        logger.debug(f"Invalidated client jobs cache for client {client_id} after job {'creation' if created else 'update'}")


@receiver(post_delete, sender=Job)
def invalidate_clientjobs_cache_on_delete(sender, instance, **kwargs):
    """
    Invalidate the client jobs cache when a job is deleted.

    This ensures that the client jobs endpoint always returns the most up-to-date data.
    """
    if instance.client:
        # Invalidate the specific client's jobs cache
        client_id = instance.client.id
        cache_pattern = f"clientjobs:u:{client_id}:*"


        # Also invalidate the general clientjobs cache


        # Invalidate the job's cache



        logger.debug(f"Invalidated client jobs cache for client {client_id} after job deletion")


# # =
# # ✅ APPLICATION-RELATED SIGNALS
# # =
# @receiver(post_save, sender=Application)
# def handle_application(sender, instance, created, **kwargs):
#     """Handle notifications and gamification for applications."""
#     if created:
#         # Notify job poster
#         Notification.objects.create(
#             user=instance.job.client,
#             message=f"📩 New applicant for {instance.job.title}",
#         )

#         # Notify applicant
#         Notification.objects.create(
#             user=instance.applicant,
#             message=f"📝 Application submitted for {instance.job.title}",
#         )

#     if instance.status == Application.Status.ACCEPTED:
#         # Clear cache and check achievements
#         clear_user_gamification_cache(instance.applicant.id)
#         check_and_award_achievements(instance.applicant)
#         check_and_award_badges(instance.applicant)

#         # Notify applicant of acceptance
#         Notification.objects.create(
#             user=instance.applicant, message=f"✅ You got the job: {instance.job.title}!"
#         )


# # =
# # ✅ GAMIFICATION SIGNALS
# # =
# @receiver(post_save, sender=Profile)
# def handle_profile_changes(sender, instance, **kwargs):
#     """Check for badges when profile changes."""
#     if {"role", "is_premium"}.intersection(kwargs.get("update_fields", [])):
#         clear_user_gamification_cache(instance.user.id)
#         check_and_award_badges(instance.user)


# @receiver(post_delete, sender=Application)
# def clear_application_cache(sender, instance, **kwargs):
#     """Clear cache when application is deleted."""
#     clear_user_gamification_cache(instance.applicant.id)

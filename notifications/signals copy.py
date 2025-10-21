# signals.py
import logging
from django.db import transaction
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP

from jobs.models import (
    Job, 
    JobIndustry, 
    JobSubCategory, 
    Application, 
    ApplicationStatusLog,
    SavedJob,
)
from disputes.models import (
    Dispute,
)
from rating.models import (
    Review,
)
from accounts.models import CustomUser, Profile
from payment.models import Payment, EscrowPayment, Transaction
from notifications.utils import create_notification
from .utils import (
    get_nearby_applicants, 
    send_websocket_notification,
    send_job_websocket_notification,
    send_review_websocket_notification,
    send_dispute_websocket_notification,
    send_wallet_websocket_notification,
)

logger = logging.getLogger(__name__)
User = get_user_model()

# ====
# Helper Functions
# ====

def create_status_notification(user, entity_type, entity_title, old_status, new_status):
    """Helper to create standardized, human-friendly status change notifications"""
    status_messages = {
        'job': {
            'pending': ("Waiting for Approval", f"Hey {user.get_full_name()}, your job '{entity_title}' is awaiting approval. We'll let you know once it's live!"),
            'upcoming': ("Your Job is Scheduled!", f"Great news! Your job '{entity_title}' is set to start soon. Check the details to prepare."),
            'ongoing': ("Job in Progress!", f"Your job '{entity_title}' has started. Stay tuned for updates!"),
            'completed': ("Job Done!", f"Woohoo! Your job '{entity_title}' is complete. Rate your experience to share feedback."),
            'canceled': ("Job Canceled", f"Sorry, your job '{entity_title}' was canceled. Need help? Contact support.")
        },
        'payment': {
            'pending': ("Payment in Process", f"Your payment for '{entity_title}' is being processed. We'll confirm soon!"),
            'held': ("Funds Secured", f"Your payment for '{entity_title}' is safely held in escrow. You're all set!"),
            'partial': ("Partial Payment Sent", f"A partial payment for '{entity_title}' was sent. Check your account for details."),
            'paid': ("Payment Complete!", f"Your payment for '{entity_title}' went through successfully. Thanks!"),
            'completed': ("Payment Finalized", f"Your payment for '{entity_title}' is complete. View transaction details in your account."),
            'failed': ("Payment Issue", f"Oops, the payment for '{entity_title}' didn't go through. Try again or contact support."),
            'refunded': ("Refund Processed", f"Your refund for '{entity_title}' is complete. Check your account for details.")
        },
        'application': {
            'accepted': ("🎉 You're Hired!", f"Congrats, {user.get_full_name()}! Your application for '{entity_title}' was accepted. Check the job details to get started."),
            'rejected': ("Application Update", f"Thanks for applying to '{entity_title}', {user.get_full_name()}. This one didn't work out, but explore more opportunities!"),
            'withdrawn': ("Application Withdrawn", f"You've withdrawn your application for '{entity_title}'. Browse other jobs to find your next gig!"),
            'pending': ("Application in Review", f"Your application for '{entity_title}' is under review. We'll notify you soon, {user.get_full_name()}!")
        },
        'profile': {
            'updated': ("Profile Updated", f"Nice work, {user.get_full_name()}! Your profile is looking great. Keep it updated to stand out."),
            'picture_updated': ("New Profile Pic!", f"Looking sharp, {user.get_full_name()}! Your new profile picture is live."),
            'completed': ("Profile Complete!", f"Awesome, {user.get_full_name()}! Your profile is now complete. You're ready to shine!")
        },
        'dispute': {
            'open': ("Dispute Filed", f"Hi {user.get_full_name()}, your dispute for '{entity_title}' has been filed. We'll keep you updated on the next steps."),
            'assigned': ("Dispute Assigned", f"Good news, {user.get_full_name()}! Your dispute for '{entity_title}' has been assigned to an admin for review."),
            'in_review': ("Dispute in Review", f"Your dispute for '{entity_title}' is now under review, {user.get_full_name()}. We'll update you soon!"),
            'resolved': ("Dispute Resolved", f"Your dispute for '{entity_title}' has been resolved, {user.get_full_name()}! Check the details for more info."),
            'closed': ("Dispute Closed", f"The dispute for '{entity_title}' is now closed, {user.get_full_name()}. Contact support if you need further assistance."),
            'escalated': ("Dispute Escalated", f"Your dispute for '{entity_title}' has been escalated, {user.get_full_name()}. Our team is prioritizing it.")
        }
    }
    
    if entity_type in status_messages and new_status in status_messages[entity_type]:
        title, message = status_messages[entity_type][new_status]
        create_notification(
            user=user,
            title=title,
            message=message,
            notification_type=f"{entity_type}_status_update",
            importance="high"
        )

# ====
# User Related Signals
# ====

@receiver(post_save, sender=CustomUser)
def handle_user_creation(sender, instance, created, **kwargs):
    """
    Handles notifications for user account creation and updates.
    """
    try:
        with transaction.atomic():
            if created:
                create_notification(
                    user=instance,
                    title="🎉 Welcome Aboard!",
                    message=f"Hi {instance.get_full_name()}, we're thrilled you're here! Complete your profile to unlock all features.",
                    notification_type="account_welcome",
                    importance="high"
                )
                
                admins = User.objects.filter(is_staff=True).values_list('id', flat=True)
                for admin_id in admins:
                    create_notification(
                        user_id=admin_id,
                        title="👤 New User Joined",
                        message=f"A new user, {instance.get_full_name()} ({instance.email}), just signed up!",
                        notification_type="admin_new_user",
                        importance="medium"
                    )
            elif not instance._state.adding and 'is_active' in kwargs.get('update_fields', []):
                status = "activated" if instance.is_active else "deactivated"
                create_notification(
                    user=instance,
                    title=f"🔒 Account {status.capitalize()}",
                    message=f"Your account is now {status}, {instance.get_full_name()}. {'' if instance.is_active else 'Need assistance? Contact support.'}",
                    notification_type=f"account_{status}",
                    importance="high"
                )
    except Exception as e:
        logger.error(f"Error handling user creation: {str(e)}")

# @receiver(pre_save, sender=Profile)
# def handle_profile_picture_change(sender, instance, **kwargs):
#     """
#     Handle profile picture changes and clean up old files.
#     """
#     if not instance.pk:
#         return False
        
#     try:
#         old_profile = Profile.objects.get(pk=instance.pk)
#         if old_profile.profile_pic and old_profile.profile_pic != instance.profile_pic:
#             if default_storage.exists(old_profile.profile_pic.name):
#                 default_storage.delete(old_profile.profile_pic.name)
#     except Profile.DoesNotExist:
#         pass

@receiver(post_save, sender=Profile)
def handle_profile_updates(sender, instance, created, **kwargs):
    """
    Notifications for profile changes.
    """
    try:
        update_fields = kwargs.get('update_fields', None)
        
        if created:
            create_notification(
                user=instance.user,
                title="📝 Profile Created",
                message=f"Welcome, {instance.user.get_full_name()}! Your profile is set up. Add more details to boost your visibility!",
                notification_type="profile_created",
                importance="medium"
            )
        else:
            if update_fields and 'profile_pic' in update_fields:
                create_status_notification(
                    instance.user,
                    'profile',
                    None,
                    None,
                    'picture_updated'
                )
            
            required_fields = ['bio', 'location', 'experience', 'education']
            if all(getattr(instance, field) for field in required_fields):
                create_status_notification(
                    instance.user,
                    'profile',
                    None,
                    None,
                    'completed'
                )
            elif update_fields and any(field in update_fields for field in required_fields):
                create_status_notification(
                    instance.user,
                    'profile',
                    None,
                    None,
                    'updated'
                )
    except Exception as e:
        logger.error(f"Error handling profile update: {str(e)}")

# ====
# Job Related Signals
# ====

@receiver(post_save, sender=Job)
def handle_job_notifications(sender, instance, created, **kwargs):
    """
    Handles notifications for job changes.
    """
    try:
        update_fields = kwargs.get('update_fields', None)
        if created:
            create_notification(
                user=instance.client,
                title="📢 Job Posted!",
                message=f"Your job '{instance.title}' is live, {instance.client.get_full_name()}! Applicants will start applying soon.",
                notification_type="job_posted",
                importance="high"
            )
            if instance.location_coordinates:
                nearby_users = get_nearby_applicants(instance)
                for user in nearby_users:
                    create_notification(
                        user=user,
                        title="📍 New Job Opportunity Nearby!",
                        message=f"Check out '{instance.title}', a new job in your area, {user.get_full_name()}!",
                        notification_type="job_nearby",
                        importance="medium"
                    )
        elif update_fields:
            if 'status' in update_fields:
                create_status_notification(
                    instance.client,
                    'job',
                    instance.title,
                    None,
                    instance.status
                )
                if instance.selected_applicant:
                    create_status_notification(
                        instance.selected_applicant,
                        'job',
                        instance.title,
                        None,
                        instance.status
                    )
            if 'payment_status' in update_fields:
                create_status_notification(
                    instance.client,
                    'payment',
                    instance.title,
                    None,
                    instance.payment_status
                )
    except Exception as e:
        logger.error(f"Error handling job notification: {str(e)}")

@receiver(post_delete, sender=Job)
def handle_job_deletion(sender, instance, **kwargs):
    """
    Notify when a job is deleted.
    """
    try:
        create_notification(
            user=instance.client,
            title="🗑️ Job Removed",
            message=f"Your job '{instance.title}' has been deleted, {instance.client.get_full_name()}. Need help? Contact support.",
            notification_type="job_deleted",
            importance="high"
        )
        
        if instance.selected_applicant:
            create_notification(
                user=instance.selected_applicant,
                title="❌ Job No Longer Available",
                message=f"Sorry, {instance.selected_applicant.get_full_name()}, the job '{instance.title}' was canceled. Explore other opportunities!",
                notification_type="job_canceled_applicant",
                importance="high"
            )
    except Exception as e:
        logger.error(f"Error handling job deletion: {str(e)}")

@receiver(post_save, sender=Job)
def handle_job_completion(sender, instance, created, **kwargs):
    # Only call if just transitioned to COMPLETED and not just created
    if not created and instance.status == Job.Status.COMPLETED:
        # Optionally, check if this transition is new (not already completed)
        # This requires tracking previous status, which can be done with a custom field or cache
        instance.end_shift()

# ====
# Application Related Signals
# ====

@receiver(pre_save, sender=Application)
def track_application_status_changes(sender, instance, **kwargs):
    """
    Track previous status before saving to detect changes.
    """
    if instance.pk:
        try:
            original = Application.objects.get(pk=instance.pk)
            instance._previous_status = original.status
        except Application.DoesNotExist:
            pass

@receiver(post_save, sender=Application)
def handle_application_notifications(sender, instance, created, **kwargs):
    """
    Handles notifications for application changes.
    """
    try:
        if created:
            create_notification(
                user=instance.job.client,
                title="📨 New Application Received",
                message=f"{instance.applicant.get_full_name()} applied to your job '{instance.job.title}'. Review their application now!",
                notification_type="new_application",
                importance="high"
            )
            create_notification(
                user=instance.applicant,
                title="📩 Application Sent",
                message=f"Your application for '{instance.job.title}' is in, {instance.applicant.get_full_name()}! We'll keep you posted.",
                notification_type="application_submitted",
                importance="medium"
            )
        elif hasattr(instance, '_previous_status') and instance._previous_status != instance.status:
            create_status_notification(
                instance.applicant,
                'application',
                instance.job.title,
                instance._previous_status,
                instance.status
            )
            if instance.status == 'Rejected':
                create_notification(
                    user=instance.applicant,
                    title="❌ Application Rejected",
                    message=f"Sorry, {instance.applicant.get_full_name()}, your application for '{instance.job.title}' was rejected.",
                    notification_type="application_rejected",
                    importance="high"
                )
            if instance.status == 'Accepted':
                create_notification(
                    user=instance.applicant,
                    title="🎉 Application Accepted",
                    message=f"Congratulations! Your application for '{instance.job.title}' was accepted.",
                    notification_type="application_accepted",
                    importance="high"
                )
    except Exception as e:
        logger.error(f"Error handling application notification: {str(e)}")


@receiver(post_save, sender=ApplicationStatusLog)
def log_application_status_change(sender, instance, created, **kwargs):
    """
    Additional notifications for detailed status changes.
    """
    if created:
        try:
            create_notification(
                user=instance.application.applicant,
                title="📝 Application Status Update",
                message=f"Hi {instance.application.applicant.get_full_name()}, your application for '{instance.application.job.title}' changed from {instance.old_status} to {instance.new_status}.",
                notification_type="application_status_change",
                importance="medium"
            )
        except Exception as e:
            logger.error(f"Error handling status log: {str(e)}")

# ====
# Payment Related Signals
# ====

@receiver(post_save, sender=Payment)
def handle_payment_updates(sender, instance, created, **kwargs):
    """
    Handles notifications for payment changes. Prevents duplicate notifications.
    """
    try:
        # Only send notification on creation, not on every save
        if created:
            create_notification(
                user=instance.payer,
                title="💳 Payment Started",
                message=f"Your payment of {instance.original_amount} is in progress, {instance.payer.get_full_name()}. We'll confirm once it's complete.",
                notification_type="payment_initiated",
                importance="high"
            )
            if instance.recipient:
                create_notification(
                    user=instance.recipient,
                    title="💰 Payment on the Way",
                    message=f"A payment of {instance.original_amount} from {instance.payer.get_full_name()} is coming your way, {instance.recipient.get_full_name()}!",
                    notification_type="payment_incoming",
                    importance="high"
                )
        # Only send status change notification if status just changed to completed
        elif hasattr(instance, '_previous_status') and instance.status == 'completed' and instance._previous_status != 'completed':
            create_notification(
                user=instance.payer,
                title="✅ Payment Successful",
                message=f"Your payment of {instance.original_amount} went through, {instance.payer.get_full_name()}! Check your transaction history.",
                notification_type="payment_completed",
                importance="high"
            )
            if instance.recipient:
                create_notification(
                    user=instance.recipient,
                    title="💰 Payment Received",
                    message=f"You've received {instance.final_amount} from {instance.payer.get_full_name()}, {instance.recipient.get_full_name()}!",
                    notification_type="payment_received",
                    importance="high"
                )
        elif instance.status == 'failed' and (not hasattr(instance, '_previous_status') or instance._previous_status != 'failed'):
            create_notification(
                user=instance.payer,
                title="❌ Payment Failed",
                message=f"Sorry, {instance.payer.get_full_name()}, your payment of {instance.original_amount} didn't go through. Try again or contact support.",
                notification_type="payment_failed",
                importance="high"
            )
    except Exception as e:
        logger.error(f"Error handling payment update: {str(e)}")

# Patch Payment model to track previous status for duplicate prevention
from payment.models import Payment

def payment_pre_save(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = Payment.objects.get(pk=instance.pk)
            instance._previous_status = old.status
        except Payment.DoesNotExist:
            instance._previous_status = None
    else:
        instance._previous_status = None

from django.db.models.signals import pre_save
pre_save.connect(payment_pre_save, sender=Payment)

@receiver(post_save, sender=EscrowPayment)
def handle_escrow_updates(sender, instance, created, **kwargs):
    """
    Notifications for escrow transactions.
    """
    try:
        if created:
            create_notification(
                user=instance.client,
                title="🔒 Funds Secured in Escrow",
                message=f"Your payment of {instance.total_amount} for '{instance.job.title}' is safely held, {instance.client.get_full_name()}!",
                notification_type="escrow_created",
                importance="high"
            )
        elif 'status' in kwargs.get('update_fields', []):
            if instance.status == 'released':
                create_notification(
                    user=instance.client,
                    title="💸 Funds Released",
                    message=f"Your payment of {instance.escrow_amount} for '{instance.job.title}' was sent to {instance.applicant.get_full_name()}, {instance.client.get_full_name()}!",
                    notification_type="escrow_released_client",
                    importance="high"
                )
                
                create_notification(
                    user=instance.applicant,
                    title="💰 Payment Received",
                    message=f"You've received {instance.escrow_amount} for '{instance.job.title}', {instance.applicant.get_full_name()}! Check your account.",
                    notification_type="escrow_released_applicant",
                    importance="high"
                )
            
            elif instance.status == 'refunded':
                create_notification(
                    user=instance.client,
                    title="↩️ Refund Issued",
                    message=f"Your payment of {instance.total_amount} for '{instance.job.title}' was refunded, {instance.client.get_full_name()}.",
                    notification_type="escrow_refunded",
                    importance="high"
                )
    except Exception as e:
        logger.error(f"Error handling escrow update: {str(e)}")

# ====
# Dispute Related Signals
# ====

@receiver(pre_save, sender=Dispute)
def track_dispute_status_changes(sender, instance, **kwargs):
    """
    Track previous status before saving to detect changes.
    """
    if instance.pk:
        try:
            original = Dispute.objects.get(pk=instance.pk)
            instance._previous_status = original.status
        except Dispute.DoesNotExist:
            pass

@receiver(post_save, sender=Dispute)
def handle_dispute_updates(sender, instance, created, **kwargs):
    """
    Handles notifications for dispute creation and updates.
    """
    try:
        title = instance.title or f"Dispute #{instance.id}"
        if created:
            # Notify dispute creator
            create_notification(
                user=instance.created_by,
                title="⚖️ Dispute Filed",
                message=f"Hi {instance.created_by.get_full_name()}, your dispute '{title}' for job '{instance.job.title}' has been submitted. We'll keep you updated!",
                notification_type="dispute_created",
                importance="high"
            )
            
            # Notify job client if not the creator
            if instance.job.client != instance.created_by:
                create_notification(
                    user=instance.job.client,
                    title="⚖️ New Dispute Filed",
                    message=f"A dispute '{title}' was filed for your job '{instance.job.title}' by {instance.created_by.get_full_name()}. Review the details.",
                    notification_type="dispute_filed_client",
                    importance="high"
                )
            
            # Notify admins
            admins = User.objects.filter(is_staff=True).values_list('id', flat=True)
            for admin_id in admins:
                create_notification(
                    user_id=admin_id,
                    title="⚖️ New Dispute Filed",
                    message=f"A new dispute '{title}' was filed for job '{instance.job.title}' by {instance.created_by.get_full_name()}.",
                    notification_type="admin_dispute_filed",
                    importance="high"
                )
        
        elif hasattr(instance, '_previous_status') and instance._previous_status != instance.status:
            # Notify creator on status change
            create_status_notification(
                user=instance.created_by,
                entity_type='dispute',
                entity_title=title,
                old_status=instance._previous_status,
                new_status=instance.status
            )
            
            # Notify job client if not the creator
            if instance.job.client != instance.created_by:
                create_status_notification(
                    user=instance.job.client,
                    entity_type='dispute',
                    entity_title=title,
                    old_status=instance._previous_status,
                    new_status=instance.status
                )
            
            # Notify assigned admin
            if instance.assigned_admin and instance.status == 'assigned':
                create_notification(
                    user=instance.assigned_admin,
                    title="⚖️ Dispute Assigned to You",
                    message=f"Hi {instance.assigned_admin.get_full_name()}, you've been assigned to handle dispute '{title}' for job '{instance.job.title}'. Please review it.",
                    notification_type="dispute_assigned_admin",
                    importance="high"
                )
            
            # Notify creator and client on resolution with notes
            if instance.status == 'resolved' and instance.resolution_notes:
                for user in [instance.created_by, instance.job.client]:
                    if user != instance.created_by or instance.job.client != instance.created_by:
                        create_notification(
                            user=user,
                            title="⚖️ Dispute Resolution Details",
                            message=f"The dispute '{title}' for job '{instance.job.title}' was resolved. Notes: {instance.resolution_notes}",
                            notification_type="dispute_resolution_notes",
                            importance="high"
                        )
    except Exception as e:
        logger.error(f"Error handling dispute update: {str(e)}")

@receiver(post_delete, sender=Dispute)
def handle_dispute_deletion(sender, instance, **kwargs):
    """
    Notify when a dispute is deleted.
    """
    try:
        title = instance.title or f"Dispute #{instance.id}"
        create_notification(
            user=instance.created_by,
            title="⚖️ Dispute Deleted",
            message=f"Your dispute '{title}' for job '{instance.job.title}' was deleted, {instance.created_by.get_full_name()}. Contact support if this was unexpected.",
            notification_type="dispute_deleted",
            importance="high"
        )
        
        if instance.job.client != instance.created_by:
            create_notification(
                user=instance.job.client,
                title="⚖️ Dispute Removed",
                message=f"The dispute '{title}' for your job '{instance.job.title}' was deleted, {instance.job.client.get_full_name()}.",
                notification_type="dispute_deleted_client",
                importance="high"
            )
    except Exception as e:
        logger.error(f"Error handling dispute deletion: {str(e)}")

# ====
# Review Related Signals
# ====

@receiver(post_save, sender=Review)
def handle_review_updates(sender, instance, created, **kwargs):
    """
    Handles notifications for review creation and updates.
    """
    try:
        if created:
            # Notify reviewed user
            create_notification(
                user=instance.reviewed,
                title="🌟 New Review Received",
                message=f"Hi {instance.reviewed.get_full_name()}, {instance.reviewer.get_full_name()} left you a {instance.rating}-star review for job '{instance.job.title}'. Check it out!",
                notification_type="review_received",
                importance="high"
            )
            
            # Notify reviewer
            create_notification(
                user=instance.reviewer,
                title="📝 Review Submitted",
                message=f"Your {instance.rating}-star review for {instance.reviewed.get_full_name()} on job '{instance.job.title}' was submitted, {instance.reviewer.get_full_name()}!",
                notification_type="review_submitted",
                importance="medium"
            )
        
        elif 'is_verified' in kwargs.get('update_fields', []) and instance.is_verified:
            # Notify reviewer when review is verified
            create_notification(
                user=instance.reviewer,
                title="✅ Review Verified",
                message=f"Your review for {instance.reviewed.get_full_name()} on job '{instance.job.title}' is now verified, {instance.reviewer.get_full_name()}!",
                notification_type="review_verified",
                importance="medium"
            )
        
        elif 'response' in kwargs.get('update_fields', []) and instance.response:
            # Notify reviewer when reviewed user responds
            create_notification(
                user=instance.reviewer,
                title="💬 Review Response",
                message=f"{instance.reviewed.get_full_name()} responded to your review for job '{instance.job.title}', {instance.reviewer.get_full_name()}: '{instance.response}'",
                notification_type="review_response",
                importance="medium"
            )
    except Exception as e:
        logger.error(f"Error handling review update: {str(e)}")

# ====
# Saved Jobs Signals
# ====

@receiver(post_save, sender=SavedJob)
def handle_saved_job_actions(sender, instance, created, **kwargs):
    """
    Notifications for saved job actions.
    """
    try:
        if created:
            create_notification(
                user=instance.user,
                title="🔖 Job Saved",
                message=f"You saved '{instance.job.title}', {instance.user.get_full_name()}! Apply when you're ready.",
                notification_type="job_saved",
                importance="low"
            )
    except Exception as e:
        logger.error(f"Error handling saved job: {str(e)}")

@receiver(post_delete, sender=SavedJob)
def handle_unsaved_job(sender, instance, **kwargs):
    """
    Notification when a job is unsaved.
    """
    try:
        create_notification(
            user=instance.user,
            title="📌 Job Removed",
            message=f"You removed '{instance.job.title}' from your saved jobs, {instance.user.get_full_name()}. Browse more jobs!",
            notification_type="job_unsaved",
            importance="low"
        )
    except Exception as e:
        logger.error(f"Error handling unsaved job: {str(e)}")

# ====
# Transaction Signals
# ====

@receiver(post_save, sender=Transaction)
def handle_transaction_updates(sender, instance, created, **kwargs):
    """
    Notifications for wallet transactions.
    """
    try:
        if created:
            message = (
                f"Credit of {instance.amount} added" if instance.transaction_type == 'credit'
                else f"Debit of {instance.amount} processed"
            )
            
            create_notification(
                user=instance.wallet.user,
                title="💳 Wallet Update",
                message=f"{message}, {instance.wallet.user.get_full_name()}! Ref: {instance.reference}",
                notification_type="wallet_transaction",
                importance="medium"
            )
        
        elif 'status' in kwargs.get('update_fields', []):
            if instance.status == 'completed':
                create_notification(
                    user=instance.wallet.user,
                    title="✅ Transaction Complete",
                    message=f"Your transaction of {instance.amount} is done, {instance.wallet.user.get_full_name()}! Check your wallet.",
                    notification_type="transaction_completed",
                    importance="medium"
                )
            
            elif instance.status == 'failed':
                create_notification(
                    user=instance.wallet.user,
                    title="❌ Transaction Failed",
                    message=f"Oops, {instance.wallet.user.get_full_name()}, your transaction of {instance.amount} failed. Contact support for help.",
                    notification_type="transaction_failed",
                    importance="high"
                )
    except Exception as e:
        logger.error(f"Error handling transaction update: {str(e)}")

# ====
# Industry/Subcategory Signals
# ====

@receiver(post_save, sender=JobIndustry)
def handle_industry_updates(sender, instance, created, **kwargs):
    """
    Admin notifications for industry changes.
    """
    try:
        if created:
            admins = User.objects.filter(is_staff=True).values_list('id', flat=True)
            for admin_id in admins:
                create_notification(
                    user_id=admin_id,
                    title="🏭 New Industry Added",
                    message=f"A new industry '{instance.name}' was added to the platform.",
                    notification_type="new_industry",
                    importance="low"
                )
    except Exception as e:
        logger.error(f"Error handling industry update: {str(e)}")

@receiver(post_save, sender=JobSubCategory)
def handle_subcategory_updates(sender, instance, created, **kwargs):
    """
    Admin notifications for subcategory changes.
    """
    try:
        if created:
            admins = User.objects.filter(is_staff=True).values_list('id', flat=True)
            for admin_id in admins:
                create_notification(
                    user_id=admin_id,
                    title="📂 New Subcategory Added",
                    message=f"A new subcategory '{instance.name}' was added under '{instance.industry.name}'.",
                    notification_type="new_subcategory",
                    importance="low"
                )
    except Exception as e:
        logger.error(f"Error handling subcategory update: {str(e)}")

# ====
# Additional/Missing Notification Signals
# ====

from notifications.models import NotificationPreference
# If you have models for bot/support and gamification events, import them here
# from support.models import SupportMessage
# from gamification.models import Achievement, Badge, LevelUp

@receiver(post_save, sender=NotificationPreference)
def handle_notification_preference_update(sender, instance, created, **kwargs):
    """
    Notify user when notification preferences are updated.
    """
    try:
        if not created:
            create_notification(
                user=instance.user,
                title="🔔 Notification Preferences Updated",
                message=f"Your notification settings have been updated, {instance.user.get_full_name()}.",
                notification_type="notification_preferences_updated",
                importance="low"
            )
    except Exception as e:
        logger.error(f"Error handling notification preference update: {str(e)}")

# Example for live support/bot message (uncomment and adjust if model exists)
# @receiver(post_save, sender=SupportMessage)
# def handle_support_message(sender, instance, created, **kwargs):
#     try:
#         if created and instance.is_reply:
#             create_notification(
#                 user=instance.user,
#                 title="💬 Support Reply",
#                 message=f"Support replied: {instance.message}",
#                 notification_type="support_reply",
#                 importance="medium"
#             )
#     except Exception as e:
#         logger.error(f"Error handling support message: {str(e)}")

# Example for gamification events (uncomment and adjust if models exist)
# @receiver(post_save, sender=Achievement)
# def handle_achievement_unlocked(sender, instance, created, **kwargs):
#     try:
#         if created:
#             create_notification(
#                 user=instance.user,
#                 title="🏆 Achievement Unlocked!",
#                 message=f"You unlocked the achievement: {instance.name}",
#                 notification_type="achievement_unlocked",
#                 importance="medium"
#             )
#     except Exception as e:
#         logger.error(f"Error handling achievement unlock: {str(e)}")

# @receiver(post_save, sender=Badge)
# def handle_badge_awarded(sender, instance, created, **kwargs):
#     try:
#         if created:
#             create_notification(
#                 user=instance.user,
#                 title="🎖️ Badge Awarded!",
#                 message=f"You earned a new badge: {instance.name}",
#                 notification_type="badge_awarded",
#                 importance="medium"
#             )
#     except Exception as e:
#         logger.error(f"Error handling badge awarded: {str(e)}")

# @receiver(post_save, sender=LevelUp)
# def handle_level_up(sender, instance, created, **kwargs):
#     try:
#         if created:
#             create_notification(
#                 user=instance.user,
#                 title="⬆️ Level Up!",
#                 message=f"Congratulations! You reached level {instance.level}.",
#                 notification_type="level_up",
#                 importance="medium"
#             )
#     except Exception as e:
#         logger.error(f"Error handling level up: {str(e)}")

# For real-time notification triggers (WebSocket, etc.), ensure your notification creation logic also pushes to the real-time channel if needed.

# Connect all signals
def connect_signals():
    """Explicitly connect all signals"""
    from django.db.models.signals import post_save, pre_save, post_delete
    
    # User signals
    post_save.connect(handle_user_creation, sender=CustomUser)
    # pre_save.connect(handle_profile_picture_change, sender=Profile)
    post_save.connect(handle_profile_updates, sender=Profile)
    
    # Job signals
    post_save.connect(handle_job_notifications, sender=Job)
    post_delete.connect(handle_job_deletion, sender=Job)
    
    # Application signals
    post_save.connect(handle_application_notifications, sender=Application)
    pre_save.connect(track_application_status_changes, sender=Application)
    post_save.connect(log_application_status_change, sender=ApplicationStatusLog)
    
    # Payment signals
    post_save.connect(handle_payment_updates, sender=Payment)
    post_save.connect(handle_escrow_updates, sender=EscrowPayment)
    
    # Dispute signals
    pre_save.connect(track_dispute_status_changes, sender=Dispute)
    post_save.connect(handle_dispute_updates, sender=Dispute)
    post_delete.connect(handle_dispute_deletion, sender=Dispute)
    
    # Review signals
    post_save.connect(handle_review_updates, sender=Review)
    
    # Saved jobs signals
    post_save.connect(handle_saved_job_actions, sender=SavedJob)
    post_delete.connect(handle_unsaved_job, sender=SavedJob)
    
    # Transaction signals
    post_save.connect(handle_transaction_updates, sender=Transaction)
    
    # Industry signals
    post_save.connect(handle_industry_updates, sender=JobIndustry)
    post_save.connect(handle_subcategory_updates, sender=JobSubCategory)

# Call to connect signals when module is imported
connect_signals()

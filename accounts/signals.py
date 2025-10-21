# Django Imports
from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.db.models.signals import post_save, post_migrate
from django.dispatch import receiver
import logging
from decimal import Decimal

# Third Party Imports
from allauth.account.signals import user_signed_up

# Local Imports
from payment.models import Wallet
from .models import Role, Profile, CustomUser

logger = logging.getLogger(__name__)


@receiver(post_migrate)
def create_default_roles(sender, **kwargs):
    """
    Create default roles after migrations are complete.
    This ensures that the required roles exist in the database.
    """
    if sender.name == 'accounts':  # Only run for the accounts app
        try:
            # Create the default roles if they don't exist
            default_roles = [
                {'name': Role.APPLICANT, 'description': 'Job applicant role'},
                {'name': Role.CLIENT, 'description': 'Client role for posting jobs'},
                {'name': Role.ADMIN, 'description': 'Administrator role with full access'}
            ]

            for role_data in default_roles:
                role, created = Role.objects.get_or_create(
                    name=role_data['name'],
                    defaults={'description': role_data['description']}
                )
                if created:
                    logger.info(f"Created default role: {role.name}")
                else:
                    logger.debug(f"Default role already exists: {role.name}")
        except Exception as e:
            logger.error(f"Error creating default roles: {str(e)}")


@receiver(post_save, sender=CustomUser)
def create_user_wallet(instance, created, **_):
    """
    Creates wallet for new users if it doesn't already exist.
    """
    if created:
        # Check if wallet already exists to avoid duplicates
        if hasattr(instance, 'wallet'):
            logger.debug(f"Wallet already exists for user {instance.email}")
            return

        try:
            # Create wallet only if it doesn't exist
            wallet, created = Wallet.objects.get_or_create(
                user=instance,
                defaults={'balance': Decimal("0.00")}
            )
            if created:
                logger.debug(f"Created wallet for user {instance.email}")
            else:
                logger.debug(f"Found existing wallet for user {instance.email}")
        except Exception as e:
            # Log error but don't raise - this allows user creation to proceed
            # even if wallet creation fails
            logger.error(f"Error creating wallet for user {instance.email}: {str(e)}")
            # We'll try to create the wallet again later if needed


@receiver(post_save, sender=CustomUser)
def create_wallet_for_user(sender, instance, created, **kwargs):
    if created and not hasattr(instance, 'wallet'):
        wallet = Wallet.objects.create()
        instance.wallet = wallet
        instance.save()

@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Create a profile for a new user if it doesn't exist.

    This is a fallback mechanism in case the profile wasn't created during signup.
    The primary profile creation happens in the signup API view.
    """
    if created:
        # Check if profile already exists to avoid duplicates
        try:
            if Profile.objects.filter(user=instance).exists():
                logger.debug(f"Profile already exists for user {instance.email}")
                return

            # Get role name safely - handle case where role field might not exist yet
            try:
                # First try to get role as a direct attribute (CharField)
                if hasattr(instance, 'role'):
                    if isinstance(instance.role, str):
                        role_name = instance.role
                    # If it's a Role object, get the name
                    elif hasattr(instance.role, 'name'):
                        role_name = instance.role.name
                    else:
                        role_name = Role.CLIENT
                else:
                    role_name = Role.CLIENT
            except (AttributeError, Exception) as e:
                # Fallback to default role if role field doesn't exist or has issues
                role_name = Role.CLIENT
                logger.warning(f"Using default role '{role_name}' for user {instance.email} - role field may not exist yet: {str(e)}")

            # Use a transaction to ensure atomicity
            with transaction.atomic():
                try:
                    # Create profile with minimal required fields to avoid foreign key issues
                    profile = Profile.objects.create(
                        user=instance,
                        role=role_name,  # Use the role name string for Profile
                        badges=[],  # Initialize badges as empty list
                    )
                    logger.info(f"Created profile for user {instance.email} with role {role_name}")
                except Exception as inner_e:
                    logger.error(f"Error creating profile with transaction for user {instance.email}: {str(inner_e)}")
                    # If we can't create the profile with a transaction, try without
                    profile = Profile(
                        user=instance,
                        role=role_name,
                        badges=[],  # Initialize badges as empty list
                    )
                    profile.save()
                    logger.info(f"Created profile without transaction for user {instance.email}")
        except Exception as e:
            logger.error(f"Error creating profile for user {instance.email}: {str(e)}")
            # Don't raise the exception - this allows user creation to proceed
            # even if profile creation fails


@receiver(user_signed_up)
def populate_social_profile(request, user, **kwargs):
    """
    Updates user fields from social login data.
    Profile creation is handled separately to avoid session issues.

    This function also checks for a 'role' parameter in the request
    to set the appropriate role for the user.
    """
    if user.socialaccount_set.exists():
        try:
            social_account = user.socialaccount_set.first()
            extra_data = social_account.extra_data

            # Update user fields from social data
            user.first_name = extra_data.get("given_name", user.first_name)
            user.last_name = extra_data.get("family_name", user.last_name)

            # Update user without triggering signals
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE auth_user SET first_name = %s, last_name = %s WHERE id = %s",
                    [user.first_name, user.last_name, user.id]
                )

            # Get role from request if available
            role_name = None
            if request and hasattr(request, 'GET') and 'role' in request.GET:
                role_name = request.GET.get('role')
                logger.info(f"Found role parameter in request: {role_name}")

            # Create profile using direct SQL to avoid session issues
            try:
                # Get or create the role (use the one from request if available)
                if role_name:
                    role, created = Role.objects.get_or_create(
                        name=role_name,
                        defaults={'description': f'Role created from social login: {role_name}'}
                    )
                    if created:
                        logger.info(f"Created new role from request: {role_name}")
                else:
                    # Default to applicant role
                    role, created = Role.objects.get_or_create(
                        name=Role.APPLICANT,
                        defaults={'description': 'Default applicant role'}
                    )
                    if created:
                        logger.info(f"Created default role: {Role.APPLICANT}")

                # Try to set the role for the user
                try:
                    if hasattr(user, 'role'):
                        user.role = role
                        user.save(update_fields=['role'])
                    else:
                        logger.warning(f"Could not set role for social user {user.email} - role field may not exist yet")
                except Exception as e:
                    logger.warning(f"Error setting role for social user {user.email}: {str(e)}")

                # Check if profile exists and create if needed
                if not Profile.objects.filter(user=user).exists():
                    Profile.objects.create(
                        user=user,
                        role=role.name,  # Use the role name string for Profile
                        badges=[]  # Initialize badges as empty list
                    )
                    logger.info(f"Created profile for social user {user.email} with role {role.name}")
                else:
                    # Update existing profile with the role if needed
                    profile = Profile.objects.get(user=user)
                    if profile.role != role.name:
                        profile.role = role.name
                        profile.save(update_fields=['role'])
                        logger.info(f"Updated profile role to {role.name} for user {user.email}")
            except Exception as inner_e:
                logger.error(f"Error creating/updating profile for social user {user.email}: {str(inner_e)}")

        except Exception as e:
            logger.error(f"Error in populate_social_profile for {user.email}: {str(e)}")

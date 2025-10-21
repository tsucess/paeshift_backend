"""
Social authentication API endpoints.

This module provides API endpoints for social authentication, including:
- Google authentication
- Facebook authentication
- Apple authentication
"""

import logging
from decimal import Decimal

from allauth.socialaccount.models import SocialAccount, SocialApp, SocialToken
from django.contrib.auth import get_user_model, login
from django.db import transaction
from django.http import JsonResponse
from ninja import Router
from ninja.security import HttpBearer

from .models import Profile, GoogleAuthSession
from .schemas import SocialLoginSchema, LoginOut

class BearerAuth(HttpBearer):
    def authenticate(self, request, token):
        # In a real application, you would validate the token here
        return token

User = get_user_model()
logger = logging.getLogger(__name__)

# Required scopes for Gmail API access
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]

social_router = Router(tags=["Social Auth"])


@social_router.post("/google", tags=["Social Auth"])
def google_login(request, payload: SocialLoginSchema):
    """
    Handle Google authentication.

    This endpoint accepts a Google access token and creates or retrieves a user account.
    It also creates a SocialAccount record to link the user to their Google account.
    """
    try:
        # Validate the token with Google
        import requests

        # Get user info from Google
        userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"
        response = requests.get(
            userinfo_url,
            headers={"Authorization": f"Bearer {payload.access_token}"}
        )

        if response.status_code != 200:
            return JsonResponse({
                "error": "Invalid token or token expired"
            }, status=401)

        userinfo = response.json()

        # Get or create user
        email = userinfo.get("email")
        if not email:
            return JsonResponse({
                "error": "Email not provided by Google"
            }, status=400)

        # Check if user exists
        try:
            user = User.objects.get(email=email)
            created = False
        except User.DoesNotExist:
            # Create new user
            with transaction.atomic():
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    first_name=userinfo.get("given_name", ""),
                    last_name=userinfo.get("family_name", ""),
                    # Use a random password since the user will login via Google
                    password=User.objects.make_random_password(),
                )
                created = True

        # Get or create social account
        try:
            social_account = SocialAccount.objects.get(user=user, provider="google")
        except SocialAccount.DoesNotExist:
            # Get the Google social app
            try:
                social_app = SocialApp.objects.get(provider="google")
            except SocialApp.DoesNotExist:
                # Create a placeholder social app if none exists
                social_app = SocialApp.objects.create(
                    provider="google",
                    name="Google",
                    client_id="placeholder",
                    secret="placeholder",
                )

            # Create social account
            social_account = SocialAccount.objects.create(
                user=user,
                provider="google",
                uid=userinfo.get("sub"),
                extra_data=userinfo,
            )

            # Create social token
            SocialToken.objects.create(
                account=social_account,
                app=social_app,
                token=payload.access_token,
            )

        # Update user info if needed
        if user.first_name != userinfo.get("given_name", "") or user.last_name != userinfo.get("family_name", ""):
            user.first_name = userinfo.get("given_name", "")
            user.last_name = userinfo.get("family_name", "")
            user.save()

        # Get or create profile
        # Use the role from the payload, defaulting to "applicant" if not provided
        role = getattr(payload, "role", "applicant")
        print(f"Using role: {role} for user: {user.email}")

        # Check if profile exists
        try:
            profile = Profile.objects.get(user=user)
            # Update role if provided and different from current
            if role != profile.role:
                profile.role = role
                profile.save()
                print(f"Updated role to {role} for existing profile")
        except Profile.DoesNotExist:
            # Create new profile with the specified role
            profile = Profile.objects.create(
                user=user,
                role=role,
                badges=[],
                balance=Decimal("0.00"),
            )
            print(f"Created new profile with role {role}")

        # Store Google auth session in the database with Gmail API scopes
        GoogleAuthSession.create_session(
            user=user,
            access_token=payload.access_token,
            google_user_id=userinfo.get("sub"),
            google_email=email,
            profile_data=userinfo,
            ip_address=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT"),
            scopes=GMAIL_SCOPES  # Add Gmail API scopes
        )

        # Log the user in with explicit backend
        from django.contrib.auth import get_backends
        backend = get_backends()[0]  # Use the first backend
        login(request, user, backend=backend.__class__.__name__)

        # Generate JWT tokens
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)

        # Return success response using LoginOut schema
        return JsonResponse({
            "message": "success",
            "user_id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": profile.role,
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "profile_pic": None,  # Add profile pic if available
        })

    except Exception as e:
        logger.exception(f"Error in Google login: {str(e)}")
        return JsonResponse({
            "error": f"Unexpected error: {str(e)}"
        }, status=500)


@social_router.post("/connect-social", auth=BearerAuth())
def connect_social_account(request, payload: SocialLoginSchema):
    """
    Connect a social account to an existing user.

    This endpoint accepts a social provider token and connects it to an existing user account.
    The user must be authenticated to use this endpoint.
    """
    try:
        # Validate the token with the provider
        import requests

        if payload.provider != "google":
            return JsonResponse({
                "error": f"Provider {payload.provider} not supported yet"
            }, status=400)

        # Get user info from Google
        userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"
        response = requests.get(
            userinfo_url,
            headers={"Authorization": f"Bearer {payload.access_token}"}
        )

        if response.status_code != 200:
            return JsonResponse({
                "error": "Invalid token or token expired"
            }, status=401)

        userinfo = response.json()

        # Get email from userinfo
        email = userinfo.get("email")
        if not email:
            return JsonResponse({
                "error": "Email not provided by Google"
            }, status=400)

        # Get the user to connect to
        try:
            # If connect_to_user_id is provided, use that
            if hasattr(payload, "connect_to_user_id") and payload.connect_to_user_id:
                user = User.objects.get(id=payload.connect_to_user_id)
            else:
                # Otherwise use the authenticated user
                user = request.user

            # Verify the email matches
            if user.email != email:
                return JsonResponse({
                    "error": "The email from the social account doesn't match your account email"
                }, status=400)

        except User.DoesNotExist:
            return JsonResponse({
                "error": "User not found"
            }, status=404)

        # Check if a social account already exists for this user and provider
        try:
            social_account = SocialAccount.objects.get(user=user, provider=payload.provider)
            # Update the social account if it exists
            social_account.uid = userinfo.get("sub")
            social_account.extra_data = userinfo
            social_account.save()
        except SocialAccount.DoesNotExist:
            # Get or create the social app
            try:
                social_app = SocialApp.objects.get(provider=payload.provider)
            except SocialApp.DoesNotExist:
                # Create a placeholder social app if none exists
                social_app = SocialApp.objects.create(
                    provider=payload.provider,
                    name=payload.provider.capitalize(),
                    client_id="placeholder",
                    secret="placeholder",
                )

            # Create the social account
            social_account = SocialAccount.objects.create(
                user=user,
                provider=payload.provider,
                uid=userinfo.get("sub"),
                extra_data=userinfo,
            )

            # Create the social token
            SocialToken.objects.create(
                account=social_account,
                app=social_app,
                token=payload.access_token,
            )

        # Store Google auth session in the database with Gmail API scopes
        GoogleAuthSession.create_session(
            user=user,
            access_token=payload.access_token,
            google_user_id=userinfo.get("sub"),
            google_email=email,
            profile_data=userinfo,
            ip_address=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT"),
            scopes=GMAIL_SCOPES  # Add Gmail API scopes
        )

        # Return success response
        return JsonResponse({
            "message": "success",
            "user_id": user.id,
            "email": user.email,
            "provider": payload.provider
        })

    except Exception as e:
        logger.exception(f"Error connecting social account: {str(e)}")
        return JsonResponse({
            "error": f"Unexpected error: {str(e)}"
        }, status=500)

@social_router.get("/check-social-account")
def check_social_account(request, email: str):
    """
    Check if a user has a social account.

    This endpoint accepts an email and checks if the user has a social account.
    """
    try:
        # Check if user exists
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return JsonResponse({
                "error": "User not found"
            }, status=404)

        # Check if user has a social account
        has_social_account = SocialAccount.objects.filter(user=user).exists()

        return JsonResponse({
            "has_social_account": has_social_account,
            "email": email
        })

    except Exception as e:
        logger.exception(f"Error checking social account: {str(e)}")
        return JsonResponse({
            "error": f"Unexpected error: {str(e)}"
        }, status=500)


@social_router.post("/direct-social-login")
def direct_social_login(request, payload: SocialLoginSchema):
    """
    Direct login with a social account.

    This endpoint accepts an email and provider and logs in the user directly,
    bypassing the normal social authentication flow. This is useful when the
    social provider's token is having issues but we know the user exists.
    """
    try:
        # Get the email from the payload
        email = payload.email
        if not email:
            return JsonResponse({
                "error": "Email is required"
            }, status=400)

        # Check if user exists
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return JsonResponse({
                "error": "User not found"
            }, status=404)

        # Check if user has a social account with the specified provider
        try:
            social_account = SocialAccount.objects.get(user=user, provider=payload.provider)
        except SocialAccount.DoesNotExist:
            return JsonResponse({
                "error": f"No {payload.provider} account found for this user"
            }, status=404)

        # Get or create profile
        # Use the role from the payload, defaulting to "applicant" if not provided
        role = getattr(payload, "role", "applicant")

        # Check if profile exists
        try:
            profile = Profile.objects.get(user=user)
            # Update role if provided and different from current
            if role != profile.role:
                profile.role = role
                profile.save()
        except Profile.DoesNotExist:
            # Create new profile with the specified role
            profile = Profile.objects.create(
                user=user,
                role=role,
                badges=[],
                balance=Decimal("0.00"),
            )

        # Store Google auth session in the database if we have a token
        if payload.access_token:
            # Get Google user ID from social account
            google_user_id = social_account.uid

            # Store the session with Gmail API scopes
            GoogleAuthSession.create_session(
                user=user,
                access_token=payload.access_token,
                google_user_id=google_user_id,
                google_email=email,
                profile_data=social_account.extra_data,
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT"),
                scopes=GMAIL_SCOPES  # Add Gmail API scopes
            )

        # Log the user in with explicit backend
        from django.contrib.auth import get_backends
        backend = get_backends()[0]  # Use the first backend
        login(request, user, backend=backend.__class__.__name__)

        # Generate JWT tokens
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)

        # Return success response
        return JsonResponse({
            "message": "success",
            "user_id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": profile.role,
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "profile_pic": None,  # Add profile pic if available
        })

    except Exception as e:
        logger.exception(f"Error in direct social login: {str(e)}")
        return JsonResponse({
            "error": f"Unexpected error: {str(e)}"
        }, status=500)


# Google sessions endpoint removed to disable this functionality in the frontend


# No need for URL patterns here, we're using the router
# The router will be added to the API in accounts/urls.py

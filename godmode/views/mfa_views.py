"""
Views for MFA setup and verification.

This module provides views for:
1. Setting up MFA
2. Verifying MFA
3. Disabling MFA
"""

import logging
from typing import Dict, Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from godmode.audit import log_audit
from godmode.mfa import (
    confirm_mfa_setup,
    disable_mfa,
    generate_qr_code,
    get_user_mfa_secret,
    is_mfa_enabled,
    is_mfa_verified,
    set_mfa_verified,
    setup_mfa,
    verify_totp_code,
)

logger = logging.getLogger(__name__)


def superuser_required(view_func):
    """
    Decorator to require superuser privileges.
    """
    return user_passes_test(lambda u: u.is_superuser)(view_func)


@login_required
@superuser_required
@csrf_protect
@require_GET
def mfa_setup_view(request: HttpRequest) -> HttpResponse:
    """
    View for setting up MFA.
    
    Args:
        request: HTTP request
        
    Returns:
        HTTP response
    """
    # Check if MFA is already enabled
    if is_mfa_enabled(request.user.id):
        messages.info(request, "MFA is already enabled for your account.")
        return redirect(reverse("godmode:dashboard"))
    
    # Set up MFA
    secret, uri = setup_mfa(request.user.id)
    
    # Log the action
    log_audit(
        request=request,
        action_type="mfa",
        action="MFA setup initiated",
        details={"uri_generated": True},
    )
    
    # Render the setup page
    context = {
        "secret": secret,
        "uri": uri,
    }
    return render(request, "godmode/mfa/setup.html", context)


@login_required
@superuser_required
@csrf_protect
@require_POST
def mfa_setup_confirm_view(request: HttpRequest) -> HttpResponse:
    """
    View for confirming MFA setup.
    
    Args:
        request: HTTP request
        
    Returns:
        HTTP response
    """
    # Get the verification code
    code = request.POST.get("code")
    
    if not code:
        messages.error(request, "Verification code is required.")
        return redirect(reverse("godmode:mfa_setup"))
    
    # Confirm MFA setup
    success = confirm_mfa_setup(request.user.id, code)
    
    if success:
        # Set MFA as verified for this session
        set_mfa_verified(request)
        
        # Log the action
        log_audit(
            request=request,
            action_type="mfa",
            action="MFA setup completed",
            details={"success": True},
        )
        
        messages.success(request, "MFA has been successfully enabled for your account.")
        
        # Redirect to the dashboard or the original URL
        redirect_url = request.session.get("mfa_redirect_url", reverse("godmode:dashboard"))
        return redirect(redirect_url)
    else:
        # Log the action
        log_audit(
            request=request,
            action_type="mfa",
            action="MFA setup failed",
            details={"success": False},
        )
        
        messages.error(request, "Invalid verification code. Please try again.")
        return redirect(reverse("godmode:mfa_setup"))


@login_required
@superuser_required
@csrf_protect
@require_GET
def mfa_verify_view(request: HttpRequest) -> HttpResponse:
    """
    View for verifying MFA.
    
    Args:
        request: HTTP request
        
    Returns:
        HTTP response
    """
    # Check if MFA is enabled
    if not is_mfa_enabled(request.user.id):
        messages.info(request, "MFA is not enabled for your account.")
        return redirect(reverse("godmode:dashboard"))
    
    # Check if MFA is already verified
    if is_mfa_verified(request):
        messages.info(request, "MFA is already verified for this session.")
        return redirect(request.session.get("mfa_redirect_url", reverse("godmode:dashboard")))
    
    # Render the verification page
    return render(request, "godmode/mfa/verify.html")


@login_required
@superuser_required
@csrf_protect
@require_POST
def mfa_verify_confirm_view(request: HttpRequest) -> HttpResponse:
    """
    View for confirming MFA verification.
    
    Args:
        request: HTTP request
        
    Returns:
        HTTP response
    """
    # Get the verification code
    code = request.POST.get("code")
    
    if not code:
        messages.error(request, "Verification code is required.")
        return redirect(reverse("godmode:mfa_verify"))
    
    # Get the MFA secret
    secret = get_user_mfa_secret(request.user.id)
    
    if not secret:
        messages.error(request, "MFA is not enabled for your account.")
        return redirect(reverse("godmode:dashboard"))
    
    # Verify the code
    if verify_totp_code(secret, code):
        # Set MFA as verified for this session
        set_mfa_verified(request)
        
        # Log the action
        log_audit(
            request=request,
            action_type="mfa",
            action="MFA verification successful",
            details={"success": True},
        )
        
        messages.success(request, "MFA verification successful.")
        
        # Redirect to the original URL
        redirect_url = request.session.get("mfa_redirect_url", reverse("godmode:dashboard"))
        return redirect(redirect_url)
    else:
        # Log the action
        log_audit(
            request=request,
            action_type="mfa",
            action="MFA verification failed",
            details={"success": False},
        )
        
        messages.error(request, "Invalid verification code. Please try again.")
        return redirect(reverse("godmode:mfa_verify"))


@login_required
@superuser_required
@csrf_protect
@require_POST
def mfa_disable_view(request: HttpRequest) -> HttpResponse:
    """
    View for disabling MFA.
    
    Args:
        request: HTTP request
        
    Returns:
        HTTP response
    """
    # Check if MFA is enabled
    if not is_mfa_enabled(request.user.id):
        messages.info(request, "MFA is not enabled for your account.")
        return redirect(reverse("godmode:dashboard"))
    
    # Disable MFA
    success = disable_mfa(request.user.id)
    
    if success:
        # Log the action
        log_audit(
            request=request,
            action_type="mfa",
            action="MFA disabled",
            details={"success": True},
        )
        
        messages.success(request, "MFA has been successfully disabled for your account.")
    else:
        # Log the action
        log_audit(
            request=request,
            action_type="mfa",
            action="MFA disable failed",
            details={"success": False},
        )
        
        messages.error(request, "Failed to disable MFA. Please try again.")
    
    return redirect(reverse("godmode:dashboard"))


@login_required
@superuser_required
@require_GET
def mfa_qr_code_view(request: HttpRequest) -> HttpResponse:
    """
    View for generating QR code for MFA setup.
    
    Args:
        request: HTTP request
        
    Returns:
        HTTP response with QR code image
    """
    # Get the URI from the session
    uri = request.GET.get("uri")
    
    if not uri:
        return HttpResponse("URI is required", status=400)
    
    # Generate QR code
    qr_code = generate_qr_code(uri)
    
    # Return the QR code image
    response = HttpResponse(qr_code, content_type="image/png")
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


@login_required
@superuser_required
@csrf_protect
@require_POST
def mfa_api_verify_view(request: HttpRequest) -> JsonResponse:
    """
    API view for verifying MFA.
    
    Args:
        request: HTTP request
        
    Returns:
        JSON response
    """
    # Get the verification code
    code = request.POST.get("code")
    
    if not code:
        return JsonResponse({"success": False, "error": "Verification code is required."}, status=400)
    
    # Get the MFA secret
    secret = get_user_mfa_secret(request.user.id)
    
    if not secret:
        return JsonResponse({"success": False, "error": "MFA is not enabled for your account."}, status=400)
    
    # Verify the code
    if verify_totp_code(secret, code):
        # Set MFA as verified for this session
        set_mfa_verified(request)
        
        # Log the action
        log_audit(
            request=request,
            action_type="mfa",
            action="MFA API verification successful",
            details={"success": True},
        )
        
        return JsonResponse({"success": True, "message": "MFA verification successful."})
    else:
        # Log the action
        log_audit(
            request=request,
            action_type="mfa",
            action="MFA API verification failed",
            details={"success": False},
        )
        
        return JsonResponse({"success": False, "error": "Invalid verification code."}, status=400)

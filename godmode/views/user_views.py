"""
User-related views for God Mode.

This module provides views for user management in God Mode.
"""

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render


@staff_member_required
def user_activity(request):
    """
    View for monitoring user activity.
    
    Args:
        request: HTTP request
        
    Returns:
        Rendered user activity template
    """
    context = {
        "title": "User Activity",
    }
    return render(request, "godmode/user_activity.html", context)


@staff_member_required
def user_detail(request, user_id):
    """
    View for user details.
    
    Args:
        request: HTTP request
        user_id: User ID
        
    Returns:
        Rendered user detail template
    """
    context = {
        "title": "User Detail",
        "user_id": user_id,
    }
    return render(request, "godmode/user_detail.html", context)


@staff_member_required
def delete_user(request, user_id):
    """
    View for deleting a user.
    
    Args:
        request: HTTP request
        user_id: User ID
        
    Returns:
        Rendered delete user template
    """
    context = {
        "title": "Delete User",
        "user_id": user_id,
    }
    return render(request, "godmode/delete_user.html", context)


@staff_member_required
def location_verification(request):
    """
    View for location verification.
    
    Args:
        request: HTTP request
        
    Returns:
        Rendered location verification template
    """
    context = {
        "title": "Location Verification",
    }
    return render(request, "godmode/location_verification.html", context)


@staff_member_required
def verify_location(request, verification_id):
    """
    View for verifying a specific location.
    
    Args:
        request: HTTP request
        verification_id: Verification ID
        
    Returns:
        Rendered verify location template
    """
    context = {
        "title": "Verify Location",
        "verification_id": verification_id,
    }
    return render(request, "godmode/verify_location.html", context)

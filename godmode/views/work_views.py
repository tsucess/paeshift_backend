"""
Work assignment-related views for God Mode.

This module provides views for managing work assignments in God Mode.
"""

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render


@staff_member_required
def work_assignments(request):
    """
    View for listing work assignments.
    
    Args:
        request: HTTP request
        
    Returns:
        Rendered work assignments template
    """
    context = {
        "title": "Work Assignments",
    }
    return render(request, "godmode/work_assignments.html", context)


@staff_member_required
def work_assignment_detail(request, assignment_id):
    """
    View for work assignment details.
    
    Args:
        request: HTTP request
        assignment_id: Assignment ID
        
    Returns:
        Rendered work assignment detail template
    """
    context = {
        "title": "Work Assignment Detail",
        "assignment_id": assignment_id,
    }
    return render(request, "godmode/work_assignment_detail.html", context)


@staff_member_required
def create_work_assignment(request):
    """
    View for creating a work assignment.
    
    Args:
        request: HTTP request
        
    Returns:
        Rendered create work assignment template
    """
    context = {
        "title": "Create Work Assignment",
    }
    return render(request, "godmode/create_work_assignment.html", context)

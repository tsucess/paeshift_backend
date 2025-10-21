"""
Ranking-related views for God Mode.

This module provides views for user rankings in God Mode.
"""

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render


@staff_member_required
def user_rankings(request):
    """
    View for user rankings.
    
    Args:
        request: HTTP request
        
    Returns:
        Rendered user rankings template
    """
    context = {
        "title": "User Rankings",
    }
    return render(request, "godmode/user_rankings.html", context)


@staff_member_required
def generate_rankings(request, ranking_type=None):
    """
    View for generating rankings.
    
    Args:
        request: HTTP request
        ranking_type: Type of ranking to generate
        
    Returns:
        Rendered generate rankings template
    """
    context = {
        "title": "Generate Rankings",
        "ranking_type": ranking_type,
    }
    return render(request, "godmode/generate_rankings.html", context)

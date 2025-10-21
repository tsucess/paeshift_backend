"""
Data export-related views for God Mode.

This module provides views for data exports in God Mode.
"""

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render


@staff_member_required
def data_exports(request):
    """
    View for listing data exports.
    
    Args:
        request: HTTP request
        
    Returns:
        Rendered data exports template
    """
    context = {
        "title": "Data Exports",
    }
    return render(request, "godmode/data_exports.html", context)


@staff_member_required
def create_export_config(request):
    """
    View for creating an export configuration.
    
    Args:
        request: HTTP request
        
    Returns:
        Rendered create export config template
    """
    context = {
        "title": "Create Export Configuration",
    }
    return render(request, "godmode/create_export_config.html", context)


@staff_member_required
def run_export(request, config_id):
    """
    View for running an export.
    
    Args:
        request: HTTP request
        config_id: Configuration ID
        
    Returns:
        Rendered run export template
    """
    context = {
        "title": "Run Export",
        "config_id": config_id,
    }
    return render(request, "godmode/run_export.html", context)

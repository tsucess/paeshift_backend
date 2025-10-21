"""
Simulation-related views for God Mode.

This module provides views for running and managing simulations in God Mode.
"""

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render


@staff_member_required
def run_simulation(request):
    """
    View for running a simulation.
    
    Args:
        request: HTTP request
        
    Returns:
        Rendered run simulation template
    """
    context = {
        "title": "Run Simulation",
    }
    return render(request, "godmode/run_simulation.html", context)


@staff_member_required
def simulations(request):
    """
    View for listing simulations.
    
    Args:
        request: HTTP request
        
    Returns:
        Rendered simulations template
    """
    context = {
        "title": "Simulations",
    }
    return render(request, "godmode/simulations.html", context)


@staff_member_required
def simulation_detail(request, simulation_id):
    """
    View for simulation details.
    
    Args:
        request: HTTP request
        simulation_id: Simulation ID
        
    Returns:
        Rendered simulation detail template
    """
    context = {
        "title": "Simulation Detail",
        "simulation_id": simulation_id,
    }
    return render(request, "godmode/simulation_detail.html", context)

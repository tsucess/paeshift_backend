"""
Example views with Redis caching integration.

This module provides example views that use Redis caching decorators
and utilities to improve performance and reduce database load.
"""

import logging
from typing import Dict, List, Optional

from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from core.cache import cache_api_response
from core.redis_decorators import (
    time_view,
    track_user_activity,
    use_cached_model,
    with_redis_lock,
)
from core.redis_models import get_cached_model
from core.redis_rate_limit import api_rate_limit
from jobs.models_example import CachedJob, JobCategory, JobSkill

logger = logging.getLogger(__name__)


@require_GET
@api_rate_limit(limit=100, window=60)  # 100 requests per minute
@cache_api_response(timeout=60 * 5)  # Cache for 5 minutes
@time_view("job_list")
@track_user_activity("view_job_list")
def job_list(request):
    """
    Get a list of jobs with caching.
    
    Args:
        request: HTTP request
        
    Returns:
        JsonResponse with job list
    """
    # Get query parameters
    category_id = request.GET.get("category")
    skill_id = request.GET.get("skill")
    location = request.GET.get("location")
    
    # Build queryset
    queryset = CachedJob.objects.filter(is_active=True)
    
    # Apply filters
    if category_id:
        queryset = queryset.filter(category_id=category_id)
        
    if skill_id:
        queryset = queryset.filter(skills__id=skill_id)
        
    if location:
        queryset = queryset.filter(location__icontains=location)
        
    # Get jobs
    jobs = []
    for job in queryset[:20]:  # Limit to 20 jobs
        # Cache the job
        job.cache()
        
        # Add to result
        jobs.append({
            "id": job.id,
            "title": job.title,
            "location": job.location,
            "category": {
                "id": job.category.id,
                "name": job.category.name,
            } if job.category else None,
        })
        
    return JsonResponse({
        "count": len(jobs),
        "results": jobs,
    })


@require_GET
@api_rate_limit(limit=200, window=60)  # 200 requests per minute
@cache_api_response(timeout=60 * 5)  # Cache for 5 minutes
@time_view("job_detail")
@track_user_activity("view_job_detail")
@use_cached_model("job", CachedJob)
def job_detail(request, job):
    """
    Get job details with caching.
    
    Args:
        request: HTTP request
        job: Job instance (from use_cached_model decorator)
        
    Returns:
        JsonResponse with job details
    """
    # Convert to dictionary
    job_data = {
        "id": job.id,
        "title": job.title,
        "description": job.description,
        "location": job.location,
        "salary": job.salary,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "is_active": job.is_active,
        "category": {
            "id": job.category.id,
            "name": job.category.name,
        } if job.category else None,
        "skills": [
            {
                "id": skill.id,
                "name": skill.name,
            } for skill in job.skills.all()
        ],
    }
    
    return JsonResponse(job_data)


@require_GET
@api_rate_limit(limit=100, window=60)  # 100 requests per minute
@cache_api_response(timeout=60 * 60)  # Cache for 1 hour
@time_view("category_list")
def category_list(request):
    """
    Get a list of job categories with caching.
    
    Args:
        request: HTTP request
        
    Returns:
        JsonResponse with category list
    """
    # Get categories
    categories = []
    for category in JobCategory.objects.all():
        # Cache the category
        category.cache()
        
        # Add to result
        categories.append({
            "id": category.id,
            "name": category.name,
            "description": category.description,
        })
        
    return JsonResponse({
        "count": len(categories),
        "results": categories,
    })


@require_GET
@api_rate_limit(limit=100, window=60)  # 100 requests per minute
@cache_api_response(timeout=60 * 60)  # Cache for 1 hour
@time_view("skill_list")
def skill_list(request):
    """
    Get a list of job skills with caching.
    
    Args:
        request: HTTP request
        
    Returns:
        JsonResponse with skill list
    """
    # Get query parameters
    category_id = request.GET.get("category")
    
    # Build queryset
    queryset = JobSkill.objects.all()
    
    # Apply filters
    if category_id:
        queryset = queryset.filter(category_id=category_id)
        
    # Get skills
    skills = []
    for skill in queryset:
        # Cache the skill
        skill.cache()
        
        # Add to result
        skills.append({
            "id": skill.id,
            "name": skill.name,
            "description": skill.description,
            "category": {
                "id": skill.category.id,
                "name": skill.category.name,
            } if skill.category else None,
        })
        
    return JsonResponse({
        "count": len(skills),
        "results": skills,
    })


@with_redis_lock("job_apply:{job_id}")
@time_view("job_apply")
@track_user_activity("apply_to_job")
def job_apply(request, job_id):
    """
    Apply to a job with Redis locking to prevent duplicate applications.
    
    Args:
        request: HTTP request
        job_id: Job ID
        
    Returns:
        JsonResponse with application status
    """
    # Get job from cache or database
    job = get_cached_model(CachedJob, job_id)
    
    if not job:
        raise Http404(f"Job with ID {job_id} not found")
        
    # Check if job is active
    if not job.is_active:
        return JsonResponse({
            "error": "Job is not active",
        }, status=400)
        
    # Process application
    # ... (application processing logic)
    
    return JsonResponse({
        "success": True,
        "message": f"Successfully applied to job: {job.title}",
    })

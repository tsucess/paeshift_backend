"""
Examples of using Redis caching in the Payshift application.

This module provides examples of how to use the Redis caching decorators
and utilities in different scenarios.
"""

import time
from typing import Dict, List, Optional

from django.db.models import Q

from accounts.models import User
from core.redis_decorators import redis_cache, cache_method_result
from jobs.models import Job, JobIndustry, Application
from userlocation.models import UserLocation

# Example 1: Simple function caching
@redis_cache(timeout=300, prefix="example", cache_type="api")
def get_user_by_id(user_id: int) -> Dict:
    """
    Get a user by ID with caching.
    
    This function will cache the result for 5 minutes (300 seconds).
    The cache key will include the user_id parameter.
    
    Args:
        user_id: User ID
        
    Returns:
        User data dictionary
    """
    print(f"Cache miss for user_id={user_id}, fetching from database")
    
    # Simulate database query
    time.sleep(0.5)  # Simulate slow database query
    
    # Get user from database
    user = User.objects.get(id=user_id)
    
    # Convert to dictionary
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_active": user.is_active,
        "date_joined": user.date_joined.isoformat(),
    }


# Example 2: Caching with multiple parameters
@redis_cache(
    timeout=600,  # 10 minutes
    prefix="jobs",
    cache_type="api",
    key_kwargs=["industry_id", "location", "page", "page_size"],  # Only include these kwargs in the cache key
)
def search_jobs(
    industry_id: Optional[int] = None,
    location: Optional[str] = None,
    min_salary: Optional[int] = None,
    max_salary: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    include_expired: bool = False,
) -> Dict:
    """
    Search for jobs with caching.
    
    This function will cache the result for 10 minutes (600 seconds).
    The cache key will include only the industry_id, location, page, and page_size parameters.
    
    Args:
        industry_id: Optional industry ID filter
        location: Optional location filter
        min_salary: Optional minimum salary filter
        max_salary: Optional maximum salary filter
        page: Page number
        page_size: Page size
        include_expired: Whether to include expired jobs
        
    Returns:
        Dictionary with job search results
    """
    print(f"Cache miss for job search, fetching from database")
    
    # Build query
    query = Q()
    
    if industry_id:
        query &= Q(industry_id=industry_id)
        
    if location:
        query &= Q(location__icontains=location)
        
    if min_salary:
        query &= Q(salary__gte=min_salary)
        
    if max_salary:
        query &= Q(salary__lte=max_salary)
        
    if not include_expired:
        query &= Q(is_expired=False)
    
    # Execute query with pagination
    offset = (page - 1) * page_size
    limit = page_size
    
    jobs = Job.objects.filter(query)[offset:offset + limit]
    total_count = Job.objects.filter(query).count()
    
    # Convert to dictionary
    results = []
    for job in jobs:
        results.append({
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "salary": job.salary,
            "created_at": job.created_at.isoformat(),
        })
    
    return {
        "results": results,
        "total_count": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": (total_count + page_size - 1) // page_size,
    }


# Example 3: Method caching
class JobService:
    """Service class for job-related operations."""
    
    @cache_method_result(timeout=3600, cache_type="job")
    def get_applications_for_job(self, job_id: int) -> List[Dict]:
        """
        Get applications for a job with caching.
        
        This method will cache the result for 1 hour (3600 seconds).
        The cache key will include the job_id parameter and the instance ID.
        
        Args:
            job_id: Job ID
            
        Returns:
            List of application dictionaries
        """
        print(f"Cache miss for applications of job_id={job_id}, fetching from database")
        
        # Get applications from database
        applications = Application.objects.filter(job_id=job_id)
        
        # Convert to dictionary
        results = []
        for app in applications:
            results.append({
                "id": app.id,
                "applicant_id": app.applicant_id,
                "status": app.status,
                "created_at": app.created_at.isoformat(),
            })
        
        return results
    
    def invalidate_job_cache(self, job_id: int) -> None:
        """
        Invalidate the cache for a job.
        
        This method demonstrates how to manually invalidate a cache entry.
        
        Args:
            job_id: Job ID
        """
        # Get the method reference
        method_ref = self.get_applications_for_job
        
        # Call the invalidate_cache method that was added by the decorator
        if hasattr(method_ref, "invalidate_cache"):
            method_ref.invalidate_cache(self, job_id)


# Example 4: Model method caching
class Job(models.Model):
    # ... existing model fields ...
    
    @cache_method_result(timeout=3600, cache_type="job")
    def get_related_jobs(self, limit: int = 5) -> List[Dict]:
        """
        Get related jobs with caching.
        
        This method will cache the result for 1 hour (3600 seconds).
        The cache key will include the limit parameter and the job ID.
        
        Args:
            limit: Maximum number of related jobs to return
            
        Returns:
            List of related job dictionaries
        """
        print(f"Cache miss for related jobs of job_id={self.id}, fetching from database")
        
        # Get related jobs from database
        related_jobs = Job.objects.filter(
            industry_id=self.industry_id,
            is_expired=False,
        ).exclude(id=self.id)[:limit]
        
        # Convert to dictionary
        results = []
        for job in related_jobs:
            results.append({
                "id": job.id,
                "title": job.title,
                "company": job.company,
                "location": job.location,
            })
        
        return results


# Example 5: Using cache invalidation
def update_job_status(job_id: int, new_status: str) -> bool:
    """
    Update a job's status and invalidate related caches.
    
    This function demonstrates how to manually invalidate caches
    when updating data.
    
    Args:
        job_id: Job ID
        new_status: New job status
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Update job in database
        job = Job.objects.get(id=job_id)
        job.status = new_status
        job.save()
        
        # Manually invalidate specific caches
        from core.redis.redis_invalidation import invalidate_model_cache
        invalidate_model_cache(Job, job_id)
        
        # Invalidate function cache
        search_jobs.invalidate_cache()
        
        return True
    except Exception as e:
        print(f"Error updating job status: {str(e)}")
        return False


# Example usage
if __name__ == "__main__":
    # Example 1: Simple function caching
    user_data = get_user_by_id(1)  # Cache miss, fetches from database
    user_data = get_user_by_id(1)  # Cache hit, returns cached data
    
    # Example 2: Caching with multiple parameters
    jobs = search_jobs(industry_id=1, location="New York", page=1)  # Cache miss
    jobs = search_jobs(industry_id=1, location="New York", page=1)  # Cache hit
    
    # Example 3: Method caching
    job_service = JobService()
    applications = job_service.get_applications_for_job(1)  # Cache miss
    applications = job_service.get_applications_for_job(1)  # Cache hit
    
    # Invalidate cache
    job_service.invalidate_job_cache(1)
    applications = job_service.get_applications_for_job(1)  # Cache miss again
    
    # Example 5: Using cache invalidation
    update_job_status(1, "closed")  # Updates database and invalidates caches

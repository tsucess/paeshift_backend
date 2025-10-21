"""
Example models with Redis caching integration.

This module provides example models that use the Redis caching mixin
to automatically cache model instances in Redis and keep the cache in sync
with database changes.
"""

from django.db import models

from core.redis_model_mixin import RedisCachedModelMixin


class JobCategory(models.Model, RedisCachedModelMixin):
    """
    Job category model with Redis caching.
    """
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Redis caching configuration
    cache_enabled = True
    cache_exclude = []
    
    def __str__(self):
        return self.name


class JobSkill(models.Model, RedisCachedModelMixin):
    """
    Job skill model with Redis caching.
    """
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    category = models.ForeignKey(JobCategory, on_delete=models.CASCADE, related_name="skills")
    
    # Redis caching configuration
    cache_enabled = True
    cache_exclude = []
    
    def __str__(self):
        return self.name


class CachedJob(models.Model, RedisCachedModelMixin):
    """
    Job model with Redis caching.
    """
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    location = models.CharField(max_length=200)
    salary = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    category = models.ForeignKey(JobCategory, on_delete=models.CASCADE, related_name="jobs")
    skills = models.ManyToManyField(JobSkill, related_name="jobs")
    
    # Redis caching configuration
    cache_enabled = True
    cache_related = ["category", "skills"]
    cache_exclude = []
    
    def __str__(self):
        return self.title
    
    def to_dict(self):
        """
        Convert the model instance to a dictionary.
        
        Returns:
            Dictionary representation of the instance
        """
        # Get base dictionary from parent class
        data = super().to_dict()
        
        # Add custom fields
        data["skill_count"] = self.skills.count()
        
        # Add computed fields
        data["is_new"] = (self.created_at is not None and 
                          (self.updated_at - self.created_at).days < 7)
        
        return data


# Example view function using the cached model
def get_job_details(job_id):
    """
    Get job details using the cached model.
    
    Args:
        job_id: Job ID
        
    Returns:
        Job details dictionary
    """
    # Get job from cache or database
    job = CachedJob.get_cached(job_id)
    
    if not job:
        return None
        
    # Convert to dictionary
    return {
        "id": job.id,
        "title": job.title,
        "description": job.description,
        "location": job.location,
        "salary": job.salary,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
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

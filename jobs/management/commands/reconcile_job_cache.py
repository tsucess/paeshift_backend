"""
Management command to reconcile job cache with database.

This command ensures that the cache is consistent with the database by:
1. Removing cache entries for jobs that no longer exist in the database
2. Adding cache entries for jobs that exist in the database but not in the cache
"""

import logging
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone

from jobs.models import Job
from core.cache import get_cache_stats, invalidate_cache_pattern, redis_client

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Reconcile job cache with database to ensure consistency'

    def add_arguments(self, parser):
        parser.add_argument('--client_id', type=int, help='Specific client ID to reconcile cache for')
        parser.add_argument('--full', action='store_true', help='Perform a full reconciliation (slower but more thorough)')

    def handle(self, *args, **options):
        client_id = options.get('client_id')
        full_reconciliation = options.get('full')
        
        self.stdout.write(self.style.SUCCESS(f'Starting job cache reconciliation...'))
        
        # Get initial cache stats
        initial_stats = get_cache_stats()
        self.stdout.write(f'Initial cache stats: {initial_stats}')
        
        # Reconcile job cache
        removed, added = self._reconcile_job_cache(client_id, full_reconciliation)
        
        # Get final cache stats
        final_stats = get_cache_stats()
        self.stdout.write(f'Final cache stats: {final_stats}')
        
        # Calculate difference
        keys_diff = final_stats.get('total_keys', 0) - initial_stats.get('total_keys', 0)
        self.stdout.write(self.style.SUCCESS(
            f'Cache reconciliation complete. Removed {removed} stale entries, added {added} missing entries. '
            f'Net change: {keys_diff} keys.'
        ))

    def _reconcile_job_cache(self, client_id=None, full_reconciliation=False):
        """Reconcile job cache with database"""
        self.stdout.write('Reconciling job cache with database...')
        
        # Track stats
        removed_count = 0
        added_count = 0
        
        # 1. Remove stale cache entries
        if full_reconciliation:
            # Get all job IDs from cache
            job_keys = redis_client.keys('job:*')
            model_job_keys = redis_client.keys('model:job:*')
            
            # Extract job IDs from keys
            job_ids_from_cache = set()
            for key in job_keys:
                try:
                    job_id = int(key.split(':')[1])
                    job_ids_from_cache.add(job_id)
                except (ValueError, IndexError):
                    continue
                    
            for key in model_job_keys:
                try:
                    job_id = int(key.split(':')[2])
                    job_ids_from_cache.add(job_id)
                except (ValueError, IndexError):
                    continue
            
            # Get all job IDs from database
            job_query = Job.objects.all()
            if client_id:
                job_query = job_query.filter(client_id=client_id)
            job_ids_from_db = set(job_query.values_list('id', flat=True))
            
            # Find stale cache entries
            stale_job_ids = job_ids_from_cache - job_ids_from_db
            
            # Remove stale cache entries
            for job_id in stale_job_ids:
                invalidate_cache_pattern(f'job:{job_id}')
                invalidate_cache_pattern(f'model:job:{job_id}')
                removed_count += 1
                
            self.stdout.write(self.style.SUCCESS(f'Removed {removed_count} stale job cache entries'))
        
        # 2. Add missing cache entries
        job_query = Job.objects.all()
        if client_id:
            job_query = job_query.filter(client_id=client_id)
            
        # Limit to recent jobs to avoid caching everything
        recent_date = timezone.now() - timezone.timedelta(days=30)
        job_query = job_query.filter(date__gte=recent_date)
        
        # Cache each job
        for job in job_query:
            try:
                # Check if job is already in cache
                job_key = f'model:job:{job.id}'
                if not redis_client.exists(job_key):
                    # Cache the job
                    job.cache()
                    added_count += 1
                    
                    if added_count % 100 == 0:
                        self.stdout.write(f'Cached {added_count} jobs...')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error caching job {job.id}: {str(e)}'))
                
        self.stdout.write(self.style.SUCCESS(f'Added {added_count} missing job cache entries'))
        
        # 3. Invalidate client jobs cache to force refresh
        if client_id:
            invalidate_cache_pattern(f'clientjobs:u:{client_id}:*')
        else:
            invalidate_cache_pattern('clientjobs:*')
            
        return removed_count, added_count

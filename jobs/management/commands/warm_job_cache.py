"""
Management command to warm the job cache.

This command proactively caches frequently accessed data to improve performance.
"""

import logging
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone

from jobs.models import Job
from core.cache import get_cache_stats

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Warm the job cache by proactively caching frequently accessed data'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=7, help='Number of days of recent jobs to cache')
        parser.add_argument('--limit', type=int, default=100, help='Maximum number of jobs to cache per client')
        parser.add_argument('--client_id', type=int, help='Specific client ID to warm cache for')

    def handle(self, *args, **options):
        days = options.get('days')
        limit = options.get('limit')
        client_id = options.get('client_id')
        
        self.stdout.write(self.style.SUCCESS(f'Starting job cache warming...'))
        
        # Get initial cache stats
        initial_stats = get_cache_stats()
        self.stdout.write(f'Initial cache stats: {initial_stats}')
        
        # Cache recent jobs
        self._cache_recent_jobs(days, limit, client_id)
        
        # Cache client jobs
        self._cache_client_jobs(days, limit, client_id)
        
        # Get final cache stats
        final_stats = get_cache_stats()
        self.stdout.write(f'Final cache stats: {final_stats}')
        
        # Calculate difference
        keys_added = final_stats.get('total_keys', 0) - initial_stats.get('total_keys', 0)
        self.stdout.write(self.style.SUCCESS(f'Cache warming complete. Added {keys_added} keys to cache.'))

    def _cache_recent_jobs(self, days, limit, client_id=None):
        """Cache recent jobs"""
        self.stdout.write('Caching recent jobs...')
        
        # Get recent jobs
        recent_date = timezone.now() - timezone.timedelta(days=days)
        jobs_query = Job.objects.filter(date__gte=recent_date)
        
        # Filter by client if specified
        if client_id:
            jobs_query = jobs_query.filter(client_id=client_id)
        
        # Limit the number of jobs
        jobs = jobs_query.order_by('-date')[:limit]
        
        # Cache each job
        count = 0
        for job in jobs:
            try:
                job.cache()
                count += 1
                if count % 10 == 0:
                    self.stdout.write(f'Cached {count} jobs...')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error caching job {job.id}: {str(e)}'))
        
        self.stdout.write(self.style.SUCCESS(f'Cached {count} recent jobs'))

    def _cache_client_jobs(self, days, limit, client_id=None):
        """Cache client jobs endpoints"""
        self.stdout.write('Caching client jobs endpoints...')
        
        # Get active clients
        if client_id:
            clients = User.objects.filter(id=client_id, role='client')
        else:
            # Get clients with recent jobs
            recent_date = timezone.now() - timezone.timedelta(days=days)
            clients = User.objects.filter(
                jobs_as_client__date__gte=recent_date,
                role='client'
            ).distinct()
        
        # Cache client jobs for each client
        count = 0
        for client in clients:
            try:
                # Get client's jobs
                jobs = Job.objects.filter(client=client).order_by('-date')[:limit]
                
                # Cache each job
                for job in jobs:
                    job.cache()
                
                # Simulate a request to the client jobs endpoint to cache it
                from django.test import Client as TestClient
                test_client = TestClient()
                response = test_client.get(f'/jobs/clients/clientjobs/{client.id}')
                
                if response.status_code == 200:
                    count += 1
                    self.stdout.write(f'Cached client jobs for client {client.id}')
                else:
                    self.stdout.write(self.style.ERROR(f'Error caching client jobs for client {client.id}: {response.status_code}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error caching client jobs for client {client.id}: {str(e)}'))
        
        self.stdout.write(self.style.SUCCESS(f'Cached client jobs for {count} clients'))

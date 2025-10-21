import logging
import random
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone

from jobs.models import Job, JobIndustry, JobSubCategory
from core.cache import get_cache_stats, invalidate_cache_pattern

User = get_user_model()
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Simulate client job creation and test caching'

    def add_arguments(self, parser):
        parser.add_argument('--client_id', type=int, help='Specific client ID to use')
        parser.add_argument('--num_jobs', type=int, default=3, help='Number of jobs to create')
        parser.add_argument('--clear_cache', action='store_true', help='Clear cache before testing')

    def handle(self, *args, **options):
        client_id = options.get('client_id')
        num_jobs = options.get('num_jobs')
        clear_cache = options.get('clear_cache')

        # Clear cache if requested
        if clear_cache:
            self.stdout.write(self.style.WARNING('Clearing cache...'))
            invalidate_cache_pattern('clientjobs:*')
            invalidate_cache_pattern('job:*')
            self.stdout.write(self.style.SUCCESS('Cache cleared'))

        # Get or create test client
        client = self._get_or_create_client(client_id)
        self.stdout.write(self.style.SUCCESS(f'Using client: {client.username} (ID: {client.id})'))

        # Create test jobs
        self._create_test_jobs(client, num_jobs)

        # Test clientjobs endpoint
        self._test_clientjobs_endpoint(client.id)

        # Print cache stats
        self._print_cache_stats()

    def _get_or_create_client(self, client_id=None):
        """Get existing client or create a new test client"""
        if client_id:
            try:
                return User.objects.get(id=client_id)
            except User.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'Client with ID {client_id} not found, creating new test client'))

        # Create a new test client
        username = f'testclient_{timezone.now().strftime("%Y%m%d%H%M%S")}'
        client = User.objects.create_user(
            username=username,
            email=f'{username}@example.com',
            password='testpassword',
            first_name='Test',
            last_name='Client',
            role='client'
        )
        return client

    def _create_test_jobs(self, client, num_jobs):
        """Create test jobs for the client"""
        self.stdout.write(self.style.WARNING(f'Creating {num_jobs} test jobs for client {client.username}...'))

        # Get random industry and subcategory
        try:
            industry = JobIndustry.objects.order_by('?').first()
            if not industry:
                industry = JobIndustry.objects.create(name=f'Test Industry {random.randint(1, 1000)}')

            subcategory = JobSubCategory.objects.filter(industry=industry).order_by('?').first()
            if not subcategory:
                subcategory = JobSubCategory.objects.create(
                    industry=industry,
                    name=f'Test Subcategory {random.randint(1, 1000)}'
                )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error getting industry/subcategory: {e}'))
            industry = None
            subcategory = None

        # Create jobs
        jobs_created = []
        for i in range(num_jobs):
            try:
                # Generate random job data
                start_time = timezone.now().replace(hour=9, minute=0, second=0, microsecond=0)
                end_time = start_time.replace(hour=17)

                job = Job.objects.create(
                    title=f'Test Job {timezone.now().strftime("%Y%m%d%H%M%S")}_{i}',
                    description=f'This is a test job created by the simulation script',
                    client=client,
                    created_by=client,
                    industry=industry,
                    subcategory=subcategory,
                    job_type=Job.JobType.SINGLE_DAY,
                    shift_type=Job.ShiftType.DAY,
                    date=(timezone.now() + timedelta(days=i+1)).date(),
                    start_time=start_time.time(),
                    end_time=end_time.time(),
                    rate=random.randint(15, 50),
                    location=f'Test Location {i}',
                    applicants_needed=random.randint(1, 5),
                    status=Job.Status.PENDING
                )
                jobs_created.append(job)
                self.stdout.write(self.style.SUCCESS(f'Created job: {job.title} (ID: {job.id})'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error creating job: {e}'))

        self.stdout.write(self.style.SUCCESS(f'Created {len(jobs_created)} jobs for client {client.username}'))
        return jobs_created

    def _test_clientjobs_endpoint(self, client_id):
        """Test the clientjobs endpoint using Django's test client"""
        from django.test import Client as TestClient
        from django.urls import reverse
        import json
        import time
        from django.conf import settings

        # Add 'localhost' to ALLOWED_HOSTS temporarily
        original_allowed_hosts = settings.ALLOWED_HOSTS
        settings.ALLOWED_HOSTS = list(original_allowed_hosts) + ['testserver', 'localhost', '127.0.0.1']

        test_client = TestClient(HTTP_HOST='localhost')

        # First request (should be a cache miss)
        self.stdout.write(self.style.WARNING('Making first request to clientjobs endpoint (should be cache miss)...'))
        start_time = time.time()
        response = test_client.get(f'/jobs/clients/clientjobs/{client_id}')
        first_request_time = time.time() - start_time

        if response.status_code == 200:
            data = json.loads(response.content)
            self.stdout.write(self.style.SUCCESS(f'First request successful - returned {len(data["jobs"])} jobs in {first_request_time:.4f} seconds'))
        else:
            self.stdout.write(self.style.ERROR(f'First request failed with status code {response.status_code}'))
            return

        # Second request (should be a cache hit)
        self.stdout.write(self.style.WARNING('Making second request to clientjobs endpoint (should be cache hit)...'))
        start_time = time.time()
        response = test_client.get(f'/jobs/clients/clientjobs/{client_id}')
        second_request_time = time.time() - start_time

        if response.status_code == 200:
            data = json.loads(response.content)
            self.stdout.write(self.style.SUCCESS(f'Second request successful - returned {len(data["jobs"])} jobs in {second_request_time:.4f} seconds'))

            # Compare times to see if caching is working
            if second_request_time < first_request_time:
                self.stdout.write(self.style.SUCCESS(f'Caching is working! Second request was {first_request_time/second_request_time:.2f}x faster'))
            else:
                self.stdout.write(self.style.WARNING(f'Caching might not be working properly. Second request took {second_request_time:.4f}s vs first request {first_request_time:.4f}s'))
        else:
            self.stdout.write(self.style.ERROR(f'Second request failed with status code {response.status_code}'))

        # Restore original ALLOWED_HOSTS
        settings.ALLOWED_HOSTS = original_allowed_hosts

    def _print_cache_stats(self):
        """Print Redis cache statistics"""
        self.stdout.write(self.style.WARNING('Cache statistics:'))
        stats = get_cache_stats()

        # Format and print stats
        self.stdout.write(f'Total keys: {stats.get("total_keys", "N/A")}')
        self.stdout.write(f'Hit rate: {stats.get("hit_rate", "N/A")}%')
        self.stdout.write(f'Hits: {stats.get("hits", "N/A")}')
        self.stdout.write(f'Misses: {stats.get("misses", "N/A")}')

        # Print key counts by type
        key_counts = stats.get("key_counts_by_type", {})
        self.stdout.write('Key counts by type:')
        for key_type, count in key_counts.items():
            if count > 0:
                self.stdout.write(f'  - {key_type}: {count}')

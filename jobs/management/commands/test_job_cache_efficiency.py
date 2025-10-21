import logging
import random
import time
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.test import Client as TestClient
from django.conf import settings
import json

from jobs.models import Job, JobIndustry, JobSubCategory
from core.cache import get_cache_stats, invalidate_cache_pattern
from django.core.cache import cache as redis_client

User = get_user_model()
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Test job cache efficiency with create, update, and delete operations'

    def add_arguments(self, parser):
        parser.add_argument('--client_id', type=int, default=135, help='Client ID to use')
        parser.add_argument('--clear_cache', action='store_true', help='Clear cache before testing')

    def handle(self, *args, **options):
        client_id = options.get('client_id')
        clear_cache = options.get('clear_cache')

        self.stdout.write(self.style.SUCCESS(f'Starting cache efficiency test for client ID: {client_id}'))

        # Setup test environment
        self._setup_test_environment()

        # Clear cache if requested
        if clear_cache:
            self.stdout.write(self.style.WARNING('Clearing cache...'))
            invalidate_cache_pattern('clientjobs:*')
            invalidate_cache_pattern('job:*')
            self.stdout.write(self.style.SUCCESS('Cache cleared'))

        # Get client
        try:
            client = User.objects.get(id=client_id)
            self.stdout.write(self.style.SUCCESS(f'Using client: {client.username} (ID: {client.id})'))
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Client with ID {client_id} not found'))
            return

        # Test cache efficiency
        self._test_cache_efficiency(client)

        # Restore test environment
        self._restore_test_environment()

    def _setup_test_environment(self):
        """Setup test environment"""
        # Add test hosts to ALLOWED_HOSTS
        self.original_allowed_hosts = settings.ALLOWED_HOSTS
        settings.ALLOWED_HOSTS = list(self.original_allowed_hosts) + ['testserver', 'localhost', '127.0.0.1']

        # Create test client
        self.test_client = TestClient(HTTP_HOST='localhost')

        # Store initial cache stats
        self.initial_stats = get_cache_stats()
        self.stdout.write(self.style.SUCCESS('Test environment setup complete'))

    def _restore_test_environment(self):
        """Restore test environment"""
        # Restore ALLOWED_HOSTS
        settings.ALLOWED_HOSTS = self.original_allowed_hosts
        self.stdout.write(self.style.SUCCESS('Test environment restored'))

    def _test_cache_efficiency(self, client):
        """Test cache efficiency with create, update, and delete operations"""
        self.stdout.write(self.style.NOTICE('\n=== TESTING CACHE EFFICIENCY ===\n'))

        # 1. Test initial cache state
        self._test_initial_cache(client)

        # 2. Test job creation and caching
        job = self._test_job_creation(client)

        # 3. Test job update and cache invalidation
        if job:
            self._test_job_update(client, job)

        # 4. Test job deletion and cache invalidation
            self._test_job_deletion(client, job)

        # 5. Print final cache stats
        self._print_cache_efficiency()

    def _test_initial_cache(self, client):
        """Test initial cache state"""
        self.stdout.write(self.style.NOTICE('\n1. Testing Initial Cache State\n'))

        # Make first request to get client jobs (might be cache miss)
        self.stdout.write('Making first request to get client jobs...')
        start_time = time.time()
        response = self.test_client.get(f'/jobs/clients/clientjobs/{client.id}')
        first_request_time = time.time() - start_time

        if response.status_code == 200:
            data = json.loads(response.content)
            initial_job_count = len(data['jobs'])
            self.stdout.write(self.style.SUCCESS(
                f'First request successful - found {initial_job_count} jobs in {first_request_time:.4f} seconds'
            ))

            # Make second request (should be cache hit)
            self.stdout.write('Making second request (should be cache hit)...')
            start_time = time.time()
            response = self.test_client.get(f'/jobs/clients/clientjobs/{client.id}')
            second_request_time = time.time() - start_time

            if response.status_code == 200:
                data = json.loads(response.content)
                self.stdout.write(self.style.SUCCESS(
                    f'Second request successful - returned {len(data["jobs"])} jobs in {second_request_time:.4f} seconds'
                ))

                # Calculate speedup
                if first_request_time > 0:
                    speedup = first_request_time / second_request_time
                    self.stdout.write(self.style.SUCCESS(
                        f'Cache hit speedup: {speedup:.2f}x faster'
                    ))

                    # Check if speedup is significant (>5x)
                    if speedup > 5:
                        self.stdout.write(self.style.SUCCESS('✅ Initial cache is working efficiently'))
                    else:
                        self.stdout.write(self.style.WARNING('⚠️ Initial cache speedup is lower than expected'))
            else:
                self.stdout.write(self.style.ERROR(f'Second request failed with status code {response.status_code}'))
        else:
            self.stdout.write(self.style.ERROR(f'First request failed with status code {response.status_code}'))

    def _test_job_creation(self, client):
        """Test job creation and caching"""
        self.stdout.write(self.style.NOTICE('\n2. Testing Job Creation and Caching\n'))

        # Get or create industry and subcategory
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
            return None

        # Create a new job
        try:
            # Generate random job data
            start_time = timezone.now().replace(hour=9, minute=0, second=0, microsecond=0)
            end_time = start_time.replace(hour=17)

            job_title = f'Cache Test Job {timezone.now().strftime("%Y%m%d%H%M%S")}'

            self.stdout.write(f'Creating new job: {job_title}')
            job = Job.objects.create(
                title=job_title,
                description=f'This is a test job created to test cache efficiency',
                client=client,
                created_by=client,
                industry=industry,
                subcategory=subcategory,
                job_type=Job.JobType.SINGLE_DAY,
                shift_type=Job.ShiftType.DAY,
                date=(timezone.now() + timedelta(days=1)).date(),
                start_time=start_time.time(),
                end_time=end_time.time(),
                rate=random.randint(15, 50),
                location=f'123 Test Street, New York, NY',
                applicants_needed=random.randint(1, 5),
                status=Job.Status.PENDING
            )
            self.stdout.write(self.style.SUCCESS(f'Created job: {job.title} (ID: {job.id})'))

            # Check if job is in cache - try different cache key formats
            possible_keys = [
                f"job:{job.id}",
                f"model:job:{job.id}",
                f"model:job:{job.id}:v1.0"
            ]

            self.stdout.write(f'Checking for job in cache with possible keys: {possible_keys}')

            job_in_cache = False
            for key in possible_keys:
                cached_job = redis_client.get(key)
                if cached_job:
                    self.stdout.write(self.style.SUCCESS(f'✅ Job {job.id} found in cache with key: {key}'))
                    job_in_cache = True
                    break

            if not job_in_cache:
                self.stdout.write(self.style.WARNING(f'⚠️ Job {job.id} is not in cache with any of the expected keys'))

            # Force cache the job
            self.stdout.write('Forcing job to be cached...')
            job.cache()

            # Invalidate the clientjobs cache to force a fresh fetch
            self.stdout.write('Invalidating clientjobs cache to force a fresh fetch...')
            invalidate_cache_pattern('clientjobs:*')

            # Make request to get client jobs (should include new job)
            self.stdout.write('Making request to get client jobs after creation...')
            response = self.test_client.get(f'/jobs/clients/clientjobs/{client.id}')

            if response.status_code == 200:
                data = json.loads(response.content)

                # Check if new job is in response
                job_found = False
                for job_data in data['jobs']:
                    if job_data.get('id') == job.id:
                        job_found = True
                        break

                if job_found:
                    self.stdout.write(self.style.SUCCESS(f'✅ New job {job.id} found in client jobs response'))
                else:
                    self.stdout.write(self.style.ERROR(f'❌ New job {job.id} not found in client jobs response'))

                    # Debug: Print all job IDs in the response
                    job_ids = [job_data.get('id') for job_data in data['jobs']]
                    self.stdout.write(f'Jobs in response: {job_ids}')
            else:
                self.stdout.write(self.style.ERROR(f'Request failed with status code {response.status_code}'))

            return job

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error creating job: {e}'))
            return None

    def _test_job_update(self, client, job):
        """Test job update and cache invalidation"""
        self.stdout.write(self.style.NOTICE('\n3. Testing Job Update and Cache Invalidation\n'))

        if not job:
            self.stdout.write(self.style.ERROR('No job to update'))
            return

        # Find the correct cache key for the job
        possible_keys = [
            f"job:{job.id}",
            f"model:job:{job.id}",
            f"model:job:{job.id}:v1.0"
        ]

        cache_key = None
        cached_job_before = None

        for key in possible_keys:
            cached_data = redis_client.get(key)
            if cached_data:
                cache_key = key
                cached_job_before = cached_data
                self.stdout.write(self.style.SUCCESS(f'Found job in cache with key: {key}'))
                break

        if not cache_key:
            self.stdout.write(self.style.WARNING('Job not found in cache before update, forcing cache...'))
            job.cache()
            # Try again to find the cache key
            for key in possible_keys:
                cached_data = redis_client.get(key)
                if cached_data:
                    cache_key = key
                    cached_job_before = cached_data
                    self.stdout.write(self.style.SUCCESS(f'Found job in cache after forcing with key: {key}'))
                    break

        # Update job
        new_title = f'{job.title} - UPDATED'
        self.stdout.write(f'Updating job {job.id} title to: {new_title}')

        job.title = new_title
        job.save()

        self.stdout.write(self.style.SUCCESS(f'Updated job {job.id}'))

        # Check if job cache was updated
        if cache_key:
            cached_job_after = redis_client.get(cache_key)

            if cached_job_after and cached_job_after != cached_job_before:
                self.stdout.write(self.style.SUCCESS(f'✅ Job {job.id} cache was updated after job update'))
            else:
                self.stdout.write(self.style.ERROR(f'❌ Job {job.id} cache was not updated after job update'))
        else:
            self.stdout.write(self.style.ERROR('Could not find job in cache to check update'))

        # Invalidate the clientjobs cache to force a fresh fetch
        self.stdout.write('Invalidating clientjobs cache to force a fresh fetch...')
        invalidate_cache_pattern('clientjobs:*')

        # Make request to get client jobs (should include updated job)
        self.stdout.write('Making request to get client jobs after update...')
        response = self.test_client.get(f'/jobs/clients/clientjobs/{client.id}')

        if response.status_code == 200:
            data = json.loads(response.content)

            # Check if updated job is in response
            job_updated = False
            for job_data in data['jobs']:
                if job_data.get('id') == job.id and job_data.get('title') == new_title:
                    job_updated = True
                    break

            if job_updated:
                self.stdout.write(self.style.SUCCESS(f'✅ Updated job {job.id} found in client jobs response'))
            else:
                self.stdout.write(self.style.ERROR(f'❌ Updated job {job.id} not found in client jobs response'))

                # Debug: Print all job IDs and titles in the response
                job_info = [(job_data.get('id'), job_data.get('title')) for job_data in data['jobs']]
                self.stdout.write(f'Jobs in response: {job_info}')
        else:
            self.stdout.write(self.style.ERROR(f'Request failed with status code {response.status_code}'))

    def _test_job_deletion(self, client, job):
        """Test job deletion and cache invalidation"""
        self.stdout.write(self.style.NOTICE('\n4. Testing Job Deletion and Cache Invalidation\n'))

        if not job:
            self.stdout.write(self.style.ERROR('No job to delete'))
            return

        # Get job ID before deletion
        job_id = job.id

        # Delete job
        self.stdout.write(f'Deleting job {job_id}')
        job.delete()

        self.stdout.write(self.style.SUCCESS(f'Deleted job {job_id}'))

        # Check if job was removed from cache - try all possible keys
        possible_keys = [
            f"job:{job_id}",
            f"model:job:{job_id}",
            f"model:job:{job_id}:v1.0"
        ]

        job_still_in_cache = False
        for key in possible_keys:
            cached_job = redis_client.get(key)
            if cached_job:
                job_still_in_cache = True
                self.stdout.write(self.style.ERROR(f'❌ Job {job_id} is still in cache after deletion with key: {key}'))

        if not job_still_in_cache:
            self.stdout.write(self.style.SUCCESS(f'✅ Job {job_id} was removed from cache after deletion'))

        # Invalidate the clientjobs cache to force a fresh fetch
        self.stdout.write('Invalidating clientjobs cache to force a fresh fetch...')
        invalidate_cache_pattern('clientjobs:*')

        # Make request to get client jobs (should not include deleted job)
        self.stdout.write('Making request to get client jobs after deletion...')
        response = self.test_client.get(f'/jobs/clients/clientjobs/{client.id}')

        if response.status_code == 200:
            data = json.loads(response.content)

            # Check if deleted job is not in response
            job_found = False
            for job_data in data['jobs']:
                if job_data.get('id') == job_id:
                    job_found = True
                    break

            if not job_found:
                self.stdout.write(self.style.SUCCESS(f'✅ Deleted job {job_id} not found in client jobs response'))
            else:
                self.stdout.write(self.style.ERROR(f'❌ Deleted job {job_id} still found in client jobs response'))

            # Debug: Print all job IDs in the response
            job_ids = [job_data.get('id') for job_data in data['jobs']]
            self.stdout.write(f'Jobs in response after deletion: {job_ids}')
        else:
            self.stdout.write(self.style.ERROR(f'Request failed with status code {response.status_code}'))

    def _print_cache_efficiency(self):
        """Print cache efficiency statistics"""
        self.stdout.write(self.style.NOTICE('\n5. Cache Efficiency Statistics\n'))

        # Get current cache stats
        current_stats = get_cache_stats()

        # Calculate hit rate
        hit_rate = current_stats.get('hit_rate', 0)
        hits = current_stats.get('hits', 0)
        misses = current_stats.get('misses', 0)

        self.stdout.write(f'Cache hit rate: {hit_rate:.2f}%')
        self.stdout.write(f'Cache hits: {hits}')
        self.stdout.write(f'Cache misses: {misses}')

        # Print key counts
        key_counts = current_stats.get('key_counts_by_type', {})
        self.stdout.write('Cache key counts:')
        for key_type, count in key_counts.items():
            if count > 0:
                self.stdout.write(f'  - {key_type}: {count}')

        # Evaluate overall efficiency
        if hit_rate >= 90:
            self.stdout.write(self.style.SUCCESS('\n✅ CACHE EFFICIENCY: EXCELLENT (90%+ hit rate)'))
        elif hit_rate >= 75:
            self.stdout.write(self.style.SUCCESS('\n✅ CACHE EFFICIENCY: GOOD (75%+ hit rate)'))
        elif hit_rate >= 50:
            self.stdout.write(self.style.WARNING('\n⚠️ CACHE EFFICIENCY: MODERATE (50%+ hit rate)'))
        else:
            self.stdout.write(self.style.ERROR('\n❌ CACHE EFFICIENCY: POOR (<50% hit rate)'))

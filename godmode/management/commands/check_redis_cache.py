"""
Django management command to check Redis cache status.

This command allows checking the Redis cache status from the command line.
"""

import logging
import time

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Check Redis cache status and perform basic operations"

    def add_arguments(self, parser):
        parser.add_argument(
            "--test-keys", type=int, default=5, help="Number of test keys to create"
        )
        parser.add_argument(
            "--cleanup", action="store_true", help="Clean up test keys after running"
        )

    def handle(self, *args, **options):
        test_keys = options["test_keys"]
        cleanup = options["cleanup"]

        self.stdout.write(self.style.SUCCESS("Starting Redis cache check..."))

        # Check if Redis is running
        try:
            cache.set("redis_test", "connected", 5)
            result = cache.get("redis_test")
            if result == "connected":
                self.stdout.write(
                    self.style.SUCCESS("✅ Redis is running and accessible")
                )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        "❌ Redis is running but not storing values correctly"
                    )
                )
                return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Redis connection error: {str(e)}"))
            return

        # Test basic operations
        self.stdout.write(self.style.NOTICE("Testing basic cache operations..."))

        # Test setting and getting values
        start_time = time.time()
        for i in range(test_keys):
            key = f"test:key:{i}"
            value = f"test-value-{i}-{timezone.now().isoformat()}"
            cache.set(key, value, 60)

        set_time = time.time() - start_time
        self.stdout.write(f"  - Set {test_keys} keys in {set_time:.4f} seconds")

        # Test retrieving values
        start_time = time.time()
        hits = 0
        for i in range(test_keys):
            key = f"test:key:{i}"
            value = cache.get(key)
            if value:
                hits += 1

        get_time = time.time() - start_time
        self.stdout.write(
            f"  - Retrieved {hits}/{test_keys} keys in {get_time:.4f} seconds"
        )

        # Test cache invalidation
        if hits > 0:
            start_time = time.time()
            deleted = 0
            for i in range(test_keys):
                key = f"test:key:{i}"
                if cache.delete(key):
                    deleted += 1

            delete_time = time.time() - start_time
            self.stdout.write(
                f"  - Deleted {deleted}/{test_keys} keys in {delete_time:.4f} seconds"
            )

        # Clean up test keys if requested
        if cleanup:
            self.stdout.write(self.style.NOTICE("Cleaning up test keys..."))
            for i in range(test_keys):
                cache.delete(f"test:key:{i}")

        # Summary
        self.stdout.write(
            self.style.SUCCESS("Redis cache check completed successfully!")
        )
        self.stdout.write("Summary:")
        self.stdout.write(f"  - Cache backend: {cache.__class__.__name__}")
        self.stdout.write(
            f"  - Set operation speed: {(set_time / test_keys) * 1000:.2f} ms per key"
        )
        self.stdout.write(
            f"  - Get operation speed: {(get_time / test_keys) * 1000:.2f} ms per key"
        )
        if hits > 0:
            self.stdout.write(
                f"  - Delete operation speed: {(delete_time / deleted) * 1000:.2f} ms per key"
            )

        self.stdout.write(self.style.SUCCESS("✅ Redis cache is working correctly"))

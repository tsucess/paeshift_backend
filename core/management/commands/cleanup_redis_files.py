"""
Management command to clean up redundant Redis caching files.

This command removes redundant Redis caching files that have been consolidated
into other files to eliminate redundancy.
"""

import os
import sys
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Clean up redundant Redis caching files"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting",
        )

    def handle(self, **options):
        dry_run = options.get("dry-run", False)

        # Files to be removed
        redundant_files = [
            "redis_decorators_v2.py",
            "cache_warming.py",
            "redis_timestamp_decorators.py",
        ]

        # Get the core directory path
        core_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        # Print the core directory path
        self.stdout.write(f"Core directory: {core_dir}")

        # Count of files deleted
        deleted_count = 0

        for filename in redundant_files:
            file_path = os.path.join(core_dir, filename)

            if os.path.exists(file_path):
                if dry_run:
                    self.stdout.write(f"Would delete: {file_path}")
                else:
                    try:
                        os.remove(file_path)
                        deleted_count += 1
                        self.stdout.write(f"Deleted: {file_path}")
                    except Exception as e:
                        self.stdout.write(f"Error deleting {file_path}: {str(e)}")
            else:
                self.stdout.write(f"File not found: {file_path}")

        # Summary
        if dry_run:
            self.stdout.write(f"Dry run completed. Would delete {len(redundant_files)} files.")
        else:
            self.stdout.write(f"Cleanup completed. Deleted {deleted_count} of {len(redundant_files)} files.")

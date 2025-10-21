"""
Management command to reconcile cache with database.

This command ensures that the cache is consistent with the database by:
1. Checking for missing cache entries and creating them
2. Checking for stale cache entries and updating them
3. Checking for orphaned cache entries and removing them
"""

import logging
import time
from django.core.management.base import BaseCommand, CommandError
from django.apps import apps

from godmode.cache_sync import reconcile_cache_for_model, reconcile_all_caches

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Reconcile cache with database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            type=str,
            help='Model to reconcile (app_label.model_name)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force reconciliation even if timestamps suggest DB is older',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of instances to process in each batch',
        )
        parser.add_argument(
            '--max-instances',
            type=int,
            default=1000,
            help='Maximum number of instances to process per model',
        )
        parser.add_argument(
            '--check-only',
            action='store_true',
            help='Only check for inconsistencies without fixing them',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output',
        )

    def handle(self, *args, **options):
        model_name = options.get('model')
        force = options.get('force', False)
        batch_size = options.get('batch_size', 100)
        max_instances = options.get('max_instances', 1000)
        check_only = options.get('check_only', False)
        verbose = options.get('verbose', False)

        # Set up logging
        if verbose:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)

        start_time = time.time()

        if model_name:
            # Reconcile specific model
            try:
                app_label, model_name = model_name.split('.')
                model = apps.get_model(app_label, model_name)
            except ValueError:
                raise CommandError(f"Invalid model name: {model_name}. Use format 'app_label.model_name'")
            except LookupError:
                raise CommandError(f"Model not found: {model_name}")

            self.stdout.write(f"Reconciling cache for {model._meta.label}...")

            if check_only:
                from godmode.cache_sync import check_cache_consistency
                stats = check_cache_consistency(model, sample_size=max_instances)
                self.stdout.write(self.style.SUCCESS(
                    f"Cache consistency check for {model._meta.label}: "
                    f"{stats['total']} instances checked, "
                    f"{stats['consistent']} consistent, "
                    f"{stats['inconsistent']} inconsistent, "
                    f"{stats['missing']} missing"
                ))
                
                if stats['inconsistent'] > 0:
                    self.stdout.write(self.style.WARNING(
                        f"Inconsistent fields: {stats['inconsistent_fields']}"
                    ))
                    
                    if verbose:
                        self.stdout.write("Inconsistent instances:")
                        for detail in stats['details']:
                            if detail['status'] != 'consistent':
                                self.stdout.write(f"  {detail['id']}: {detail['message']}")
            else:
                stats = reconcile_cache_for_model(
                    model, force=force, batch_size=batch_size, max_instances=max_instances
                )
                self.stdout.write(self.style.SUCCESS(
                    f"Reconciled cache for {model._meta.label}: "
                    f"{stats['cached_instances']} cached, "
                    f"{stats['updated_instances']} updated, "
                    f"{stats['removed_instances']} removed, "
                    f"{stats['errors']} errors "
                    f"in {stats['elapsed_time']:.2f} seconds"
                ))
        else:
            # Reconcile all models
            self.stdout.write("Reconciling cache for all models...")

            if check_only:
                self.stdout.write(self.style.WARNING(
                    "Check-only mode not supported for all models. Use --model option."
                ))
                return

            stats = reconcile_all_caches(
                force=force, batch_size=batch_size, max_instances=max_instances
            )
            self.stdout.write(self.style.SUCCESS(
                f"Reconciled cache for all models: "
                f"{stats['total_models']} models, "
                f"{stats['total_instances']} instances, "
                f"{stats['cached_instances']} cached, "
                f"{stats['updated_instances']} updated, "
                f"{stats['removed_instances']} removed, "
                f"{stats['errors']} errors "
                f"in {stats['elapsed_time']:.2f} seconds"
            ))

        elapsed_time = time.time() - start_time
        self.stdout.write(f"Total execution time: {elapsed_time:.2f} seconds")

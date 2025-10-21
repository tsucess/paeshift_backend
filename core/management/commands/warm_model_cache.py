"""
Management command to warm the Redis model cache.

This command pre-populates the Redis cache with model instances to improve
performance for frequently accessed models.
"""

import logging
import time
from typing import List, Type

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import models

from core.redis_models import cache_model

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Warm the Redis model cache by pre-populating it with model instances"

    def add_arguments(self, parser):
        parser.add_argument(
            "--models",
            type=str,
            nargs="+",
            help="List of models to cache in the format app_label.model_name",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=1000,
            help="Maximum number of instances to cache per model",
        )
        parser.add_argument(
            "--recent",
            action="store_true",
            help="Only cache recently updated instances",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=7,
            help="Number of days to consider for recent instances",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Batch size for processing instances",
        )

    def handle(self, *args, **options):
        models_to_cache = options["models"]
        limit = options["limit"]
        recent = options["recent"]
        days = options["days"]
        batch_size = options["batch_size"]

        # Get all models if not specified
        if not models_to_cache:
            models_to_cache = []
            for app_config in apps.get_app_configs():
                for model in app_config.get_models():
                    # Skip built-in models
                    if model._meta.app_label not in ["auth", "contenttypes", "sessions", "admin"]:
                        models_to_cache.append(f"{model._meta.app_label}.{model._meta.model_name}")

        # Process each model
        for model_name in models_to_cache:
            try:
                # Get model class
                app_label, model_name = model_name.split(".")
                model_class = apps.get_model(app_label, model_name)

                # Cache model instances
                self.cache_model_instances(model_class, limit, recent, days, batch_size)
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Error caching model {model_name}: {str(e)}"))

    def cache_model_instances(
        self, model_class: Type[models.Model], limit: int, recent: bool, days: int, batch_size: int
    ):
        """
        Cache instances of a model.

        Args:
            model_class: Model class
            limit: Maximum number of instances to cache
            recent: Whether to only cache recent instances
            days: Number of days to consider for recent instances
            batch_size: Batch size for processing instances
        """
        model_name = f"{model_class._meta.app_label}.{model_class._meta.model_name}"
        self.stdout.write(f"Caching instances of {model_name}...")

        # Get queryset
        queryset = model_class.objects.all()

        # Filter by recent if requested
        if recent:
            from datetime import datetime, timedelta
            from django.utils import timezone

            # Get the date field to use for filtering
            date_field = None
            for field in model_class._meta.fields:
                if isinstance(field, models.DateTimeField) and field.name in ["updated_at", "modified_at", "updated", "modified"]:
                    date_field = field.name
                    break
            if not date_field and hasattr(model_class, "updated_at"):
                date_field = "updated_at"
            elif not date_field and hasattr(model_class, "modified_at"):
                date_field = "modified_at"
            elif not date_field and hasattr(model_class, "updated"):
                date_field = "updated"
            elif not date_field and hasattr(model_class, "modified"):
                date_field = "modified"
            elif not date_field and hasattr(model_class, "created_at"):
                date_field = "created_at"
            elif not date_field and hasattr(model_class, "created"):
                date_field = "created"

            if date_field:
                # Filter by date
                since = timezone.now() - timedelta(days=days)
                queryset = queryset.filter(**{f"{date_field}__gte": since})
                self.stdout.write(f"Filtering by {date_field} >= {since}")

        # Limit the queryset
        queryset = queryset[:limit]

        # Get total count
        total_count = queryset.count()
        self.stdout.write(f"Found {total_count} instances to cache")

        # Cache instances in batches
        cached_count = 0
        start_time = time.time()

        for i in range(0, total_count, batch_size):
            batch = queryset[i:i + batch_size]
            for instance in batch:
                try:
                    cache_model(instance)
                    cached_count += 1
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f"Error caching {model_name} with ID {instance.pk}: {str(e)}"))

            # Print progress
            progress = (i + len(batch)) / total_count * 100
            self.stdout.write(f"Progress: {progress:.1f}% ({i + len(batch)}/{total_count})")

        # Print summary
        elapsed_time = time.time() - start_time
        self.stdout.write(
            self.style.SUCCESS(
                f"Cached {cached_count}/{total_count} instances of {model_name} in {elapsed_time:.2f}s"
            )
        )

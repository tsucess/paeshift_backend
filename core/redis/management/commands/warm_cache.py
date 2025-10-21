"""
Management command to warm the Redis cache.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Type

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import models

from core.redis.client import redis_client
from core.redis.models import cache_model
from core.redis.settings import CACHE_ENABLED
from core.redis.warming import (
    warm_cache,
    warm_critical_models,
    warm_model_cache,
)

# Set up logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Management command to warm the Redis cache.
    """

    help = "Warm the Redis cache with frequently accessed data"

    def add_arguments(self, parser):
        """
        Add command arguments.
        """
        parser.add_argument(
            "--type",
            choices=["full", "critical", "model"],
            default="full",
            help="Type of cache warming to perform",
        )
        parser.add_argument(
            "--model",
            help="Model to warm (required if type=model)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Limit the number of instances to cache",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Number of instances to cache in each batch",
        )
        parser.add_argument(
            "--sleep",
            type=float,
            default=0.1,
            help="Sleep time between batches to reduce load",
        )
        parser.add_argument(
            "--filter",
            help="Filter criteria in the format field=value",
            action="append",
        )
        parser.add_argument(
            "--order-by",
            help="Order by field (prefix with - for descending)",
            action="append",
        )
        parser.add_argument(
            "--permanent",
            action="store_true",
            help="Cache permanently (no expiration)",
        )

    def handle(self, *args, **options):
        """
        Handle the command.
        """
        if not CACHE_ENABLED:
            self.stderr.write(self.style.ERROR("Redis cache is disabled"))
            return

        if not redis_client:
            self.stderr.write(self.style.ERROR("Redis client not available"))
            return

        warm_type = options["type"]
        start_time = time.time()

        if warm_type == "full":
            self.stdout.write(self.style.SUCCESS("Starting full cache warming..."))
            result = warm_cache()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Completed full cache warming in {time.time() - start_time:.2f} seconds"
                )
            )
            self.stdout.write(str(result))
        elif warm_type == "critical":
            self.stdout.write(self.style.SUCCESS("Starting critical cache warming..."))
            result = warm_critical_models()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Completed critical cache warming in {time.time() - start_time:.2f} seconds"
                )
            )
            self.stdout.write(str(result))
        elif warm_type == "model":
            model_name = options["model"]
            if not model_name:
                raise CommandError("--model is required when type=model")

            try:
                # Get model class
                model_class = apps.get_model(model_name)
            except Exception as e:
                raise CommandError(f"Error getting model {model_name}: {str(e)}")

            # Parse filter criteria
            filter_kwargs = {}
            if options["filter"]:
                for filter_str in options["filter"]:
                    try:
                        field, value = filter_str.split("=", 1)
                        filter_kwargs[field] = value
                    except ValueError:
                        raise CommandError(f"Invalid filter format: {filter_str}")

            # Parse order by
            order_by = options["order_by"]

            # Get limit
            limit = options["limit"]

            # Get batch size
            batch_size = options["batch_size"]

            # Get sleep time
            sleep = options["sleep"]

            # Get permanent flag
            permanent = options["permanent"]

            self.stdout.write(
                self.style.SUCCESS(
                    f"Starting cache warming for model {model_name}..."
                )
            )
            total, cached = warm_model_cache(
                model_class,
                batch_size=batch_size,
                sleep_between_batches=sleep,
                filter_kwargs=filter_kwargs,
                order_by=order_by,
                limit=limit,
                permanent=permanent,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Completed cache warming for model {model_name} in "
                    f"{time.time() - start_time:.2f} seconds"
                )
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Cached {cached}/{total} instances of {model_name}"
                )
            )

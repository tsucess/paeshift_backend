"""
Simple cache warming command for testing.

This command warms the Redis cache by pre-populating it with model instances.
"""

import logging
from django.core.management.base import BaseCommand
from django.apps import apps
from django.utils import timezone
from datetime import timedelta

from core.cache import cache_model_instance

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Simple cache warming command for testing"

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
            default=100,
            help="Maximum number of instances to cache per model",
        )

    def handle(self, *args, **options):
        models = options.get("models", [])
        limit = options.get("limit", 100)

        if not models:
            self.stdout.write(self.style.WARNING("No models specified for cache warming"))
            return

        total_cached = 0

        for model_path in models:
            try:
                app_label, model_name = model_path.split(".")
                model_class = apps.get_model(app_label, model_name)

                self.stdout.write(f"Warming cache for {model_path}...")

                # Get instances
                instances = model_class.objects.all()[:limit]
                count = 0

                for instance in instances:
                    try:
                        # Basic serialization
                        data = {
                            "id": instance.id,
                            "model": model_class.__name__,
                        }

                        # Add common fields if they exist
                        for field in ["name", "title", "email", "username"]:
                            if hasattr(instance, field):
                                data[field] = getattr(instance, field)

                        # Cache instance
                        model_type = model_class.__name__.lower()
                        if cache_model_instance(model_type, instance.id, data, timeout=3600):
                            count += 1
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f"Error caching {model_path} instance {instance.id}: {str(e)}")
                        )

                self.stdout.write(
                    self.style.SUCCESS(f"Cached {count} {model_path} instances")
                )
                total_cached += count

            except ValueError:
                self.stdout.write(
                    self.style.ERROR(f"Invalid model format: {model_path}. Use app_label.model_name")
                )
            except LookupError:
                self.stdout.write(
                    self.style.ERROR(f"Model not found: {model_path}")
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error warming cache for {model_path}: {str(e)}")
                )

        self.stdout.write(
            self.style.SUCCESS(f"Cache warming completed. Cached {total_cached} instances.")
        )

"""
Management command to check and fix cache consistency.

This command checks the consistency of the Redis cache against the database
and can fix inconsistencies by updating or invalidating stale cache entries.
"""

import logging
import time
from typing import Dict, List, Optional, Set, Tuple, Type

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import models
from django.utils import timezone

from core.cache import redis_client
from core.redis_models import get_model_cache
from core.redis_timestamp_validation import (
    get_model_timestamp, get_cache_timestamp, 
    is_cache_valid, ensure_timestamp_in_data
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Check and fix cache consistency"
    
    def add_arguments(self, parser):
        parser.add_argument(
            "--model",
            type=str,
            help="Model to check in the format app_label.model_name",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Check all cacheable models",
        )
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Fix inconsistencies by updating or invalidating stale cache entries",
        )
        parser.add_argument(
            "--sample",
            type=int,
            default=100,
            help="Number of instances to check per model",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Show detailed information about each instance",
        )
        
    def handle(self, *args, **options):
        model_name = options.get("model")
        check_all = options.get("all")
        fix = options.get("fix")
        sample_size = options.get("sample")
        verbose = options.get("verbose")
        
        if not model_name and not check_all:
            raise CommandError("You must specify either --model or --all")
            
        if model_name:
            # Check a specific model
            try:
                app_label, model_name = model_name.split(".")
                model = apps.get_model(app_label, model_name)
                self.check_model(model, fix, sample_size, verbose)
            except ValueError:
                raise CommandError("Model must be in the format app_label.model_name")
            except LookupError:
                raise CommandError(f"Model {model_name} not found")
        else:
            # Check all cacheable models
            self.check_all_models(fix, sample_size, verbose)
            
    def check_all_models(self, fix: bool, sample_size: int, verbose: bool):
        """
        Check all cacheable models.
        
        Args:
            fix: Whether to fix inconsistencies
            sample_size: Number of instances to check per model
            verbose: Whether to show detailed information
        """
        self.stdout.write("Checking all cacheable models...")
        
        # Find all models with Redis caching
        cacheable_models = []
        for app_config in apps.get_app_configs():
            for model in app_config.get_models():
                # Check if model has Redis caching mixins
                if (hasattr(model, 'cache_enabled') or 
                    hasattr(model, 'redis_cache_prefix') or
                    hasattr(model, 'redis_cache_timeout')):
                    cacheable_models.append(model)
        
        if not cacheable_models:
            self.stdout.write("No cacheable models found")
            return
            
        self.stdout.write(f"Found {len(cacheable_models)} cacheable models")
        
        # Check each model
        for model in cacheable_models:
            model_name = f"{model._meta.app_label}.{model.__name__}"
            self.stdout.write(f"\nChecking {model_name}...")
            self.check_model(model, fix, sample_size, verbose)
            
    def check_model(self, model: Type[models.Model], fix: bool, sample_size: int, verbose: bool):
        """
        Check a specific model.
        
        Args:
            model: Model to check
            fix: Whether to fix inconsistencies
            sample_size: Number of instances to check
            verbose: Whether to show detailed information
        """
        model_name = f"{model._meta.app_label}.{model.__name__}"
        
        # Check if model has timestamp fields
        has_timestamp = False
        for field_name in ["last_updated", "updated_at", "timestamp", "modified_at", "created_at"]:
            if hasattr(model, field_name):
                has_timestamp = True
                break
                
        if not has_timestamp:
            self.stdout.write(self.style.WARNING(
                f"Warning: Model {model_name} does not have a timestamp field"
            ))
            
        # Check if model has version field
        has_version = hasattr(model, "version")
        if not has_version:
            self.stdout.write(self.style.WARNING(
                f"Warning: Model {model_name} does not have a version field"
            ))
            
        # Get a sample of instances
        instances = model.objects.all()[:sample_size]
        instance_count = instances.count()
        
        if instance_count == 0:
            self.stdout.write(f"No instances found for {model_name}")
            return
            
        self.stdout.write(f"Checking {instance_count} instances of {model_name}...")
        
        # Initialize statistics
        stats = {
            "total": instance_count,
            "in_cache": 0,
            "not_in_cache": 0,
            "consistent": 0,
            "inconsistent": 0,
            "fixed": 0,
            "errors": 0,
        }
        
        # Get model cache
        model_cache = get_model_cache(model)
        
        # Check each instance
        for instance in instances:
            try:
                # Generate cache key
                cache_key = model_cache._get_cache_key(instance.pk)
                
                # Get cached data
                from core.cache import get_cached_data
                cached_data = get_cached_data(cache_key)
                
                if not cached_data:
                    stats["not_in_cache"] += 1
                    if verbose:
                        self.stdout.write(f"  {instance.pk}: Not in cache")
                    continue
                    
                stats["in_cache"] += 1
                
                # Check if cache is valid
                is_valid, reason = is_cache_valid(instance, cached_data)
                
                if is_valid:
                    stats["consistent"] += 1
                    if verbose:
                        self.stdout.write(f"  {instance.pk}: Consistent")
                else:
                    stats["inconsistent"] += 1
                    if verbose:
                        self.stdout.write(self.style.WARNING(f"  {instance.pk}: Inconsistent - {reason}"))
                    
                    # Fix if requested
                    if fix:
                        # Update cache
                        model_cache.cache(instance)
                        stats["fixed"] += 1
                        if verbose:
                            self.stdout.write(self.style.SUCCESS(f"  {instance.pk}: Fixed"))
            except Exception as e:
                stats["errors"] += 1
                if verbose:
                    self.stdout.write(self.style.ERROR(f"  {instance.pk}: Error - {str(e)}"))
                    
        # Print statistics
        self.stdout.write("\nStatistics:")
        self.stdout.write(f"  Total instances: {stats['total']}")
        self.stdout.write(f"  In cache: {stats['in_cache']}")
        self.stdout.write(f"  Not in cache: {stats['not_in_cache']}")
        self.stdout.write(f"  Consistent: {stats['consistent']}")
        self.stdout.write(f"  Inconsistent: {stats['inconsistent']}")
        
        if fix:
            self.stdout.write(f"  Fixed: {stats['fixed']}")
            
        self.stdout.write(f"  Errors: {stats['errors']}")
        
        # Calculate consistency percentage
        if stats["in_cache"] > 0:
            consistency_pct = (stats["consistent"] / stats["in_cache"]) * 100
            self.stdout.write(f"  Consistency: {consistency_pct:.2f}%")
            
            if consistency_pct < 90:
                self.stdout.write(self.style.WARNING(
                    f"Warning: Consistency is below 90% for {model_name}"
                ))
            elif consistency_pct < 99:
                self.stdout.write(self.style.WARNING(
                    f"Warning: Consistency is below 99% for {model_name}"
                ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f"Consistency is good for {model_name}"
                ))

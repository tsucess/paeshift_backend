"""
Management command to optimize Redis cache settings.

This command analyzes cache usage and optimizes settings for maximum hit rate.
"""

import logging
import time
from datetime import datetime, timedelta

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import models

from core.cache import get_cache_stats, redis_client
from core.redis_models import cache_model

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Optimize Redis cache settings for maximum hit rate"

    def add_arguments(self, parser):
        parser.add_argument(
            "--target-hit-rate",
            type=float,
            default=100.0,
            help="Target hit rate percentage",
        )
        parser.add_argument(
            "--analyze-only",
            action="store_true",
            help="Only analyze cache usage without making changes",
        )
        parser.add_argument(
            "--aggressive",
            action="store_true",
            help="Use aggressive optimization strategies",
        )

    def handle(self, *args, **options):
        target_hit_rate = options["target_hit_rate"]
        analyze_only = options["analyze_only"]
        aggressive = options["aggressive"]

        self.stdout.write(f"Starting cache optimization with target hit rate: {target_hit_rate}%")
        
        # Get initial stats
        initial_stats = get_cache_stats()
        self.stdout.write(
            f"Initial hit rate: {initial_stats.get('hit_rate', 0):.2f}%, "
            f"Keys: {initial_stats.get('total_keys', 0)}, "
            f"Memory: {initial_stats.get('memory_used_mb', 0):.2f}MB"
        )
        
        # Analyze cache usage
        self.stdout.write("Analyzing cache usage...")
        cache_analysis = self.analyze_cache_usage()
        
        # Print analysis
        self.print_cache_analysis(cache_analysis)
        
        # If only analyzing, stop here
        if analyze_only:
            self.stdout.write(self.style.SUCCESS("Analysis completed. No changes made."))
            return
        
        # Optimize cache
        self.stdout.write("Optimizing cache...")
        optimized = self.optimize_cache(cache_analysis, target_hit_rate, aggressive)
        
        # Get final stats
        final_stats = get_cache_stats()
        self.stdout.write(
            f"Final hit rate: {final_stats.get('hit_rate', 0):.2f}%, "
            f"Keys: {final_stats.get('total_keys', 0)}, "
            f"Memory: {final_stats.get('memory_used_mb', 0):.2f}MB"
        )
        
        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f"Optimization completed: {optimized} changes made"
            )
        )
        self.stdout.write(
            f"Hit rate change: {initial_stats.get('hit_rate', 0):.2f}% -> {final_stats.get('hit_rate', 0):.2f}%"
        )
        
    def analyze_cache_usage(self):
        """Analyze cache usage patterns."""
        analysis = {
            "key_types": {},
            "key_sizes": {},
            "key_ttls": {},
            "key_hits": {},
            "missing_models": [],
            "recommendations": [],
        }
        
        # Get all keys
        keys = redis_client.keys("*")
        
        # Sample keys if there are too many
        if len(keys) > 1000:
            import random
            keys = random.sample(keys, 1000)
        
        # Analyze each key
        for key in keys:
            key_str = key.decode("utf-8") if isinstance(key, bytes) else key
            
            # Get key type
            key_type = redis_client.type(key).decode("utf-8")
            
            # Get key size
            size = redis_client.memory_usage(key)
            size_kb = size / 1024 if size else 0
            
            # Get TTL
            ttl = redis_client.ttl(key)
            
            # Extract key prefix
            prefix = key_str.split(":")[0] if ":" in key_str else "unknown"
            
            # Update analysis
            if prefix not in analysis["key_types"]:
                analysis["key_types"][prefix] = {"count": 0, "types": {}}
                analysis["key_sizes"][prefix] = {"total": 0, "avg": 0, "max": 0}
                analysis["key_ttls"][prefix] = {"no_expiry": 0, "avg": 0, "min": float("inf")}
            
            analysis["key_types"][prefix]["count"] += 1
            analysis["key_types"][prefix]["types"][key_type] = analysis["key_types"][prefix]["types"].get(key_type, 0) + 1
            
            analysis["key_sizes"][prefix]["total"] += size_kb
            analysis["key_sizes"][prefix]["avg"] = analysis["key_sizes"][prefix]["total"] / analysis["key_types"][prefix]["count"]
            analysis["key_sizes"][prefix]["max"] = max(analysis["key_sizes"][prefix]["max"], size_kb)
            
            if ttl == -1:
                analysis["key_ttls"][prefix]["no_expiry"] += 1
            elif ttl > 0:
                if analysis["key_ttls"][prefix]["avg"] == 0:
                    analysis["key_ttls"][prefix]["avg"] = ttl
                else:
                    analysis["key_ttls"][prefix]["avg"] = (analysis["key_ttls"][prefix]["avg"] + ttl) / 2
                analysis["key_ttls"][prefix]["min"] = min(analysis["key_ttls"][prefix]["min"], ttl)
        
        # Check for models that should be cached but aren't
        for app_config in apps.get_app_configs():
            for model in app_config.get_models():
                # Skip built-in models
                if model._meta.app_label in ["auth", "contenttypes", "sessions", "admin"]:
                    continue
                
                # Check if model is cacheable
                if hasattr(model, "cache_enabled") and model.cache_enabled:
                    model_name = model.__name__.lower()
                    model_prefix = f"model:{model_name}"
                    
                    # Check if model is cached
                    if model_prefix not in analysis["key_types"] or analysis["key_types"][model_prefix]["count"] == 0:
                        analysis["missing_models"].append(model)
        
        # Generate recommendations
        if any(analysis["key_ttls"][prefix]["no_expiry"] > 0 for prefix in analysis["key_ttls"]):
            analysis["recommendations"].append("Set expiration times for keys without TTL")
        
        for prefix, ttl_data in analysis["key_ttls"].items():
            if ttl_data["min"] != float("inf") and ttl_data["min"] < 60:
                analysis["recommendations"].append(f"Increase minimum TTL for {prefix} keys")
        
        if analysis["missing_models"]:
            analysis["recommendations"].append("Cache missing models")
        
        return analysis
    
    def print_cache_analysis(self, analysis):
        """Print cache analysis results."""
        self.stdout.write("=== Cache Analysis ===")
        
        # Print key types
        self.stdout.write("\nKey Types:")
        for prefix, data in sorted(analysis["key_types"].items(), key=lambda x: x[1]["count"], reverse=True):
            self.stdout.write(f"  {prefix}: {data['count']} keys")
            for key_type, count in data["types"].items():
                self.stdout.write(f"    {key_type}: {count}")
        
        # Print key sizes
        self.stdout.write("\nKey Sizes:")
        for prefix, data in sorted(analysis["key_sizes"].items(), key=lambda x: x[1]["total"], reverse=True):
            self.stdout.write(f"  {prefix}: {data['total']:.2f} KB total, {data['avg']:.2f} KB avg, {data['max']:.2f} KB max")
        
        # Print TTLs
        self.stdout.write("\nKey TTLs:")
        for prefix, data in sorted(analysis["key_ttls"].items(), key=lambda x: x[1]["no_expiry"], reverse=True):
            if data["min"] == float("inf"):
                data["min"] = 0
            self.stdout.write(f"  {prefix}: {data['no_expiry']} keys without expiry, {data['avg']:.2f}s avg TTL, {data['min']:.2f}s min TTL")
        
        # Print missing models
        if analysis["missing_models"]:
            self.stdout.write("\nMissing Models:")
            for model in analysis["missing_models"]:
                self.stdout.write(f"  {model._meta.app_label}.{model.__name__}")
        
        # Print recommendations
        if analysis["recommendations"]:
            self.stdout.write("\nRecommendations:")
            for recommendation in analysis["recommendations"]:
                self.stdout.write(f"  - {recommendation}")
    
    def optimize_cache(self, analysis, target_hit_rate, aggressive):
        """Optimize cache based on analysis."""
        changes_made = 0
        
        # Set expiration times for keys without TTL
        for prefix, data in analysis["key_ttls"].items():
            if data["no_expiry"] > 0:
                self.stdout.write(f"Setting expiration for {prefix} keys without TTL...")
                
                # Get keys without TTL
                pattern = f"{prefix}:*"
                keys = redis_client.keys(pattern)
                
                for key in keys:
                    ttl = redis_client.ttl(key)
                    if ttl == -1:
                        # Set TTL based on key type
                        if prefix == "model":
                            # Model cache: 24 hours
                            redis_client.expire(key, 60 * 60 * 24)
                        elif prefix == "payment":
                            # Payment cache: 15 minutes
                            redis_client.expire(key, 60 * 15)
                        elif prefix == "job":
                            # Job cache: 6 hours
                            redis_client.expire(key, 60 * 60 * 6)
                        elif prefix == "user":
                            # User cache: 12 hours
                            redis_client.expire(key, 60 * 60 * 12)
                        else:
                            # Default: 1 hour
                            redis_client.expire(key, 60 * 60)
                        
                        changes_made += 1
        
        # Cache missing models
        if analysis["missing_models"]:
            self.stdout.write("Caching missing models...")
            
            for model in analysis["missing_models"]:
                self.stdout.write(f"  Caching {model._meta.app_label}.{model.__name__}...")
                
                # Get instances
                instances = model.objects.all()[:1000]
                
                # Cache instances
                cached_count = 0
                for instance in instances:
                    try:
                        cache_model(instance)
                        cached_count += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error caching {model.__name__} with ID {instance.pk}: {str(e)}"))
                
                self.stdout.write(f"  Cached {cached_count} instances of {model.__name__}")
                changes_made += cached_count
        
        # Increase TTLs for keys with short expiration
        for prefix, data in analysis["key_ttls"].items():
            if data["min"] != float("inf") and data["min"] < 60:
                self.stdout.write(f"Increasing TTL for {prefix} keys with short expiration...")
                
                # Get keys with short TTL
                pattern = f"{prefix}:*"
                keys = redis_client.keys(pattern)
                
                for key in keys:
                    ttl = redis_client.ttl(key)
                    if 0 < ttl < 60:
                        # Increase TTL to at least 5 minutes
                        redis_client.expire(key, max(ttl, 60 * 5))
                        changes_made += 1
        
        # If aggressive optimization is enabled, pre-cache frequently accessed data
        if aggressive:
            self.stdout.write("Performing aggressive optimization...")
            
            # Pre-cache active jobs
            self.stdout.write("  Pre-caching active jobs...")
            try:
                Job = apps.get_model("jobs", "Job")
                active_jobs = Job.objects.filter(is_active=True)[:1000]
                
                cached_count = 0
                for job in active_jobs:
                    try:
                        cache_model(job)
                        cached_count += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error caching Job with ID {job.pk}: {str(e)}"))
                
                self.stdout.write(f"  Cached {cached_count} active jobs")
                changes_made += cached_count
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error pre-caching active jobs: {str(e)}"))
            
            # Pre-cache recent users
            self.stdout.write("  Pre-caching recent users...")
            try:
                User = apps.get_model("accounts", "CustomUser")
                recent_users = User.objects.filter(
                    last_login__gte=datetime.now() - timedelta(days=7)
                )[:1000]
                
                cached_count = 0
                for user in recent_users:
                    try:
                        cache_model(user)
                        cached_count += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error caching User with ID {user.pk}: {str(e)}"))
                
                self.stdout.write(f"  Cached {cached_count} recent users")
                changes_made += cached_count
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error pre-caching recent users: {str(e)}"))
        
        return changes_made

"""
Management command to monitor Redis cache health.

This command checks the health of the Redis cache and reports statistics.
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Monitor Redis cache health and report statistics"

    def add_arguments(self, parser):
        parser.add_argument(
            "--continuous",
            action="store_true",
            help="Run continuously",
        )
        parser.add_argument(
            "--interval",
            type=int,
            default=60,
            help="Interval between checks in seconds (only used with --continuous)",
        )
        parser.add_argument(
            "--alert-threshold",
            type=float,
            default=80.0,
            help="Memory usage threshold for alerts (percentage)",
        )
        parser.add_argument(
            "--output-file",
            type=str,
            help="File to write statistics to (JSON format)",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Print verbose output",
        )

    def handle(self, *args, **options):
        continuous = options["continuous"]
        interval = options["interval"]
        alert_threshold = options["alert_threshold"]
        output_file = options["output_file"]
        verbose = options["verbose"]

        if continuous:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Starting continuous monitoring of Redis cache (interval: {interval}s)"
                )
            )
            try:
                while True:
                    self._check_redis_health(alert_threshold, output_file, verbose)
                    time.sleep(interval)
            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING("Interrupted by user"))
        else:
            self._check_redis_health(alert_threshold, output_file, verbose)

    def _check_redis_health(self, alert_threshold: float, output_file: Optional[str], verbose: bool):
        """
        Check Redis cache health and report statistics.

        Args:
            alert_threshold: Memory usage threshold for alerts (percentage)
            output_file: File to write statistics to (JSON format)
            verbose: Whether to print verbose output
        """
        try:
            from core.cache import get_cache_stats, redis_client

            # Get Redis info
            stats = get_cache_stats()

            if "error" in stats:
                self.stderr.write(self.style.ERROR(f"Error getting Redis stats: {stats['error']}"))
                return

            # Calculate memory usage percentage
            memory_used_mb = stats.get("memory_used_mb", 0)
            memory_peak_mb = stats.get("memory_peak_mb", 0)
            memory_usage_pct = (memory_used_mb / memory_peak_mb * 100) if memory_peak_mb > 0 else 0

            # Print basic stats
            self.stdout.write(f"Redis version: {stats.get('version', 'unknown')}")
            self.stdout.write(f"Uptime: {self._format_seconds(stats.get('uptime_seconds', 0))}")
            self.stdout.write(f"Connected clients: {stats.get('connected_clients', 0)}")
            self.stdout.write(f"Total keys: {stats.get('total_keys', 0)}")
            self.stdout.write(f"Memory used: {memory_used_mb:.2f} MB")
            self.stdout.write(f"Memory peak: {memory_peak_mb:.2f} MB")
            self.stdout.write(f"Memory usage: {memory_usage_pct:.1f}%")
            self.stdout.write(f"Hit rate: {stats.get('hit_rate', 0):.1f}%")
            self.stdout.write(f"Hits: {stats.get('hits', 0)}")
            self.stdout.write(f"Misses: {stats.get('misses', 0)}")

            # Print key counts by type if verbose
            if verbose:
                self.stdout.write("\nKey counts by type:")
                key_counts = stats.get("key_counts_by_type", {})
                for key_type, count in sorted(key_counts.items(), key=lambda x: x[1], reverse=True):
                    self.stdout.write(f"  {key_type}: {count}")

                # Get database size
                db_size = redis_client.dbsize()
                self.stdout.write(f"\nDatabase size: {db_size} keys")

                # Get memory usage of largest keys
                self.stdout.write("\nLargest keys by memory usage:")
                largest_keys = self._get_largest_keys(redis_client, 10)
                for i, (key, size) in enumerate(largest_keys):
                    self.stdout.write(f"  {i+1}. {key}: {size:.2f} KB")

            # Check for alerts
            alerts = []
            if memory_usage_pct > alert_threshold:
                alert_msg = f"Memory usage is high: {memory_usage_pct:.1f}% (threshold: {alert_threshold:.1f}%)"
                alerts.append(alert_msg)
                self.stderr.write(self.style.ERROR(alert_msg))

            if stats.get("hit_rate", 0) < 50:
                alert_msg = f"Cache hit rate is low: {stats.get('hit_rate', 0):.1f}%"
                alerts.append(alert_msg)
                self.stderr.write(self.style.WARNING(alert_msg))

            # Write to output file if specified
            if output_file:
                output_data = {
                    "timestamp": datetime.now().isoformat(),
                    "stats": stats,
                    "alerts": alerts,
                }
                with open(output_file, "w") as f:
                    json.dump(output_data, f, indent=2)
                self.stdout.write(f"Statistics written to {output_file}")

            # Print separator for continuous mode
            self.stdout.write("\n" + "-" * 80 + "\n")
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error checking Redis health: {str(e)}"))

    def _format_seconds(self, seconds: int) -> str:
        """
        Format seconds as a human-readable string.

        Args:
            seconds: Number of seconds

        Returns:
            Formatted string
        """
        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if seconds > 0 or not parts:
            parts.append(f"{seconds}s")

        return " ".join(parts)

    def _get_largest_keys(self, redis_client, limit: int = 10) -> List[tuple]:
        """
        Get the largest keys in Redis by memory usage.

        Args:
            redis_client: Redis client
            limit: Maximum number of keys to return

        Returns:
            List of (key, size_kb) tuples
        """
        try:
            # Get all keys
            keys = redis_client.keys("*")
            
            # Sample keys if there are too many
            if len(keys) > 1000:
                import random
                keys = random.sample(keys, 1000)

            # Get memory usage for each key
            key_sizes = []
            for key in keys:
                try:
                    # Get memory usage in bytes
                    size = redis_client.memory_usage(key)
                    if size:
                        # Convert to KB
                        key_sizes.append((key, size / 1024))
                except Exception:
                    pass

            # Sort by size (descending) and return top N
            return sorted(key_sizes, key=lambda x: x[1], reverse=True)[:limit]
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error getting largest keys: {str(e)}"))
            return []

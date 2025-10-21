"""
Management command to monitor Redis cache performance.

This command monitors Redis cache performance and logs statistics.
"""

import logging
import time
from datetime import datetime

from django.core.management.base import BaseCommand

from core.cache import get_cache_stats

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Monitor Redis cache performance and log statistics"

    def add_arguments(self, parser):
        parser.add_argument(
            "--interval",
            type=int,
            default=60,
            help="Interval in seconds between checks",
        )
        parser.add_argument(
            "--duration",
            type=int,
            default=3600,
            help="Duration in seconds to run the monitor",
        )
        parser.add_argument(
            "--alert-threshold",
            type=float,
            default=50.0,
            help="Hit rate threshold for alerts (percentage)",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Print verbose output",
        )

    def handle(self, *args, **options):
        interval = options["interval"]
        duration = options["duration"]
        alert_threshold = options["alert_threshold"]
        verbose = options["verbose"]

        self.stdout.write(f"Starting cache monitor with {interval}s interval for {duration}s")
        self.stdout.write(f"Alert threshold: {alert_threshold}% hit rate")

        start_time = time.time()
        end_time = start_time + duration
        check_count = 0

        # Initial stats
        initial_stats = get_cache_stats()
        self.log_stats(initial_stats, "Initial", verbose)

        try:
            while time.time() < end_time:
                # Sleep for interval
                time.sleep(interval)

                # Get stats
                stats = get_cache_stats()
                check_count += 1

                # Log stats
                self.log_stats(stats, f"Check {check_count}", verbose)

                # Check hit rate
                hit_rate = stats.get("hit_rate", 0)
                if hit_rate < alert_threshold:
                    self.stdout.write(
                        self.style.WARNING(
                            f"ALERT: Hit rate {hit_rate:.2f}% below threshold {alert_threshold}%"
                        )
                    )
                    logger.warning(
                        f"Cache hit rate {hit_rate:.2f}% below threshold {alert_threshold}%"
                    )

        except KeyboardInterrupt:
            self.stdout.write("Monitor stopped by user")

        # Final stats
        final_stats = get_cache_stats()
        self.log_stats(final_stats, "Final", verbose)

        # Summary
        elapsed_time = time.time() - start_time
        self.stdout.write(
            self.style.SUCCESS(
                f"Monitoring completed: {check_count} checks in {elapsed_time:.2f}s"
            )
        )
        self.stdout.write(
            f"Hit rate: {initial_stats.get('hit_rate', 0):.2f}% -> {final_stats.get('hit_rate', 0):.2f}%"
        )
        self.stdout.write(
            f"Total keys: {initial_stats.get('total_keys', 0)} -> {final_stats.get('total_keys', 0)}"
        )
        self.stdout.write(
            f"Memory used: {initial_stats.get('memory_used_mb', 0):.2f}MB -> {final_stats.get('memory_used_mb', 0):.2f}MB"
        )

    def log_stats(self, stats, prefix="", verbose=False):
        """Log cache statistics."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        hit_rate = stats.get("hit_rate", 0)
        total_keys = stats.get("total_keys", 0)
        memory_used = stats.get("memory_used_mb", 0)

        # Log basic stats
        log_message = (
            f"{prefix} stats [{timestamp}]: "
            f"Hit rate: {hit_rate:.2f}%, "
            f"Keys: {total_keys}, "
            f"Memory: {memory_used:.2f}MB"
        )
        self.stdout.write(log_message)
        logger.info(log_message)

        # Log detailed stats if verbose
        if verbose:
            # Key counts by type
            self.stdout.write("  Key counts by type:")
            key_counts = stats.get("key_counts_by_type", {})
            for key_type, count in sorted(key_counts.items(), key=lambda x: x[1], reverse=True):
                if count > 0:
                    self.stdout.write(f"    {key_type}: {count}")

            # Memory usage
            memory_peak = stats.get("memory_peak_mb", 0)
            memory_usage_pct = (memory_used / memory_peak * 100) if memory_peak > 0 else 0
            self.stdout.write(
                f"  Memory usage: {memory_used:.2f}MB / {memory_peak:.2f}MB ({memory_usage_pct:.1f}%)"
            )

            # Hit/miss counts
            hits = stats.get("hits", 0)
            misses = stats.get("misses", 0)
            self.stdout.write(f"  Hits: {hits}, Misses: {misses}")

            # Connected clients
            connected_clients = stats.get("connected_clients", 0)
            self.stdout.write(f"  Connected clients: {connected_clients}")

            # Uptime
            uptime_seconds = stats.get("uptime_seconds", 0)
            uptime_days = uptime_seconds / (60 * 60 * 24)
            self.stdout.write(f"  Uptime: {uptime_days:.2f} days")

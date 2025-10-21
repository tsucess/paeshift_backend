"""
Management command to monitor Redis cache health.
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.redis.client import redis_client
from core.redis.monitoring import (
    get_cache_stats,
    check_alerts,
    trigger_alert,
    analyze_key_size,
)
from core.redis.settings import CACHE_ENABLED
from core.redis.telemetry import (
    get_slow_operations,
    analyze_slow_operations,
)

# Set up logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Management command to monitor Redis cache health.
    """

    help = "Monitor Redis cache health and report statistics"

    def add_arguments(self, parser):
        """
        Add command arguments.
        """
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
        """
        Handle the command.
        """
        if not CACHE_ENABLED:
            self.stderr.write(self.style.ERROR("Redis cache is disabled"))
            return

        if not redis_client:
            self.stderr.write(self.style.ERROR("Redis client not available"))
            return

        continuous = options["continuous"]
        interval = options["interval"]
        alert_threshold = options["alert_threshold"]
        output_file = options["output_file"]
        verbose = options["verbose"]

        if continuous:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Starting continuous Redis monitoring (interval: {interval}s)"
                )
            )
            try:
                while True:
                    self.check_redis_health(
                        alert_threshold=alert_threshold,
                        output_file=output_file,
                        verbose=verbose,
                    )
                    time.sleep(interval)
            except KeyboardInterrupt:
                self.stdout.write(self.style.SUCCESS("Monitoring stopped"))
        else:
            self.check_redis_health(
                alert_threshold=alert_threshold,
                output_file=output_file,
                verbose=verbose,
            )

    def check_redis_health(
        self,
        alert_threshold: float = 80.0,
        output_file: Optional[str] = None,
        verbose: bool = False,
    ):
        """
        Check Redis health and report statistics.
        """
        try:
            # Get cache stats
            stats = get_cache_stats()
            redis_info = stats.get("redis_info", {})

            # Check memory usage
            if "used_memory" in redis_info and "maxmemory" in redis_info:
                used_memory = int(redis_info["used_memory"])
                max_memory = int(redis_info["maxmemory"])
                memory_usage_percent = (used_memory / max_memory) * 100 if max_memory > 0 else 0

                if memory_usage_percent > alert_threshold:
                    self.stdout.write(
                        self.style.ERROR(
                            f"ALERT: Redis memory usage is high: {memory_usage_percent:.2f}%"
                        )
                    )
                    # Trigger alert
                    alert = {
                        "type": "memory_usage_high",
                        "message": f"Redis memory usage is high: {memory_usage_percent:.2f}%",
                        "severity": "warning",
                        "timestamp": timezone.now().isoformat(),
                    }
                    trigger_alert(alert)
                else:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Redis memory usage: {memory_usage_percent:.2f}%"
                        )
                    )

            # Check hit rate
            if "hits" in stats and "misses" in stats:
                hits = stats["hits"]
                misses = stats["misses"]
                total = hits + misses
                hit_rate = (hits / total) * 100 if total > 0 else 0

                if hit_rate < 50:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Redis hit rate is low: {hit_rate:.2f}%"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Redis hit rate: {hit_rate:.2f}%"
                        )
                    )

            # Check for alerts
            alerts = check_alerts()
            for alert in alerts:
                if alert["severity"] == "critical":
                    self.stdout.write(
                        self.style.ERROR(
                            f"CRITICAL ALERT: {alert['message']}"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"WARNING: {alert['message']}"
                        )
                    )
                # Trigger alert
                trigger_alert(alert)

            # Analyze slow operations
            if verbose:
                slow_ops_analysis = analyze_slow_operations(days=1)
                if slow_ops_analysis["count"] > 0:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Found {slow_ops_analysis['count']} slow Redis operations"
                        )
                    )
                    if verbose:
                        self.stdout.write(json.dumps(slow_ops_analysis, indent=2))

            # Write to output file if specified
            if output_file:
                with open(output_file, "w") as f:
                    json.dump(stats, f, indent=2)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Wrote statistics to {output_file}"
                    )
                )

        except Exception as e:
            self.stderr.write(
                self.style.ERROR(
                    f"Error checking Redis health: {str(e)}"
                )
            )

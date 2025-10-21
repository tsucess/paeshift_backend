"""
Management command to set up scheduled tasks for Redis cache warming and monitoring.

This command creates scheduled tasks for cache warming and monitoring using
either Windows Task Scheduler (on Windows) or cron (on Linux/Mac).
"""

import logging
import os
import platform
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Set up scheduled tasks for Redis cache warming and monitoring"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force recreation of scheduled tasks",
        )
        parser.add_argument(
            "--python-path",
            type=str,
            help="Path to Python executable (default: sys.executable)",
            default=sys.executable,
        )
        parser.add_argument(
            "--project-path",
            type=str,
            help="Path to Django project (default: settings.BASE_DIR)",
            default=settings.BASE_DIR,
        )

    def handle(self, *args, **options):
        force = options["force"]
        python_path = options["python_path"]
        project_path = options["project_path"]

        # Determine OS
        os_name = platform.system()

        if os_name == "Windows":
            self.setup_windows_tasks(python_path, project_path, force)
        elif os_name in ["Linux", "Darwin"]:  # Linux or Mac
            self.setup_cron_tasks(python_path, project_path, force)
        else:
            self.stderr.write(
                self.style.ERROR(f"Unsupported operating system: {os_name}")
            )

    def setup_windows_tasks(self, python_path, project_path, force):
        """
        Set up scheduled tasks using Windows Task Scheduler.
        """
        self.stdout.write("Setting up scheduled tasks using Windows Task Scheduler...")

        # Define tasks
        tasks = [
            {
                "name": "RedisCacheWarming",
                "description": "Warm Redis cache for frequently accessed models",
                "command": f'"{python_path}" "{project_path}\\manage.py" warm_model_cache --recent --days=7',
                "schedule": "DAILY",
                "start_time": "03:00",  # 3 AM
            },
            {
                "name": "RedisCacheMonitoring",
                "description": "Monitor Redis cache health",
                "command": f'"{python_path}" "{project_path}\\manage.py" monitor_redis_cache --output-file="{project_path}\\logs\\redis_stats.json"',
                "schedule": "HOURLY",
                "start_time": "00:00",  # Every hour
            },
        ]

        # Create each task
        for task in tasks:
            # Check if task exists
            check_cmd = f'schtasks /query /tn "{task["name"]}" 2>nul'
            task_exists = subprocess.call(check_cmd, shell=True) == 0

            if task_exists and not force:
                self.stdout.write(
                    self.style.WARNING(
                        f"Task '{task['name']}' already exists. Use --force to recreate."
                    )
                )
                continue

            # Delete existing task if force is True
            if task_exists and force:
                delete_cmd = f'schtasks /delete /tn "{task["name"]}" /f'
                subprocess.call(delete_cmd, shell=True)
                self.stdout.write(f"Deleted existing task '{task['name']}'")

            # Create task
            if task["schedule"] == "DAILY":
                create_cmd = (
                    f'schtasks /create /tn "{task["name"]}" /tr "{task["command"]}" '
                    f'/sc {task["schedule"]} /st {task["start_time"]} '
                    f'/ru SYSTEM /f /rl HIGHEST /d MON,TUE,WED,THU,FRI,SAT,SUN'
                )
            elif task["schedule"] == "HOURLY":
                create_cmd = (
                    f'schtasks /create /tn "{task["name"]}" /tr "{task["command"]}" '
                    f'/sc HOURLY /st {task["start_time"]} '
                    f'/ru SYSTEM /f /rl HIGHEST'
                )

            result = subprocess.call(create_cmd, shell=True)
            if result == 0:
                self.stdout.write(
                    self.style.SUCCESS(f"Created scheduled task '{task['name']}'")
                )
            else:
                self.stderr.write(
                    self.style.ERROR(
                        f"Failed to create scheduled task '{task['name']}'. Error code: {result}"
                    )
                )

    def setup_cron_tasks(self, python_path, project_path, force):
        """
        Set up scheduled tasks using cron.
        """
        self.stdout.write("Setting up scheduled tasks using cron...")

        # Define cron entries
        cron_entries = [
            {
                "name": "RedisCacheWarming",
                "schedule": "0 3 * * *",  # 3 AM daily
                "command": f"{python_path} {project_path}/manage.py warm_model_cache --recent --days=7",
            },
            {
                "name": "RedisCacheMonitoring",
                "schedule": "0 * * * *",  # Every hour
                "command": f"{python_path} {project_path}/manage.py monitor_redis_cache --output-file={project_path}/logs/redis_stats.json",
            },
        ]

        # Get current crontab
        try:
            process = subprocess.Popen(
                ["crontab", "-l"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            current_crontab, error = process.communicate()
            current_crontab = current_crontab.decode("utf-8")
        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f"Failed to read current crontab: {str(e)}")
            )
            current_crontab = ""

        # Create new crontab
        new_crontab = current_crontab

        for entry in cron_entries:
            # Check if entry already exists
            entry_marker = f"# {entry['name']}"
            if entry_marker in new_crontab and not force:
                self.stdout.write(
                    self.style.WARNING(
                        f"Cron entry '{entry['name']}' already exists. Use --force to recreate."
                    )
                )
                continue

            # Remove existing entry if force is True
            if entry_marker in new_crontab and force:
                lines = new_crontab.split("\n")
                new_lines = []
                skip = False
                for line in lines:
                    if entry_marker in line:
                        skip = True
                        continue
                    if skip and line.strip() and not line.startswith("#"):
                        skip = False
                    if not skip:
                        new_lines.append(line)
                new_crontab = "\n".join(new_lines)
                self.stdout.write(f"Removed existing cron entry '{entry['name']}'")

            # Add new entry
            new_crontab += f"\n# {entry['name']} - Added on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            new_crontab += f"{entry['schedule']} {entry['command']}\n"

        # Write new crontab
        try:
            process = subprocess.Popen(
                ["crontab", "-"], stdin=subprocess.PIPE, stderr=subprocess.PIPE
            )
            _, error = process.communicate(input=new_crontab.encode("utf-8"))
            if process.returncode != 0:
                self.stderr.write(
                    self.style.ERROR(
                        f"Failed to update crontab: {error.decode('utf-8')}"
                    )
                )
            else:
                self.stdout.write(self.style.SUCCESS("Updated crontab successfully"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Failed to update crontab: {str(e)}"))

    def create_log_directory(self, project_path):
        """
        Create log directory if it doesn't exist.
        """
        log_dir = os.path.join(project_path, "logs")
        os.makedirs(log_dir, exist_ok=True)
        self.stdout.write(f"Created log directory: {log_dir}")

"""
Compatibility module for core.scheduler.

This module provides backward compatibility with the old scheduler system.
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Union

# Set up logging
logger = logging.getLogger(__name__)

def setup_scheduled_tasks():
    """
    Set up scheduled tasks.

    This is a compatibility function that logs a warning and does nothing.
    """
    logger.warning("setup_scheduled_tasks called from compatibility module (no-op)")
    return True

# Placeholder for scheduler functionality
def register_task(name: str, func: Callable, interval: int = 60, **kwargs) -> None:
    """
    Register a task to be executed periodically.

    This is a compatibility function that logs a warning and does nothing.

    Args:
        name: Task name
        func: Function to execute
        interval: Interval in seconds
        **kwargs: Additional arguments
    """
    logger.warning(f"Task {name} registered with compatibility scheduler (not actually scheduled)")

def schedule_task(name: str, func: Callable, run_at: Union[str, int], **kwargs) -> None:
    """
    Schedule a task to run at a specific time.

    This is a compatibility function that logs a warning and does nothing.

    Args:
        name: Task name
        func: Function to execute
        run_at: Time to run (cron expression or timestamp)
        **kwargs: Additional arguments
    """
    logger.warning(f"Task {name} scheduled with compatibility scheduler (not actually scheduled)")

def cancel_task(name: str) -> bool:
    """
    Cancel a scheduled task.

    This is a compatibility function that logs a warning and does nothing.

    Args:
        name: Task name

    Returns:
        True if successful, False otherwise
    """
    logger.warning(f"Task {name} cancelled with compatibility scheduler (no-op)")
    return True

def list_tasks() -> List[Dict[str, Any]]:
    """
    List all scheduled tasks.

    This is a compatibility function that returns an empty list.

    Returns:
        List of task information
    """
    return []

# Re-export all functions
__all__ = [
    "register_task",
    "schedule_task",
    "cancel_task",
    "list_tasks",
]

"""
Resource limiting utilities for God Mode.

This module provides utilities for limiting resource usage in God Mode operations,
particularly for simulations.
"""

import logging
import resource
import signal
import threading
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple, Union

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Constants
DEFAULT_CPU_LIMIT = 60  # seconds
DEFAULT_MEMORY_LIMIT = 1024 * 1024 * 1024  # 1 GB
DEFAULT_TIME_LIMIT = 300  # seconds
SIMULATION_QUEUE_KEY = "godmode:simulation_queue"
SIMULATION_RUNNING_KEY = "godmode:simulation_running"
MAX_CONCURRENT_SIMULATIONS = 3


class ResourceLimitExceeded(Exception):
    """Exception raised when a resource limit is exceeded."""
    pass


def set_resource_limits(
    cpu_limit: Optional[int] = None,
    memory_limit: Optional[int] = None,
):
    """
    Set resource limits for the current process.
    
    Args:
        cpu_limit: CPU time limit in seconds
        memory_limit: Memory limit in bytes
    """
    # Set CPU time limit
    if cpu_limit is not None:
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit))
    
    # Set memory limit
    if memory_limit is not None:
        resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))


def cpu_limit_handler(signum, frame):
    """
    Handler for CPU time limit exceeded signal.
    
    Args:
        signum: Signal number
        frame: Current stack frame
    """
    raise ResourceLimitExceeded("CPU time limit exceeded")


def time_limit_handler(signum, frame):
    """
    Handler for time limit exceeded signal.
    
    Args:
        signum: Signal number
        frame: Current stack frame
    """
    raise ResourceLimitExceeded("Time limit exceeded")


def with_resource_limits(
    cpu_limit: Optional[int] = None,
    memory_limit: Optional[int] = None,
    time_limit: Optional[int] = None,
):
    """
    Decorator to apply resource limits to a function.
    
    Args:
        cpu_limit: CPU time limit in seconds
        memory_limit: Memory limit in bytes
        time_limit: Time limit in seconds
        
    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get limits from settings if not provided
            actual_cpu_limit = cpu_limit or getattr(
                settings, "GODMODE_CPU_LIMIT", DEFAULT_CPU_LIMIT
            )
            actual_memory_limit = memory_limit or getattr(
                settings, "GODMODE_MEMORY_LIMIT", DEFAULT_MEMORY_LIMIT
            )
            actual_time_limit = time_limit or getattr(
                settings, "GODMODE_TIME_LIMIT", DEFAULT_TIME_LIMIT
            )
            
            # Set up signal handlers
            signal.signal(signal.SIGXCPU, cpu_limit_handler)
            
            # Set up time limit
            if actual_time_limit:
                signal.signal(signal.SIGALRM, time_limit_handler)
                signal.alarm(actual_time_limit)
            
            try:
                # Set resource limits
                set_resource_limits(actual_cpu_limit, actual_memory_limit)
                
                # Call the function
                return func(*args, **kwargs)
            except ResourceLimitExceeded as e:
                logger.warning(f"Resource limit exceeded: {str(e)}")
                raise
            finally:
                # Reset time limit
                if actual_time_limit:
                    signal.alarm(0)
        
        return wrapper
    
    return decorator


def can_run_simulation() -> bool:
    """
    Check if a simulation can be run.
    
    Returns:
        True if a simulation can be run, False otherwise
    """
    # Get number of running simulations
    running_count = cache.get(SIMULATION_RUNNING_KEY, 0)
    
    # Check if limit reached
    return running_count < MAX_CONCURRENT_SIMULATIONS


def increment_running_simulations() -> int:
    """
    Increment the count of running simulations.
    
    Returns:
        New count of running simulations
    """
    # Get current count
    running_count = cache.get(SIMULATION_RUNNING_KEY, 0)
    
    # Increment count
    running_count += 1
    
    # Update cache
    cache.set(SIMULATION_RUNNING_KEY, running_count)
    
    return running_count


def decrement_running_simulations() -> int:
    """
    Decrement the count of running simulations.
    
    Returns:
        New count of running simulations
    """
    # Get current count
    running_count = cache.get(SIMULATION_RUNNING_KEY, 0)
    
    # Decrement count
    running_count = max(0, running_count - 1)
    
    # Update cache
    cache.set(SIMULATION_RUNNING_KEY, running_count)
    
    return running_count


def queue_simulation(simulation_id: str, priority: int = 0) -> int:
    """
    Queue a simulation for execution.
    
    Args:
        simulation_id: Simulation ID
        priority: Priority (higher values = higher priority)
        
    Returns:
        Position in queue
    """
    # Add to queue with score based on priority and time
    score = priority * 1000000 + int(time.time())
    cache.zadd(SIMULATION_QUEUE_KEY, {simulation_id: score})
    
    # Get position in queue
    position = cache.zrank(SIMULATION_QUEUE_KEY, simulation_id)
    
    return position or 0


def get_next_simulation() -> Optional[str]:
    """
    Get the next simulation from the queue.
    
    Returns:
        Simulation ID or None if queue is empty
    """
    # Get highest priority simulation
    result = cache.zpopmax(SIMULATION_QUEUE_KEY)
    
    if not result:
        return None
    
    # Return simulation ID
    return result[0][0]


def with_simulation_queue(func):
    """
    Decorator to run a function with simulation queue management.
    
    Args:
        func: Function to decorate
        
    Returns:
        Decorated function
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Check if simulation can run
        if not can_run_simulation():
            # Queue simulation
            simulation_id = kwargs.get("simulation_id")
            if simulation_id:
                position = queue_simulation(simulation_id)
                return {
                    "status": "queued",
                    "position": position,
                    "message": f"Simulation queued at position {position}",
                }
            else:
                return {
                    "status": "error",
                    "message": "Maximum number of concurrent simulations reached",
                }
        
        # Increment running count
        increment_running_simulations()
        
        try:
            # Run simulation
            return func(*args, **kwargs)
        finally:
            # Decrement running count
            decrement_running_simulations()
    
    return wrapper

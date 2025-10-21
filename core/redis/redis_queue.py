"""
Redis-based job queuing and processing.

This module provides utilities for queuing and processing jobs using Redis,
which is useful for background processing and task scheduling.
"""

import json
import logging
import time
import uuid
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from core.cache import (
    add_to_list,
    delete_cached_data,
    get_cached_data,
    get_list_range,
    publish_notification,
    set_cached_data,
)
from core.redis_lock import redis_lock

logger = logging.getLogger(__name__)

# Constants
JOB_EXPIRATION = 60 * 60 * 24 * 7  # 7 days
PROCESSING_EXPIRATION = 60 * 5  # 5 minutes
LOCK_TIMEOUT = 30  # 30 seconds
BATCH_SIZE = 100  # Number of jobs to process in a batch


class RedisQueue:
    """
    Redis-based job queue.
    
    This class provides methods for queuing and processing jobs using Redis.
    """
    
    def __init__(self, queue_name: str, expiration: int = JOB_EXPIRATION):
        """
        Initialize a Redis queue.
        
        Args:
            queue_name: Name of the queue
            expiration: Expiration time for jobs in seconds
        """
        self.queue_name = queue_name
        self.expiration = expiration
        self.pending_key = f"queue:{queue_name}:pending"
        self.processing_key = f"queue:{queue_name}:processing"
        self.completed_key = f"queue:{queue_name}:completed"
        self.failed_key = f"queue:{queue_name}:failed"
        self.job_key_prefix = f"queue:{queue_name}:job:"
        
    def enqueue(self, job_data: Dict[str, Any], job_id: Optional[str] = None) -> str:
        """
        Enqueue a job.
        
        Args:
            job_data: Job data
            job_id: Optional job ID (generated if not provided)
            
        Returns:
            Job ID
        """
        # Generate job ID if not provided
        if job_id is None:
            job_id = str(uuid.uuid4())
            
        # Add metadata
        job_data["_id"] = job_id
        job_data["_queue"] = self.queue_name
        job_data["_enqueued_at"] = datetime.now().isoformat()
        job_data["_status"] = "pending"
        
        # Store job data
        job_key = f"{self.job_key_prefix}{job_id}"
        set_cached_data(job_key, job_data, self.expiration)
        
        # Add to pending list
        add_to_list(self.pending_key, job_id, expiration=self.expiration)
        
        logger.info(f"Enqueued job {job_id} in queue {self.queue_name}")
        return job_id
        
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job data.
        
        Args:
            job_id: Job ID
            
        Returns:
            Job data or None if not found
        """
        job_key = f"{self.job_key_prefix}{job_id}"
        return get_cached_data(job_key)
        
    def update_job(self, job_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update job data.
        
        Args:
            job_id: Job ID
            updates: Dictionary of updates to apply
            
        Returns:
            True if successful, False otherwise
        """
        # Get current job data
        job_data = self.get_job(job_id)
        if not job_data:
            logger.error(f"Cannot update job {job_id}: not found")
            return False
            
        # Update job data
        job_data.update(updates)
        job_data["_updated_at"] = datetime.now().isoformat()
        
        # Store updated job data
        job_key = f"{self.job_key_prefix}{job_id}"
        return set_cached_data(job_key, job_data, self.expiration)
        
    def delete_job(self, job_id: str) -> bool:
        """
        Delete a job.
        
        Args:
            job_id: Job ID
            
        Returns:
            True if successful, False otherwise
        """
        job_key = f"{self.job_key_prefix}{job_id}"
        return delete_cached_data(job_key)
        
    def mark_as_processing(self, job_id: str) -> bool:
        """
        Mark a job as being processed.
        
        Args:
            job_id: Job ID
            
        Returns:
            True if successful, False otherwise
        """
        # Get job data
        job_data = self.get_job(job_id)
        if not job_data:
            logger.error(f"Cannot mark job {job_id} as processing: not found")
            return False
            
        # Update status
        job_data["_status"] = "processing"
        job_data["_processing_started"] = datetime.now().isoformat()
        
        # Store updated job data
        job_key = f"{self.job_key_prefix}{job_id}"
        success = set_cached_data(job_key, job_data, self.expiration)
        
        if success:
            # Move from pending to processing
            add_to_list(self.processing_key, job_id, expiration=PROCESSING_EXPIRATION)
            
        return success
        
    def mark_as_completed(self, job_id: str, result: Optional[Dict[str, Any]] = None) -> bool:
        """
        Mark a job as completed.
        
        Args:
            job_id: Job ID
            result: Optional result data
            
        Returns:
            True if successful, False otherwise
        """
        # Get job data
        job_data = self.get_job(job_id)
        if not job_data:
            logger.error(f"Cannot mark job {job_id} as completed: not found")
            return False
            
        # Update status
        job_data["_status"] = "completed"
        job_data["_completed_at"] = datetime.now().isoformat()
        
        if result:
            job_data["_result"] = result
            
        # Store updated job data
        job_key = f"{self.job_key_prefix}{job_id}"
        success = set_cached_data(job_key, job_data, self.expiration)
        
        if success:
            # Move from processing to completed
            add_to_list(self.completed_key, job_id, expiration=self.expiration)
            
            # Publish notification
            publish_notification(
                f"queue:{self.queue_name}:notifications",
                {
                    "type": "job_completed",
                    "job_id": job_id,
                    "queue": self.queue_name,
                    "result": result,
                }
            )
            
        return success
        
    def mark_as_failed(self, job_id: str, error: str) -> bool:
        """
        Mark a job as failed.
        
        Args:
            job_id: Job ID
            error: Error message
            
        Returns:
            True if successful, False otherwise
        """
        # Get job data
        job_data = self.get_job(job_id)
        if not job_data:
            logger.error(f"Cannot mark job {job_id} as failed: not found")
            return False
            
        # Update status
        job_data["_status"] = "failed"
        job_data["_failed_at"] = datetime.now().isoformat()
        job_data["_error"] = error
        
        # Store updated job data
        job_key = f"{self.job_key_prefix}{job_id}"
        success = set_cached_data(job_key, job_data, self.expiration)
        
        if success:
            # Move from processing to failed
            add_to_list(self.failed_key, job_id, expiration=self.expiration)
            
            # Publish notification
            publish_notification(
                f"queue:{self.queue_name}:notifications",
                {
                    "type": "job_failed",
                    "job_id": job_id,
                    "queue": self.queue_name,
                    "error": error,
                }
            )
            
        return success
        
    def get_pending_jobs(self, limit: int = BATCH_SIZE) -> List[str]:
        """
        Get pending job IDs.
        
        Args:
            limit: Maximum number of job IDs to return
            
        Returns:
            List of job IDs
        """
        return get_list_range(self.pending_key, 0, limit - 1)
        
    def get_processing_jobs(self, limit: int = BATCH_SIZE) -> List[str]:
        """
        Get processing job IDs.
        
        Args:
            limit: Maximum number of job IDs to return
            
        Returns:
            List of job IDs
        """
        return get_list_range(self.processing_key, 0, limit - 1)
        
    def get_completed_jobs(self, limit: int = BATCH_SIZE) -> List[str]:
        """
        Get completed job IDs.
        
        Args:
            limit: Maximum number of job IDs to return
            
        Returns:
            List of job IDs
        """
        return get_list_range(self.completed_key, 0, limit - 1)
        
    def get_failed_jobs(self, limit: int = BATCH_SIZE) -> List[str]:
        """
        Get failed job IDs.
        
        Args:
            limit: Maximum number of job IDs to return
            
        Returns:
            List of job IDs
        """
        return get_list_range(self.failed_key, 0, limit - 1)
        
    def process_jobs(self, processor_func: Callable, batch_size: int = BATCH_SIZE) -> Tuple[int, int]:
        """
        Process pending jobs.
        
        Args:
            processor_func: Function to process jobs (takes job data, returns result dict or raises exception)
            batch_size: Number of jobs to process in a batch
            
        Returns:
            Tuple of (success_count, failure_count)
        """
        # Get lock
        lock_name = f"process_jobs:{self.queue_name}"
        
        with redis_lock(lock_name, LOCK_TIMEOUT) as acquired:
            if not acquired:
                logger.warning(f"Could not acquire lock for processing queue {self.queue_name}")
                return (0, 0)
                
            # Get pending job IDs
            pending_ids = self.get_pending_jobs(batch_size)
            
            if not pending_ids:
                logger.info(f"No pending jobs in queue {self.queue_name}")
                return (0, 0)
                
            logger.info(f"Processing {len(pending_ids)} pending jobs in queue {self.queue_name}")
            
            success_count = 0
            failure_count = 0
            
            for job_id in pending_ids:
                try:
                    # Mark as processing
                    self.mark_as_processing(job_id)
                    
                    # Get job data
                    job_data = self.get_job(job_id)
                    if not job_data:
                        logger.error(f"Job {job_id} not found")
                        continue
                        
                    # Process job
                    result = processor_func(job_data)
                    
                    # Mark as completed
                    self.mark_as_completed(job_id, result)
                    
                    success_count += 1
                except Exception as e:
                    # Mark as failed
                    self.mark_as_failed(job_id, str(e))
                    
                    logger.exception(f"Error processing job {job_id}: {str(e)}")
                    failure_count += 1
                    
            logger.info(f"Processed {success_count + failure_count} jobs in queue {self.queue_name}: {success_count} succeeded, {failure_count} failed")
            return (success_count, failure_count)
            
    def retry_failed_jobs(self, processor_func: Callable, batch_size: int = BATCH_SIZE) -> Tuple[int, int]:
        """
        Retry failed jobs.
        
        Args:
            processor_func: Function to process jobs (takes job data, returns result dict or raises exception)
            batch_size: Number of jobs to process in a batch
            
        Returns:
            Tuple of (success_count, failure_count)
        """
        # Get lock
        lock_name = f"retry_failed:{self.queue_name}"
        
        with redis_lock(lock_name, LOCK_TIMEOUT) as acquired:
            if not acquired:
                logger.warning(f"Could not acquire lock for retrying failed jobs in queue {self.queue_name}")
                return (0, 0)
                
            # Get failed job IDs
            failed_ids = self.get_failed_jobs(batch_size)
            
            if not failed_ids:
                logger.info(f"No failed jobs in queue {self.queue_name}")
                return (0, 0)
                
            logger.info(f"Retrying {len(failed_ids)} failed jobs in queue {self.queue_name}")
            
            success_count = 0
            failure_count = 0
            
            for job_id in failed_ids:
                try:
                    # Get job data
                    job_data = self.get_job(job_id)
                    if not job_data:
                        logger.error(f"Job {job_id} not found")
                        continue
                        
                    # Update status
                    job_data["_status"] = "pending"
                    job_data["_retried_at"] = datetime.now().isoformat()
                    
                    # Store updated job data
                    job_key = f"{self.job_key_prefix}{job_id}"
                    set_cached_data(job_key, job_data, self.expiration)
                    
                    # Process job
                    result = processor_func(job_data)
                    
                    # Mark as completed
                    self.mark_as_completed(job_id, result)
                    
                    success_count += 1
                except Exception as e:
                    # Mark as failed
                    self.mark_as_failed(job_id, str(e))
                    
                    logger.exception(f"Error retrying job {job_id}: {str(e)}")
                    failure_count += 1
                    
            logger.info(f"Retried {success_count + failure_count} failed jobs in queue {self.queue_name}: {success_count} succeeded, {failure_count} failed")
            return (success_count, failure_count)


def enqueue_job(queue_name: str, job_data: Dict[str, Any]) -> str:
    """
    Enqueue a job in the specified queue.
    
    Args:
        queue_name: Name of the queue
        job_data: Job data
        
    Returns:
        Job ID
    """
    queue = RedisQueue(queue_name)
    return queue.enqueue(job_data)


def process_queue(queue_name: str, processor_func: Callable, batch_size: int = BATCH_SIZE) -> Tuple[int, int]:
    """
    Process jobs in the specified queue.
    
    Args:
        queue_name: Name of the queue
        processor_func: Function to process jobs (takes job data, returns result dict or raises exception)
        batch_size: Number of jobs to process in a batch
        
    Returns:
        Tuple of (success_count, failure_count)
    """
    queue = RedisQueue(queue_name)
    return queue.process_jobs(processor_func, batch_size)


def background_task(queue_name: str):
    """
    Decorator for background tasks.
    
    Args:
        queue_name: Name of the queue
        
    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Prepare job data
            job_data = {
                "func": func.__name__,
                "module": func.__module__,
                "args": args,
                "kwargs": kwargs,
            }
            
            # Enqueue job
            job_id = enqueue_job(queue_name, job_data)
            
            # Return job ID
            return job_id
        
        # Add reference to original function
        wrapper.original_func = func
        
        return wrapper
    return decorator

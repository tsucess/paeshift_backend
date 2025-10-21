"""
Redis Data Manager for ensuring data consistency and validation.

This module provides a comprehensive Redis data management system that acts as a buffer
before data is stored in the database, ensuring consistency and validation.
"""

import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction

from core.cache import (
    acquire_lock,
    add_to_list,
    add_to_sorted_set,
    delete_cached_data,
    delete_hash_field,
    get_cached_data,
    get_hash_all,
    get_hash_field,
    get_list_range,
    get_sorted_set_range,
    publish_notification,
    release_lock,
    set_cached_data,
    set_hash_field,
)

logger = logging.getLogger(__name__)

# Constants
DATA_EXPIRATION = 60 * 60 * 24 * 7  # 7 days
PROCESSING_EXPIRATION = 60 * 5  # 5 minutes
LOCK_TIMEOUT = 30  # 30 seconds
BATCH_SIZE = 100  # Number of items to process in a batch


class RedisDataManager:
    """
    Redis Data Manager for ensuring data consistency and validation.
    
    This class provides methods for managing data in Redis before it is stored in the database.
    It ensures data consistency, validation, and provides a buffer for high-throughput operations.
    """
    
    def __init__(self, data_type: str, expiration: int = DATA_EXPIRATION):
        """
        Initialize the Redis Data Manager.
        
        Args:
            data_type: Type of data being managed (e.g., "job", "user", "payment")
            expiration: Expiration time for data in seconds
        """
        self.data_type = data_type
        self.expiration = expiration
        self.pending_key = f"pending:{data_type}"
        self.processing_key = f"processing:{data_type}"
        self.failed_key = f"failed:{data_type}"
        self.data_key_prefix = f"data:{data_type}:"
        
    def generate_data_id(self) -> str:
        """
        Generate a unique ID for data.
        
        Returns:
            Unique ID string
        """
        return str(uuid.uuid4())
        
    def store_data(self, data: Dict[str, Any], data_id: Optional[str] = None) -> str:
        """
        Store data in Redis for later processing.
        
        Args:
            data: Data to store
            data_id: Optional ID for the data (generated if not provided)
            
        Returns:
            Data ID
        """
        # Generate ID if not provided
        if data_id is None:
            data_id = self.generate_data_id()
            
        # Add metadata
        data["_id"] = data_id
        data["_type"] = self.data_type
        data["_timestamp"] = datetime.now().isoformat()
        data["_status"] = "pending"
        
        # Store data
        data_key = f"{self.data_key_prefix}{data_id}"
        set_cached_data(data_key, data, self.expiration)
        
        # Add to pending list
        add_to_list(self.pending_key, data_id, expiration=self.expiration)
        
        logger.info(f"Stored {self.data_type} data with ID {data_id}")
        return data_id
        
    def get_data(self, data_id: str) -> Optional[Dict[str, Any]]:
        """
        Get data from Redis.
        
        Args:
            data_id: ID of the data to get
            
        Returns:
            Data dictionary or None if not found
        """
        data_key = f"{self.data_key_prefix}{data_id}"
        return get_cached_data(data_key)
        
    def update_data(self, data_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update data in Redis.
        
        Args:
            data_id: ID of the data to update
            updates: Dictionary of updates to apply
            
        Returns:
            True if successful, False otherwise
        """
        # Get current data
        data = self.get_data(data_id)
        if not data:
            logger.error(f"Cannot update {self.data_type} data with ID {data_id}: not found")
            return False
            
        # Update data
        data.update(updates)
        data["_updated"] = datetime.now().isoformat()
        
        # Store updated data
        data_key = f"{self.data_key_prefix}{data_id}"
        return set_cached_data(data_key, data, self.expiration)
        
    def delete_data(self, data_id: str) -> bool:
        """
        Delete data from Redis.
        
        Args:
            data_id: ID of the data to delete
            
        Returns:
            True if successful, False otherwise
        """
        data_key = f"{self.data_key_prefix}{data_id}"
        return delete_cached_data(data_key)
        
    def mark_as_processing(self, data_id: str) -> bool:
        """
        Mark data as being processed.
        
        Args:
            data_id: ID of the data to mark
            
        Returns:
            True if successful, False otherwise
        """
        # Get data
        data = self.get_data(data_id)
        if not data:
            logger.error(f"Cannot mark {self.data_type} data with ID {data_id} as processing: not found")
            return False
            
        # Update status
        data["_status"] = "processing"
        data["_processing_started"] = datetime.now().isoformat()
        
        # Store updated data
        data_key = f"{self.data_key_prefix}{data_id}"
        success = set_cached_data(data_key, data, self.expiration)
        
        if success:
            # Move from pending to processing
            add_to_list(self.processing_key, data_id, expiration=PROCESSING_EXPIRATION)
            
        return success
        
    def mark_as_completed(self, data_id: str, result: Optional[Dict[str, Any]] = None) -> bool:
        """
        Mark data as completed.
        
        Args:
            data_id: ID of the data to mark
            result: Optional result data
            
        Returns:
            True if successful, False otherwise
        """
        # Get data
        data = self.get_data(data_id)
        if not data:
            logger.error(f"Cannot mark {self.data_type} data with ID {data_id} as completed: not found")
            return False
            
        # Update status
        data["_status"] = "completed"
        data["_completed"] = datetime.now().isoformat()
        
        if result:
            data["_result"] = result
            
        # Store updated data
        data_key = f"{self.data_key_prefix}{data_id}"
        return set_cached_data(data_key, data, self.expiration)
        
    def mark_as_failed(self, data_id: str, error: str) -> bool:
        """
        Mark data as failed.
        
        Args:
            data_id: ID of the data to mark
            error: Error message
            
        Returns:
            True if successful, False otherwise
        """
        # Get data
        data = self.get_data(data_id)
        if not data:
            logger.error(f"Cannot mark {self.data_type} data with ID {data_id} as failed: not found")
            return False
            
        # Update status
        data["_status"] = "failed"
        data["_failed"] = datetime.now().isoformat()
        data["_error"] = error
        
        # Store updated data
        data_key = f"{self.data_key_prefix}{data_id}"
        success = set_cached_data(data_key, data, self.expiration)
        
        if success:
            # Add to failed list
            add_to_list(self.failed_key, data_id, expiration=self.expiration)
            
        return success
        
    def get_pending_data_ids(self, limit: int = BATCH_SIZE) -> List[str]:
        """
        Get IDs of pending data.
        
        Args:
            limit: Maximum number of IDs to return
            
        Returns:
            List of data IDs
        """
        return get_list_range(self.pending_key, 0, limit - 1)
        
    def get_processing_data_ids(self, limit: int = BATCH_SIZE) -> List[str]:
        """
        Get IDs of data being processed.
        
        Args:
            limit: Maximum number of IDs to return
            
        Returns:
            List of data IDs
        """
        return get_list_range(self.processing_key, 0, limit - 1)
        
    def get_failed_data_ids(self, limit: int = BATCH_SIZE) -> List[str]:
        """
        Get IDs of failed data.
        
        Args:
            limit: Maximum number of IDs to return
            
        Returns:
            List of data IDs
        """
        return get_list_range(self.failed_key, 0, limit - 1)
        
    def process_pending_data(self, processor_func, batch_size: int = BATCH_SIZE) -> Tuple[int, int]:
        """
        Process pending data.
        
        Args:
            processor_func: Function to process data (takes data dict, returns result dict or raises exception)
            batch_size: Number of items to process in a batch
            
        Returns:
            Tuple of (success_count, failure_count)
        """
        # Get lock
        lock_name = f"process_pending:{self.data_type}"
        lock_owner = f"process_{time.time()}"
        
        if not acquire_lock(lock_name, lock_owner, LOCK_TIMEOUT):
            logger.warning(f"Could not acquire lock for processing {self.data_type} data")
            return (0, 0)
            
        try:
            # Get pending data IDs
            pending_ids = self.get_pending_data_ids(batch_size)
            
            if not pending_ids:
                logger.info(f"No pending {self.data_type} data to process")
                return (0, 0)
                
            logger.info(f"Processing {len(pending_ids)} pending {self.data_type} data items")
            
            success_count = 0
            failure_count = 0
            
            for data_id in pending_ids:
                try:
                    # Mark as processing
                    self.mark_as_processing(data_id)
                    
                    # Get data
                    data = self.get_data(data_id)
                    if not data:
                        logger.error(f"Data {data_id} not found")
                        continue
                        
                    # Process data
                    result = processor_func(data)
                    
                    # Mark as completed
                    self.mark_as_completed(data_id, result)
                    
                    success_count += 1
                except Exception as e:
                    # Mark as failed
                    self.mark_as_failed(data_id, str(e))
                    
                    logger.exception(f"Error processing {self.data_type} data {data_id}: {str(e)}")
                    failure_count += 1
                    
            logger.info(f"Processed {success_count + failure_count} {self.data_type} data items: {success_count} succeeded, {failure_count} failed")
            return (success_count, failure_count)
        finally:
            # Release lock
            release_lock(lock_name, lock_owner)
            
    def retry_failed_data(self, processor_func, batch_size: int = BATCH_SIZE) -> Tuple[int, int]:
        """
        Retry failed data.
        
        Args:
            processor_func: Function to process data (takes data dict, returns result dict or raises exception)
            batch_size: Number of items to process in a batch
            
        Returns:
            Tuple of (success_count, failure_count)
        """
        # Get lock
        lock_name = f"retry_failed:{self.data_type}"
        lock_owner = f"retry_{time.time()}"
        
        if not acquire_lock(lock_name, lock_owner, LOCK_TIMEOUT):
            logger.warning(f"Could not acquire lock for retrying {self.data_type} data")
            return (0, 0)
            
        try:
            # Get failed data IDs
            failed_ids = self.get_failed_data_ids(batch_size)
            
            if not failed_ids:
                logger.info(f"No failed {self.data_type} data to retry")
                return (0, 0)
                
            logger.info(f"Retrying {len(failed_ids)} failed {self.data_type} data items")
            
            success_count = 0
            failure_count = 0
            
            for data_id in failed_ids:
                try:
                    # Get data
                    data = self.get_data(data_id)
                    if not data:
                        logger.error(f"Data {data_id} not found")
                        continue
                        
                    # Update status
                    data["_status"] = "pending"
                    data["_retried"] = datetime.now().isoformat()
                    
                    # Store updated data
                    data_key = f"{self.data_key_prefix}{data_id}"
                    set_cached_data(data_key, data, self.expiration)
                    
                    # Process data
                    result = processor_func(data)
                    
                    # Mark as completed
                    self.mark_as_completed(data_id, result)
                    
                    success_count += 1
                except Exception as e:
                    # Mark as failed
                    self.mark_as_failed(data_id, str(e))
                    
                    logger.exception(f"Error retrying {self.data_type} data {data_id}: {str(e)}")
                    failure_count += 1
                    
            logger.info(f"Retried {success_count + failure_count} {self.data_type} data items: {success_count} succeeded, {failure_count} failed")
            return (success_count, failure_count)
        finally:
            # Release lock
            release_lock(lock_name, lock_owner)
            
    def cleanup_stale_processing(self) -> int:
        """
        Clean up stale processing data.
        
        Returns:
            Number of items cleaned up
        """
        # Get lock
        lock_name = f"cleanup_stale:{self.data_type}"
        lock_owner = f"cleanup_{time.time()}"
        
        if not acquire_lock(lock_name, lock_owner, LOCK_TIMEOUT):
            logger.warning(f"Could not acquire lock for cleaning up stale {self.data_type} data")
            return 0
            
        try:
            # Get processing data IDs
            processing_ids = self.get_processing_data_ids()
            
            if not processing_ids:
                logger.info(f"No processing {self.data_type} data to clean up")
                return 0
                
            logger.info(f"Checking {len(processing_ids)} processing {self.data_type} data items for staleness")
            
            cleanup_count = 0
            stale_threshold = datetime.now() - timedelta(minutes=5)
            
            for data_id in processing_ids:
                # Get data
                data = self.get_data(data_id)
                if not data:
                    logger.error(f"Data {data_id} not found")
                    continue
                    
                # Check if stale
                processing_started = data.get("_processing_started")
                if processing_started:
                    started_time = datetime.fromisoformat(processing_started)
                    if started_time < stale_threshold:
                        # Mark as failed
                        self.mark_as_failed(data_id, "Processing timed out")
                        
                        logger.warning(f"Marked stale processing {self.data_type} data {data_id} as failed")
                        cleanup_count += 1
                        
            logger.info(f"Cleaned up {cleanup_count} stale {self.data_type} data items")
            return cleanup_count
        finally:
            # Release lock
            release_lock(lock_name, lock_owner)


class JobDataManager(RedisDataManager):
    """
    Redis Data Manager for job data.
    """
    
    def __init__(self):
        super().__init__("job")
        
    def store_job(self, job_data: Dict[str, Any]) -> str:
        """
        Store job data in Redis.
        
        Args:
            job_data: Job data to store
            
        Returns:
            Job ID
        """
        # Validate job data
        required_fields = ["title", "description", "client_id"]
        for field in required_fields:
            if field not in job_data:
                raise ValueError(f"Missing required field: {field}")
                
        # Store job data
        return self.store_data(job_data)
        
    def process_jobs(self, batch_size: int = BATCH_SIZE) -> Tuple[int, int]:
        """
        Process pending jobs.
        
        Args:
            batch_size: Number of jobs to process in a batch
            
        Returns:
            Tuple of (success_count, failure_count)
        """
        def job_processor(job_data: Dict[str, Any]) -> Dict[str, Any]:
            """Process a job."""
            # Here you would typically save to database
            # For now, we'll just simulate processing
            logger.info(f"Processing job: {job_data.get('title')}")
            
            # Simulate database save
            time.sleep(0.1)
            
            # Return result
            return {
                "job_id": job_data.get("_id"),
                "status": "created",
                "created_at": datetime.now().isoformat()
            }
            
        return self.process_pending_data(job_processor, batch_size)


class UserDataManager(RedisDataManager):
    """
    Redis Data Manager for user data.
    """
    
    def __init__(self):
        super().__init__("user")
        
    def store_user(self, user_data: Dict[str, Any]) -> str:
        """
        Store user data in Redis.
        
        Args:
            user_data: User data to store
            
        Returns:
            User ID
        """
        # Validate user data
        required_fields = ["username", "email"]
        for field in required_fields:
            if field not in user_data:
                raise ValueError(f"Missing required field: {field}")
                
        # Store user data
        return self.store_data(user_data)
        
    def process_users(self, batch_size: int = BATCH_SIZE) -> Tuple[int, int]:
        """
        Process pending users.
        
        Args:
            batch_size: Number of users to process in a batch
            
        Returns:
            Tuple of (success_count, failure_count)
        """
        def user_processor(user_data: Dict[str, Any]) -> Dict[str, Any]:
            """Process a user."""
            # Here you would typically save to database
            # For now, we'll just simulate processing
            logger.info(f"Processing user: {user_data.get('username')}")
            
            # Simulate database save
            time.sleep(0.1)
            
            # Return result
            return {
                "user_id": user_data.get("_id"),
                "status": "created",
                "created_at": datetime.now().isoformat()
            }
            
        return self.process_pending_data(user_processor, batch_size)


class PaymentDataManager(RedisDataManager):
    """
    Redis Data Manager for payment data.
    """
    
    def __init__(self):
        super().__init__("payment")
        
    def store_payment(self, payment_data: Dict[str, Any]) -> str:
        """
        Store payment data in Redis.
        
        Args:
            payment_data: Payment data to store
            
        Returns:
            Payment ID
        """
        # Validate payment data
        required_fields = ["amount", "user_id", "payment_method"]
        for field in required_fields:
            if field not in payment_data:
                raise ValueError(f"Missing required field: {field}")
                
        # Store payment data
        return self.store_data(payment_data)
        
    def process_payments(self, batch_size: int = BATCH_SIZE) -> Tuple[int, int]:
        """
        Process pending payments.
        
        Args:
            batch_size: Number of payments to process in a batch
            
        Returns:
            Tuple of (success_count, failure_count)
        """
        def payment_processor(payment_data: Dict[str, Any]) -> Dict[str, Any]:
            """Process a payment."""
            # Here you would typically save to database and process payment
            # For now, we'll just simulate processing
            logger.info(f"Processing payment: {payment_data.get('amount')} for user {payment_data.get('user_id')}")
            
            # Simulate payment processing
            time.sleep(0.2)
            
            # Return result
            return {
                "payment_id": payment_data.get("_id"),
                "status": "processed",
                "processed_at": datetime.now().isoformat()
            }
            
        return self.process_pending_data(payment_processor, batch_size)

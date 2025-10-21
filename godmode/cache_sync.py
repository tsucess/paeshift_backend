"""
Cache-to-DB synchronization utilities for God Mode.

This module provides utilities for synchronizing Redis cache with the database,
ensuring data consistency between cache and database through version tracking,
timestamp validation, and atomic updates.
"""

import json
import logging
import time
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Union, Any

from django.apps import apps
from django.conf import settings
from django.db import transaction, models
from django.utils import timezone
from django.core.cache import cache

from core.cache import redis_client, get_cached_data, set_cached_data, delete_cached_data
from core.redis_settings import CACHE_ENABLED
from core.redis_lock import redis_lock

# Configure logging with more detailed format
logger = logging.getLogger(__name__)

# Constants
CACHE_VERSION = getattr(settings, 'CACHE_VERSION', '1.0')
CONSISTENCY_CHECK_BATCH_SIZE = 100
STANDARD_TIMESTAMP_FIELD = 'last_updated'
CACHE_SYNC_LOCK_TIMEOUT = 60  # seconds


def calculate_data_hash(data: Dict) -> str:
    """
    Calculate a hash of the data for consistency checking.

    Args:
        data: Dictionary of data

    Returns:
        Hash string
    """
    # Convert data to a stable string representation
    data_str = json.dumps(data, sort_keys=True)
    # Calculate hash
    return hashlib.md5(data_str.encode()).hexdigest()


def check_cache_consistency(model_class, sample_size=CONSISTENCY_CHECK_BATCH_SIZE):
    """
    Check cache consistency for a sample of model instances.

    Args:
        model_class: Model class to check
        sample_size: Number of instances to check

    Returns:
        Dictionary with consistency statistics
    """
    model_name = model_class.__name__.lower()

    # Get a random sample of instances
    instances = model_class.objects.order_by('?')[:sample_size]

    stats = {
        'total': len(instances),
        'consistent': 0,
        'inconsistent': 0,
        'missing': 0,
        'inconsistent_fields': {},
        'version_mismatches': 0,
        'timestamp_mismatches': 0,
        'details': []
    }

    for instance in instances:
        # Generate cache key
        cache_key = f"{model_name}:{instance.pk}"

        # Try to get from both regular and permanent cache
        cached_data = get_cached_data(cache_key)
        if cached_data is None:
            # Try permanent cache
            from core.redis_permanent import get_permanent_cache
            cached_data = get_permanent_cache(cache_key)

        if cached_data is None:
            stats['missing'] += 1
            stats['details'].append({
                'id': instance.pk,
                'status': 'missing',
                'message': f"No cache entry found for {model_name}:{instance.pk}"
            })
            continue

        # Check version if available
        if 'version' in cached_data and hasattr(instance, 'version'):
            db_version = getattr(instance, 'version')
            cache_version = cached_data['version']

            if db_version != cache_version:
                stats['version_mismatches'] += 1
                stats['inconsistent'] += 1
                stats['details'].append({
                    'id': instance.pk,
                    'status': 'version_mismatch',
                    'message': f"Version mismatch: DB={db_version}, Cache={cache_version}"
                })
                continue

        # Check timestamp if available
        timestamp_fields = ["last_updated", "updated_at", "timestamp", "modified_at", "created_at"]

        cache_timestamp = None
        db_timestamp = None

        # Find timestamps in both cache and DB
        for field in timestamp_fields:
            if field in cached_data:
                try:
                    if isinstance(cached_data[field], str):
                        cache_timestamp = datetime.fromisoformat(cached_data[field])
                    elif isinstance(cached_data[field], (int, float)):
                        cache_timestamp = datetime.fromtimestamp(cached_data[field])
                    break
                except (ValueError, TypeError):
                    continue

            if hasattr(instance, field):
                db_field_value = getattr(instance, field)
                if isinstance(db_field_value, datetime):
                    db_timestamp = db_field_value
                    break

        # Compare timestamps if both are available
        if cache_timestamp and db_timestamp:
            # Allow a small tolerance (1 second) for timestamp comparison
            if abs((cache_timestamp - db_timestamp).total_seconds()) > 1:
                stats['timestamp_mismatches'] += 1
                stats['inconsistent'] += 1
                stats['details'].append({
                    'id': instance.pk,
                    'status': 'timestamp_mismatch',
                    'message': f"Timestamp mismatch: DB={db_timestamp.isoformat()}, Cache={cache_timestamp.isoformat()}"
                })
                continue

        # Check field by field consistency
        inconsistent_fields = []

        for field in instance._meta.fields:
            field_name = field.name

            # Skip fields that aren't in the cache
            if field_name not in cached_data:
                continue

            # Get values
            db_value = getattr(instance, field_name)
            cache_value = cached_data[field_name]

            # Handle special field types
            if isinstance(db_value, models.Model):
                db_value = db_value.pk
            elif hasattr(db_value, 'isoformat'):
                db_value = db_value.isoformat()

            # Compare values
            if db_value != cache_value:
                inconsistent_fields.append(field_name)

                if field_name not in stats['inconsistent_fields']:
                    stats['inconsistent_fields'][field_name] = 0
                stats['inconsistent_fields'][field_name] += 1

        if inconsistent_fields:
            stats['inconsistent'] += 1
            stats['details'].append({
                'id': instance.pk,
                'status': 'field_mismatch',
                'message': f"Field mismatches: {', '.join(inconsistent_fields)}",
                'fields': inconsistent_fields
            })
        else:
            stats['consistent'] += 1
            stats['details'].append({
                'id': instance.pk,
                'status': 'consistent',
                'message': "Cache and DB are consistent"
            })

    # Calculate percentages
    if stats['total'] > 0:
        stats['consistent_percent'] = (stats['consistent'] / stats['total']) * 100
        stats['inconsistent_percent'] = (stats['inconsistent'] / stats['total']) * 100
        stats['missing_percent'] = (stats['missing'] / stats['total']) * 100

    return stats


class CacheSyncManager:
    """
    Enhanced manager for synchronizing Redis cache with the database.

    Features:
    - Version-based consistency checking
    - Timestamp validation
    - Atomic updates with locking
    - Comprehensive logging
    - Cache consistency monitoring
    """

    def __init__(self):
        """Initialize the cache sync manager."""
        self.sync_log = []
        self.sync_stats = {
            "total_keys": 0,
            "synced_keys": 0,
            "skipped_keys": 0,
            "error_keys": 0,
            "models_synced": {},
            "version_mismatches": 0,
            "timestamp_mismatches": 0,
        }
        self.last_consistency_check = {}

    def get_model_keys(self, model_name: str) -> List[str]:
        """
        Get all Redis keys for a specific model.

        Args:
            model_name: Name of the model (lowercase)

        Returns:
            List of Redis keys
        """
        if not CACHE_ENABLED or not redis_client:
            return []

        try:
            # Get keys for the model
            pattern = f"{model_name}:*"
            keys = redis_client.keys(pattern)

            # Also check for permanent cache
            permanent_pattern = f"permanent:{model_name}:*"
            permanent_keys = redis_client.keys(permanent_pattern)

            # Combine and return
            return [k.decode('utf-8') for k in keys + permanent_keys]
        except Exception as e:
            logger.error(f"Error getting keys for model {model_name}: {str(e)}")
            return []

    def get_cached_data(self, key: str) -> Optional[Dict]:
        """
        Get cached data for a key.

        Args:
            key: Redis key

        Returns:
            Cached data or None if not found
        """
        if not CACHE_ENABLED or not redis_client:
            return None

        try:
            # Get data from Redis
            data = redis_client.get(key)

            if data:
                # Parse JSON data
                return json.loads(data)

            return None
        except Exception as e:
            logger.error(f"Error getting cached data for key {key}: {str(e)}")
            return None

    def get_model_and_id_from_key(self, key: str) -> Tuple[Optional[str], Optional[int]]:
        """
        Extract model name and ID from a Redis key.

        Args:
            key: Redis key

        Returns:
            Tuple of (model_name, id)
        """
        try:
            # Handle permanent keys
            if key.startswith("permanent:"):
                key = key[len("permanent:"):]

            # Split the key
            parts = key.split(":")

            if len(parts) >= 2:
                model_name = parts[0]
                model_id = int(parts[1])
                return model_name, model_id

            return None, None
        except Exception as e:
            logger.error(f"Error parsing key {key}: {str(e)}")
            return None, None

    def get_db_model(self, model_name: str) -> Optional[object]:
        """
        Get the Django model class for a model name.

        Args:
            model_name: Name of the model (lowercase)

        Returns:
            Django model class or None if not found
        """
        try:
            # Try common app names
            common_apps = ["accounts", "jobs", "payment", "disputes", "userlocation", "godmode"]

            for app in common_apps:
                try:
                    return apps.get_model(app, model_name)
                except LookupError:
                    continue

            # If not found in common apps, try all apps
            for app_config in apps.get_app_configs():
                try:
                    return apps.get_model(app_config.label, model_name)
                except LookupError:
                    continue

            logger.error(f"Model {model_name} not found in any app")
            return None
        except Exception as e:
            logger.error(f"Error getting model class for {model_name}: {str(e)}")
            return None

    def sync_key_to_db(self, key: str, force: bool = False) -> bool:
        """
        Synchronize a Redis key to the database with enhanced consistency checks.

        Args:
            key: Redis key
            force: Whether to force sync even if the cache is older

        Returns:
            True if synced successfully, False otherwise
        """
        try:
            # Get model name and ID from key
            model_name, model_id = self.get_model_and_id_from_key(key)

            if not model_name or not model_id:
                logger.error(f"Invalid key format: {key}")
                self.sync_log.append({
                    "key": key,
                    "status": "error",
                    "message": "Invalid key format",
                    "timestamp": timezone.now().isoformat(),
                })
                self.sync_stats["error_keys"] += 1
                return False

            # Get cached data
            cached_data = self.get_cached_data(key)

            if not cached_data:
                logger.error(f"No cached data found for key: {key}")
                self.sync_log.append({
                    "key": key,
                    "status": "error",
                    "message": "No cached data found",
                    "timestamp": timezone.now().isoformat(),
                })
                self.sync_stats["error_keys"] += 1
                return False

            # Get model class
            model_class = self.get_db_model(model_name)

            if not model_class:
                logger.error(f"Model class not found for: {model_name}")
                self.sync_log.append({
                    "key": key,
                    "status": "error",
                    "message": f"Model class not found: {model_name}",
                    "timestamp": timezone.now().isoformat(),
                })
                self.sync_stats["error_keys"] += 1
                return False

            # Use a lock to prevent concurrent updates to the same object
            lock_name = f"sync_lock:{model_name}:{model_id}"

            with redis_lock(lock_name, timeout=CACHE_SYNC_LOCK_TIMEOUT) as acquired:
                if not acquired:
                    logger.warning(f"Could not acquire lock for {key}, another process may be updating it")
                    self.sync_log.append({
                        "key": key,
                        "status": "skipped",
                        "message": "Could not acquire lock, another process may be updating this object",
                        "timestamp": timezone.now().isoformat(),
                    })
                    self.sync_stats["skipped_keys"] += 1
                    return False

                # Get the database object with select_for_update to lock the row
                with transaction.atomic():
                    try:
                        # Use select_for_update to lock the row during the transaction
                        db_obj = model_class.objects.select_for_update().get(id=model_id)
                    except model_class.DoesNotExist:
                        logger.error(f"Object not found in DB: {model_name} {model_id}")
                        self.sync_log.append({
                            "key": key,
                            "status": "error",
                            "message": f"Object not found in DB: {model_name} {model_id}",
                            "timestamp": timezone.now().isoformat(),
                        })
                        self.sync_stats["error_keys"] += 1
                        return False

                # Check version if available
                if 'version' in cached_data and hasattr(db_obj, 'version'):
                    db_version = getattr(db_obj, 'version')
                    cache_version = cached_data['version']

                    if not force and db_version > cache_version:
                        logger.info(f"DB version is newer than cache: {key} (DB: {db_version}, Cache: {cache_version})")
                        self.sync_log.append({
                            "key": key,
                            "status": "skipped",
                            "message": f"DB version is newer than cache (DB: {db_version}, Cache: {cache_version})",
                            "timestamp": timezone.now().isoformat(),
                        })
                        self.sync_stats["skipped_keys"] += 1
                        self.sync_stats["version_mismatches"] += 1
                        return False

                # Check if cache is newer than DB using timestamps
                timestamp_fields = ["last_updated", "updated_at", "timestamp", "modified_at", "created_at"]

                cache_timestamp = None
                db_timestamp = None

                # Find a timestamp in the cached data
                for field in timestamp_fields:
                    if field in cached_data:
                        try:
                            if isinstance(cached_data[field], str):
                                cache_timestamp = datetime.fromisoformat(cached_data[field])
                            elif isinstance(cached_data[field], (int, float)):
                                # Handle timestamp as seconds since epoch
                                cache_timestamp = datetime.fromtimestamp(cached_data[field])
                            break
                        except (ValueError, TypeError):
                            continue

                # Find a timestamp in the DB object
                for field in timestamp_fields:
                    if hasattr(db_obj, field):
                        db_field_value = getattr(db_obj, field)
                        if isinstance(db_field_value, datetime):
                            db_timestamp = db_field_value
                            break

                # If we have both timestamps and not forcing, compare them
                if not force and cache_timestamp and db_timestamp:
                    # Allow a small tolerance (1 second) for timestamp comparison
                    if (db_timestamp - cache_timestamp).total_seconds() > 1:
                        logger.info(f"DB object is newer than cache: {key}")
                        self.sync_log.append({
                            "key": key,
                            "status": "skipped",
                            "message": f"DB object is newer than cache (DB: {db_timestamp.isoformat()}, Cache: {cache_timestamp.isoformat()})",
                            "timestamp": timezone.now().isoformat(),
                        })
                        self.sync_stats["skipped_keys"] += 1
                        self.sync_stats["timestamp_mismatches"] += 1
                        return False
                    else:
                        logger.info(f"Cache is newer than or equal to DB: {key} (Cache: {cache_timestamp.isoformat()}, DB: {db_timestamp.isoformat()})")
                elif not force and (cache_timestamp is None or db_timestamp is None):
                    # If we're missing timestamps and not forcing, log it but continue with sync
                    logger.warning(f"Missing timestamps for comparison: {key} (Cache timestamp: {cache_timestamp}, DB timestamp: {db_timestamp})")
                    self.sync_log.append({
                        "key": key,
                        "status": "warning",
                        "message": f"Missing timestamps for comparison (Cache: {cache_timestamp}, DB: {db_timestamp})",
                        "timestamp": timezone.now().isoformat(),
                    })

                # Calculate a hash of the original DB object for change detection
                original_data = {}
                for field in db_obj._meta.fields:
                    field_name = field.name
                    value = getattr(db_obj, field_name)

                    # Handle special field types
                    if isinstance(value, models.Model):
                        original_data[field_name] = value.pk
                    elif hasattr(value, 'isoformat'):
                        original_data[field_name] = value.isoformat()
                    else:
                        original_data[field_name] = value

                original_hash = calculate_data_hash(original_data)

                # Update fields from cached data
                updated_fields = []
                for field, value in cached_data.items():
                    # Skip ID field and fields ending with _id (foreign keys)
                    if field == "id" or field.endswith("_id"):
                        continue

                    # Skip fields that don't exist in the model
                    if not hasattr(db_obj, field):
                        continue

                    # Handle datetime fields
                    if isinstance(value, str) and field in ["created_at", "updated_at", "last_updated", "timestamp"]:
                        try:
                            value = datetime.fromisoformat(value)
                        except ValueError:
                            # Skip if we can't parse the datetime
                            continue

                    # Set the field value
                    current_value = getattr(db_obj, field)
                    if current_value != value:
                        setattr(db_obj, field, value)  # Fixed: Added missing value parameter
                        updated_fields.append(field)

                # If version field exists, increment it
                if hasattr(db_obj, 'version'):
                    db_obj.version = getattr(db_obj, 'version') + 1
                    updated_fields.append('version')

                # If standard timestamp field exists, update it
                if hasattr(db_obj, STANDARD_TIMESTAMP_FIELD):
                    setattr(db_obj, STANDARD_TIMESTAMP_FIELD, timezone.now())
                    updated_fields.append(STANDARD_TIMESTAMP_FIELD)

                # Save the object with updated fields
                if updated_fields:
                    with transaction.atomic():
                        db_obj.save(update_fields=updated_fields)

                    # Calculate new hash to verify changes
                    new_data = {}
                    for field in db_obj._meta.fields:
                        field_name = field.name
                        value = getattr(db_obj, field_name)

                        # Handle special field types
                        if isinstance(value, models.Model):
                            new_data[field_name] = value.pk
                        elif hasattr(value, 'isoformat'):
                            new_data[field_name] = value.isoformat()
                        else:
                            new_data[field_name] = value

                    new_hash = calculate_data_hash(new_data)

                    if original_hash == new_hash:
                        logger.info(f"No changes detected after sync for {key}")
                    else:
                        logger.info(f"Changes detected after sync for {key}: {', '.join(updated_fields)}")
                else:
                    logger.info(f"No fields needed updating for {key}")

                # Log the sync
                logger.info(f"Synced key to DB: {key}")
                self.sync_log.append({
                    "key": key,
                    "status": "success",
                    "message": f"Synced {model_name} {model_id} to DB",
                    "timestamp": timezone.now().isoformat(),
                    "updated_fields": updated_fields if 'updated_fields' in locals() else [],
                })

                # Update stats
                self.sync_stats["synced_keys"] += 1
                if model_name in self.sync_stats["models_synced"]:
                    self.sync_stats["models_synced"][model_name] += 1
                else:
                    self.sync_stats["models_synced"][model_name] = 1

                return True

        except Exception as e:
            logger.exception(f"Error syncing key {key} to DB: {str(e)}")
            self.sync_log.append({
                "key": key,
                "status": "error",
                "message": str(e),
                "timestamp": timezone.now().isoformat(),
            })
            self.sync_stats["error_keys"] += 1
            return False

    def sync_model_to_db(self, model_name: str, force: bool = False) -> Dict:
        """
        Synchronize all Redis keys for a model to the database.

        Args:
            model_name: Name of the model (lowercase)
            force: Whether to force sync even if the cache is older

        Returns:
            Dictionary with sync statistics
        """
        start_time = time.time()

        # Reset stats
        self.sync_stats = {
            "total_keys": 0,
            "synced_keys": 0,
            "skipped_keys": 0,
            "error_keys": 0,
            "models_synced": {},
        }
        self.sync_log = []

        # Get all keys for the model
        keys = self.get_model_keys(model_name)
        self.sync_stats["total_keys"] = len(keys)

        # Sync each key
        for key in keys:
            self.sync_key_to_db(key, force)

        # Calculate elapsed time
        elapsed_time = time.time() - start_time

        # Return stats
        return {
            "model": model_name,
            "stats": self.sync_stats,
            "elapsed_time": elapsed_time,
            "log": self.sync_log,
        }

    def sync_all_to_db(self, force: bool = False) -> Dict:
        """
        Synchronize all Redis keys to the database.

        Args:
            force: Whether to force sync even if the cache is older

        Returns:
            Dictionary with sync statistics
        """
        start_time = time.time()

        # Reset stats
        self.sync_stats = {
            "total_keys": 0,
            "synced_keys": 0,
            "skipped_keys": 0,
            "error_keys": 0,
            "models_synced": {},
        }
        self.sync_log = []

        # Get all keys
        if not CACHE_ENABLED or not redis_client:
            return {
                "error": "Redis cache is not enabled",
                "elapsed_time": 0,
            }

        try:
            # Get all keys (excluding system keys)
            all_keys = redis_client.keys("*")
            filtered_keys = []

            for key in all_keys:
                key_str = key.decode('utf-8')

                # Skip system keys and non-model keys
                if (
                    key_str.startswith("celery") or
                    key_str.startswith("_kombu") or
                    key_str.startswith("unacked") or
                    ":" not in key_str
                ):
                    continue

                filtered_keys.append(key_str)

            self.sync_stats["total_keys"] = len(filtered_keys)

            # Sync each key
            for key in filtered_keys:
                self.sync_key_to_db(key, force)

            # Calculate elapsed time
            elapsed_time = time.time() - start_time

            # Return stats
            return {
                "stats": self.sync_stats,
                "elapsed_time": elapsed_time,
                "log": self.sync_log,
            }
        except Exception as e:
            logger.exception(f"Error syncing all keys to DB: {str(e)}")
            return {
                "error": str(e),
                "elapsed_time": time.time() - start_time,
            }


# Create a singleton instance
cache_sync_manager = CacheSyncManager()


def reconcile_cache_for_model(model_class, force=False, batch_size=100, max_instances=1000):
    """
    Reconcile cache with database for a specific model.

    This function ensures that the cache is consistent with the database by:
    1. Checking for missing cache entries and creating them
    2. Checking for stale cache entries and updating them
    3. Checking for orphaned cache entries and removing them

    Args:
        model_class: Django model class
        force: Whether to force reconciliation even if timestamps suggest DB is older
        batch_size: Number of instances to process in each batch
        max_instances: Maximum number of instances to process

    Returns:
        Dictionary with reconciliation statistics
    """
    model_name = model_class.__name__.lower()
    logger.info(f"Starting cache reconciliation for {model_name}")

    stats = {
        "model": model_name,
        "total_instances": 0,
        "cached_instances": 0,
        "updated_instances": 0,
        "removed_instances": 0,
        "errors": 0,
        "elapsed_time": 0,
    }

    start_time = time.time()

    try:
        # Get all instances of the model
        instances = model_class.objects.all()[:max_instances]
        total_instances = len(instances)
        stats["total_instances"] = total_instances

        # Process in batches
        for i in range(0, total_instances, batch_size):
            batch = instances[i:i+batch_size]

            for instance in batch:
                try:
                    # Generate cache key
                    cache_key = f"{model_name}:{instance.pk}"

                    # Check if instance is in cache
                    cached_data = get_cached_data(cache_key)
                    if cached_data is None:
                        # Try permanent cache
                        from core.redis_permanent import get_permanent_cache
                        cached_data = get_permanent_cache(cache_key)

                    if cached_data is None:
                        # Instance not in cache, add it
                        if hasattr(instance, 'to_dict'):
                            # Use to_dict method if available
                            data = instance.to_dict()
                        else:
                            # Create dictionary from model fields
                            data = {}
                            for field in instance._meta.fields:
                                field_name = field.name
                                value = getattr(instance, field_name)

                                # Handle special field types
                                if isinstance(value, models.Model):
                                    data[field_name] = value.pk
                                elif hasattr(value, 'isoformat'):
                                    data[field_name] = value.isoformat()
                                else:
                                    data[field_name] = value

                        # Add timestamp if not present
                        if STANDARD_TIMESTAMP_FIELD not in data and hasattr(instance, STANDARD_TIMESTAMP_FIELD):
                            data[STANDARD_TIMESTAMP_FIELD] = getattr(instance, STANDARD_TIMESTAMP_FIELD).isoformat()

                        # Add version if not present
                        if 'version' not in data and hasattr(instance, 'version'):
                            data['version'] = getattr(instance, 'version')

                        # Cache the data
                        if hasattr(instance, 'redis_cache_permanent') and instance.redis_cache_permanent:
                            from core.redis_permanent import cache_permanently
                            cache_permanently(data, cache_key)
                        else:
                            # Get timeout from model if available
                            timeout = None
                            if hasattr(instance, 'redis_cache_timeout'):
                                timeout = instance.redis_cache_timeout

                            set_cached_data(cache_key, data, timeout)

                        stats["cached_instances"] += 1
                        logger.info(f"Added {model_name}:{instance.pk} to cache")
                    else:
                        # Instance in cache, check if it needs updating
                        needs_update = False

                        # Check version if available
                        if 'version' in cached_data and hasattr(instance, 'version'):
                            db_version = getattr(instance, 'version')
                            cache_version = cached_data['version']

                            if db_version > cache_version:
                                needs_update = True

                        # Check timestamp if available
                        if not needs_update:
                            timestamp_fields = ["last_updated", "updated_at", "timestamp", "modified_at", "created_at"]

                            cache_timestamp = None
                            db_timestamp = None

                            # Find timestamps in both cache and DB
                            for field in timestamp_fields:
                                if field in cached_data:
                                    try:
                                        if isinstance(cached_data[field], str):
                                            cache_timestamp = datetime.fromisoformat(cached_data[field])
                                        elif isinstance(cached_data[field], (int, float)):
                                            cache_timestamp = datetime.fromtimestamp(cached_data[field])
                                        break
                                    except (ValueError, TypeError):
                                        continue

                                if hasattr(instance, field):
                                    db_field_value = getattr(instance, field)
                                    if isinstance(db_field_value, datetime):
                                        db_timestamp = db_field_value
                                        break

                            # Compare timestamps if both are available
                            if cache_timestamp and db_timestamp:
                                # Allow a small tolerance (1 second) for timestamp comparison
                                if (db_timestamp - cache_timestamp).total_seconds() > 1:
                                    needs_update = True

                        if needs_update or force:
                            # Update cache with latest data from DB
                            if hasattr(instance, 'to_dict'):
                                # Use to_dict method if available
                                data = instance.to_dict()
                            else:
                                # Create dictionary from model fields
                                data = {}
                                for field in instance._meta.fields:
                                    field_name = field.name
                                    value = getattr(instance, field_name)

                                    # Handle special field types
                                    if isinstance(value, models.Model):
                                        data[field_name] = value.pk
                                    elif hasattr(value, 'isoformat'):
                                        data[field_name] = value.isoformat()
                                    else:
                                        data[field_name] = value

                            # Cache the data
                            if hasattr(instance, 'redis_cache_permanent') and instance.redis_cache_permanent:
                                from core.redis_permanent import cache_permanently
                                cache_permanently(data, cache_key)
                            else:
                                # Get timeout from model if available
                                timeout = None
                                if hasattr(instance, 'redis_cache_timeout'):
                                    timeout = instance.redis_cache_timeout

                                set_cached_data(cache_key, data, timeout)

                            stats["updated_instances"] += 1
                            logger.info(f"Updated {model_name}:{instance.pk} in cache")

                except Exception as e:
                    logger.exception(f"Error reconciling {model_name}:{instance.pk}: {str(e)}")
                    stats["errors"] += 1

            # Sleep between batches to reduce load
            if i + batch_size < total_instances:
                time.sleep(0.1)

        # Check for orphaned cache entries
        try:
            # Get all keys for the model
            all_keys = cache_sync_manager.get_model_keys(model_name)

            # Get all instance IDs
            instance_ids = set(str(instance.pk) for instance in instances)

            # Find orphaned keys
            orphaned_keys = []
            for key in all_keys:
                # Extract ID from key
                parts = key.split(":")
                if len(parts) >= 2:
                    key_id = parts[1]
                    if key_id not in instance_ids:
                        orphaned_keys.append(key)

            # Remove orphaned keys
            for key in orphaned_keys:
                delete_cached_data(key)
                stats["removed_instances"] += 1
                logger.info(f"Removed orphaned cache entry: {key}")

        except Exception as e:
            logger.exception(f"Error checking for orphaned cache entries: {str(e)}")
            stats["errors"] += 1

    except Exception as e:
        logger.exception(f"Error reconciling cache for {model_name}: {str(e)}")
        stats["errors"] += 1

    # Calculate elapsed time
    stats["elapsed_time"] = time.time() - start_time

    logger.info(f"Completed cache reconciliation for {model_name}: "
                f"{stats['cached_instances']} cached, {stats['updated_instances']} updated, "
                f"{stats['removed_instances']} removed, {stats['errors']} errors "
                f"in {stats['elapsed_time']:.2f} seconds")

    return stats


def reconcile_all_caches(force=False, batch_size=100, max_instances=1000):
    """
    Reconcile cache with database for all models.

    Args:
        force: Whether to force reconciliation even if timestamps suggest DB is older
        batch_size: Number of instances to process in each batch
        max_instances: Maximum number of instances to process per model

    Returns:
        Dictionary with reconciliation statistics
    """
    logger.info("Starting cache reconciliation for all models")

    stats = {
        "models": {},
        "total_models": 0,
        "total_instances": 0,
        "cached_instances": 0,
        "updated_instances": 0,
        "removed_instances": 0,
        "errors": 0,
        "elapsed_time": 0,
    }

    start_time = time.time()

    # Get all models that use Redis caching
    cacheable_models = []

    # Check for models with RedisCachedModelMixin
    for app_config in apps.get_app_configs():
        for model in app_config.get_models():
            # Check if model has Redis caching mixins
            if (hasattr(model, 'cache_enabled') or
                hasattr(model, 'redis_cache_prefix') or
                hasattr(model, 'redis_cache_timeout')):
                cacheable_models.append(model)

    stats["total_models"] = len(cacheable_models)

    # Reconcile each model
    for model in cacheable_models:
        model_stats = reconcile_cache_for_model(
            model, force=force, batch_size=batch_size, max_instances=max_instances
        )

        # Add to overall stats
        stats["models"][model.__name__] = model_stats
        stats["total_instances"] += model_stats["total_instances"]
        stats["cached_instances"] += model_stats["cached_instances"]
        stats["updated_instances"] += model_stats["updated_instances"]
        stats["removed_instances"] += model_stats["removed_instances"]
        stats["errors"] += model_stats["errors"]

    # Calculate elapsed time
    stats["elapsed_time"] = time.time() - start_time

    logger.info(f"Completed cache reconciliation for all models: "
                f"{stats['total_models']} models, {stats['total_instances']} instances, "
                f"{stats['cached_instances']} cached, {stats['updated_instances']} updated, "
                f"{stats['removed_instances']} removed, {stats['errors']} errors "
                f"in {stats['elapsed_time']:.2f} seconds")

    return stats

"""
Redis-based pub/sub messaging utilities.

This module provides utilities for publishing and subscribing to messages
using Redis pub/sub, which is useful for real-time notifications and events.
"""

import json
import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, Union

import redis
from django.conf import settings

from core.cache import publish_notification

logger = logging.getLogger(__name__)

# Redis connection settings
REDIS_HOST = getattr(settings, "REDIS_HOST", "localhost")
REDIS_PORT = getattr(settings, "REDIS_PORT", 6379)
REDIS_PASSWORD = getattr(settings, "REDIS_PASSWORD", None)


class RedisPubSub:
    """
    Redis pub/sub messaging.
    
    This class provides methods for publishing and subscribing to messages
    using Redis pub/sub.
    """
    
    def __init__(self):
        """Initialize Redis pub/sub."""
        self.redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            decode_responses=True,
        )
        self.pubsub = self.redis_client.pubsub()
        self.subscribers: Dict[str, List[Callable]] = {}
        self.listener_thread = None
        self.running = False
        
    def publish(self, channel: str, message: Dict[str, Any]) -> bool:
        """
        Publish a message to a channel.
        
        Args:
            channel: Channel to publish to
            message: Message to publish
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Add timestamp if not provided
            if "timestamp" not in message:
                message["timestamp"] = datetime.now().isoformat()
                
            # Serialize message
            serialized_message = json.dumps(message)
            
            # Publish message
            self.redis_client.publish(channel, serialized_message)
            
            return True
        except Exception as e:
            logger.error(f"Error publishing message to channel {channel}: {str(e)}")
            return False
            
    def subscribe(self, channel: str, callback: Callable) -> bool:
        """
        Subscribe to a channel.
        
        Args:
            channel: Channel to subscribe to
            callback: Callback function to call when a message is received
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Subscribe to channel
            self.pubsub.subscribe(channel)
            
            # Add callback to subscribers
            if channel not in self.subscribers:
                self.subscribers[channel] = []
            self.subscribers[channel].append(callback)
            
            # Start listener thread if not already running
            if not self.running:
                self._start_listener()
                
            return True
        except Exception as e:
            logger.error(f"Error subscribing to channel {channel}: {str(e)}")
            return False
            
    def unsubscribe(self, channel: str, callback: Optional[Callable] = None) -> bool:
        """
        Unsubscribe from a channel.
        
        Args:
            channel: Channel to unsubscribe from
            callback: Callback function to remove (if None, remove all callbacks)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Remove callback from subscribers
            if channel in self.subscribers:
                if callback is None:
                    # Remove all callbacks
                    self.subscribers[channel] = []
                else:
                    # Remove specific callback
                    self.subscribers[channel] = [
                        cb for cb in self.subscribers[channel] if cb != callback
                    ]
                    
                # Unsubscribe from channel if no more callbacks
                if not self.subscribers[channel]:
                    self.pubsub.unsubscribe(channel)
                    del self.subscribers[channel]
                    
            # Stop listener thread if no more subscribers
            if not self.subscribers and self.running:
                self._stop_listener()
                
            return True
        except Exception as e:
            logger.error(f"Error unsubscribing from channel {channel}: {str(e)}")
            return False
            
    def _start_listener(self) -> None:
        """Start the listener thread."""
        self.running = True
        self.listener_thread = threading.Thread(target=self._listen)
        self.listener_thread.daemon = True
        self.listener_thread.start()
        
    def _stop_listener(self) -> None:
        """Stop the listener thread."""
        self.running = False
        if self.listener_thread:
            self.listener_thread.join(timeout=1.0)
            self.listener_thread = None
            
    def _listen(self) -> None:
        """Listen for messages."""
        while self.running:
            try:
                # Get message
                message = self.pubsub.get_message(timeout=0.1)
                
                if message and message["type"] == "message":
                    # Get channel and data
                    channel = message["channel"]
                    data = message["data"]
                    
                    # Parse data
                    try:
                        parsed_data = json.loads(data)
                    except json.JSONDecodeError:
                        parsed_data = data
                        
                    # Call callbacks
                    if channel in self.subscribers:
                        for callback in self.subscribers[channel]:
                            try:
                                callback(channel, parsed_data)
                            except Exception as e:
                                logger.error(f"Error in callback for channel {channel}: {str(e)}")
            except Exception as e:
                logger.error(f"Error in listener thread: {str(e)}")
                time.sleep(1.0)  # Avoid tight loop on error
                
    def close(self) -> None:
        """Close the pub/sub connection."""
        self._stop_listener()
        self.pubsub.close()
        self.redis_client.close()


# Singleton instance
_pubsub_instance = None


def get_pubsub() -> RedisPubSub:
    """
    Get the singleton pub/sub instance.
    
    Returns:
        RedisPubSub instance
    """
    global _pubsub_instance
    if _pubsub_instance is None:
        _pubsub_instance = RedisPubSub()
    return _pubsub_instance


def publish_message(channel: str, message: Dict[str, Any]) -> bool:
    """
    Publish a message to a channel.
    
    Args:
        channel: Channel to publish to
        message: Message to publish
        
    Returns:
        True if successful, False otherwise
    """
    return get_pubsub().publish(channel, message)


def subscribe_to_channel(channel: str, callback: Callable) -> bool:
    """
    Subscribe to a channel.
    
    Args:
        channel: Channel to subscribe to
        callback: Callback function to call when a message is received
        
    Returns:
        True if successful, False otherwise
    """
    return get_pubsub().subscribe(channel, callback)


def unsubscribe_from_channel(channel: str, callback: Optional[Callable] = None) -> bool:
    """
    Unsubscribe from a channel.
    
    Args:
        channel: Channel to unsubscribe from
        callback: Callback function to remove (if None, remove all callbacks)
        
    Returns:
        True if successful, False otherwise
    """
    return get_pubsub().unsubscribe(channel, callback)


def close_pubsub() -> None:
    """Close the pub/sub connection."""
    global _pubsub_instance
    if _pubsub_instance is not None:
        _pubsub_instance.close()
        _pubsub_instance = None

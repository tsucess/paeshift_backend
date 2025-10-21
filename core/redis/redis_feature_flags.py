"""
Redis-based feature flag utilities.

This module provides utilities for managing feature flags using Redis,
which is useful for enabling or disabling features without deploying code.
"""

import json
import logging
import random
from typing import Any, Dict, List, Optional, Set, Union

from core.redis.redis_config import RedisConfig

logger = logging.getLogger(__name__)

# Constants
FEATURE_FLAGS_NAMESPACE = "feature_flags"


class FeatureFlags:
    """
    Redis-based feature flags.

    This class provides methods for managing feature flags using Redis.
    """

    def __init__(self, namespace: str = FEATURE_FLAGS_NAMESPACE):
        """
        Initialize feature flags.

        Args:
            namespace: Feature flags namespace
        """
        self.config = RedisConfig(namespace)

    def enable(self, feature: str) -> bool:
        """
        Enable a feature.

        Args:
            feature: Feature name

        Returns:
            True if successful, False otherwise
        """
        return self.config.set(feature, True)

    def disable(self, feature: str) -> bool:
        """
        Disable a feature.

        Args:
            feature: Feature name

        Returns:
            True if successful, False otherwise
        """
        return self.config.set(feature, False)

    def is_enabled(self, feature: str, default: bool = False) -> bool:
        """
        Check if a feature is enabled.

        Args:
            feature: Feature name
            default: Default value if not found

        Returns:
            True if enabled, False otherwise
        """
        return bool(self.config.get(feature, default))

    def set_percentage(self, feature: str, percentage: float) -> bool:
        """
        Set a percentage rollout for a feature.

        Args:
            feature: Feature name
            percentage: Percentage of users to enable (0-100)

        Returns:
            True if successful, False otherwise
        """
        # Validate percentage
        if percentage < 0 or percentage > 100:
            logger.error(f"Invalid percentage for feature {feature}: {percentage}")
            return False

        # Set percentage
        return self.config.set(f"{feature}:percentage", percentage)

    def is_enabled_for_user(self, feature: str, user_id: str, default: bool = False) -> bool:
        """
        Check if a feature is enabled for a specific user.

        Args:
            feature: Feature name
            user_id: User ID
            default: Default value if not found

        Returns:
            True if enabled for the user, False otherwise
        """
        # Check if feature is enabled globally
        if self.is_enabled(feature):
            return True

        # Check if feature has a percentage rollout
        percentage = self.config.get(f"{feature}:percentage")
        if percentage is not None:
            # Convert to float
            try:
                percentage = float(percentage)
            except (ValueError, TypeError):
                logger.error(f"Invalid percentage for feature {feature}: {percentage}")
                return default

            # Check if user is in the rollout
            if percentage >= 100:
                return True
            elif percentage <= 0:
                return False
            else:
                # Use user ID to determine if in rollout
                # This ensures the same user always gets the same result
                user_hash = hash(user_id) % 100
                return user_hash < percentage

        # Check if user is in the allowlist
        allowlist = self.config.get(f"{feature}:allowlist", [])
        if allowlist and user_id in allowlist:
            return True

        # Check if user is in the denylist
        denylist = self.config.get(f"{feature}:denylist", [])
        if denylist and user_id in denylist:
            return False

        # Return default
        return default

    def add_to_allowlist(self, feature: str, user_id: str) -> bool:
        """
        Add a user to the feature allowlist.

        Args:
            feature: Feature name
            user_id: User ID

        Returns:
            True if successful, False otherwise
        """
        # Get current allowlist
        allowlist = self.config.get(f"{feature}:allowlist", [])

        # Add user to allowlist if not already in it
        if user_id not in allowlist:
            allowlist.append(user_id)

            # Save allowlist
            return self.config.set(f"{feature}:allowlist", allowlist)

        return True

    def remove_from_allowlist(self, feature: str, user_id: str) -> bool:
        """
        Remove a user from the feature allowlist.

        Args:
            feature: Feature name
            user_id: User ID

        Returns:
            True if successful, False otherwise
        """
        # Get current allowlist
        allowlist = self.config.get(f"{feature}:allowlist", [])

        # Remove user from allowlist if in it
        if user_id in allowlist:
            allowlist.remove(user_id)

            # Save allowlist
            return self.config.set(f"{feature}:allowlist", allowlist)

        return True

    def add_to_denylist(self, feature: str, user_id: str) -> bool:
        """
        Add a user to the feature denylist.

        Args:
            feature: Feature name
            user_id: User ID

        Returns:
            True if successful, False otherwise
        """
        # Get current denylist
        denylist = self.config.get(f"{feature}:denylist", [])

        # Add user to denylist if not already in it
        if user_id not in denylist:
            denylist.append(user_id)

            # Save denylist
            return self.config.set(f"{feature}:denylist", denylist)

        return True

    def remove_from_denylist(self, feature: str, user_id: str) -> bool:
        """
        Remove a user from the feature denylist.

        Args:
            feature: Feature name
            user_id: User ID

        Returns:
            True if successful, False otherwise
        """
        # Get current denylist
        denylist = self.config.get(f"{feature}:denylist", [])

        # Remove user from denylist if in it
        if user_id in denylist:
            denylist.remove(user_id)

            # Save denylist
            return self.config.set(f"{feature}:denylist", denylist)

        return True

    def get_all_features(self) -> Dict[str, Any]:
        """
        Get all feature flags.

        Returns:
            Dictionary of feature flags
        """
        # Get all config values
        all_config = self.config.get_all()

        # Filter out metadata
        features = {}
        for key, value in all_config.items():
            if ":" not in key:
                features[key] = value

        return features


def get_feature_flags() -> FeatureFlags:
    """
    Get feature flags.

    Returns:
        FeatureFlags instance
    """
    return FeatureFlags()


def is_feature_enabled(feature: str, default: bool = False) -> bool:
    """
    Check if a feature is enabled.

    Args:
        feature: Feature name
        default: Default value if not found

    Returns:
        True if enabled, False otherwise
    """
    feature_flags = get_feature_flags()
    return feature_flags.is_enabled(feature, default)


def is_feature_enabled_for_user(feature: str, user_id: str, default: bool = False) -> bool:
    """
    Check if a feature is enabled for a specific user.

    Args:
        feature: Feature name
        user_id: User ID
        default: Default value if not found

    Returns:
        True if enabled for the user, False otherwise
    """
    feature_flags = get_feature_flags()
    return feature_flags.is_enabled_for_user(feature, user_id, default)


def enable_feature(feature: str) -> bool:
    """
    Enable a feature.

    Args:
        feature: Feature name

    Returns:
        True if successful, False otherwise
    """
    feature_flags = get_feature_flags()
    return feature_flags.enable(feature)


def disable_feature(feature: str) -> bool:
    """
    Disable a feature.

    Args:
        feature: Feature name

    Returns:
        True if successful, False otherwise
    """
    feature_flags = get_feature_flags()
    return feature_flags.disable(feature)

import json

from django.conf import settings
from django.core.cache import cache
from django.core.serializers.json import DjangoJSONEncoder


class GamificationCache:
    """Handles caching for gamification-related data."""

    @staticmethod
    def _get_redis():
        """Get Redis connection."""
        return cache.client.get_client()

    @staticmethod
    def _serialize(data):
        """Serialize data for Redis storage."""
        return json.dumps(data, cls=DjangoJSONEncoder)

    @staticmethod
    def _deserialize(data):
        """Deserialize data from Redis storage."""
        return json.loads(data) if data else None

    @staticmethod
    def cache_achievement(achievement_id, data):
        """Cache an achievement."""
        redis = GamificationCache._get_redis()
        key = f"achievement:{achievement_id}"
        redis.set(key, GamificationCache._serialize(data))
        redis.expire(key, 3600)  # Cache for 1 hour

    @staticmethod
    def get_achievement(achievement_id):
        """Get a cached achievement."""
        redis = GamificationCache._get_redis()
        key = f"achievement:{achievement_id}"
        data = redis.get(key)
        return GamificationCache._deserialize(data)

    @staticmethod
    def cache_badge(badge_id, data):
        """Cache a badge."""
        redis = GamificationCache._get_redis()
        key = f"badge:{badge_id}"
        redis.set(key, GamificationCache._serialize(data))
        redis.expire(key, 3600)  # Cache for 1 hour

    @staticmethod
    def get_badge(badge_id):
        """Get a cached badge."""
        redis = GamificationCache._get_redis()
        key = f"badge:{badge_id}"
        data = redis.get(key)
        return GamificationCache._deserialize(data)

    @staticmethod
    def clear_pattern(pattern):
        """Clear all keys matching a pattern."""
        redis = GamificationCache._get_redis()
        keys = redis.keys(pattern)
        if keys:
            redis.delete(*keys)

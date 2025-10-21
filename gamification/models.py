import uuid
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Badge(models.Model):
    class BadgeTier(models.TextChoices):
        BRONZE = "bronze", _("Bronze")
        SILVER = "silver", _("Silver")
        GOLD = "gold", _("Gold")
        PLATINUM = "platinum", _("Platinum")
        DIAMOND = "diamond", _("Diamond")

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField()
    tier = models.CharField(
        max_length=10, choices=BadgeTier.choices, default=BadgeTier.BRONZE
    )
    image = models.CharField(max_length=255, blank=True, null=True)
    points = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_secret = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    display_order = models.PositiveIntegerField(default=0)
    share_message = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["tier", "display_order", "name"]
        verbose_name = _("Badge")
        verbose_name_plural = _("Badges")

    def __str__(self):
        return f"{self.get_tier_display()} - {self.name}"


class LevelConfig(models.Model):
    level = models.PositiveIntegerField(unique=True)
    xp_required = models.PositiveIntegerField()
    badge_reward = models.ForeignKey(
        Badge, null=True, blank=True, on_delete=models.SET_NULL
    )
    point_reward = models.PositiveIntegerField(default=0)
    celebration_animation = models.CharField(max_length=100, blank=True, null=True)
    dashboard_color = models.CharField(max_length=7, default="#4CAF50")

    class Meta:
        ordering = ["level"]
        verbose_name = _("Level Configuration")
        verbose_name_plural = _("Level Configurations")

    def __str__(self):
        return f"Level {self.level}"


class Achievement(models.Model):
    class AchievementType(models.TextChoices):
        JOB_COUNT = "jobs", _("Job Count")
        EARNINGS = "earnings", _("Earnings")
        REFERRALS = "referrals", _("Referrals")
        STREAK = "streak", _("Streak")
        LEVEL = "level", _("Level")
        COMPLETION = "completion", _("Completion")
        CLIENT = "client", _("Client Specific")
        REGIONAL = "regional", _("Regional")
        HOLIDAY = "holiday", _("Holiday Special")

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField()
    achievement_type = models.CharField(
        max_length=20,
        choices=AchievementType.choices,
        default=AchievementType.JOB_COUNT,
    )
    criteria = models.JSONField()
    points = models.PositiveIntegerField()
    badge = models.ForeignKey(Badge, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_secret = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    animation = models.CharField(max_length=100, blank=True, null=True)
    is_client_specific = models.BooleanField(default=False)
    is_nigeria_specific = models.BooleanField(default=False)
    region = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Achievement")
        verbose_name_plural = _("Achievements")
        indexes = [
            models.Index(fields=["achievement_type"]),
            models.Index(fields=["is_client_specific"]),
            models.Index(fields=["is_nigeria_specific"]),
        ]

    def __str__(self):
        return self.name


class UserPoints(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="gamification_points",
    )
    total_points = models.PositiveIntegerField(default=0)
    level = models.PositiveIntegerField(default=1)
    xp_to_next = models.PositiveIntegerField(default=100)
    last_updated = models.DateTimeField(auto_now=True)
    streak_days = models.PositiveIntegerField(default=0)
    last_streak_update = models.DateField(auto_now_add=True)
    share_code = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    last_level_up = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("User Points")
        verbose_name_plural = _("User Points")
        indexes = [
            models.Index(fields=["total_points"]),
            models.Index(fields=["level"]),
        ]

    def add_xp(self, amount):
        self.total_points += amount

        level_before = self.level
        while self.total_points >= self.xp_to_next:
            self.total_points -= self.xp_to_next
            self.level += 1

            level_config = LevelConfig.objects.filter(level=self.level).first()
            if level_config:
                self.xp_to_next = level_config.xp_required
                if level_config.point_reward > 0:
                    self.total_points += level_config.point_reward
            else:
                self.xp_to_next = int(self.xp_to_next * 1.2)

        if self.level > level_before:
            self.last_level_up = timezone.now()
            cache.set(f"user_{self.user_id}_levelup", True, 300)

        self.save()

    def get_share_url(self):
        return f"{settings.FRONTEND_URL}/profile/{self.share_code}/"

    def __str__(self):
        return f"{self.user.username} - Lvl {self.level}"


class UserAchievement(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="gamify_achievements",
    )
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE)
    unlocked_at = models.DateTimeField(default=timezone.now)
    progress = models.JSONField(default=dict)

    class Meta:
        unique_together = ("user", "achievement")
        verbose_name = _("User Achievement")
        verbose_name_plural = _("User Achievements")

    def __str__(self):
        return f"{self.user.username} - {self.achievement.name}"


class RewardItem(models.Model):
    """
    Enhanced reward system with inventory management
    """

    class RewardType(models.TextChoices):
        PHYSICAL = "physical", _("Physical")
        DIGITAL = "digital", _("Digital")
        SERVICE = "service", _("Service")
        DISCOUNT = "discount", _("Discount")

    name = models.CharField(max_length=100)
    description = models.TextField()
    cost = models.PositiveIntegerField()
    reward_type = models.CharField(
        max_length=10, choices=RewardType.choices, default=RewardType.DIGITAL
    )
    stock = models.PositiveIntegerField(default=0)  # 0 = unlimited
    image = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_available = models.BooleanField(default=True)  # For backward compatibility
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Reward Item")
        verbose_name_plural = _("Reward Items")

    @property
    def is_available(self):
        """Check if reward is currently available"""
        now = timezone.now()
        available = self.is_active

        if self.start_date and self.start_date > now:
            available = False
        if self.end_date and self.end_date < now:
            available = False
        if self.stock == 0:
            available = False

        return available

    def __str__(self):
        return f"{self.name} ({self.get_reward_type_display()})"


class Team(models.Model):
    """
    Teams for collaborative achievements
    """

    name = models.CharField(max_length=100)
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="gamify_teams"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    invite_code = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    description = models.TextField(blank=True, null=True)
    logo = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = _("Team")
        verbose_name_plural = _("Teams")

    def __str__(self):
        return self.name


class TeamAchievement(models.Model):
    """
    Achievements unlocked by teams
    """

    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name="achievements"
    )
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE)
    unlocked_at = models.DateTimeField(default=timezone.now)
    progress = models.JSONField(default=dict)

    class Meta:
        unique_together = ("team", "achievement")
        verbose_name = _("Team Achievement")
        verbose_name_plural = _("Team Achievements")

    def __str__(self):
        return f"{self.team.name} - {self.achievement.name}"


class UserActivity(models.Model):
    """
    Track user activities for analytics and engagement
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="activities"
    )
    activity_type = models.CharField(max_length=50)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    points_earned = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "activity_type"]),
            models.Index(fields=["created_at"]),
        ]
        verbose_name = _("User Activity")
        verbose_name_plural = _("User Activities")

    def __str__(self):
        return f"{self.user.username} - {self.activity_type}"


class Leaderboard(models.Model):
    """
    Enhanced leaderboard system with different time periods and categories
    """

    class LeaderboardType(models.TextChoices):
        WEEKLY = "weekly", _("Weekly")
        MONTHLY = "monthly", _("Monthly")
        REGIONAL = "regional", _("Regional")
        INDUSTRY = "industry", _("Industry")
        ALL_TIME = "all_time", _("All Time")

    leaderboard_type = models.CharField(
        max_length=10, choices=LeaderboardType.choices, default=LeaderboardType.WEEKLY
    )
    region = models.CharField(max_length=50, blank=True, null=True)
    industry = models.CharField(max_length=50, blank=True, null=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-end_date"]
        verbose_name = _("Leaderboard")
        verbose_name_plural = _("Leaderboards")
        indexes = [
            models.Index(fields=["leaderboard_type"]),
            models.Index(fields=["region"]),
            models.Index(fields=["industry"]),
        ]

    @classmethod
    def get_current(cls, leaderboard_type="weekly", region=None, industry=None):
        now = timezone.now()
        return cls.objects.filter(
            leaderboard_type=leaderboard_type,
            region=region,
            industry=industry,
            start_date__lte=now,
            end_date__gte=now,
        ).first()

    def __str__(self):
        return f"{self.get_leaderboard_type_display()} Leaderboard"


class SocialShare(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="social_shares"
    )
    achievement = models.ForeignKey(
        Achievement, on_delete=models.CASCADE, null=True, blank=True
    )
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, null=True, blank=True)
    platform = models.CharField(max_length=20)
    shared_at = models.DateTimeField(auto_now_add=True)
    points_earned = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = _("Social Share")
        verbose_name_plural = _("Social Shares")

    def __str__(self):
        return f"{self.user.username} shared on {self.platform}"


class UserReward(models.Model):
    """
    Track rewards redeemed by users with status
    """

    class RewardStatus(models.TextChoices):
        REDEEMED = "redeemed", _("Redeemed")
        PROCESSING = "processing", _("Processing")
        DELIVERED = "delivered", _("Delivered")
        CANCELLED = "cancelled", _("Cancelled")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="rewards_redeemed",
    )
    reward = models.ForeignKey(RewardItem, on_delete=models.CASCADE)
    redeemed_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(
        max_length=10, choices=RewardStatus.choices, default=RewardStatus.REDEEMED
    )
    transaction_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-redeemed_at"]
        verbose_name = _("User Reward")
        verbose_name_plural = _("User Rewards")

    def __str__(self):
        return f"{self.user.username} - {self.reward.name} ({self.status})"

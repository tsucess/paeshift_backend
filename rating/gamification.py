from decimal import Decimal

from django.core.cache import cache
from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone

from accounts.models import CustomUser as User
from accounts.models import Profile

from gamification.models import *

# most jobs in days
# maintaining rate
# referrals
# give away from number of jobs completed
# online presence


class AchievementChecker:
    @staticmethod
    def check_job_count(user, criteria):
        """Check job completion achievements with caching"""
        cache_key = f"user_{user.id}_job_count"
        completed_jobs = cache.get(cache_key)

        if completed_jobs is None:
            completed_jobs = Application.objects.filter(
                applicant=user, status=Application.Status.ACCEPTED, is_shown_up=True
            ).count()
            cache.set(cache_key, completed_jobs, 3600)  # Cache for 1 hour

        return completed_jobs >= criteria["required_count"]

    @staticmethod
    def check_earnings(user, criteria):
        """Check earnings achievements with caching"""
        cache_key = f"user_{user.id}_earnings"
        total_earnings = cache.get(cache_key)

        if total_earnings is None:
            total_earnings = Application.objects.filter(
                applicant=user, status=Application.Status.ACCEPTED, is_shown_up=True
            ).aggregate(total=Sum("job__rate"))["total"] or Decimal("0")
            cache.set(cache_key, total_earnings, 3600)

        return total_earnings >= Decimal(str(criteria["required_amount"]))

    @staticmethod
    def check_rating(user, criteria):
        """Check rating achievements with caching"""
        cache_key = f"user_{user.id}_rating"
        avg_rating = cache.get(cache_key)

        if avg_rating is None:
            avg_rating = (
                Review.objects.filter(reviewed=user).aggregate(avg=Avg("rating"))["avg"]
                or 0
            )
            cache.set(cache_key, avg_rating, 3600)

        return avg_rating >= criteria["required_rating"]

    @staticmethod
    def check_referrals(user, criteria):
        """Check referral achievements with caching"""
        cache_key = f"user_{user.id}_referrals"
        referral_count = cache.get(cache_key)

        if referral_count is None:
            referral_count = user.referrals.count()
            cache.set(cache_key, referral_count, 3600)

        return referral_count >= criteria["required_count"]

    @staticmethod
    def check_streak(user, criteria):
        """Check streak achievements"""
        # Implementation for streak tracking
        return False


class BadgeChecker:
    @staticmethod
    def check_job_completion(user, criteria):
        """Check job completion badges with caching"""
        cache_key = f"user_{user.id}_job_stats"
        job_stats = cache.get(cache_key)

        if job_stats is None:
            job_stats = Application.objects.filter(
                applicant=user, status=Application.Status.ACCEPTED
            ).aggregate(
                total=Count("id"),
                success_rate=Count("id", filter=Q(is_shown_up=True))
                * 100.0
                / Count("id"),
            )
            cache.set(cache_key, job_stats, 3600)

        return job_stats["total"] >= criteria.get("required_jobs", 0) and job_stats[
            "success_rate"
        ] >= criteria.get("required_success_rate", 0)

    @staticmethod
    def check_rating_badge(user, criteria):
        """Check rating badges with caching"""
        cache_key = f"user_{user.id}_rating_stats"
        rating_stats = cache.get(cache_key)

        if rating_stats is None:
            reviews = Review.objects.filter(reviewed=user)
            rating_stats = {
                "avg_rating": reviews.aggregate(avg=Avg("rating"))["avg"] or 0,
                "review_count": reviews.count(),
            }
            cache.set(cache_key, rating_stats, 3600)

        return rating_stats["avg_rating"] >= criteria.get(
            "required_rating", 0
        ) and rating_stats["review_count"] >= criteria.get("required_reviews", 0)

    @staticmethod
    def check_premium_badge(user, criteria):
        """Check premium status badges with caching"""
        cache_key = f"user_{user.id}_premium_status"
        is_premium = cache.get(cache_key)

        if is_premium is None:
            # Check if user has premium subscription
            is_premium = False

            # Check if user role is premium in profile
            try:
                profile = Profile.objects.get(user=user)
                is_premium = (
                    getattr(profile, "is_premium", False) or profile.role == "premium"
                )
            except Profile.DoesNotExist:
                pass

            # Check for premium subscription model if it exists
            if hasattr(user, "premium_subscription"):
                is_premium = is_premium or (
                    user.premium_subscription.is_active
                    if hasattr(user.premium_subscription, "is_active")
                    else False
                )

            cache.set(cache_key, is_premium, 3600)  # Cache for 1 hour

        return is_premium

    @staticmethod
    def check_safety_badge(user, criteria):
        """Check safety metrics badges with caching"""
        cache_key = f"user_{user.id}_safety_metrics"
        safety_metrics = cache.get(cache_key)

        if safety_metrics is None:
            # Get all completed jobs
            completed_jobs = Application.objects.filter(
                applicant=user, status=Application.Status.ACCEPTED, is_shown_up=True
            ).count()

            # Calculate safety score (placeholder - implement your actual safety metrics)
            # This could be based on check-ins, reviews, reported issues, etc.
            safety_score = 100  # Perfect score to start with

            safety_metrics = {
                "completed_jobs": completed_jobs,
                "safety_score": safety_score,
            }

            cache.set(cache_key, safety_metrics, 3600)

        return safety_metrics["completed_jobs"] >= criteria.get(
            "required_jobs", 0
        ) and safety_metrics["safety_score"] >= criteria.get("required_safety_score", 0)

    @staticmethod
    def check_client_jobs(user, criteria):
        """Check client job posting badges with caching"""
        cache_key = f"user_{user.id}_client_jobs"
        job_stats = cache.get(cache_key)

        if job_stats is None:
            posted_jobs = Job.objects.filter(client=user)
            completed_jobs = posted_jobs.filter(status=Job.Status.COMPLETED)

            total_jobs = posted_jobs.count()
            completed_count = completed_jobs.count()
            completion_rate = (
                (completed_count / total_jobs * 100) if total_jobs > 0 else 0
            )

            job_stats = {
                "total_jobs": total_jobs,
                "completed_jobs": completed_count,
                "completion_rate": completion_rate,
            }

            cache.set(cache_key, job_stats, 3600)  # Cache for 1 hour

        return job_stats["total_jobs"] >= criteria.get(
            "required_jobs", 0
        ) and job_stats["completion_rate"] >= criteria.get(
            "required_completion_rate", 0
        )

    @staticmethod
    def check_client_pay(user, criteria):
        """Check if client pays above average rates with caching"""
        cache_key = f"user_{user.id}_client_pay"
        pay_stats = cache.get(cache_key)

        if pay_stats is None:
            # Get client's jobs
            client_jobs = Job.objects.filter(client=user)

            # Calculate client's average pay rate
            client_avg_rate = (
                client_jobs.aggregate(avg_rate=Avg("rate"))["avg_rate"] or 0
            )

            # Get market average for those job categories
            industry_ids = client_jobs.values_list("industry_id", flat=True).distinct()
            market_avg_rate = (
                Job.objects.filter(industry_id__in=industry_ids)
                .exclude(client=user)
                .aggregate(avg_rate=Avg("rate"))["avg_rate"]
                or 1
            )  # Avoid division by zero

            # Calculate pay percentage compared to market
            pay_percentage = (
                (client_avg_rate / market_avg_rate * 100) if market_avg_rate > 0 else 0
            )

            pay_stats = {
                "avg_rate": client_avg_rate,
                "market_avg": market_avg_rate,
                "pay_percentage": pay_percentage,
            }

            cache.set(cache_key, pay_stats, 3600)  # Cache for 1 hour

        return pay_stats["pay_percentage"] >= criteria.get("required_pay_percentage", 0)

    @staticmethod
    def check_client_payment_speed(user, criteria):
        """Check how quickly client releases payments after job completion"""
        cache_key = f"user_{user.id}_payment_speed"
        speed_stats = cache.get(cache_key)

        if speed_stats is None:
            # This is a placeholder implementation since payment release timing might be tracked differently
            # Actual implementation would depend on how payment release is tracked in the system

            # For example:
            # from django.db.models import F, ExpressionWrapper, fields
            # from django.db.models.functions import Extract

            # payment_releases = PaymentRelease.objects.filter(
            #     job__client=user,
            #     job__status=Job.Status.COMPLETED
            # ).annotate(
            #     release_hours=ExpressionWrapper(
            #         Extract(F('released_at') - F('job__actual_shift_end'), 'epoch') / 3600,
            #         output_field=fields.FloatField()
            #     )
            # )

            # fast_releases = payment_releases.filter(
            #     release_hours__lte=criteria.get('required_speed_hours', 24)
            # ).count()

            # Placeholder implementation:
            fast_releases = 0
            total_releases = 0

            speed_stats = {
                "fast_releases": fast_releases,
                "total_releases": total_releases,
            }

            cache.set(cache_key, speed_stats, 3600)  # Cache for 1 hour

        return speed_stats["total_releases"] >= criteria.get(
            "required_jobs", 0
        ) and speed_stats["fast_releases"] >= criteria.get("required_jobs", 0)

    @staticmethod
    def check_client_rating(user, criteria):
        """Check client rating from workers"""
        cache_key = f"user_{user.id}_client_rating"
        rating_stats = cache.get(cache_key)

        if rating_stats is None:
            reviews = Review.objects.filter(reviewed=user)
            avg_rating = reviews.aggregate(avg=Avg("rating"))["avg"] or 0
            review_count = reviews.count()

            rating_stats = {"avg_rating": avg_rating, "review_count": review_count}

            cache.set(cache_key, rating_stats, 3600)  # Cache for 1 hour

        return rating_stats["avg_rating"] >= criteria.get(
            "required_rating", 0
        ) and rating_stats["review_count"] >= criteria.get("required_reviews", 0)

    @staticmethod
    def check_client_diversity(user, criteria):
        """Check if client creates jobs in diverse categories"""
        cache_key = f"user_{user.id}_job_diversity"
        diversity_stats = cache.get(cache_key)

        if diversity_stats is None:
            # Count distinct industries/subcategories client has posted jobs in
            distinct_industries = (
                Job.objects.filter(client=user).values("industry").distinct().count()
            )
            distinct_subcategories = (
                Job.objects.filter(client=user).values("subcategory").distinct().count()
            )

            diversity_stats = {
                "distinct_industries": distinct_industries,
                "distinct_subcategories": distinct_subcategories,
            }

            cache.set(cache_key, diversity_stats, 3600)  # Cache for 1 hour

        # Use either industries or subcategories, whichever is higher
        categories_count = max(
            diversity_stats["distinct_industries"],
            diversity_stats["distinct_subcategories"],
        )

        return categories_count >= criteria.get("required_categories", 0)

    @staticmethod
    def check_client_community(user, criteria):
        """Check if client creates jobs in underserved regions"""
        # This is a placeholder implementation - actual implementation would depend on
        # how you define and track underserved regions in your system

        cache_key = f"user_{user.id}_community_jobs"
        community_stats = cache.get(cache_key)

        if community_stats is None:
            # For example, this could be defined as regions with fewer job postings
            # You would need to define what regions are underserved in your system

            # Placeholder implementation - assume all jobs are in served regions
            underserved_job_count = 0

            community_stats = {"underserved_job_count": underserved_job_count}

            cache.set(cache_key, community_stats, 3600)  # Cache for 1 hour

        return community_stats["underserved_job_count"] >= criteria.get(
            "required_jobs", 0
        )


def check_and_award_achievements(user):
    """Check and award any new achievements for a user"""
    achievements = Achievement.objects.filter(is_active=True)
    new_achievements = []

    user_points, _ = UserPoints.objects.get_or_create(
        user=user,
        defaults={"total_points": 0, "current_level": 1, "points_to_next_level": 100},
    )

    for achievement in achievements:
        # Skip if already earned
        if UserAchievement.objects.filter(user=user, achievement=achievement).exists():
            continue

        checker = getattr(
            AchievementChecker, f"check_{achievement.achievement_type}", None
        )
        if checker and checker(user, achievement.criteria):
            user_achievement = UserAchievement.objects.create(
                user=user, achievement=achievement, unlocked_at=timezone.now()
            )
            user_points.add_points(achievement.points)
            new_achievements.append(user_achievement)

    return new_achievements


def check_and_award_badges(user):
    """Check and award any new badges for a user"""
    badges = Badge.objects.filter(is_active=True)
    new_badges = []

    user_points, _ = UserPoints.objects.get_or_create(
        user=user,
        defaults={"total_points": 0, "current_level": 1, "points_to_next_level": 100},
    )

    profile, _ = Profile.objects.get_or_create(user=user)

    for badge in badges:
        # Skip if already earned
        if badge.id in profile.badges:
            continue

        checker = getattr(BadgeChecker, f"check_{badge.badge_type}", None)
        if checker and checker(user, badge.criteria):
            profile.badges.append(badge.id)
            user_points.add_points(badge.points)
            new_badges.append(badge)

    if new_badges:
        profile.save()

    return new_badges


def clear_user_gamification_cache(user_id):
    """Clear all cached gamification data for a user"""
    cache_keys = [
        f"user_{user_id}_job_count",
        f"user_{user_id}_earnings",
        f"user_{user_id}_rating",
        f"user_{user_id}_referrals",
        f"user_{user_id}_job_stats",
        f"user_{user_id}_rating_stats",
    ]
    cache.delete_many(cache_keys)

# gamification/utils.py
from datetime import timedelta

from django.contrib.auth.decorators import login_required
# views.py
from django.shortcuts import render
from django.utils.timezone import now

from .models import Achievement, Badge, LeaderboardEntry, UserProfile


@login_required
def profile_badges_view(request):
    achievements = Achievement.objects.filter(user=request.user)
    return render(
        request, "gamification/profile_badges.html", {"achievements": achievements}
    )


@login_required
def leaderboard_view(request):
    from datetime import date, timedelta

    start_of_week = date.today() - timedelta(days=date.today().weekday())
    leaderboard = LeaderboardEntry.objects.filter(week=start_of_week).order_by(
        "-points"
    )[:10]
    return render(
        request, "gamification/leaderboard.html", {"leaderboard": leaderboard}
    )


@login_required
def dashboard_progress_view(request):
    profile = UserProfile.objects.get(user=request.user)
    return render(
        request,
        "dashboard/progress_bar.html",
        {"level": profile.level, "progress": profile.progress_percentage()},
    )


def award_badge(user, badge_name):
    badge = Badge.objects.get(name=badge_name)
    if not Achievement.objects.filter(user=user, badge=badge).exists():
        Achievement.objects.create(user=user, badge=badge)
        return True
    return False


def check_and_award_job_post_badges(client):
    job_count = client.jobs_posted.count()
    if job_count >= 5:
        award_badge(client.user, "Consistent Employer")
    if client.average_rating >= 4.5:
        award_badge(client.user, "Top Employer")


def add_experience(user, points):
    profile = UserProfile.objects.get(user=user)
    profile.experience += points
    while profile.experience >= profile.level * 100:
        profile.experience -= profile.level * 100
        profile.level += 1
    profile.save()


# Import for gamification functionality
from typing import Optional

from ninja import Router
from ninja.security import django_auth

# Router for gamification endpoints
router = Router()


# TODO: Implement gamification engine and endpoints when the gamification system is ready

# class GamificationEngine:
#     def award_xp(self, user, amount, source=None):
#         """Award XP to a user and handle level progression"""
#         pass

# #  ENDPOINTS
# @router.get("/points", response=dict, auth=django_auth)
# def get_user_points(request):
#     """Get current user's points and level information"""
#     pass

# @router.post("/award-xp/{amount}", response=dict, auth=django_auth)
# def award_xp(request, amount: int, source: Optional[str] = None):
#     """Award XP to the current user"""
#     pass

# @router.get("/achievements", auth=django_auth)
# def list_achievements(request, unlocked: bool = None):
#     """List all achievements (filter by unlocked status)"""
#     pass

# @router.get("/achievements/unlock/{achievement_id}", auth=django_auth)
# def unlock_achievement(request, achievement_id: int):
#     """Manually unlock an achievement (admin only)"""
#     pass

# @router.get("/badges", auth=django_auth)
# def list_badges(request, earned: bool = None):
#     """List all badges (filter by earned status)"""
#     pass

# TODO: Implement rewards functionality when the gamification system is ready

# @router.get("/rewards", response=List[RewardItemSchema], auth=django_auth)
# def list_rewards(request):
#     """List all available rewards"""
#     pass

# @router.post("/rewards/redeem/{reward_id}", auth=django_auth)
# def redeem_reward(request, reward_id: int):
#     """Redeem a reward using points"""
#     pass

# TODO: Implement leaderboard functionality when the gamification system is ready

# @router.get("/leaderboard", response=dict)
# def get_leaderboard(
#     request,
#     type: str = "weekly",
#     region: Optional[str] = None,
#     industry: Optional[str] = None
# ):
#     """Get leaderboard by type (weekly/monthly/regional/industry)"""
#     pass

# TODO: Implement the following gamification endpoints when the gamification system is ready

# @router.get("/client-achievements", response=List[AchievementSchema], auth=django_auth)
# def check_client_achievements(request):
#     """Check and unlock client-specific achievements"""
#     pass

# @router.get("/nigeria-achievements", response=List[AchievementSchema], auth=django_auth)
# def check_nigeria_achievements(request):
#     """Check and unlock Nigeria-specific achievements"""
#     pass

# @router.post("/social/share", auth=django_auth)
# def share_achievement(request, data: SocialShareRequest):
#     """Share an achievement or badge on social media"""
#     pass

# @router.get("/teams", response=List[TeamSchema], auth=django_auth)
# def list_teams(request):
#     """List all teams the user belongs to"""
#     pass

# @router.post("/teams/create", response=TeamSchema, auth=django_auth)
# def create_team(request, name: str):
#     """Create a new team"""
#     pass

# @router.post("/teams/join/{invite_code}", response=TeamSchema, auth=django_auth)
# def join_team(request, invite_code: str):
#     """Join a team using invite code"""
#     pass

# @router.get("/teams/achievements/{team_id}", response=List[AchievementSchema], auth=django_auth)
# def get_team_achievements(request, team_id: int):
#     """Get achievements unlocked by a team"""
#     pass

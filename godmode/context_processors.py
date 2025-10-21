from .models import UserRanking


def godmode_context(request):
    """
    Context processor for God Mode templates.
    """
    return {
        "dict_ranking_types": dict(UserRanking.RANKING_TYPE_CHOICES),
    }

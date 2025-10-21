# from django.shortcuts import render

# # Create your views here.
# def get_user_credit_score(user):
#     jobs = user.jobs_completed
#     rating = user.average_rating
#     earnings = user.total_earnings
#     return 300 + 3 * jobs + 100 * rating + 0.001 * earnings

# def suggest_jobs_for_user(user):
#     score = get_user_credit_score(user)
#     if score < 2000:
#         return Job.objects.filter(tier=1)
#     elif score < 5000:
#         return Job.objects.filter(tier__in=[1, 2])
#     return Job.objects.all()


# if credit_score < 2000:
#     show = Job.objects.filter(tier=1)
# elif credit_score < 5000:
#     show = Job.objects.filter(tier__in=[1, 2])
# else:
#     show = Job.objects.all()
# credit_score = 300 + 3.0 * jobs_completed + 100 * rating + 0.001 * earnings
# credit_score = 300 + 3*15 + 100*4.2 + 0.001*300000
#               = 300 + 45 + 420 + 300
#               = 1,065

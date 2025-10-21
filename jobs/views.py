from django.shortcuts import render

from .models import Job


def jobs(request):
    jobs = Job.objects.all()
    return render(request, "job.html", {"jobs": jobs})

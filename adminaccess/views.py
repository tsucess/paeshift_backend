from django.views import View
from django.http import HttpResponse

class AdminAccessView(View):
    def get(self, request):
        return HttpResponse("Admin Access Home")

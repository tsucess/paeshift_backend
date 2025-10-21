from django.urls import path
from .views import AdminAccessView

urlpatterns = [
    path('', AdminAccessView.as_view(), name='adminaccess-home'),
]

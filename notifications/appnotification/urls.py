from django.urls import path
from .views import *
app_name = 'appnotification'

urlpatterns = [
    path("all/", getAllNotifications, name="All Notifications"),
    path("view/<int:notification_id>/", viewNotification, name="View Notification"),
]

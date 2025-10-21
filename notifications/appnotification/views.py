from django.http.response import JsonResponse
from notifications.models import Notification  # Use the main Notification model
from django.shortcuts import render, redirect
from django.forms.models import model_to_dict
import json
import requests
# Create your views here.


def getAllNotifications(request):
    notifications = list(Notification.objects.filter(user=request.user))
    notifications.sort(key=lambda x: x.created_at, reverse=True)
    data = {'notifications': [], 'unread_notifications': 0}
    for notification in notifications:
        notif_dict = model_to_dict(notification)
        notif_dict['viewed'] = not notification.is_read  # for compatibility
        notif_dict['time'] = notification.created_at     # for compatibility
        notif_dict['navigate_url'] = notification.navigate_url
        data['notifications'].append(json.dumps(notif_dict))
        if not notif_dict['viewed']:
            data['unread_notifications'] += 1
    return JsonResponse(data)


def createNotification(user, title, message, navigate_url):
    notification = Notification(
        user=user, title=title, message=message, is_read=False, navigate_url=navigate_url)
    notification.save()
    if hasattr(user, 'profile') and getattr(user.profile, 'fcm_token', None):
        token = user.profile.fcm_token
        url = "https://fcm.googleapis.com/fcm/send"
        body = {
            "notification": {
                "title": title,
                "body": message,
                "click_action": "https://app.rfm360.io/"+navigate_url,
                "icon": "https://app.rfm360.io/static/images/newrfm.jpeg"
            },
            "to": token
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": "key=AAAAQogK98M:APA91bHb7xSSuTK2ekESyrjImR5pFX5Qh6KraTsmPgbcnA3tdJfelG5XprLl3Jr2LC7YWlQQyf0VCwFOliHy-dQbysXprRuyyPu3R2MGnDgNasSbhgXjcf41TpIHpXyELXQhjQ3wTjn_"
        }
        data=requests.post(url, data=json.dumps(body), headers=headers)
        print(data.json())

def viewNotification(request, notification_id):
    try:
        notification = Notification.objects.get(id=notification_id)
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return JsonResponse({"url": notification.navigate_url})
    except Exception:
        return JsonResponse({"error": "Something went wrong!!!"})

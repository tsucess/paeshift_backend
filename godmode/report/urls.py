
from rest_framework import routers
from django.urls import path, include, re_path
from .views import *
from django.urls import re_path as url
app_name = 'report'

urlpatterns = [
    path('', Report_Main, name='report'),
    path('datareport', data_report),
    path('taskreport', task_report),
    path('incomereport', income_report),
    path('expensereport', expense_report),
    path('leadsreport', leads_report),
    path('dealsreport', deals_report),
    path('integrations', integrations),
    path('emailreport', email_report)
]

from rest_framework import routers
from django.urls import path, include, re_path
from .views import *
from django.urls import re_path as url
app_name = 'report'

urlpatterns = [
    path('', Report_Main, name='report'),
    path('datareport', data_report),
    path('taskreport', task_report),
    path('incomereport', income_report),
    path('expensereport', expense_report),
    path('leadsreport', leads_report),
    path('dealsreport', deals_report),
    path('integrations', integrations),
    path('emailreport', email_report)
]


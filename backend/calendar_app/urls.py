# calendar_app/urls.py
from django.urls import path
from .views import CompanyEventListAPI

app_name = 'calendar'

urlpatterns = [
    path('api/events/', CompanyEventListAPI.as_view(), name='events_api'),
]

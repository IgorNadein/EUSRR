from django.urls import path
from . import views, test_views

app_name = 'notifications'

urlpatterns = [
    path('', views.notification_list, name='list'),
    path('settings/', views.notification_settings, name='settings'),
    path('test/create/', test_views.create_test_notification, name='test_create'),
]

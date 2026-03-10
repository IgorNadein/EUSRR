"""
URL routing для модуля notifications.

Включает:
- API endpoints (из notifications.api.urls)
- Service Worker для Web Push уведомлений
"""
from django.urls import path, include
from notifications.api.urls import urlpatterns as api_urlpatterns, app_name
from . import views

# Публичные URLs приложения (Service Worker должен быть в корне)
urlpatterns = [
    # Service Worker для Web Push уведомлений
    path('sw.js', views.serve_service_worker, name='notifications_sw'),
    
    # API endpoints
    path('api/', include((api_urlpatterns, app_name))),
]

__all__ = ['urlpatterns', 'app_name']

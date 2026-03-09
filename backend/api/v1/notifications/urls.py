"""
URL routing для API v2 уведомлений.

DEPRECATED: Этот файл оставлен для обратной совместимости.
Используйте notifications.api.urls напрямую.

Новая архитектура: verb-based notifications с channel preferences.
"""
# Импортируем из самого модуля notifications для обратной совместимости
from notifications.api.urls import urlpatterns, app_name  # noqa

# app_name = 'notifications_api_v1' - уже импортирован
    path('push/unsubscribe/', views.unsubscribe_push, name='push_unsubscribe'),
]

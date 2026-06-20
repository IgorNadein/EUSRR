"""
URL routing для API v2 уведомлений.

Новая архитектура: verb-based notifications с channel preferences.
"""

from django.urls import path
from . import views

app_name = "notifications_api_v1"

urlpatterns = [
    # Список и счетчики
    path("", views.get_notifications, name="list"),
    path("count/", views.get_unread_count, name="count"),
    path("summary/", views.get_unread_summary_view, name="summary"),
    path("verb-types/", views.get_verb_types, name="verb_types"),
    # Операции с уведомлениями
    path("<int:notification_id>/read/", views.mark_as_read, name="mark_read"),
    path(
        "<int:notification_id>/unread/",
        views.mark_as_unread,
        name="mark_unread",
    ),
    path("<int:notification_id>/", views.delete_notification, name="delete"),
    # Массовые операции
    path("read-all/", views.mark_all_as_read, name="mark_all_read"),
    path(
        "category/read/", views.mark_category_as_read, name="mark_category_read"
    ),
    path("delete-all-read/", views.delete_all_read, name="delete_all_read"),
    # Настройки каналов
    path("preferences/", views.channel_preferences, name="preferences"),
    # Web Push интеграция
    path("push/vapid-key/", views.get_vapid_public_key, name="vapid_key"),
    path("push/subscribe/", views.subscribe_push, name="push_subscribe"),
    path("push/unsubscribe/", views.unsubscribe_push, name="push_unsubscribe"),
]

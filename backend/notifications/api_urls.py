"""
DEPRECATED: Этот файл устарел и будет удалён в следующей версии.

Используйте вместо него: api.v1.notifications.urls

URL routing перенесён в api/v1/notifications/urls.py
Новые пути: /api/v1/notifications/* вместо /api/v1/notifications/*

Миграция: 9 января 2026
"""
from django.urls import path
from . import api_views

app_name = 'notifications_api'

urlpatterns = [
    path('notifications/', api_views.get_notifications, name='list'),
    path('notifications/count/', api_views.get_unread_count, name='count'),
    path(
        'notifications/<int:notification_id>/read/',
        api_views.mark_as_read,
        name='mark_read'
    ),
    path(
        'notifications/read-all/',
        api_views.mark_all_as_read,
        name='mark_all_read'
    ),
    path(
        'notifications/<int:notification_id>/',
        api_views.delete_notification,
        name='delete'
    ),
    path('notifications/categories/', api_views.get_categories, name='categories'),
    path('notifications/settings/', api_views.get_user_settings, name='settings_get'),
    path(
        'notifications/settings/update/',
        api_views.update_user_settings,
        name='settings_update'
    ),
    path(
        'notifications/settings/category/update/',
        api_views.update_category_settings,
        name='category_settings_update'
    ),
    # Telegram integration
    path(
        'notifications/telegram/status/',
        api_views.get_telegram_link_status,
        name='telegram_status'
    ),
    path(
        'notifications/telegram/generate-code/',
        api_views.generate_telegram_link_code,
        name='telegram_generate_code'
    ),
    path(
        'notifications/telegram/unlink/',
        api_views.unlink_telegram,
        name='telegram_unlink'
    ),
    # Web Push integration
    path(
        'notifications/push/vapid-key/',
        api_views.get_vapid_public_key,
        name='push_vapid_key'
    ),
    path(
        'notifications/push/subscribe/',
        api_views.subscribe_push,
        name='push_subscribe'
    ),
    path(
        'notifications/push/unsubscribe/',
        api_views.unsubscribe_push,
        name='push_unsubscribe'
    ),
    path(
        'notifications/push/subscriptions/',
        api_views.get_push_subscriptions,
        name='push_subscriptions'
    ),
]
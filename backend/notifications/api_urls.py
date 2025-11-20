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
]

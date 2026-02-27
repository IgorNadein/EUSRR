"""
URL routing для API v1 уведомлений.
"""
from django.urls import path
from . import views

app_name = 'notifications_api_v1'

urlpatterns = [
    # CRUD уведомлений
    path('', views.get_notifications, name='list'),
    path('count/', views.get_unread_count, name='count'),
    path('<int:notification_id>/read/', views.mark_as_read, name='mark_read'),
    path('read-all/', views.mark_all_as_read, name='mark_all_read'),
    path('<int:notification_id>/', views.delete_notification, name='delete'),
    
    # Категории
    path('categories/', views.get_categories, name='categories'),
    
    # Настройки
    path('settings/', views.get_user_settings, name='settings_get'),
    path('settings/update/', views.update_user_settings, name='settings_update'),
    path('settings/category/update/', views.update_category_settings, name='category_settings_update'),
    
    # Telegram интеграция
    path('telegram/status/', views.get_telegram_link_status, name='telegram_status'),
    path('telegram/generate-code/', views.generate_telegram_link_code, name='telegram_generate_code'),
    path('telegram/unlink/', views.unlink_telegram, name='telegram_unlink'),
    
    # Web Push интеграция
    path('push/vapid-key/', views.get_vapid_public_key, name='push_vapid_key'),
    path('push/subscribe/', views.subscribe_push, name='push_subscribe'),
    path('push/unsubscribe/', views.unsubscribe_push, name='push_unsubscribe'),
    path('push/subscriptions/', views.get_push_subscriptions, name='push_subscriptions'),
]

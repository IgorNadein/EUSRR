"""
Обработчики каналов доставки уведомлений

Слушают post_save сигнал от Notification и отправляют по каналам:
- WebSocket (realtime)
- Email  
- Web Push
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
import logging

from .senders import (
    EmailNotificationSender,
    WebSocketNotificationSender,
    PushNotificationSender,
)

logger = logging.getLogger(__name__)


@receiver(post_save, sender='notifications.Notification')
def handle_notification_channels(sender, instance, created, **kwargs):
    """
    Главный роутер уведомлений по каналам
    Вызывается при создании нового уведомления
    """
    if not created:
        return  # Обрабатываем только новые уведомления
    
    notification = instance
    user = notification.recipient
    
    # Получаем настройки пользователя
    try:
        prefs = user.channel_preferences
    except Exception:
        # Если настроек нет - создаем с дефолтными значениями
        from .models_new import UserChannelPreferences
        prefs = UserChannelPreferences.objects.create(user=user)
    
    # Проверяем, не отключен ли этот тип уведомлений
    if not prefs.is_verb_enabled(notification.verb):
        logger.debug(f'Notification verb "{notification.verb}" disabled for user {user.id}')
        return
    
    # Проверяем режим "Не беспокоить"
    if prefs.is_in_dnd_period():
        logger.debug(f'User {user.id} is in DND period, skipping non-web channels')
        # В DND режиме отправляем только веб (без звука)
        if prefs.web_enabled:
            send_websocket_notification(notification, silent=True)
        return
    
    # Отправляем по каналам согласно настройкам
    
    if prefs.web_enabled:
        sender = WebSocketNotificationSender()
        sender.send(notification, silent=prefs.is_in_dnd_period())
    
    if prefs.email_enabled and prefs.email_frequency == 'instant':
        sender = EmailNotificationSender()
        sender.send(notification)
    
    if prefs.push_enabled:
        sender = PushNotificationSender()
        sender.send(notification)


def send_websocket_notification(notification, silent=False):
    """
    Отправка через WebSocket (realtime)
    
    Args:
        notification: Объект Notification
        silent: Если True, уведомление без звука/визуальных эффектов
    
    DEPRECATED: Используйте WebSocketNotificationSender().send()
    """
    sender = WebSocketNotificationSender()
    return sender.send(notification, silent=silent)


def send_email_notification(notification):
    """
    Отправка email уведомления
    
    Args:
        notification: Объект Notification
    
    DEPRECATED: Используйте EmailNotificationSender().send()
    """
    sender = EmailNotificationSender()
    return sender.send(notification)


def send_push_notification(notification):
    """
    Отправка Web Push уведомления
    
    Args:
        notification: Объект Notification
    
    DEPRECATED: Используйте PushNotificationSender().send()
    """
    sender = PushNotificationSender()
    return sender.send(notification)


# === Digest Email (для email_frequency = daily/weekly) ===

def send_email_digest(user, frequency='daily'):
    """
    Отправка дайджеста уведомлений
    
    Args:
        user: User объект
        frequency: 'daily' или 'weekly'
    """
    try:
        from datetime import timedelta
        from django.utils import timezone
        from .models_new import Notification
        
        # Определяем период
        if frequency == 'daily':
            since = timezone.now() - timedelta(days=1)
        elif frequency == 'weekly':
            since = timezone.now() - timedelta(weeks=1)
        else:
            raise ValueError(f'Invalid frequency: {frequency}')
        
        # Получаем неотправленные уведомления
        notifications = Notification.objects.filter(
            recipient=user,
            timestamp__gte=since,
            emailed=False,
            deleted=False,
        ).order_by('-timestamp')
        
        if not notifications.exists():
            logger.debug(f'No notifications to digest for user {user.id}')
            return
        
        # Используем EmailNotificationSender для отправки дайджеста
        sender = EmailNotificationSender()
        success = sender.send_digest(user, notifications, frequency)
        
        if success:
            logger.info(
                f'Email digest ({frequency}) sent to {user.email} '
                f'with {notifications.count()} notifications'
            )
        
    except Exception as e:
        logger.error(f'Failed to send email digest: {e}', exc_info=True)

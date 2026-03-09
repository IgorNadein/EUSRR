"""
Обработчики каналов доставки уведомлений

Слушают post_save сигнал от Notification и асинхронно отправляют через Celery:
- WebSocket (realtime) - мгновенно
- Email - с retry и rate limiting  
- Web Push - с автоматическим удалением неактивных устройств
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender='notifications.Notification')
def route_notification_to_channels(sender, instance, created, **kwargs):
    """
    Главный роутер уведомлений по каналам.
    Вызывается при создании нового уведомления.
    
    Асинхронно отправляет в Celery очередь для каждого канала.
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
        from .models import UserChannelPreferences
        prefs = UserChannelPreferences.objects.create(user=user)
    
    # Проверяем, не отключен ли этот тип уведомлений
    if not prefs.is_verb_enabled(notification.verb):
        logger.debug(f'Notification verb "{notification.verb}" disabled for user {user.id}')
        return
    
    # Импортируем задачи
    from .tasks import (
        send_websocket_notification,
        send_email_notification,
        send_push_notification,
    )
    
    # Проверяем режим "Не беспокоить"
    is_dnd = prefs.is_in_dnd_period()
    
    if is_dnd:
        logger.debug(f'User {user.id} is in DND period, only web notifications (silent)')
        # В DND режиме только WebSocket без звука
        if prefs.web_enabled:
            send_websocket_notification.delay(notification.id, silent=True)
        return
    
    # Отправляем по каналам асинхронно через Celery
    
    if prefs.web_enabled:
        send_websocket_notification.delay(notification.id, silent=False)
    
    if prefs.email_enabled and prefs.email_frequency == 'instant':
        send_email_notification.delay(notification.id)
    
    if prefs.push_enabled:
        send_push_notification.delay(notification.id)
    
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
        from .models import Notification
        
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

"""
Обработчики каналов доставки уведомлений

Слушают post_save сигнал от Notification и отправляют по каналам:
- WebSocket (realtime)
- Email  
- Web Push
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging

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
        send_websocket_notification(notification)
    
    if prefs.email_enabled and prefs.email_frequency == 'instant':
        send_email_notification(notification)
    
    if prefs.push_enabled:
        send_push_notification(notification)


def send_websocket_notification(notification, silent=False):
    """
    Отправка через WebSocket (realtime)
    
    Args:
        notification: Объект Notification
        silent: Если True, уведомление без звука/визуальных эффектов
    """
    try:
        channel_layer = get_channel_layer()
        user_channel = f"user_{notification.recipient.id}"
        
        # Формируем данные для фронтенда
        message_data = {
            'type': 'notification',
            'id': notification.id,
            'verb': notification.verb,
            'description': notification.description,
            'action_url': notification.action_url,
            'timestamp': notification.timestamp.isoformat(),
            'unread': notification.unread,
            'silent': silent,
            'data': notification.data,
        }
        
        # Добавляем actor если есть
        if notification.actor:
            message_data['actor'] = {
                'type': notification.actor_content_type.model,
                'id': notification.actor_object_id,
                'str': str(notification.actor),
            }
        
        # Добавляем target если есть
        if notification.target:
            message_data['target'] = {
                'type': notification.target_content_type.model,
                'id': notification.target_object_id,
                'str': str(notification.target),
            }
        
        # Отправляем через Channels
        async_to_sync(channel_layer.group_send)(
            user_channel,
            {
                'type': 'notification_message',
                'message': message_data
            }
        )
        
        logger.info(f'WebSocket notification sent to user {notification.recipient.id}')
        
    except Exception as e:
        logger.error(f'Failed to send WebSocket notification: {e}', exc_info=True)


def send_email_notification(notification):
    """
    Отправка email уведомления
    
    Args:
        notification: Объект Notification
    """
    try:
        from common.emails import send_email
        
        user = notification.recipient
        
        # Формируем email
        subject = f'Уведомление: {notification.verb}'
        
        context = {
            'notification': notification,
            'user': user,
            'action_url': notification.action_url,
            'site_url': settings.SITE_URL if hasattr(settings, 'SITE_URL') else 'http://localhost:8000',
        }
        
        # Используем общий шаблон или специфичный для verb
        template_name = f'notifications/email/{notification.verb}.html'
        fallback_template = 'notifications/email/default.html'
        
        send_email(
            subject=subject,
            template_name=template_name,
            fallback_template=fallback_template,
            context=context,
            recipient_list=[user.email],
        )
        
        # Отмечаем что отправлено
        notification.emailed = True
        notification.save(update_fields=['emailed'])
        
        logger.info(f'Email notification sent to {user.email}')
        
    except Exception as e:
        logger.error(f'Failed to send email notification: {e}', exc_info=True)


def send_push_notification(notification):
    """
    Отправка Web Push уведомления
    
    Args:
        notification: Объект Notification
    """
    try:
        from push_notifications.models import WebPushDevice
        from .web_push_models import WebPushSubscription
        
        user = notification.recipient
        
        # Получаем активные подписки
        subscriptions = WebPushSubscription.objects.filter(
            user=user,
            is_active=True
        )
        
        if not subscriptions.exists():
            logger.debug(f'User {user.id} has no active push subscriptions')
            return
        
        # Формируем данные для push
        actor_str = str(notification.actor) if notification.actor else 'Система'
        title = f'{actor_str} {notification.verb}'
        body = notification.description or ''
        
        push_data = {
            'head': title,
            'body': body,
            'icon': '/static/img/logo.png',
            'url': notification.action_url or '/',
            'tag': f'notification-{notification.id}',
            'requireInteraction': False,
        }
        
        # Отправляем через django-push-notifications
        for sub in subscriptions:
            try:
                # Используем push_notifications для отправки
                # (предполагается что WebPushSubscription связана с WebPushDevice)
                device = WebPushDevice.objects.filter(
                    registration_id=sub.endpoint
                ).first()
                
                if device:
                    device.send_message(
                        message=push_data,
                        extra={
                            'notification_id': notification.id
                        }
                    )
                    logger.info(f'Push notification sent to device {device.id}')
                    
            except Exception as e:
                logger.error(f'Failed to send push to subscription {sub.id}: {e}')
        
    except Exception as e:
        logger.error(f'Failed to send push notification: {e}', exc_info=True)


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
        from common.emails import send_email
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
        
        # Формируем email
        subject = f'Дайджест уведомлений за {"день" if frequency == "daily" else "неделю"}'
        
        context = {
            'user': user,
            'notifications': notifications,
            'count': notifications.count(),
            'site_url': settings.SITE_URL if hasattr(settings, 'SITE_URL') else 'http://localhost:8000',
        }
        
        send_email(
            subject=subject,
            template_name='notifications/email/digest.html',
            context=context,
            recipient_list=[user.email],
        )
        
        # Отмечаем как отправленные
        notifications.update(emailed=True)
        
        logger.info(f'Email digest ({frequency}) sent to {user.email} with {notifications.count()} notifications')
        
    except Exception as e:
        logger.error(f'Failed to send email digest: {e}', exc_info=True)

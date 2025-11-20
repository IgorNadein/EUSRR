"""
Сервисный слой для работы с уведомлениями
"""
import json
from typing import Any, Dict, Optional
from django.contrib.auth import get_user_model
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import (
    Notification,
    NotificationType,
    UserNotificationSettings,
)

User = get_user_model()


class NotificationService:
    """Сервис для создания и отправки уведомлений"""

    @staticmethod
    def create_notification(
        recipient: User,
        notification_type_code: str,
        title: str,
        message: str,
        content_object=None,
        action_url: str = '',
        action_text: str = 'Посмотреть',
        metadata: Optional[Dict[str, Any]] = None,
        send_immediately: bool = True,
    ) -> Optional[Notification]:
        """
        Создать и отправить уведомление

        Args:
            recipient: Получатель уведомления
            notification_type_code: Код типа уведомления
            title: Заголовок
            message: Текст сообщения
            content_object: Связанный объект (опционально)
            action_url: URL для действия
            action_text: Текст кнопки действия
            metadata: Дополнительные данные
            send_immediately: Отправить сразу или отложить

        Returns:
            Созданное уведомление или None если тип не найден
        """
        try:
            notification_type = NotificationType.objects.get(
                code=notification_type_code,
                is_active=True
            )
        except NotificationType.DoesNotExist:
            return None

        # Проверить настройки пользователя
        settings = NotificationService.get_user_settings(
            recipient, notification_type
        )

        if not settings.is_enabled:
            return None

        # Создать краткое сообщение
        short_message = message[:150] if len(message) > 150 else message

        # Создать уведомление
        notification = Notification.objects.create(
            recipient=recipient,
            notification_type=notification_type,
            title=title,
            message=message,
            short_message=short_message,
            content_object=content_object,
            action_url=action_url,
            action_text=action_text,
            metadata=metadata or {},
        )

        # Отправить если нужно
        if send_immediately:
            NotificationService.send_notification(notification, settings)

        return notification

    @staticmethod
    def send_notification(
        notification: Notification,
        settings: Optional[UserNotificationSettings] = None
    ):
        """Отправить уведомление по всем каналам"""
        if settings is None:
            settings = NotificationService.get_user_settings(
                notification.recipient,
                notification.notification_type
            )

        # Отправить на веб (WebSocket)
        if settings.send_web:
            NotificationService.send_web_notification(notification)
            notification.sent_web = True

        # Отправить на email (будет реализовано позже)
        if settings.send_email:
            # TODO: Реализовать email отправку
            notification.sent_email = False

        # Отправить в Telegram (будет реализовано позже)
        if settings.send_telegram:
            # TODO: Реализовать Telegram отправку
            notification.sent_telegram = False

        # Обновить время отправки
        notification.sent_at = timezone.now()
        notification.save(update_fields=[
            'sent_web',
            'sent_email',
            'sent_telegram',
            'sent_whatsapp',
            'sent_wechat',
            'sent_at'
        ])

    @staticmethod
    def send_web_notification(notification: Notification):
        """Отправить уведомление через WebSocket"""
        channel_layer = get_channel_layer()
        notification_data = {
            'id': notification.id,
            'title': notification.title,
            'message': notification.short_message,
            'category': notification.notification_type.category.code,
            'category_name': notification.notification_type.category.name,
            'icon': notification.notification_type.category.icon,
            'color': notification.notification_type.category.color,
            'priority': notification.notification_type.priority,
            'action_url': notification.action_url,
            'action_text': notification.action_text,
            'created_at': notification.created_at.isoformat(),
        }

        async_to_sync(channel_layer.group_send)(
            f'notifications_{notification.recipient.id}',
            {
                'type': 'notification_new',
                'notification': notification_data
            }
        )

        # Обновить счетчик
        unread_count = Notification.objects.filter(
            recipient=notification.recipient,
            is_read=False,
            is_archived=False
        ).count()

        async_to_sync(channel_layer.group_send)(
            f'notifications_{notification.recipient.id}',
            {
                'type': 'notification_count_update',
                'count': unread_count
            }
        )

    @staticmethod
    def get_user_settings(
        user: User,
        notification_type: NotificationType
    ) -> UserNotificationSettings:
        """Получить или создать настройки пользователя"""
        settings, created = UserNotificationSettings.objects.get_or_create(
            user=user,
            notification_type=notification_type,
            defaults={
                'is_enabled': notification_type.default_enabled,
                'send_web': notification_type.default_channels.get(
                    'web', True
                ),
                'send_email': notification_type.default_channels.get(
                    'email', False
                ),
                'send_telegram': notification_type.default_channels.get(
                    'telegram', False
                ),
                'send_whatsapp': notification_type.default_channels.get(
                    'whatsapp', False
                ),
                'send_wechat': notification_type.default_channels.get(
                    'wechat', False
                ),
            }
        )
        return settings

    @staticmethod
    def mark_as_read(notification_id: int, user: User) -> bool:
        """Отметить уведомление как прочитанное"""
        try:
            notification = Notification.objects.get(
                id=notification_id,
                recipient=user
            )
            notification.mark_as_read()

            # Обновить счетчик через WebSocket
            channel_layer = get_channel_layer()
            unread_count = Notification.objects.filter(
                recipient=user,
                is_read=False,
                is_archived=False
            ).count()

            async_to_sync(channel_layer.group_send)(
                f'notifications_{user.id}',
                {
                    'type': 'notification_count_update',
                    'count': unread_count
                }
            )

            return True
        except Notification.DoesNotExist:
            return False

    @staticmethod
    def mark_all_as_read(user: User, category: Optional[str] = None) -> int:
        """Отметить все уведомления как прочитанные"""
        queryset = Notification.objects.filter(
            recipient=user,
            is_read=False
        )

        if category:
            queryset = queryset.filter(
                notification_type__category__code=category
            )

        count = queryset.update(
            is_read=True,
            read_at=timezone.now()
        )

        # Обновить счетчик
        channel_layer = get_channel_layer()
        unread_count = Notification.objects.filter(
            recipient=user,
            is_read=False,
            is_archived=False
        ).count()

        async_to_sync(channel_layer.group_send)(
            f'notifications_{user.id}',
            {
                'type': 'notification_count_update',
                'count': unread_count
            }
        )

        return count

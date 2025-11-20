import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model

User = get_user_model()
logger = logging.getLogger(__name__)


class NotificationConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer для уведомлений в реальном времени"""

    async def connect(self):
        """Подключение к WebSocket"""
        self.user = self.scope['user']

        if self.user.is_anonymous:
            await self.close()
            return

        # Добавить в группу уведомлений пользователя
        self.notification_group_name = f'notifications_{self.user.id}'
        await self.channel_layer.group_add(
            self.notification_group_name,
            self.channel_name
        )

        await self.accept()
        
        logger.info(f'NotificationConsumer connected: user={self.user.id}, group={self.notification_group_name}')

        # Отправить текущее количество непрочитанных
        unread_count = await self.get_unread_count()
        await self.send(text_data=json.dumps({
            'type': 'unread_count',
            'count': unread_count
        }))

    async def disconnect(self, close_code):
        """Отключение от WebSocket"""
        if hasattr(self, 'notification_group_name'):
            await self.channel_layer.group_discard(
                self.notification_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        """Получение сообщения от клиента"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')

            if message_type == 'mark_read':
                notification_id = data.get('notification_id')
                if notification_id:
                    await self.mark_notification_as_read(notification_id)

            elif message_type == 'mark_all_read':
                await self.mark_all_notifications_as_read()

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON'
            }))

    async def notification_new(self, event):
        """Отправить новое уведомление клиенту"""
        logger.info(f'Sending new notification to user {self.user.id}: {event.get("notification", {}).get("title", "No title")}')
        await self.send(text_data=json.dumps({
            'type': 'new_notification',
            'notification': event['notification']
        }))

    async def notification_count_update(self, event):
        """Обновить счетчик непрочитанных"""
        await self.send(text_data=json.dumps({
            'type': 'unread_count',
            'count': event['count']
        }))

    @database_sync_to_async
    def get_unread_count(self):
        """Получить количество непрочитанных уведомлений"""
        from .models import Notification
        return Notification.objects.filter(
            recipient=self.user,
            is_read=False,
            is_archived=False
        ).count()

    @database_sync_to_async
    def mark_notification_as_read(self, notification_id):
        """Отметить уведомление как прочитанное"""
        from .models import Notification
        try:
            notification = Notification.objects.get(
                id=notification_id,
                recipient=self.user
            )
            notification.mark_as_read()
            return True
        except Notification.DoesNotExist:
            return False

    @database_sync_to_async
    def mark_all_notifications_as_read(self):
        """Отметить все уведомления как прочитанные"""
        from .models import Notification
        from django.utils import timezone

        Notification.objects.filter(
            recipient=self.user,
            is_read=False
        ).update(
            is_read=True,
            read_at=timezone.now()
        )

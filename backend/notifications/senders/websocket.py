"""
WebSocket отправитель для realtime уведомлений
"""
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .base import BaseNotificationSender


class WebSocketNotificationSender(BaseNotificationSender):
    """
    Отправитель WebSocket уведомлений через Django Channels.
    Обеспечивает realtime доставку в браузер.
    """
    
    def can_send(self, notification, user_preferences) -> bool:
        """Проверяет, включены ли веб уведомления"""
        if not user_preferences.web_enabled:
            self.log_skip(notification, "web_enabled=False")
            return False
        return True
    
    def send(self, notification, silent: bool = False, **kwargs) -> bool:
        """
        Отправляет уведомление через WebSocket.
        
        Args:
            notification: Объект Notification
            silent: Если True, уведомление без звука/визуальных эффектов
            **kwargs: Дополнительные параметры
            
        Returns:
            True если отправлено успешно, False иначе
        """
        try:
            channel_layer = get_channel_layer()
            if not channel_layer:
                self.log_skip(notification, "channel_layer not configured")
                return False
            
            user_id = notification.recipient.id
            user_channel = f"user_{user_id}"
            
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
            
            self.log_success(notification, f"user_{user_id}")
            return True
            
        except Exception as e:
            self.log_error(notification, e, f"user_{notification.recipient.id}")
            return False

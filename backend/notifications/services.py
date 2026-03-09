"""
Слой обратной совместимости для старого API уведомлений.

DEPRECATED: Этот модуль предоставляет facade для старого кода.
Новый код должен использовать напрямую:
- from notifications.signals import notify
- notify.send(sender=user, recipient=other, verb='liked', ...)
"""
import logging
from typing import Optional, Dict, Any
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


class NotificationService:
    """
    Facade для обратной совместимости со старым API.
    
    Все методы теперь работают через новую систему (notify.send()).
    """
    
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
    ):
        """
        Создает уведомление (старый API → новая система).
        
        DEPRECATED: Используйте notify.send() напрямую.
        
        Args:
            recipient: Получатель уведомления
            notification_type_code: Код типа (mapping в verb)
            title: Заголовок (не используется в новой системе)
            message: Описание уведомления
            content_object: Объект-источник (→ action_object)
            action_url: URL для действия
            action_text: Текст кнопки (не используется)
            metadata: Дополнительные данные
            send_immediately: Игнорируется (всегда через Celery)
            
        Returns:
            Notification объект (новая модель)
        """
        from .signals import notify
        
        # Маппинг старых типов на новые verbs
        type_to_verb = {
            'message': 'messaged',
            'message_new': 'messaged',
            'document': 'shared',
            'document_new': 'shared',
            'request': 'created',
            'request_status_changed': 'updated',
            'request_comment_added': 'commented',
            'feed_post': 'posted',
            'feed_comment': 'commented',
            'feed_like': 'liked',
            'calendar_event': 'scheduled',
            'procurement': 'created',
            'procurement_approved': 'approved',
            'procurement_rejected': 'rejected',
        }
        
        verb = type_to_verb.get(notification_type_code, 'notified')
        
        # Создаем через новую систему
        notification = notify.send(
            sender=None,  # System notification
            recipient=recipient,
            verb=verb,
            action_object=content_object,
            description=message,
            action_url=action_url,
        )
        
        # notify.send() возвращает список [(signal, [notifications])]
        if notification and len(notification) > 0:
            return notification[0][1][0] if notification[0][1] else None
        
        return None
    
    @staticmethod
    def create_notification_async(
        recipient: User,
        notification_type_code: str,
        title: str,
        message: str,
        content_object=None,
        action_url: str = '',
        action_text: str = 'Посмотреть',
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Асинхронное создание уведомления.
        
        DEPRECATED: Новая система всегда асинхронна через Celery.
        Этот метод теперь идентичен create_notification().
        """
        return NotificationService.create_notification(
            recipient=recipient,
            notification_type_code=notification_type_code,
            title=title,
            message=message,
            content_object=content_object,
            action_url=action_url,
            action_text=action_text,
            metadata=metadata,
            send_immediately=True,
        )
    
    @staticmethod
    def mark_as_read(notification_id: int, user: User) -> bool:
        """
        Отмечает уведомление как прочитанное.
        
        Args:
            notification_id: ID уведомления
            user: Пользователь (проверка владения)
            
        Returns:
            True если успешно, False иначе
        """
        try:
            from .models import Notification
            
            notification = Notification.objects.get(
                id=notification_id,
                recipient=user
            )
            notification.mark_as_read()
            return True
            
        except Notification.DoesNotExist:
            logger.warning(f"Notification {notification_id} not found for user {user.id}")
            return False
    
    @staticmethod
    def mark_all_as_read(user: User, category: Optional[str] = None) -> int:
        """
        Отмечает все уведомления как прочитанные.
        
        Args:
            user: Пользователь
            category: Категория (не используется в новой системе)
            
        Returns:
            Количество отмеченных уведомлений
        """
        from .models import Notification
        
        return Notification.objects.filter(
            recipient=user,
            unread=True
        ).mark_all_as_read()
    
    @staticmethod
    def get_user_settings(user: User, setting_type: Optional[str] = None):
        """
        Получает настройки уведомлений пользователя.
        
        DEPRECATED: Используйте UserChannelPreferences напрямую.
        
        Args:
            user: Пользователь
            setting_type: Тип настройки (игнорируется)
            
        Returns:
            UserChannelPreferences объект
        """
        try:
            return user.channel_preferences
        except Exception:
            from .models import UserChannelPreferences
            return UserChannelPreferences.objects.create(user=user)
    
    @staticmethod
    def send_websocket_notification(user_id: int, notification_data: Optional[dict] = None):
        """
        Отправка WebSocket уведомления.
        
        DEPRECATED: WebSocket уведомления отправляются автоматически
        через channels.py при создании Notification.
        """
        logger.warning(
            "NotificationService.send_websocket_notification() is deprecated. "
            "WebSocket notifications are sent automatically via channels.py"
        )
        return True

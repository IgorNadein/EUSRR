"""
Celery задачи для отправки WebSocket уведомлений (realtime)
"""
from .base import BaseNotificationTask
from notifications import config


class WebSocketNotificationTask(BaseNotificationTask):
    """
    Celery задача для асинхронной отправки WebSocket уведомлений.
    
    Особенности:
    - Минимальный retry: из config (default: 1 попытка)
    - Быстрая повторная попытка: из config (default: 5 секунд)
    - Поддержка silent режима (DND)
    """
    
    task_name = "notifications.send_websocket_notification"
    max_retries = config.websocket_max_retries()
    retry_delay = config.websocket_retry_delay()
    rate_limit = None  # Без ограничений для realtime
    
    def execute(self, celery_task, notification_id: int, silent: bool = False, **kwargs):
        """Переопределяем для поддержки параметра silent"""
        try:
            notification = self.get_notification(notification_id)
            
            if not notification:
                self.logger.warning(
                    f"⚠️ Notification {notification_id} not found "
                    f"(possibly deleted by user before delivery)"
                )
                return False
            
            # Отправляем с учетом silent режима
            success = self.send_notification(notification, silent=silent, **kwargs)
            
            if success:
                self.log_success(notification)
            else:
                self.log_failure(notification)
            
            return success
            
        except Exception as exc:
            self.log_error(notification_id, exc)
            raise celery_task.retry(exc=exc)
    
    def send_notification(self, notification, silent: bool = False, **kwargs) -> bool:
        """
        Отправляет WebSocket через WebSocketNotificationSender.
        
        Args:
            notification: Объект Notification
            silent: Если True, уведомление без звука/визуальных эффектов
            **kwargs: Дополнительные параметры
                
        Returns:
            True если успешно, False иначе
        """
        from notifications.senders.websocket import WebSocketNotificationSender
        
        sender = WebSocketNotificationSender()
        return sender.send(notification, silent=silent, **kwargs)


# Регистрируем задачу в Celery
send_websocket_notification = WebSocketNotificationTask.register_task()

"""
Celery задачи для отправки Web Push уведомлений
"""
from .base import BaseNotificationTask
from notifications import config


class PushNotificationTask(BaseNotificationTask):
    """
    Celery задача для асинхронной отправки Web Push уведомлений.
    
    Особенности:
    - Rate limiting: из config (default: 50 push/минуту)
    - Retry: из config (default: 2 попытки с интервалом 1 минута)
    - Автоматическое удаление неактивных устройств
    """
    
    task_name = "notifications.send_push"
    max_retries = config.push_max_retries()
    retry_delay = config.push_retry_delay()
    rate_limit = config.push_rate_limit()
    
    def send_notification(self, notification, **kwargs) -> bool:
        """
        Отправляет Web Push через PushNotificationSender.
        
        Args:
            notification: Объект Notification
            **kwargs: Дополнительные параметры
                
        Returns:
            True если успешно (хотя бы одно устройство), False иначе
        """
        from notifications.senders.push import PushNotificationSender
        
        sender = PushNotificationSender()
        return sender.send(notification, **kwargs)


# Регистрируем задачу в Celery
send_push_notification = PushNotificationTask.register_task()

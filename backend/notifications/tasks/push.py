"""
Celery задачи для отправки Web Push уведомлений

TODO: Вынести конфигурацию в settings:
      - NOTIFICATIONS_PUSH_RATE_LIMIT (сейчас '50/m')
      - NOTIFICATIONS_PUSH_MAX_RETRIES (сейчас 2)
      - NOTIFICATIONS_PUSH_RETRY_DELAY (сейчас 60)
"""
from .base import BaseNotificationTask


class PushNotificationTask(BaseNotificationTask):
    """
    Celery задача для асинхронной отправки Web Push уведомлений.
    
    Особенности:
    - Rate limiting: 50 push/минуту
    - Retry: 2 попытки с интервалом 1 минута
    - Автоматическое удаление неактивных устройств
    """
    
    task_name = "notifications.send_push"
    max_retries = 2
    retry_delay = 60  # 1 минута между попытками
    rate_limit = '50/m'  # Не более 50 push в минуту
    
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

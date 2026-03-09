"""
Базовый класс для Celery задач отправки уведомлений
"""
from abc import ABC, abstractmethod
from celery import shared_task
import logging

logger = logging.getLogger(__name__)


class BaseNotificationTask(ABC):
    """
    Абстрактный базовый класс для Celery задач по отправке уведомлений.
    
    Инкапсулирует общую логику:
    - Получение notification из БД
    - Обработка ошибок
    - Логирование
    - Retry логика
    
    Наследники реализуют только send_notification() с конкретным sender'ом.
    """
    
    # Настройки Celery для конкретного канала (переопределяются в наследниках)
    task_name = None
    max_retries = 3
    retry_delay = 60  # секунд
    rate_limit = None  # например '10/m' для email
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @classmethod
    def register_task(cls):
        """
        Регистрирует Celery задачу для этого класса.
        Должен вызываться при импорте модуля.
        """
        instance = cls()
        
        @shared_task(
            name=cls.task_name,
            bind=True,
            max_retries=cls.max_retries,
            default_retry_delay=cls.retry_delay,
            autoretry_for=(Exception,),
            rate_limit=cls.rate_limit,
        )
        def task_wrapper(self_task, notification_id: int, **kwargs):
            """Wrapper для вызова метода класса из Celery"""
            return instance.execute(self_task, notification_id, **kwargs)
        
        return task_wrapper
    
    def execute(self, celery_task, notification_id: int, **kwargs):
        """
        Выполняет задачу отправки уведомления.
        
        Args:
            celery_task: Объект Celery task (для retry)
            notification_id: ID уведомления
            **kwargs: Дополнительные параметры для sender
            
        Returns:
            True если успешно, False иначе
        """
        try:
            # Получаем уведомление из БД
            notification = self.get_notification(notification_id)
            
            if not notification:
                self.logger.warning(
                    f"⚠️ Notification {notification_id} not found "
                    f"(possibly deleted by user before delivery)"
                )
                return False
            
            # Отправляем через конкретный sender
            success = self.send_notification(notification, **kwargs)
            
            if success:
                self.log_success(notification)
            else:
                self.log_failure(notification)
            
            return success
            
        except Exception as exc:
            self.log_error(notification_id, exc)
            raise celery_task.retry(exc=exc)
    
    def get_notification(self, notification_id: int):
        """Получает Notification из БД"""
        try:
            from notifications.models import Notification
            return Notification.objects.get(id=notification_id)
        except Exception:
            return None
    
    @abstractmethod
    def send_notification(self, notification, **kwargs) -> bool:
        """
        Отправляет уведомление через конкретный канал.
        Должен быть реализован в наследниках.
        
        Args:
            notification: Объект Notification
            **kwargs: Дополнительные параметры
            
        Returns:
            True если успешно, False иначе
        """
        pass
    
    def log_success(self, notification):
        """Логирует успешную отправку"""
        self.logger.info(
            f"✅ Notification sent: "
            f"id={notification.id}, "
            f"recipient={notification.recipient.id}, "
            f"channel={self.__class__.__name__}"
        )
    
    def log_failure(self, notification):
        """Логирует неуспешную отправку"""
        self.logger.warning(
            f"⚠️ Notification failed: "
            f"id={notification.id}, "
            f"recipient={notification.recipient.id}, "
            f"channel={self.__class__.__name__}"
        )
    
    def log_error(self, notification_id: int, error: Exception):
        """Логирует ошибку"""
        self.logger.error(
            f"❌ Task error: "
            f"notification_id={notification_id}, "
            f"channel={self.__class__.__name__}, "
            f"error={type(error).__name__}: {error}",
            exc_info=True
        )

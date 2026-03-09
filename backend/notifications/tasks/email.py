"""
Celery задачи для отправки email уведомлений
"""
from .base import BaseNotificationTask


class EmailNotificationTask(BaseNotificationTask):
    """
    Celery задача для асинхронной отправки email уведомлений.
    
    Особенности:
    - Rate limiting: 10 email/минуту (защита от SMTP бана)
    - Retry: 3 попытки с интервалом 5 минут
    - Поддержка кастомных тем и получателей
    """
    
    task_name = "notifications.send_email"
    max_retries = 3
    retry_delay = 300  # 5 минут между попытками
    rate_limit = '10/m'  # Не более 10 email в минуту
    
    def send_notification(self, notification, **kwargs) -> bool:
        """
        Отправляет email через EmailNotificationSender.
        
        Args:
            notification: Объект Notification
            **kwargs: 
                - custom_subject: кастомная тема письма
                - recipient_email: явный email получателя
                
        Returns:
            True если успешно, False иначе
        """
        from notifications.senders.email import EmailNotificationSender
        
        sender = EmailNotificationSender()
        return sender.send(notification, **kwargs)


class DigestEmailTask(BaseNotificationTask):
    """
    Celery задача для отправки email дайджестов.
    
    Особенности:
    - Отправка сводки непрочитанных уведомлений
    - Поддержка daily/weekly частоты
    - Максимум 50 уведомлений в одном дайджесте
    """
    
    task_name = "notifications.send_digest_email"
    max_retries = 2
    retry_delay = 600  # 10 минут между попытками
    rate_limit = '5/h'  # Не более 5 дайджестов в час
    
    def execute(self, celery_task, user_id: int, frequency: str = 'daily', **kwargs):
        """Переопределяем execute для работы с user_id вместо notification_id"""
        try:
            from django.contrib.auth import get_user_model
            from notifications.models import Notification
            from notifications.senders.email import EmailNotificationSender
            from django.utils import timezone
            from datetime import timedelta
            
            User = get_user_model()
            user = User.objects.get(id=user_id)
            
            # Определяем период для дайджеста
            if frequency == 'weekly':
                cutoff = timezone.now() - timedelta(days=7)
            else:  # daily
                cutoff = timezone.now() - timedelta(days=1)
            
            # Получаем непрочитанные уведомления за период
            notifications = Notification.objects.filter(
                recipient=user,
                unread=True,
                emailed=False,  # Еще не отправлены по email
                timestamp__gte=cutoff,
            ).order_by('-timestamp')[:50]  # Максимум 50 в дайджесте
            
            if not notifications.exists():
                self.logger.info(f"📭 No notifications for digest: user={user_id}, frequency={frequency}")
                return False
            
            # Отправляем дайджест
            sender = EmailNotificationSender()
            success = sender.send_digest(user, list(notifications), frequency=frequency)
            
            if success:
                self.logger.info(
                    f"✅ Digest sent: user={user_id}, frequency={frequency}, "
                    f"count={notifications.count()}"
                )
            else:
                self.logger.warning(f"⚠️ Digest failed: user={user_id}, frequency={frequency}")
            
            return success
            
        except Exception as exc:
            self.logger.exception(f"❌ Digest task error: user={user_id}, frequency={frequency}")
            raise celery_task.retry(exc=exc)
    
    def send_notification(self, notification, **kwargs) -> bool:
        """Не используется для дайджестов"""
        pass


# Регистрируем задачи в Celery
send_email_notification = EmailNotificationTask.register_task()
send_digest_email = DigestEmailTask.register_task()

"""
Celery задачи для отправки email уведомлений
"""

from celery import shared_task

from .base import BaseNotificationTask
from notifications import config


class EmailNotificationTask(BaseNotificationTask):
    """
    Celery задача для асинхронной отправки email уведомлений.

    Особенности:
    - Rate limiting: из config (default: 10 email/минуту)
    - Retry: из config (default: 3 попытки с интервалом 5 минут)
    - Поддержка кастомных тем и получателей
    """

    task_name = "notifications.send_email_notification"
    max_retries = config.email_max_retries()
    retry_delay = config.email_retry_delay()
    rate_limit = config.email_rate_limit()

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
    rate_limit = "5/h"  # Не более 5 дайджестов в час

    def execute(
        self, celery_task, user_id: int, frequency: str = "daily", **kwargs
    ):
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
            if frequency == "weekly":
                cutoff = timezone.now() - timedelta(days=7)
            else:  # daily
                cutoff = timezone.now() - timedelta(days=1)

            # Получаем непрочитанные уведомления за период
            notifications = Notification.objects.filter(
                recipient=user,
                unread=True,
                emailed=False,  # Еще не отправлены по email
                timestamp__gte=cutoff,
            ).order_by("-timestamp")[:50]  # Максимум 50 в дайджесте

            if not notifications.exists():
                self.logger.info(
                    "📭 No notifications for digest: "
                    f"user={user_id}, frequency={frequency}"
                )
                return False

            # Отправляем дайджест
            sender = EmailNotificationSender()
            success = sender.send_digest(
                user, list(notifications), frequency=frequency
            )

            if success:
                self.logger.info(
                    f"✅ Digest sent: user={user_id}, frequency={frequency}, "
                    f"count={notifications.count()}"
                )
            else:
                self.logger.warning(
                    f"⚠️ Digest failed: user={user_id}, frequency={frequency}"
                )

            return success

        except Exception as exc:
            self.logger.exception(
                f"❌ Digest task error: user={user_id}, frequency={frequency}"
            )
            raise celery_task.retry(exc=exc)

    def send_notification(self, notification, **kwargs) -> bool:
        """Не используется для дайджестов"""
        pass


# Регистрируем задачи в Celery
send_email_notification = EmailNotificationTask.register_task()
send_digest_email = DigestEmailTask.register_task()


@shared_task(name="notifications.send_digest_emails")
def send_digest_emails(frequency: str = "daily") -> int:
    """
    Dispatches digest email tasks for users who selected daily/weekly delivery.
    """
    if frequency not in {"daily", "weekly"}:
        raise ValueError(f"Unsupported digest frequency: {frequency}")

    from datetime import timedelta

    from django.utils import timezone

    from notifications.models import UserChannelPreferences

    cutoff = timezone.now() - timedelta(days=7 if frequency == "weekly" else 1)
    preferences = UserChannelPreferences.objects.select_related("user").filter(
        email_enabled=True,
        email_frequency=frequency,
        user__email__isnull=False,
        user__notifications__unread=True,
        user__notifications__emailed=False,
        user__notifications__deleted=False,
        user__notifications__timestamp__gte=cutoff,
    ).exclude(user__email="").distinct()

    dispatched = 0
    for prefs in preferences.iterator():
        send_digest_email.delay(prefs.user_id, frequency)
        dispatched += 1

    return dispatched

"""
Celery задачи для асинхронной отправки уведомлений через различные каналы

Архитектура:
- Базовый класс BaseNotificationTask (инкапсуляция общей логики)
- Класс-задача для каждого канала
    (EmailNotificationTask, PushNotificationTask, ...)
- Автоматическая регистрация в Celery через register_task()
- Единообразное логирование, retry, rate limiting
"""

from .email import (
    send_digest_email,
    send_digest_emails,
    send_email_notification,
)
from .push import send_push_notification
from .websocket import send_websocket_notification

__all__ = [
    "send_email_notification",
    "send_push_notification",
    "send_websocket_notification",
    "send_digest_email",
    "send_digest_emails",
]

"""
Модуль уведомлений для Calendar приложения.

Публичный API:
    - NotificationVerbs - константы глаголов уведомлений
    - MessageTemplates - шаблоны сообщений
    - ActionURLs - генераторы URL-адресов
    - get_event_recipients - получение списка получателей для события

Использование:
    from calendar_app.notifications import get_event_recipients
    
    # В коде:
    recipients = get_event_recipients(event)
"""

from .config import (
    NotificationVerbs,
    MessageTemplates,
    ActionURLs,
    format_date,
    format_changes,
)
from .handlers import get_event_recipients

# Импортируем handlers и signals для регистрации
from . import handlers  # noqa: F401
from . import signals  # noqa: F401

__all__ = [
    'NotificationVerbs',
    'MessageTemplates',
    'ActionURLs',
    'get_event_recipients',
    'format_date',
    'format_changes',
]

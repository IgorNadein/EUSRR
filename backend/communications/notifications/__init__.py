"""
Модуль уведомлений для Communications приложения.

Публичный API:
    - NotificationVerbs - константы глаголов уведомлений
    - MessageTemplates - шаблоны сообщений
    - ActionURLs - генераторы URL-адресов
    - extract_mentions - извлечение упоминаний из текста
    - truncate_message - обрезка текста сообщения
    - get_chat_name - получение названия чата
    - get_users_with_notifications_enabled - проверка настроек уведомлений

Использование:
    from communications.notifications import extract_mentions, get_chat_name
    
    # В коде:
    mentions = extract_mentions(message.content)
    chat_name = get_chat_name(chat)
"""

from .config import (
    NotificationVerbs,
    MessageTemplates,
    ActionURLs,
    extract_mentions,
    truncate_message,
    get_chat_name,
)
from .handlers import get_users_with_notifications_enabled

# Импортируем handlers и signals для регистрации
from . import handlers  # noqa: F401
from . import signals  # noqa: F401

__all__ = [
    'NotificationVerbs',
    'MessageTemplates',
    'ActionURLs',
    'extract_mentions',
    'truncate_message',
    'get_chat_name',
    'get_users_with_notifications_enabled',
]

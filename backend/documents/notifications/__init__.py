"""
Модуль уведомлений для Documents приложения.

Публичный API:
    - NotificationVerbs - константы глаголов уведомлений
    - MessageTemplates - шаблоны сообщений
    - ActionURLs - генераторы URL-адресов
    - notify_document_ready - функция для ручного уведомления о документе

Использование:
    from documents.notifications import notify_document_ready

    # В коде:
    notify_document_ready(document, user)
"""

from .config import (
    NotificationVerbs,
    MessageTemplates,
    ActionURLs,
    get_uploader_name,
)
from .handlers import notify_document_ready

# Импортируем handlers и signals для регистрации
from . import handlers  # noqa: F401
from . import signals  # noqa: F401

__all__ = [
    'NotificationVerbs',
    'MessageTemplates',
    'ActionURLs',
    'notify_document_ready',
    'get_uploader_name',
]

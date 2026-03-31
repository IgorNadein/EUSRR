"""
Модуль уведомлений для Feed приложения.

Публичный API:
    - NotificationVerbs - константы глаголов уведомлений
    - MessageTemplates - шаблоны сообщений
    - ActionURLs - генераторы URL-адресов
    - notify_post_reaction - функция для уведомления о реакциях (вызывается из views)

Использование:
    from feed.notifications import notify_post_reaction

    # В view при добавлении лайка:
    notify_post_reaction(post, request.user)
"""

from .config import NotificationVerbs, MessageTemplates, ActionURLs
from .handlers import notify_post_reaction

# Импортируем handlers и signals для регистрации
from . import handlers  # noqa: F401
from . import signals  # noqa: F401

__all__ = [
    'NotificationVerbs',
    'MessageTemplates',
    'ActionURLs',
    'notify_post_reaction',
]

"""
Модуль уведомлений для приложения Requests.

Обеспечивает автоматическую отправку уведомлений при:
- Создании нового заявления
- Изменении статуса заявления
- Добавлении комментария к заявлению

Использует универсальную систему уведомлений (backend/notifications).

Структура:
- constants.py - константы (типы уведомлений, шаблоны сообщений)
- handlers.py - бизнес-логика отправки уведомлений
- signals.py - Django сигналы для автоматической генерации

Usage:
    # Сигналы подключаются автоматически через AppConfig.ready()
    # Для ручной отправки:
    from requests_app.notifications import notify_new_request
    notify_new_request(request_obj)
"""

# Импорты для удобства и обратной совместимости
from .constants import NotificationVerbs, MessageTemplates, ActionURLs
from .handlers import (
    notify_new_request,
    notify_status_change,
    notify_comment,
)

# Сигналы импортируются для регистрации через AppConfig.ready()
from . import signals  # noqa: F401


__all__ = [
    # Constants
    'NotificationVerbs',
    'MessageTemplates',
    'ActionURLs',
    
    # Handlers
    'notify_new_request',
    'notify_status_change',
    'notify_comment',
    
    # Signals module (для импорта в AppConfig)
    'signals',
]

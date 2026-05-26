"""
Модуль уведомлений для приложения Procurement.

Обеспечивает автоматическую отправку уведомлений при:
- Создании новой заявки на закупку
- Изменении статуса заявки
- Создании/изменении согласования

Использует универсальную систему уведомлений (backend/notifications).
Все уведомления (включая WebSocket) отправляются через notify.send().

Структура:
- config.py - конфигурация (типы уведомлений, шаблоны, URLs)
- handlers.py - бизнес-логика отправки уведомлений
- signals.py - Django сигналы для автоматической генерации

Usage:
    # Сигналы подключаются автоматически через AppConfig.ready()
    # Для ручной отправки:
    from procurement.notifications import notify_request_comment
    notify_request_comment(request_obj, message_obj, actor=user)

    # WebSocket broadcast происходит автоматически через:
    # notify.send() → channels.py → Celery → WebSocketNotificationSender
"""

# Импорты для удобства и обратной совместимости
from .config import NotificationVerbs, MessageTemplates, ActionURLs
from .handlers import (
    notify_new_request,
    notify_approvers,
    notify_approver,
    notify_processing_department_request,
    notify_requestor,
    notify_request_approved,
    notify_request_rejected,
    notify_request_completed,
    notify_request_in_progress,
    notify_request_cancelled,
    notify_stage_approved,
    notify_stage_rejected,
    notify_item_updated,
    notify_item_issue_reported,
    notify_request_comment,
    notify_item_comment,
)

# Сигналы импортируются для регистрации через AppConfig.ready()
from . import signals  # noqa: F401


__all__ = [
    # Config
    'NotificationVerbs',
    'MessageTemplates',
    'ActionURLs',

    # Handlers
    'notify_new_request',
    'notify_approvers',
    'notify_approver',
    'notify_processing_department_request',
    'notify_requestor',
    'notify_request_approved',
    'notify_request_rejected',
    'notify_request_completed',
    'notify_request_in_progress',
    'notify_request_cancelled',
    'notify_stage_approved',
    'notify_stage_rejected',
    'notify_item_updated',
    'notify_item_issue_reported',
    'notify_request_comment',
    'notify_item_comment',

    # Signals module (для импорта в AppConfig)
    'signals',
]

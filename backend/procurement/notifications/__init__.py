"""
Модуль уведомлений для приложения Procurement.

Обеспечивает автоматическую отправку уведомлений при:
- Создании новой заявки на закупку
- Изменении статуса заявки
- Создании/изменении согласования
- WebSocket broadcast для real-time обновлений

Использует универсальную систему уведомлений (backend/notifications).

Структура:
- config.py - конфигурация (типы уведомлений, шаблоны, URLs)
- handlers.py - бизнес-логика отправки уведомлений
- signals.py - Django сигналы для автоматической генерации
- websocket.py - WebSocket broadcast для real-time уведомлений

Usage:
    # Сигналы подключаются автоматически через AppConfig.ready()
    # Для ручной отправки:
    from procurement.notifications import notify_new_request
    notify_new_request(request_obj)
    
    # Для WebSocket broadcast:
    from procurement.notifications import broadcast_request_update
    broadcast_request_update(request_obj, 'request_updated')
"""

# Импорты для удобства и обратной совместимости
from .config import NotificationVerbs, MessageTemplates, ActionURLs
from .handlers import (
    notify_new_request,
    notify_approvers,
    notify_approver,
    notify_requestor,
    notify_request_approved,
    notify_request_rejected,
    notify_request_completed,
    notify_request_in_progress,
    notify_request_cancelled,
    notify_stage_approved,
    notify_stage_rejected,
)
from .websocket import (
    broadcast_request_update,
    broadcast_request_created,
    broadcast_request_status_changed,
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
    'notify_requestor',
    'notify_request_approved',
    'notify_request_rejected',
    'notify_request_completed',
    'notify_request_in_progress',
    'notify_request_cancelled',
    'notify_stage_approved',
    'notify_stage_rejected',
    
    # WebSocket
    'broadcast_request_update',
    'broadcast_request_created',
    'broadcast_request_status_changed',
    
    # Signals module (для импорта в AppConfig)
    'signals',
]

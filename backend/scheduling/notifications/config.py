"""
Конфигурация уведомлений для django-scheduler.
"""
from . import (
    NotificationVerbs,
    MessageTemplates,
    ActionURLs,
    FIELD_NAMES,
    IMPORTANT_FIELDS,
    format_datetime,
    format_date,
    format_changes,
)

__all__ = [
    'NotificationVerbs',
    'MessageTemplates',
    'ActionURLs',
    'FIELD_NAMES',
    'IMPORTANT_FIELDS',
    'format_datetime',
    'format_date',
    'format_changes',
]

"""
Конфигурация уведомлений для django-scheduler.

Содержит:
- NotificationVerbs - глаголы для уведомлений
- MessageTemplates - шаблоны сообщений
- ActionURLs - URL-адреса действий
- Вспомогательные функции
"""


class NotificationVerbs:
    """Глаголы (verbs) для уведомлений событий календаря."""

    EVENT_CREATED = 'event_created'
    EVENT_CHANGED = 'event_changed'
    EVENT_CANCELLED = 'event_cancelled'
    EVENT_REMINDER = 'event_reminder'  # Для будущей реализации через Celery


class MessageTemplates:
    """Шаблоны сообщений для уведомлений календаря."""

    @staticmethod
    def event_created(
        event_title: str,
        event_date: str,
        calendar_name: str = None
    ) -> str:
        """Шаблон для нового события."""
        if calendar_name:
            return (
                f'Добавлено событие в календарь "{calendar_name}": '
                f'"{event_title}" ({event_date})'
            )
        return f'Добавлено новое событие: "{event_title}" ({event_date})'

    @staticmethod
    def event_created_title() -> str:
        """Заголовок для нового события."""
        return 'Новое событие в календаре'

    @staticmethod
    def event_changed(
        event_title: str,
        changes_text: str = None
    ) -> str:
        """Шаблон для изменения события."""
        if changes_text:
            return (
                f'Событие "{event_title}" изменено. '
                f'Изменения: {changes_text}'
            )
        return f'Событие "{event_title}" изменено'

    @staticmethod
    def event_changed_title() -> str:
        """Заголовок для изменения события."""
        return 'Событие изменено'

    @staticmethod
    def event_cancelled(event_title: str, event_date: str) -> str:
        """Шаблон для отмены события."""
        return f'Событие "{event_title}" ({event_date}) отменено'

    @staticmethod
    def event_cancelled_title() -> str:
        """Заголовок для отмены события."""
        return 'Событие отменено'


class ActionURLs:
    """URL-адреса для действий с календарем."""

    CALENDAR = '/calendar'

    @staticmethod
    def event_detail(event_id: int) -> str:
        """
        Возвращает URL-адрес события.

        TODO: реализовать прямые ссылки на конкретные события
        """
        return f'/calendar?event={event_id}'


# ===== Константы для полей django-scheduler Event =====

FIELD_NAMES = {
    'title': 'название',
    'start': 'время начала',
    'end': 'время окончания',
    'description': 'описание',
    'end_recurring_period': 'окончание повторения',
}

IMPORTANT_FIELDS = [
    'title', 'start', 'end', 'description'
]


def format_datetime(dt) -> str:
    """
    Форматирует дату/время в строку.

    Args:
        dt: Объект datetime

    Returns:
        str: Отформатированная дата и время (например, "10.03.2026 14:30")
    """
    if not dt:
        return ''
    return dt.strftime('%d.%m.%Y %H:%M')


def format_date(dt) -> str:
    """
    Форматирует только дату в строку.

    Args:
        dt: Объект datetime или date

    Returns:
        str: Отформатированная дата (например, "10.03.2026")
    """
    if not dt:
        return ''
    return dt.strftime('%d.%m.%Y')


def format_changes(changed_fields: list[str]) -> str:
    """
    Форматирует список изменённых полей в текст.

    Args:
        changed_fields: Список имён полей

    Returns:
        str: Текстовое описание изменений через запятую
    """
    return ', '.join([
        FIELD_NAMES.get(f, f) for f in changed_fields
    ])

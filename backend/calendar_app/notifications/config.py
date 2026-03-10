"""
Конфигурация уведомлений для модуля Calendar.

Содержит:
- NotificationVerbs - глаголы для уведомлений
- MessageTemplates - шаблоны сообщений
- ActionURLs - URL-адреса действий
- Вспомогательные функции
"""


class NotificationVerbs:
    """Глаголы (verbs) для уведомлений calendar."""
    
    EVENT_CREATED = 'event_created'
    EVENT_CHANGED = 'event_changed'
    EVENT_CANCELLED = 'event_cancelled'
    EVENT_REMINDER = 'event_reminder'  # Для будущей реализации через Celery


class MessageTemplates:
    """Шаблоны сообщений для уведомлений calendar."""
    
    @staticmethod
    def event_created_company(event_title: str, event_date: str) -> str:
        """Шаблон для нового события компании."""
        return f'Добавлено событие компании: "{event_title}" ({event_date})'
    
    @staticmethod
    def event_created_department(
        department_name: str,
        event_title: str,
        event_date: str
    ) -> str:
        """Шаблон для нового события отдела."""
        return (
            f'Добавлено событие отдела {department_name}: '
            f'"{event_title}" ({event_date})'
        )
    
    @staticmethod
    def event_created_title() -> str:
        """Заголовок для нового события."""
        return 'Новое событие в календаре'
    
    @staticmethod
    def event_changed(event_title: str, changes_text: str) -> str:
        """Шаблон для изменения события."""
        return f'Событие "{event_title}" изменено. Изменения: {changes_text}'
    
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


# ===== Константы для полей =====

FIELD_NAMES = {
    'title': 'название',
    'start_date': 'дата начала',
    'end_date': 'дата окончания',
    'start_time': 'время начала',
    'end_time': 'время окончания',
    'location': 'место проведения',
}

IMPORTANT_FIELDS = [
    'title', 'start_date', 'end_date',
    'start_time', 'end_time', 'location'
]


def format_date(date) -> str:
    """
    Форматирует дату в строку.
    
    Args:
        date: Объект date или datetime
    
    Returns:
        str: Отформатированная дата (например, "10.03.2026")
    """
    if not date:
        return ''
    return date.strftime('%d.%m.%Y')


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

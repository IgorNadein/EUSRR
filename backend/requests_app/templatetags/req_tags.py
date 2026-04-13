from django import template
from datetime import datetime

register = template.Library()


@register.filter
def in_list(value, csv):
    items = [s.strip() for s in str(csv).split(",") if s.strip()]
    return value in items


@register.filter
def format_iso_date(value, format_string="d.m.Y"):
    """
    Форматирует ISO дату из API в читаемый формат.

    Args:
        value: строка ISO даты
               (например, "2025-12-03" или "2025-12-03T10:30:00Z")
        format_string: формат вывода ("d.m.Y", "H:i" и т.д.)

    Returns:
        Отформатированная дата или исходная строка при ошибке
    """
    if not value:
        return ""

    try:
        # Пробуем распарсить как полную ISO дату
        if 'T' in str(value):
            dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        else:
            # Только дата без времени
            dt = datetime.strptime(str(value)[:10], '%Y-%m-%d')

        # Форматируем по шаблону Django
        format_map = {
            'd.m.Y': dt.strftime('%d.%m.%Y'),
            'H:i': dt.strftime('%H:%M'),
            'd.m.Y H:i': dt.strftime('%d.%m.%Y %H:%M'),
            'Y-m-d': dt.strftime('%Y-%m-%d'),
        }

        return format_map.get(format_string, dt.strftime('%d.%m.%Y'))
    except (ValueError, AttributeError):
        # Если не удалось распарсить, возвращаем первые 10 символов
        return str(value)[:10] if value else ""


@register.filter
def can_decide_request(request_obj, user):
    """Проверяет, является ли пользователь прямым получателем заявки."""
    if not user or not getattr(user, "is_authenticated", False):
        return False

    recipients = getattr(request_obj, "recipients", None)
    if recipients is None and isinstance(request_obj, dict):
        recipients = request_obj.get("recipients")

    if recipients is None:
        return False

    if hasattr(recipients, "filter"):
        return recipients.filter(id=user.id).exists()

    for recipient in recipients:
        if isinstance(recipient, dict) and recipient.get("id") == user.id:
            return True
        if getattr(recipient, "id", None) == user.id:
            return True

    return False

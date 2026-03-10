"""
Бизнес-логика отправки уведомлений для модуля Calendar.

Функции:
- get_event_recipients - определение получателей уведомлений
- notify_event_created - уведомление о новом событии
- notify_event_changed - уведомление об изменении события
- notify_event_cancelled - уведомление об отмене события
"""

from django.contrib.auth import get_user_model
from notifications.signals import notify

from .config import (
    NotificationVerbs,
    MessageTemplates,
    ActionURLs,
    format_date,
    format_changes,
)

Employee = get_user_model()


def get_event_recipients(event) -> list:
    """
    Возвращает список получателей уведомлений для события.
    
    Args:
        event: Объект CalendarEvent
    
    Returns:
        list: Список пользователей (Employee):
        - Для личного события - только владелец
        - Для события компании - все активные сотрудники
        - Для события отдела - сотрудники этого отдела
    """
    if event.is_personal:
        # Личное событие - только владелец
        return [event.employee] if event.employee else []
    
    elif event.is_company:
        # Событие компании - все активные сотрудники
        return list(Employee.objects.filter(is_active=True))
    
    elif event.department:
        # Событие отдела - сотрудники через EmployeeDepartment
        from employees.models import EmployeeDepartment
        employee_ids = EmployeeDepartment.objects.filter(
            department=event.department,
            is_active=True
        ).values_list('employee_id', flat=True)
        return list(Employee.objects.filter(id__in=employee_ids, is_active=True))
    
    return []


def notify_event_created(event):
    """
    Отправляет уведомления о новом событии всем участникам.
    
    Args:
        event: Объект CalendarEvent
    """
    recipients = get_event_recipients(event)
    
    # Исключаем создателя события
    if event.created_by:
        recipients = [r for r in recipients if r.id != event.created_by.id]
    
    # Определяем тип события для сообщения
    event_date = format_date(event.start_date)
    
    if event.is_company:
        description = MessageTemplates.event_created_company(event.title, event_date)
    elif event.department:
        description = MessageTemplates.event_created_department(
            event.department.name,
            event.title,
            event_date
        )
    else:
        # Личное событие - не должно попадать сюда (нет других получателей)
        return
    
    # Отправляем уведомления
    for recipient in recipients:
        notify.send(
            sender=event.created_by,
            recipient=recipient,
            verb=NotificationVerbs.EVENT_CREATED,
            action_object=event,
            description=description,
            action_url=ActionURLs.CALENDAR,
            data={
                'title': MessageTemplates.event_created_title(),
                'event_id': event.id,
                'event_title': event.title,
                'event_date': event.start_date.isoformat(),
                'department_id': (
                    event.department.id if event.department else None
                ),
                'is_company_event': event.is_company,
                'created_by_id': (
                    event.created_by.id if event.created_by else None
                ),
            }
        )


def notify_event_changed(event, changed_fields: list[str]):
    """
    Отправляет уведомления об изменении события.
    
    Args:
        event: Объект CalendarEvent
        changed_fields: Список изменённых полей
    """
    if not changed_fields:
        return
    
    recipients = get_event_recipients(event)
    
    # Формируем сообщение об изменениях
    changes_text = format_changes(changed_fields)
    
    for recipient in recipients:
        notify.send(
            sender=None,
            recipient=recipient,
            verb=NotificationVerbs.EVENT_CHANGED,
            action_object=event,
            description=MessageTemplates.event_changed(event.title, changes_text),
            action_url=ActionURLs.CALENDAR,
            data={
                'title': MessageTemplates.event_changed_title(),
                'event_id': event.id,
                'event_title': event.title,
                'changed_fields': changed_fields,
                'event_date': event.start_date.isoformat(),
                'department_id': (
                    event.department.id if event.department else None
                ),
            }
        )


def notify_event_cancelled(event):
    """
    Отправляет уведомления об отмене (удалении) события.
    
    Args:
        event: Объект CalendarEvent
    """
    recipients = get_event_recipients(event)
    event_date = format_date(event.start_date)
    
    for recipient in recipients:
        notify.send(
            sender=None,
            recipient=recipient,
            verb=NotificationVerbs.EVENT_CANCELLED,
            description=MessageTemplates.event_cancelled(event.title, event_date),
            action_url=ActionURLs.CALENDAR,
            data={
                'title': MessageTemplates.event_cancelled_title(),
                'event_title': event.title,
                'event_date': event.start_date.isoformat(),
                'department_id': (
                    event.department.id if event.department else None
                ),
                'is_company_event': event.is_company,
            }
        )

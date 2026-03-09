"""
Signals для автоматической генерации уведомлений в модуле Calendar.

Обрабатывает события:
- Новое событие календаря
- Изменение события
- Отмена события

Напоминания (за час, за день) будут реализованы через Celery tasks.
"""

from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from .models import CalendarEvent
from notifications.signals import notify

Employee = get_user_model()


@receiver(post_save, sender=CalendarEvent)
def create_event_notifications(sender, instance, created, **kwargs):
    """
    Создает уведомления при создании или изменении события асинхронно.
    
    Уведомления отправляются:
    - При создании - всем сотрудникам компании или отдела
    - При изменении - участникам события
    """
    # Отправляем уведомления напрямую - channels.py автоматически отправит через Celery
    if created:
        notify_event_created(instance)
    else:
        changed_fields = getattr(instance, '_changed_fields', [])
        if changed_fields:
            notify_event_changed(instance, changed_fields)


@receiver(pre_save, sender=CalendarEvent)
def track_event_changes(sender, instance, **kwargs):
    """
    Отслеживает изменения важных полей события для уведомлений.
    """
    if instance.pk:
        try:
            old_event = CalendarEvent.objects.get(pk=instance.pk)
            changed_fields = []
            
            # Отслеживаем важные поля
            important_fields = [
                'title', 'start_date', 'end_date',
                'start_time', 'end_time', 'location'
            ]
            
            for field in important_fields:
                old_value = getattr(old_event, field)
                new_value = getattr(instance, field)
                if old_value != new_value:
                    changed_fields.append(field)
            
            instance._changed_fields = changed_fields
        except CalendarEvent.DoesNotExist:
            instance._changed_fields = []


@receiver(pre_delete, sender=CalendarEvent)
def notify_event_cancelled(sender, instance, **kwargs):
    """
    Создает уведомления при удалении (отмене) события асинхронно.
    """
    # Отправляем уведомления напрямую - channels.py автоматически отправит через Celery
    recipients = get_event_recipients(instance)
    for recipient in recipients:
            notify.send(
                sender=None,
                recipient=recipient,
                verb='event_cancelled',
                description=(
                    f'Событие "{instance.title}" '
                    f'({instance.start_date.strftime("%d.%m.%Y")}) отменено'
                ),
                action_url=get_calendar_url(instance),
                data={
                    'title': 'Событие отменено',
                    'event_title': instance.title,
                    'event_date': instance.start_date.isoformat(),
                    'department_id': (
                        instance.department.id if instance.department else None
                    ),
                    'is_company_event': instance.is_company,
                }
            )


# ===== Вспомогательные функции =====

def notify_event_created(event):
    """
    Отправляет уведомления о новом событии всем участникам.
    """
    recipients = get_event_recipients(event)
    
    # Исключаем создателя события
    if event.created_by:
        recipients = [r for r in recipients if r.id != event.created_by.id]
    
    event_scope = (
        f'отдела {event.department.name}'
        if event.department
        else 'компании'
    )
    
    for recipient in recipients:
        notify.send(
            sender=event.created_by,
            recipient=recipient,
            verb='event_created',
            action_object=event,
            description=(
                f'Добавлено событие {event_scope}: "{event.title}" '
                f'({event.start_date.strftime("%d.%m.%Y")})'
            ),
            action_url=get_calendar_url(event),
            data={
                'title': 'Новое событие в календаре',
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


def notify_event_changed(event, changed_fields):
    """
    Отправляет уведомления об изменении события.
    """
    if not changed_fields:
        return
    
    recipients = get_event_recipients(event)
    
    # Формируем сообщение об изменениях
    field_names = {
        'title': 'название',
        'start_date': 'дата начала',
        'end_date': 'дата окончания',
        'start_time': 'время начала',
        'end_time': 'время окончания',
        'location': 'место проведения',
    }
    
    changes_text = ', '.join([
        field_names.get(f, f) for f in changed_fields
    ])
    
    for recipient in recipients:
        notify.send(
            sender=None,
            recipient=recipient,
            verb='event_changed',
            action_object=event,
            description=(
                f'Событие "{event.title}" изменено. '
                f'Изменения: {changes_text}'
            ),
            action_url=get_calendar_url(event),
            data={
                'title': 'Событие изменено',
                'event_id': event.id,
                'event_title': event.title,
                'changed_fields': changed_fields,
                'event_date': event.start_date.isoformat(),
                'department_id': (
                    event.department.id if event.department else None
                ),
            }
        )


def get_event_recipients(event):
    """
    Возвращает список получателей уведомлений для события.
    
    - Для события компании - все активные сотрудники
    - Для события отдела - сотрудники этого отдела
    - Для личного события - только владелец
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


def get_calendar_url(event):
    """
    Возвращает URL календаря.
    """
    return '/calendar'

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
from notifications.services import NotificationService

Employee = get_user_model()


@receiver(post_save, sender=CalendarEvent)
def create_event_notifications(sender, instance, created, **kwargs):
    """
    Создает уведомления при создании или изменении события.
    
    Уведомления отправляются:
    - При создании - всем сотрудникам компании или отдела
    - При изменении - участникам события
    """
    event = instance
    
    if created:
        # Новое событие - уведомляем всех участников
        notify_event_created(event)
    else:
        # Проверяем изменение ключевых полей
        if hasattr(event, '_changed_fields'):
            notify_event_changed(event, event._changed_fields)


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
    Создает уведомления при удалении (отмене) события.
    """
    event = instance
    
    # Определяем получателей
    recipients = get_event_recipients(event)
    
    # Создаем уведомления об отмене
    for recipient in recipients:
        NotificationService.create_notification_async(
            recipient=recipient,
            notification_type_code='event_cancelled',
            title='Событие отменено',
            message=(
                f'Событие "{event.title}" '
                f'({event.start_date.strftime("%d.%m.%Y")}) отменено'
            ),
            action_url=get_calendar_url(event),
            metadata={
                'event_title': event.title,
                'event_date': event.start_date.isoformat(),
                'department_id': (
                    event.department.id if event.department else None
                ),
                'is_company_event': event.is_company,
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
        NotificationService.create_notification_async(
            recipient=recipient,
            notification_type_code='event_created',
            title='Новое событие в календаре',
            message=(
                f'Добавлено событие {event_scope}: "{event.title}" '
                f'({event.start_date.strftime("%d.%m.%Y")})'
            ),
            content_object=event,
            action_url=get_calendar_url(event),
            metadata={
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
        NotificationService.create_notification_async(
            recipient=recipient,
            notification_type_code='event_changed',
            title='Событие изменено',
            message=(
                f'Событие "{event.title}" изменено. '
                f'Изменения: {changes_text}'
            ),
            content_object=event,
            action_url=get_calendar_url(event),
            metadata={
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
    Возвращает URL календаря в зависимости от типа события.
    Для всех типов событий используем параметр event_id для прямого открытия.
    """
    # Возвращаем главную страницу календаря с параметром event_id
    # Это позволит открыть модал события автоматически
    return f'/?event_id={event.id}'

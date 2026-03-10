"""
Django signals для автоматической генерации уведомлений в модуле Calendar.

Обрабатывает события:
- post_save для CalendarEvent - создание или изменение события
- pre_save для CalendarEvent - отслеживание изменений полей
- pre_delete для CalendarEvent - отмена (удаление) события
"""

from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver

from ..models import CalendarEvent
from .config import IMPORTANT_FIELDS
from .handlers import (
    notify_event_created,
    notify_event_changed,
    notify_event_cancelled,
)


@receiver(post_save, sender=CalendarEvent)
def create_event_notifications(sender, instance, created, **kwargs):
    """
    Создает уведомления при создании или изменении события.
    
    Уведомления отправляются:
    - При создании - всем сотрудникам компании или отдела
    - При изменении - участникам события (если изменились важные поля)
    
    Уведомления отправляются через универсальную систему
    channels.py → Celery → WebSocket/Email/Push
    """
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
    
    Сохраняет список изменённых полей в атрибут _changed_fields,
    который затем используется в post_save signal.
    """
    if instance.pk:
        try:
            old_event = CalendarEvent.objects.get(pk=instance.pk)
            changed_fields = []
            
            # Проверяем изменения важных полей
            for field in IMPORTANT_FIELDS:
                old_value = getattr(old_event, field)
                new_value = getattr(instance, field)
                if old_value != new_value:
                    changed_fields.append(field)
            
            instance._changed_fields = changed_fields
        except CalendarEvent.DoesNotExist:
            instance._changed_fields = []


@receiver(pre_delete, sender=CalendarEvent)
def notify_event_cancelled_signal(sender, instance, **kwargs):
    """
    Создает уведомления при удалении (отмене) события.
    
    Уведомления отправляются через универсальную систему
    channels.py → Celery → WebSocket/Email/Push
    """
    notify_event_cancelled(instance)

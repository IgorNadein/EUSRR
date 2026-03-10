"""
Django signals для автоматической генерации уведомлений для django-scheduler.

Обрабатывает события:
- post_save для schedule.Event - создание или изменение события
- pre_save для schedule.Event - отслеживание изменений полей
- pre_delete для schedule.Event - отмена (удаление) события
"""
import logging
from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='schedule.Event')
def create_event_notifications(sender, instance, created, **kwargs):
    """
    Создает уведомления при создании или изменении события.
    
    Уведомления отправляются:
    - При создании - всем участникам календаря (через CalendarRelation)
    - При изменении - участникам календаря (если изменились важные поля)
    """
    from .handlers import notify_event_created, notify_event_changed
    from .config import IMPORTANT_FIELDS
    
    try:
        if created:
            # Получаем создателя события из request (если доступен)
            creator = getattr(instance, '_creator', None)
            notify_event_created(instance, creator)
        else:
            # Проверяем изменения
            changed_fields = getattr(instance, '_changed_fields', [])
            if changed_fields:
                modifier = getattr(instance, '_modifier', None)
                notify_event_changed(instance, changed_fields, modifier)
    except Exception as e:
        logger.error(f"Ошибка в сигнале create_event_notifications: {e}", exc_info=True)


@receiver(pre_save, sender='schedule.Event')
def track_event_changes(sender, instance, **kwargs):
    """
    Отслеживает изменения важных полей события для уведомлений.
    
    Сохраняет список изменённых полей в атрибут _changed_fields,
    который затем используется в post_save signal.
    """
    from .config import IMPORTANT_FIELDS
    
    if instance.pk:
        try:
            from schedule.models import Event
            old_event = Event.objects.get(pk=instance.pk)
            changed_fields = []
            
            # Проверяем изменения важных полей
            for field in IMPORTANT_FIELDS:
                old_value = getattr(old_event, field, None)
                new_value = getattr(instance, field, None)
                if old_value != new_value:
                    changed_fields.append(field)
            
            instance._changed_fields = changed_fields
        except Exception as e:
            logger.error(f"Ошибка при отслеживании изменений события: {e}", exc_info=True)
            instance._changed_fields = []
    else:
        instance._changed_fields = []


@receiver(pre_delete, sender='schedule.Event')
def notify_event_cancelled_signal(sender, instance, **kwargs):
    """
    Создает уведомления при удалении (отмене) события.
    
    Уведомления отправляются всем участникам календаря.
    """
    from .handlers import notify_event_cancelled
    
    try:
        canceller = getattr(instance, '_canceller', None)
        notify_event_cancelled(instance, canceller)
    except Exception as e:
        logger.error(f"Ошибка в сигнале notify_event_cancelled_signal: {e}", exc_info=True)

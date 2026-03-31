"""
Бизнес-логика отправки уведомлений для django-scheduler.

Функции:
- get_event_recipients - определение получателей уведомлений
- notify_event_created - уведомление о новом событии
- notify_event_changed - уведомление об изменении события
- notify_event_cancelled - уведомление об отмене события
"""
import logging
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

logger = logging.getLogger(__name__)

Employee = get_user_model()


def get_event_recipients(event) -> list:
    """
    Возвращает список получателей уведомлений для события django-scheduler.

    Args:
        event: Объект schedule.Event

    Returns:
        list: Список пользователей (Employee) с доступом к календарю события
    """
    from schedule.models import CalendarRelation

    if not event.calendar:
        return []

    # Получаем всех пользователей с доступом к календарю
    user_ct = ContentType.objects.get_for_model(Employee)
    relations = CalendarRelation.objects.filter(
        calendar=event.calendar,
        content_type=user_ct,
        object_id__isnull=False
    )

    # Собираем активных пользователей
    user_ids = relations.values_list('object_id', flat=True)
    recipients = list(Employee.objects.filter(
        id__in=user_ids,
        is_active=True
    ))

    return recipients


def notify_event_created(event, creator=None):
    """
    Отправляет уведомления о новом событии всем участникам календаря.

    Args:
        event: Объект schedule.Event
        creator: Пользователь, создавший событие (исключается из получателей)
    """
    try:
        from notifications.signals import notify
        from .config import (
            NotificationVerbs, MessageTemplates, ActionURLs, format_date
        )

        recipients = get_event_recipients(event)

        # Исключаем создателя события
        if creator:
            recipients = [r for r in recipients if r.id != creator.id]

        if not recipients:
            return

        # Формируем сообщение
        event_date = format_date(event.start)
        calendar_name = event.calendar.name if event.calendar else None
        description = MessageTemplates.event_created(
            event.title,
            event_date,
            calendar_name
        )

        # Отправляем уведомления
        for recipient in recipients:
            notify.send(
                sender=creator,
                recipient=recipient,
                verb=NotificationVerbs.EVENT_CREATED,
                action_object=event,
                description=description,
                action_url=ActionURLs.CALENDAR,
                data={
                    'title': MessageTemplates.event_created_title(),
                    'event_id': event.id,
                    'event_title': event.title,
                    'event_start': (
                        event.start.isoformat() if event.start else None
                    ),
                    'calendar_id': (
                        event.calendar.id if event.calendar else None
                    ),
                    'calendar_name': calendar_name,
                    'creator_id': creator.id if creator else None,
                }
            )

        logger.info(
            f"Отправлены уведомления о создании события '{event.title}' "
            f"для {len(recipients)} получателей"
        )

    except Exception as e:
        logger.error(
            f"Ошибка при отправке уведомлений о создании события: {e}",
            exc_info=True
        )


def notify_event_changed(
    event,
    changed_fields: list[str] = None,
    modifier=None
):
    """
    Отправляет уведомления об изменении события.

    Args:
        event: Объект schedule.Event
        changed_fields: Список изменённых полей
        modifier: Пользователь, изменивший событие
    """
    try:
        from notifications.signals import notify
        from .config import (
            NotificationVerbs, MessageTemplates, ActionURLs, format_changes
        )

        recipients = get_event_recipients(event)

        # Исключаем модификатора
        if modifier:
            recipients = [r for r in recipients if r.id != modifier.id]

        if not recipients:
            return

        # Формируем сообщение об изменениях
        changes_text = format_changes(changed_fields) if changed_fields else None
        description = MessageTemplates.event_changed(event.title, changes_text)

        # Отправляем уведомления
        for recipient in recipients:
            notify.send(
                sender=modifier,
                recipient=recipient,
                verb=NotificationVerbs.EVENT_CHANGED,
                action_object=event,
                description=description,
                action_url=ActionURLs.CALENDAR,
                data={
                    'title': MessageTemplates.event_changed_title(),
                    'event_id': event.id,
                    'event_title': event.title,
                    'changed_fields': changed_fields,
                    'event_start': event.start.isoformat() if event.start else None,
                    'calendar_id': event.calendar.id if event.calendar else None,
                    'modifier_id': modifier.id if modifier else None,
                }
            )

        logger.info(
            f"Отправлены уведомления об изменении события '{
                event.title}' для {
                len(recipients)} получателей")

    except Exception as e:
        logger.error(
            f"Ошибка при отправке уведомлений об изменении события: {e}",
            exc_info=True)


def notify_event_cancelled(event, canceller=None):
    """
    Отправляет уведомления об отмене (удалении) события.

    Args:
        event: Объект schedule.Event
        canceller: Пользователь, отменивший событие
    """
    try:
        from notifications.signals import notify
        from .config import NotificationVerbs, MessageTemplates, ActionURLs, format_date

        recipients = get_event_recipients(event)

        # Исключаем отменившего
        if canceller:
            recipients = [r for r in recipients if r.id != canceller.id]

        if not recipients:
            return

        # Формируем сообщение
        event_date = format_date(event.start)
        description = MessageTemplates.event_cancelled(event.title, event_date)

        # Отправляем уведомления
        for recipient in recipients:
            notify.send(
                sender=canceller,
                recipient=recipient,
                verb=NotificationVerbs.EVENT_CANCELLED,
                description=description,
                action_url=ActionURLs.CALENDAR,
                data={
                    'title': MessageTemplates.event_cancelled_title(),
                    'event_id': event.id,
                    'event_title': event.title,
                    'event_start': event.start.isoformat() if event.start else None,
                    'calendar_id': event.calendar.id if event.calendar else None,
                    'canceller_id': canceller.id if canceller else None,
                }
            )

        logger.info(
            f"Отправлены уведомления об отмене события '{
                event.title}' для {
                len(recipients)} получателей")

    except Exception as e:
        logger.error(
            f"Ошибка при отправке уведомлений об отмене события: {e}",
            exc_info=True)

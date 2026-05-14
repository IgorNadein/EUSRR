"""Django signals для синхронизации дней рождений.

Интеграция выполняется с django-scheduler.

Использует Service Layer паттерн через django-service-objects.

Файл: employees/signals/birthday.py
"""

from __future__ import annotations

import logging

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from employees.constants import ACTIVATING_MARKER_ACTIONS, PERMANENT_ACTIONS
from employees.models import Employee
from employees.services import (
    UpsertBirthdayEventService,
    DeleteBirthdayEventService,
)


logger = logging.getLogger(__name__)


def _action_affects_birthday_sync(action: str | None) -> bool:
    return action in PERMANENT_ACTIONS or action in ACTIVATING_MARKER_ACTIONS


def _sync_birthday_for_employee_id(employee_id: int | None) -> None:
    if not employee_id:
        return
    employee = Employee.objects.filter(pk=employee_id).first()
    if not employee:
        return
    UpsertBirthdayEventService.execute({"employee": employee})


@receiver(post_save)
def sync_birthday_event_on_employee_save(sender, instance, created, **kwargs):
    """
    Автоматически создает/обновляет событие дня рождения
    при сохранении сотрудника.

    Использует Service Layer для инкапсуляции бизнес-логики.
    Подключается динамически в AppConfig.ready()
    только для Employee модели.
    """
    if sender._meta.label != "employees.Employee":
        return

    try:
        result = UpsertBirthdayEventService.execute({"employee": instance})

        if not result["success"]:
            logger.info(
                f"Событие дня рождения не создано для {instance}: {
                    result.get('reason')
                }"
            )
    except Exception as e:
        logger.error(
            f"Ошибка при синхронизации дня рождения для {instance}: {e}",
            exc_info=True,
        )


@receiver(pre_save)
def remember_employee_action_for_birthday_sync(sender, instance, **kwargs):
    """Запоминает прежнее кадровое действие перед изменением."""
    if sender._meta.label != "employees.EmployeeAction":
        return
    if not instance.pk:
        return

    previous = (
        sender.objects.filter(pk=instance.pk)
        .values("action", "employee_id")
        .first()
    )
    if not previous:
        return

    instance._birthday_previous_action = previous["action"]
    instance._birthday_previous_employee_id = previous["employee_id"]


@receiver(post_save)
def sync_birthday_event_on_employee_action_save(sender, instance, **kwargs):
    """
    Синхронизирует ДР при кадровых действиях, меняющих актуальность сотрудника.
    """
    if sender._meta.label != "employees.EmployeeAction":
        return

    employee_ids = set()
    if _action_affects_birthday_sync(instance.action):
        employee_ids.add(instance.employee_id)

    previous_action = getattr(instance, "_birthday_previous_action", None)
    if _action_affects_birthday_sync(previous_action):
        employee_ids.add(getattr(instance, "_birthday_previous_employee_id", None))

    for employee_id in employee_ids:
        try:
            _sync_birthday_for_employee_id(employee_id)
        except Exception as e:
            logger.error(
                f"Ошибка при синхронизации дня рождения после кадрового "
                f"события #{instance.pk}: {e}",
                exc_info=True,
            )


@receiver(post_delete)
def delete_birthday_event_on_employee_delete(sender, instance, **kwargs):
    """
    Удаляет событие дня рождения при удалении сотрудника.

    Использует Service Layer для инкапсуляции бизнес-логики.
    """
    if sender._meta.label != "employees.Employee":
        return

    try:
        result = DeleteBirthdayEventService.execute({"employee": instance})

        if result["success"]:
            logger.info(
                f"Удалено событий дня рождения для {instance}: {
                    result['deleted_count']
                }"
            )
    except Exception as e:
        logger.error(
            f"Ошибка при удалении дня рождения для {instance}: {e}",
            exc_info=True,
        )


@receiver(post_delete)
def sync_birthday_event_on_employee_action_delete(sender, instance, **kwargs):
    """Пересинхронизирует ДР после удаления статусного кадрового действия."""
    if sender._meta.label != "employees.EmployeeAction":
        return
    if not _action_affects_birthday_sync(instance.action):
        return

    try:
        _sync_birthday_for_employee_id(instance.employee_id)
    except Exception as e:
        logger.error(
            f"Ошибка при синхронизации дня рождения после удаления кадрового "
            f"события #{instance.pk}: {e}",
            exc_info=True,
        )

"""Django signals для синхронизации дней рождений.

Интеграция выполняется с django-scheduler.

Использует Service Layer паттерн через django-service-objects.

Файл: employees/signals/birthday.py
"""

from __future__ import annotations

import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from employees.services import (
    UpsertBirthdayEventService,
    DeleteBirthdayEventService,
)


logger = logging.getLogger(__name__)


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

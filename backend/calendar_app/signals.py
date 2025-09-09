# backend/calendar_app/signals.py
from __future__ import annotations

from datetime import date
from typing import Optional

from django.apps import apps as django_apps
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

from calendar_app.models import CalendarEvent, Recurrence


BIRTHDAY_COLOR = "#FFC107"  # опционально — визуальный цвет
BIRTHDAY_SOURCE_FMT = "employee:{id}:birthday"


def _get_employee_birthday(obj) -> Optional[date]:
    """Извлекает дату рождения сотрудника из популярных полей.

    Args:
        obj: Экземпляр модели сотрудника.

    Returns:
        Optional[date]: Дата рождения или None.

    Raises:
        AttributeError: Не выбрасывается наружу; поля проверяются безопасно.
    """
    for attr in ("birth_date", "date_of_birth", "birthday", "dob"):
        if hasattr(obj, attr):
            val = getattr(obj, attr)
            if isinstance(val, date):
                return val
    return None


def _get_employee_display_name(obj) -> str:
    """Возвращает человекочитаемое имя сотрудника.

    Порядок предпочтения:
    - метод get_full_name()
    - поля full_name / fio
    - first_name + last_name
    - __str__()

    Args:
        obj: Экземпляр модели сотрудника.

    Returns:
        str: Имя для заголовка события.
    """
    if hasattr(obj, "get_full_name") and callable(getattr(obj, "get_full_name")):
        name = obj.get_full_name()
        if name:
            return str(name)
    for attr in ("full_name", "fio"):
        if hasattr(obj, attr):
            val = getattr(obj, attr)
            if val:
                return str(val)
    first = getattr(obj, "first_name", "") or ""
    last = getattr(obj, "last_name", "") or ""
    name = f"{first} {last}".strip()
    return name or str(obj)


def _upsert_birthday_event(*, employee, birthday: Optional[date]) -> None:
    """Создаёт/обновляет/удаляет событие дня рождения сотрудника.

    Логика:
    - Если `birthday` задана → upsert глобального ежегодного события с source='employee:<id>:birthday'.
    - Если `birthday` = None → удаляем событие по этому source.

    Args:
        employee: Экземпляр сотрудника.
        birthday (Optional[date]): Дата рождения.

    Raises:
        ValueError: Если у сотрудника нет первичного ключа (не сохранён).
    """
    if not getattr(employee, "pk", None):
        raise ValueError("Сотрудник должен быть сохранён, чтобы синхронизировать событие.")

    source_key = BIRTHDAY_SOURCE_FMT.format(id=employee.pk)

    if not birthday:
        CalendarEvent.objects.filter(source=source_key).delete()
        return

    title = _("День рождения: {name}").format(name=_get_employee_display_name(employee))

    # all-day ежегодное событие компании: department=None
    defaults = {
        "title": title,
        "description": "",
        "start_date": birthday,
        "end_date": birthday,
        "start_time": None,
        "end_time": None,
        "all_day": True,
        "recurrence": Recurrence.ANNUAL,
        "color": BIRTHDAY_COLOR,
        "location": "",
        "department": None,
    }

    # upsert по source
    obj, created = CalendarEvent.objects.update_or_create(
        source=source_key,
        defaults=defaults,
    )
    # Если человек переименован — при следующем save заголовок обновится
    # через defaults с update_or_create.


@receiver(post_save)
def handle_employee_saved(sender, instance, created, **kwargs):
    """Реакция на сохранение сотрудника — синхронизация события дня рождения.

    Подключается динамически из AppConfig.ready(), только для модели employees.Employee.

    Args:
        sender: Класс модели (ожидается Employee).
        instance: Сохранённый сотрудник.
        created (bool): True при создании, False при обновлении.
    """
    # Ограничим обработку только моделью Employee (см. apps.py)
    if sender._meta.label != "employees.Employee":
        return

    birthday = _get_employee_birthday(instance)

    # Внутри транзакции БД, чтобы не получить "призрачные" записи
    with transaction.atomic():
        _upsert_birthday_event(employee=instance, birthday=birthday)


@receiver(post_delete)
def handle_employee_deleted(sender, instance, **kwargs):
    """Удаляет календарное событие дня рождения при удалении сотрудника.

    Подключается динамически из AppConfig.ready(), только для модели employees.Employee.

    Args:
        sender: Класс модели (ожидается Employee).
        instance: Удалённый сотрудник.
    """
    if sender._meta.label != "employees.Employee":
        return

    source_key = BIRTHDAY_SOURCE_FMT.format(id=getattr(instance, "pk", None))
    if source_key:
        CalendarEvent.objects.filter(source=source_key).delete()

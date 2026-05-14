"""
Сервисы для работы с событиями дней рождений сотрудников.
Использует паттерн Service Layer через django-service-objects.
"""

import calendar as calendar_lib
from datetime import datetime, timedelta

from django.utils import timezone
from service_objects.services import Service
from service_objects.fields import ModelField

from employees.models import Employee
from schedule.models import Calendar, Event, Rule

# Константы
BIRTHDAY_COLOR = "#FFC107"  # Жёлтый/золотой цвет для дней рождения
BIRTHDAY_TITLE_PREFIX = "🎂 День рождения:"


def birthday_event_queryset(employee: Employee):
    """События дня рождения, связанные с сотрудником."""
    return Event.objects.filter(
        creator_id=employee.pk, title__startswith=BIRTHDAY_TITLE_PREFIX
    )


class UpsertBirthdayEventService(Service):
    """
    Сервис создания/обновления события дня рождения сотрудника.

    Использует паттерн External ID: creator_id + title для идентификации.
    Создает ежегодное повторяющееся событие в общем календаре "🎂 Дни рождения".
    """

    employee = ModelField(Employee)

    def process(self):
        employee = self.cleaned_data["employee"]

        should_have_event, reason = self._should_have_birthday_event(employee)
        if not should_have_event:
            deleted_count, _ = birthday_event_queryset(employee).delete()
            return {
                "success": False,
                "reason": reason,
                "event": None,
                "deleted_count": deleted_count,
            }

        # Получаем общий календарь дней рождений
        birthday_calendar = self._get_or_create_birthday_calendar()

        # Создаем или обновляем событие
        event, created = self._upsert_birthday_event(
            employee, birthday_calendar
        )

        return {"success": True, "event": event, "created": created}

    def _should_have_birthday_event(self, employee: Employee) -> tuple[bool, str | None]:
        """Проверить, должен ли сотрудник попадать в календарь ДР."""
        if not employee.birth_date:
            return False, "no_birth_date"
        if not employee.email_verified:
            return False, "email_not_verified"
        if not employee.is_active:
            return False, "not_active"
        if not employee.is_actually_active:
            return False, "not_actually_active"
        return True, None

    def _get_or_create_birthday_calendar(self) -> Calendar:
        """Получить или создать общий календарь дней рождений."""
        # TODO: отдельно настроить доступность календаря birthdays через
        # CalendarRelation/CalendarBinding для обычных пользователей.
        calendar, created = Calendar.objects.get_or_create(
            slug="birthdays", defaults={"name": "🎂 Дни рождения"}
        )

        return calendar

    def _upsert_birthday_event(
        self, employee: Employee, calendar: Calendar
    ) -> tuple[Event, bool]:
        """Создать или обновить событие дня рождения.

        Возвращает (event, created).
        """
        title = f"{BIRTHDAY_TITLE_PREFIX} {str(employee)}"

        # Ищем существующее событие по creator + начало title
        # (паттерн External ID).
        # НЕ фильтруем по календарю, чтобы найти старые события в персональных
        # календарях
        existing_event = birthday_event_queryset(employee).first()

        # Создаем правило для ежегодного повторения
        rule = self._get_or_create_yearly_rule()

        # Вычисляем даты для текущего года
        current_year = timezone.now().year
        start_date = self._birthday_start_for_year(employee, current_year)

        # Делаем aware ПЕРЕД вычислением end_date
        if timezone.is_naive(start_date):
            start_date = timezone.make_aware(start_date)

        # Теперь добавляем timedelta к уже aware datetime
        end_date = start_date + timedelta(hours=23, minutes=59, seconds=59)

        if existing_event:
            # Обновляем существующее событие и переносим в правильный календарь
            existing_event.title = title
            existing_event.start = start_date
            existing_event.end = end_date
            existing_event.calendar = (
                calendar  # Переносим в общий календарь birthdays
            )
            existing_event.rule = rule
            existing_event.end_recurring_period = None  # Бесконечное повторение
            existing_event.color_event = BIRTHDAY_COLOR
            existing_event.save()

            # Удаляем дубликаты (другие события ДР этого сотрудника)
            birthday_event_queryset(employee).exclude(pk=existing_event.pk).delete()

            return existing_event, False  # Обновлено
        else:
            # Создаем новое событие
            event = Event.objects.create(
                title=title,
                start=start_date,
                end=end_date,
                calendar=calendar,
                creator_id=employee.pk,
                rule=rule,
                end_recurring_period=None,  # Бесконечное повторение
                color_event=BIRTHDAY_COLOR,
                description=f"Автоматическое событие: день рождения {
                    str(employee)
                }",
            )
            return event, True  # Создано

    def _birthday_start_for_year(self, employee: Employee, year: int) -> datetime:
        """Дата события в конкретном году с fallback для 29 февраля."""
        birth_date = employee.birth_date
        month = birth_date.month
        day = birth_date.day
        if month == 2 and day == 29 and not calendar_lib.isleap(year):
            day = 28

        return datetime(
            year=year,
            month=month,
            day=day,
            hour=0,
            minute=0,
            second=0,
        )

    def _get_or_create_yearly_rule(self) -> Rule:
        """Получить или создать правило для ежегодного повторения."""
        rule, created = Rule.objects.get_or_create(
            name="Ежегодно",
            defaults={
                "description": "Повторять каждый год",
                "frequency": "YEARLY",
                "params": "",  # Дефолтные параметры
            },
        )
        return rule


class DeleteBirthdayEventService(Service):
    """
    Сервис удаления события дня рождения сотрудника.

    Использует паттерн External ID для поиска события.
    """

    employee = ModelField(Employee)

    def process(self):
        employee = self.cleaned_data["employee"]

        # Ищем событие по creator + паттерн title
        deleted_count, _ = birthday_event_queryset(employee).delete()

        return {"success": deleted_count > 0, "deleted_count": deleted_count}


class BulkSyncBirthdaysService(Service):
    """
    Сервис массовой синхронизации дней рождений всех сотрудников.

    Используется для миграции и периодической синхронизации.
    """

    def process(self):
        employees = Employee.objects.all().select_related()

        results = {
            "total": 0,
            "created": 0,
            "updated": 0,
            "deleted": 0,
            "skipped": 0,
            "errors": [],
        }

        for employee in employees:
            results["total"] += 1
            try:
                result = UpsertBirthdayEventService.execute(
                    {"employee": employee}
                )

                if result["success"]:
                    if result.get("created"):
                        results["created"] += 1
                    else:
                        results["updated"] += 1
                elif result.get("deleted_count", 0):
                    results["deleted"] += result["deleted_count"]
                else:
                    results["skipped"] += 1
            except Exception as e:
                results["errors"].append(
                    {"employee_id": employee.pk, "error": str(e)}
                )

        return results

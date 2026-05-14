from __future__ import annotations

from datetime import date, datetime, timedelta
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from schedule.models import Calendar, Event

from employees.constants import ACTION_DISMISSED, ACTION_REHIRED
from employees.models import EmployeeAction
from employees.services import BulkSyncBirthdaysService, UpsertBirthdayEventService
from employees.services.birthday_events import (
    BIRTHDAY_COLOR,
    BIRTHDAY_TITLE_PREFIX,
)

pytestmark = pytest.mark.django_db


def _birthday_events(employee):
    return Event.objects.filter(
        creator_id=employee.pk,
        title__startswith=BIRTHDAY_TITLE_PREFIX,
    )


def _make_stale_birthday_event(employee):
    calendar, _ = Calendar.objects.get_or_create(
        slug="birthdays",
        defaults={"name": "🎂 Дни рождения"},
    )
    start = timezone.now()
    return Event.objects.create(
        title=f"{BIRTHDAY_TITLE_PREFIX} {employee}",
        start=start,
        end=start + timedelta(hours=1),
        calendar=calendar,
        creator=employee,
        color_event=BIRTHDAY_COLOR,
    )


def _run_sync_birthdays(**options):
    output = StringIO()
    call_command("sync_birthdays", stdout=output, **options)
    return output.getvalue()


def _aware_datetime(year: int, month: int, day: int):
    return timezone.make_aware(datetime(year, month, day, 12))


def _local_start(event):
    return timezone.localtime(event.start)


def _local_end(event):
    return timezone.localtime(event.end)


def test_birthday_event_created_for_actual_employee(user_factory):
    employee = user_factory(
        first_name="Иван",
        last_name="Петров",
        birth_date=date(1990, 5, 6),
    )

    event = _birthday_events(employee).get()

    assert event.calendar.slug == "birthdays"
    assert event.title == f"{BIRTHDAY_TITLE_PREFIX} Петров Иван"
    assert _local_start(event).month == 5
    assert _local_start(event).day == 6
    assert _local_end(event).hour == 23
    assert _local_end(event).minute == 59
    assert event.rule.frequency == "YEARLY"
    assert event.end_recurring_period is None
    assert event.color_event == BIRTHDAY_COLOR


def test_birthday_event_moves_when_birth_date_changes(user_factory):
    employee = user_factory(birth_date=date(1990, 5, 6))
    original_event_id = _birthday_events(employee).get().id

    employee.birth_date = date(1990, 7, 8)
    employee.save(update_fields=["birth_date"])

    event = _birthday_events(employee).get()
    assert event.id == original_event_id
    assert _local_start(event).month == 7
    assert _local_start(event).day == 8


def test_birthday_event_deleted_when_birth_date_is_cleared(user_factory):
    employee = user_factory(birth_date=date(1990, 5, 6))
    assert _birthday_events(employee).exists()

    employee.birth_date = None
    employee.save(update_fields=["birth_date"])

    assert not _birthday_events(employee).exists()


def test_birthday_event_created_only_after_employee_becomes_actual(user_factory):
    employee = user_factory(
        verified=False,
        active=False,
        birth_date=date(1990, 5, 6),
    )
    assert not _birthday_events(employee).exists()

    employee.email_verified = True
    employee.is_active = True
    employee.save(update_fields=["email_verified", "is_active"])

    assert _birthday_events(employee).count() == 1


def test_birthday_event_deleted_when_employee_is_dismissed(user_factory):
    employee = user_factory(birth_date=date(1990, 5, 6))
    assert _birthday_events(employee).exists()

    EmployeeAction.objects.create(
        employee=employee,
        action=ACTION_DISMISSED,
        date=timezone.now(),
    )

    assert not _birthday_events(employee).exists()


def test_birthday_event_recreated_when_employee_is_rehired(user_factory):
    employee = user_factory(birth_date=date(1990, 5, 6))
    now = timezone.now()
    EmployeeAction.objects.create(
        employee=employee,
        action=ACTION_DISMISSED,
        date=now,
    )
    assert not _birthday_events(employee).exists()

    EmployeeAction.objects.create(
        employee=employee,
        action=ACTION_REHIRED,
        date=now + timedelta(seconds=1),
    )

    assert _birthday_events(employee).count() == 1


def test_leap_day_birthday_uses_february_28_in_non_leap_year(user_factory):
    employee = user_factory(birth_date=date(1988, 2, 29))

    with patch(
        "employees.services.birthday_events.timezone.now",
        return_value=_aware_datetime(2026, 1, 1),
    ):
        UpsertBirthdayEventService.execute({"employee": employee})

    event = _birthday_events(employee).get()
    assert _local_start(event).month == 2
    assert _local_start(event).day == 28


def test_leap_day_birthday_uses_february_29_in_leap_year(user_factory):
    employee = user_factory(birth_date=date(1988, 2, 29))

    with patch(
        "employees.services.birthday_events.timezone.now",
        return_value=_aware_datetime(2028, 1, 1),
    ):
        UpsertBirthdayEventService.execute({"employee": employee})

    event = _birthday_events(employee).get()
    assert _local_start(event).month == 2
    assert _local_start(event).day == 29


def test_bulk_sync_deletes_stale_events_and_skips_inactual_employees(
    user_factory,
):
    active = user_factory(birth_date=date(1990, 5, 6))
    without_birth_date = user_factory(birth_date=None)
    dismissed = user_factory(birth_date=date(1991, 7, 8))
    EmployeeAction.objects.create(
        employee=dismissed,
        action=ACTION_DISMISSED,
        date=timezone.now(),
    )

    _make_stale_birthday_event(without_birth_date)
    _make_stale_birthday_event(dismissed)

    result = BulkSyncBirthdaysService.execute({})

    assert _birthday_events(active).count() == 1
    assert not _birthday_events(without_birth_date).exists()
    assert not _birthday_events(dismissed).exists()
    assert result["deleted"] >= 2


def test_sync_birthdays_command_removes_dismissed_employee_stale_event(
    user_factory,
):
    employee = user_factory(birth_date=date(1990, 5, 6))
    EmployeeAction.objects.create(
        employee=employee,
        action=ACTION_DISMISSED,
        date=timezone.now(),
    )
    stale_event = _make_stale_birthday_event(employee)
    assert _birthday_events(employee).filter(pk=stale_event.pk).exists()

    output = _run_sync_birthdays()

    assert not _birthday_events(employee).exists()
    assert "Обработано сотрудников: 1" in output
    assert "Удалено устаревших событий: 1" in output
    assert "Синхронизация завершена успешно" in output


def test_sync_birthdays_command_dry_run_keeps_dismissed_stale_event(
    user_factory,
):
    employee = user_factory(birth_date=date(1990, 5, 6))
    EmployeeAction.objects.create(
        employee=employee,
        action=ACTION_DISMISSED,
        date=timezone.now(),
    )
    stale_event = _make_stale_birthday_event(employee)

    output = _run_sync_birthdays(dry_run=True)

    assert _birthday_events(employee).filter(pk=stale_event.pk).exists()
    assert "DRY-RUN режим" in output
    assert "Удалено устаревших событий: 1" in output
    assert "Изменения НЕ применены" in output


def test_sync_birthdays_command_handles_mixed_employee_states(user_factory):
    active_missing = user_factory(birth_date=date(1990, 5, 6))
    _birthday_events(active_missing).delete()

    active_outdated = user_factory(birth_date=date(1991, 7, 8))
    outdated_event = _birthday_events(active_outdated).get()
    outdated_event.start = timezone.make_aware(datetime(2026, 1, 1, 12))
    outdated_event.end = timezone.make_aware(datetime(2026, 1, 1, 13))
    outdated_event.color_event = "#000000"
    outdated_event.save()
    duplicate_event = _make_stale_birthday_event(active_outdated)

    without_birth_date = user_factory(birth_date=None)
    _make_stale_birthday_event(without_birth_date)

    inactive = user_factory(active=False, birth_date=date(1992, 8, 9))
    _make_stale_birthday_event(inactive)

    unverified = user_factory(verified=False, birth_date=date(1993, 9, 10))
    _make_stale_birthday_event(unverified)

    dismissed = user_factory(birth_date=date(1994, 10, 11))
    EmployeeAction.objects.create(
        employee=dismissed,
        action=ACTION_DISMISSED,
        date=timezone.now(),
    )
    _make_stale_birthday_event(dismissed)

    output = _run_sync_birthdays()

    assert _birthday_events(active_missing).count() == 1

    updated_event = _birthday_events(active_outdated).get()
    assert updated_event.pk == outdated_event.pk
    assert not Event.objects.filter(pk=duplicate_event.pk).exists()
    assert _local_start(updated_event).month == 7
    assert _local_start(updated_event).day == 8
    assert updated_event.color_event == BIRTHDAY_COLOR

    assert not _birthday_events(without_birth_date).exists()
    assert not _birthday_events(inactive).exists()
    assert not _birthday_events(unverified).exists()
    assert not _birthday_events(dismissed).exists()

    assert "Обработано сотрудников: 6" in output
    assert "Создано событий: 1" in output
    assert "Обновлено событий: 1" in output
    assert "Удалено устаревших событий: 4" in output


def test_profile_patch_moves_birthday_event(api_client, user_factory):
    employee = user_factory(birth_date=date(1990, 5, 6))
    api_client.force_authenticate(user=employee)

    response = api_client.patch(
        reverse("api:v1:employees-me"),
        {
            "first_name": employee.first_name,
            "last_name": employee.last_name,
            "patronymic": employee.patronymic,
            "birth_date": "1990-09-10",
        },
        format="json",
    )

    assert response.status_code == 200
    event = _birthday_events(employee).get()
    assert _local_start(event).month == 9
    assert _local_start(event).day == 10


def test_profile_patch_null_birth_date_deletes_birthday_event(
    api_client,
    user_factory,
):
    employee = user_factory(birth_date=date(1990, 5, 6))
    assert _birthday_events(employee).exists()
    api_client.force_authenticate(user=employee)

    response = api_client.patch(
        reverse("api:v1:employees-me"),
        {
            "first_name": employee.first_name,
            "last_name": employee.last_name,
            "patronymic": employee.patronymic,
            "birth_date": None,
        },
        format="json",
    )

    assert response.status_code == 200
    assert not _birthday_events(employee).exists()

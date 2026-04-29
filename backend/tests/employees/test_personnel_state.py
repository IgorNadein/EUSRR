from datetime import date

import pytest
from django.utils import timezone

from employees.constants import (
    ACTION_DISMISSED,
    ACTION_HIRED,
    ACTION_ON_DAY_OFF,
    ACTION_ON_LEAVE,
    ACTION_ON_SICK_LEAVE,
    ACTION_REHIRED,
    ACTION_REMOTE,
    ACTION_RETURNED_FROM_LEAVE,
    ACTION_WORKING,
)
from employees.models import EmployeeAction
from employees.services.personnel_state import (
    PERSONNEL_STATUS_NORMAL,
    resolve_employee_personnel_state,
)

pytestmark = pytest.mark.django_db


def _aware_datetime(year: int, month: int, day: int):
    return timezone.make_aware(timezone.datetime(year, month, day, 12))


def test_permanent_working_state_expects_attendance(user_factory):
    employee = user_factory()
    working = EmployeeAction.objects.create(
        employee=employee,
        action=ACTION_WORKING,
        date=_aware_datetime(2026, 4, 10),
    )

    state = resolve_employee_personnel_state(employee, date(2026, 4, 20))

    assert state.status == ACTION_WORKING
    assert state.action_id == working.id
    assert state.expects_attendance is True


def test_no_actions_falls_back_to_normal_state(user_factory):
    employee = user_factory()
    EmployeeAction.objects.filter(employee=employee).delete()

    state = resolve_employee_personnel_state(employee, date(2026, 4, 20))

    assert state.status == PERSONNEL_STATUS_NORMAL
    assert state.expects_attendance is True


def test_temporary_interval_is_active_until_date_to(user_factory):
    employee = user_factory()
    leave = EmployeeAction.objects.create(
        employee=employee,
        action=ACTION_ON_LEAVE,
        date=_aware_datetime(2026, 4, 20),
        date_to=date(2026, 4, 22),
    )

    state = resolve_employee_personnel_state(employee, date(2026, 4, 21))

    assert state.status == ACTION_ON_LEAVE
    assert state.action_id == leave.id
    assert state.date_to == date(2026, 4, 22)
    assert state.expects_attendance is False


def test_temporary_interval_ends_after_date_to(user_factory):
    employee = user_factory()
    EmployeeAction.objects.create(
        employee=employee,
        action=ACTION_ON_LEAVE,
        date=_aware_datetime(2026, 4, 20),
        date_to=date(2026, 4, 22),
    )

    state = resolve_employee_personnel_state(employee, date(2026, 4, 23))

    assert state.status == ACTION_WORKING
    assert state.expects_attendance is True


def test_temporary_without_date_to_is_one_day_legacy_fallback(user_factory):
    employee = user_factory()
    EmployeeAction.objects.create(
        employee=employee,
        action=ACTION_ON_LEAVE,
        date=_aware_datetime(2026, 4, 20),
    )
    EmployeeAction.objects.create(
        employee=employee,
        action=ACTION_RETURNED_FROM_LEAVE,
        date=_aware_datetime(2026, 4, 23),
    )

    active = resolve_employee_personnel_state(employee, date(2026, 4, 20))
    ended = resolve_employee_personnel_state(employee, date(2026, 4, 21))
    returned = resolve_employee_personnel_state(employee, date(2026, 4, 23))

    assert active.status == ACTION_ON_LEAVE
    assert active.date_to == date(2026, 4, 20)
    assert ended.status == ACTION_WORKING
    assert returned.status == ACTION_RETURNED_FROM_LEAVE
    assert returned.expects_attendance is True


def test_marker_action_is_one_day_status(user_factory):
    employee = user_factory()
    hired = EmployeeAction.objects.create(
        employee=employee,
        action=ACTION_HIRED,
        date=_aware_datetime(2026, 4, 20),
    )

    marker = resolve_employee_personnel_state(employee, date(2026, 4, 20))
    fallback = resolve_employee_personnel_state(employee, date(2026, 4, 21))

    assert marker.status == ACTION_HIRED
    assert marker.action_id == hired.id
    assert marker.expects_attendance is True
    assert fallback.status == ACTION_WORKING


def test_rehire_restores_previous_permanent_state_after_dismissal(user_factory):
    employee = user_factory()
    remote = EmployeeAction.objects.create(
        employee=employee,
        action=ACTION_REMOTE,
        date=_aware_datetime(2026, 4, 10),
    )
    dismissed = EmployeeAction.objects.create(
        employee=employee,
        action=ACTION_DISMISSED,
        date=_aware_datetime(2026, 4, 12),
    )
    rehire = EmployeeAction.objects.create(
        employee=employee,
        action=ACTION_REHIRED,
        date=_aware_datetime(2026, 4, 15),
    )

    dismissed_state = resolve_employee_personnel_state(employee, date(2026, 4, 13))
    rehire_state = resolve_employee_personnel_state(employee, date(2026, 4, 15))
    restored_state = resolve_employee_personnel_state(employee, date(2026, 4, 16))

    assert dismissed_state.status == ACTION_DISMISSED
    assert dismissed_state.action_id == dismissed.id
    assert rehire_state.status == ACTION_REHIRED
    assert rehire_state.action_id == rehire.id
    assert rehire_state.expects_attendance is True
    assert restored_state.status == ACTION_REMOTE
    assert restored_state.action_id == remote.id


def test_overlapping_temporary_intervals_use_priority(user_factory):
    employee = user_factory()
    EmployeeAction.objects.create(
        employee=employee,
        action=ACTION_ON_LEAVE,
        date=_aware_datetime(2026, 4, 20),
        date_to=date(2026, 4, 25),
    )
    sick = EmployeeAction.objects.create(
        employee=employee,
        action=ACTION_ON_SICK_LEAVE,
        date=_aware_datetime(2026, 4, 21),
        date_to=date(2026, 4, 22),
    )
    EmployeeAction.objects.create(
        employee=employee,
        action=ACTION_ON_DAY_OFF,
        date=_aware_datetime(2026, 4, 21),
        date_to=date(2026, 4, 21),
    )

    state = resolve_employee_personnel_state(employee, date(2026, 4, 21))

    assert state.status == ACTION_ON_SICK_LEAVE
    assert state.action_id == sick.id


def test_dismissal_overrides_temporary_interval(user_factory):
    employee = user_factory()
    EmployeeAction.objects.create(
        employee=employee,
        action=ACTION_ON_LEAVE,
        date=_aware_datetime(2026, 4, 20),
        date_to=date(2026, 4, 25),
    )
    dismissed = EmployeeAction.objects.create(
        employee=employee,
        action=ACTION_DISMISSED,
        date=_aware_datetime(2026, 4, 21),
    )

    state = resolve_employee_personnel_state(employee, date(2026, 4, 22))

    assert state.status == ACTION_DISMISSED
    assert state.action_id == dismissed.id
    assert state.expects_attendance is False

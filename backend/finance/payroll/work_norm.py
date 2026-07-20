from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from attendance.services import (
    get_employee_work_schedule_payload,
    get_standard_work_schedule,
    get_standard_work_schedule_payload,
)
from employees.services.personnel_state import resolve_employee_personnel_state

from finance.models import PayrollPeriod, PayrollWorkSettings

QUANTUM = Decimal("0.0001")
WEEKDAY_NAMES = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


def resolve_employee_schedule(employee) -> tuple[dict, str]:
    individual = get_employee_work_schedule_payload(employee)
    if individual is not None:
        return individual, "individual_schedule"
    standard = get_standard_work_schedule()
    if standard is not None:
        return standard.to_logstorm_payload(), "standard_schedule"
    return get_standard_work_schedule_payload(), "default_schedule"


def _override_date(value) -> date | None:
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def period_workdates(period: PayrollPeriod, schedule: dict) -> list[date]:
    workdays = set(schedule.get("workdays") or WEEKDAY_NAMES[:5])
    overrides = {}
    for item in schedule.get("date_overrides") or []:
        if not isinstance(item, dict):
            continue
        override_date = _override_date(item.get("date"))
        if override_date is not None and "is_workday" in item:
            overrides[override_date] = bool(item["is_workday"])

    dates = []
    current = period.date_from
    while current <= period.date_to:
        is_workday = current.weekday() < len(WEEKDAY_NAMES) and (
            WEEKDAY_NAMES[current.weekday()] in workdays
        )
        if overrides.get(current, is_workday):
            dates.append(current)
        current += timedelta(days=1)
    return dates


def count_period_workdays(period: PayrollPeriod, schedule: dict) -> int:
    return len(period_workdates(period, schedule))


def calculate_period_target_points(
    period: PayrollPeriod,
    *,
    employee,
    daily_target_points: Decimal | None = None,
    schedule: dict | None = None,
) -> tuple[Decimal, int, str]:
    if schedule is None:
        schedule, source = resolve_employee_schedule(employee)
    else:
        source = "schedule"
    daily_target = (
        daily_target_points
        if daily_target_points is not None
        else PayrollWorkSettings.get_daily_target_points()
    )
    workdays_count = count_period_workdays(period, schedule)
    target_points = (daily_target * workdays_count).quantize(QUANTUM)
    return target_points, workdays_count, source


def calculate_period_personnel_points(
    period: PayrollPeriod,
    *,
    employee,
    actions,
    daily_target_points: Decimal | None = None,
    schedule: dict | None = None,
) -> tuple[Decimal, int]:
    """Project points from the work calendar and official personnel events.

    A scheduled day is treated as attended unless the personnel state explicitly
    says that attendance is not expected (leave, sick leave, day off, maternity
    leave or dismissal). The result is a read-only projection and is not stored
    in payroll models.
    """

    if schedule is None:
        schedule, _ = resolve_employee_schedule(employee)
    daily_target = (
        daily_target_points
        if daily_target_points is not None
        else PayrollWorkSettings.get_daily_target_points()
    )
    attended_dates = [
        workdate
        for workdate in period_workdates(period, schedule)
        if resolve_employee_personnel_state(
            employee,
            workdate,
            actions=actions,
        ).expects_attendance
    ]
    points = (daily_target * len(attended_dates)).quantize(QUANTUM)
    return points, len(attended_dates)

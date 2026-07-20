from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from attendance.services import (
    get_employee_work_schedule_payload,
    get_standard_work_schedule,
    get_standard_work_schedule_payload,
)

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


def count_period_workdays(period: PayrollPeriod, schedule: dict) -> int:
    workdays = set(schedule.get("workdays") or WEEKDAY_NAMES[:5])
    overrides = {}
    for item in schedule.get("date_overrides") or []:
        if not isinstance(item, dict):
            continue
        override_date = _override_date(item.get("date"))
        if override_date is not None and "is_workday" in item:
            overrides[override_date] = bool(item["is_workday"])

    total = 0
    current = period.date_from
    while current <= period.date_to:
        is_workday = current.weekday() < len(WEEKDAY_NAMES) and (
            WEEKDAY_NAMES[current.weekday()] in workdays
        )
        total += int(overrides.get(current, is_workday))
        current += timedelta(days=1)
    return total


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

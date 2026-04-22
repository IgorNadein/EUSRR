"""Helpers for building EUSRR -> LogStorm attendance requests."""

from datetime import date
from typing import Any, Optional

from employees.models import Employee

from common.logstorm_client import LogStormClient


DEFAULT_WORKDAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
]


def build_logstorm_attendance_payload(
    *,
    employee: Employee,
    period_start: date,
    period_end: date,
    schedule: Optional[dict[str, Any]] = None,
    date_overrides: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """
    Build a LogStorm attendance analysis payload.

    If schedule is omitted, the payload intentionally omits it so LogStorm can
    apply its configured default schedule or reject the request by policy.
    """
    payload = {
        "employee_id": str(employee.id),
        "display_name": _employee_display_name(employee),
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
    }

    if schedule is not None:
        payload["schedule"] = normalize_logstorm_schedule(
            schedule,
            date_overrides=date_overrides,
        )

    return payload


def normalize_logstorm_schedule(
    schedule: dict[str, Any],
    *,
    date_overrides: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    return {
        "start_time": schedule["start_time"],
        "end_time": schedule["end_time"],
        "expected_hours": schedule["expected_hours"],
        "workdays": schedule.get("workdays", DEFAULT_WORKDAYS),
        "date_overrides": [
            _normalize_date_override(override)
            for override in (
                date_overrides
                if date_overrides is not None
                else schedule.get("date_overrides", [])
            )
        ],
    }


def analyze_employee_attendance(
    *,
    employee: Employee,
    period_start: date,
    period_end: date,
    schedule: Optional[dict[str, Any]] = None,
    date_overrides: Optional[list[dict[str, Any]]] = None,
    client: Optional[LogStormClient] = None,
) -> dict[str, Any]:
    payload = build_logstorm_attendance_payload(
        employee=employee,
        period_start=period_start,
        period_end=period_end,
        schedule=schedule,
        date_overrides=date_overrides,
    )
    return (client or LogStormClient()).analyze_attendance(payload)


def _normalize_date_override(override: dict[str, Any]) -> dict[str, Any]:
    result = {
        "date": _format_date(override["date"]),
        "is_workday": bool(override["is_workday"]),
    }
    for key in ("reason", "start_time", "end_time", "expected_hours"):
        if key in override and override[key] is not None:
            result[key] = override[key]
    return result


def _format_date(value: Any) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _employee_display_name(employee: Employee) -> str:
    full_name = employee.get_full_name().strip()
    return full_name or str(employee)

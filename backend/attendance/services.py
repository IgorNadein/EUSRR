from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from calendar import monthrange
from typing import Any

from django.db import transaction
from django.utils.dateparse import parse_date

from attendance.models import (
    AttendanceAnalysisRun,
    AttendanceRecord,
    EmployeeWorkSchedule,
)
from employees.constants import (
    ACTION_DISMISSED,
    ACTION_ON_DAY_OFF,
    ACTION_ON_LEAVE,
    ACTION_ON_MATERNITY,
    ACTION_ON_SICK_LEAVE,
)
from employees.models import Employee

PERSONNEL_STATUS_NORMAL = "normal"

MONTHS_RU = {
    1: "Январь",
    2: "Февраль",
    3: "Март",
    4: "Апрель",
    5: "Май",
    6: "Июнь",
    7: "Июль",
    8: "Август",
    9: "Сентябрь",
    10: "Октябрь",
    11: "Ноябрь",
    12: "Декабрь",
}

DAYS_RU = {
    0: "Пн",
    1: "Вт",
    2: "Ср",
    3: "Чт",
    4: "Пт",
    5: "Сб",
    6: "Вс",
}

NON_WORKING_PERSONNEL_ACTIONS = {
    ACTION_ON_LEAVE,
    ACTION_ON_SICK_LEAVE,
    ACTION_ON_DAY_OFF,
    ACTION_ON_MATERNITY,
    ACTION_DISMISSED,
}

SUPPRESSED_EMPLOYEE_ISSUE_MARKERS = (
    "absence",
    "absent",
    "late",
    "early",
    "underwork",
    "отсутств",
    "опозд",
    "ранн",
    "недоработ",
)

DEFAULT_WORK_SCHEDULE_PAYLOAD = {
    "start_time": "08:00",
    "end_time": "17:00",
    "expected_hours": 9,
    "workdays": list(EmployeeWorkSchedule.DEFAULT_WORKDAYS),
    "date_overrides": [],
}


@dataclass(frozen=True)
class PersonnelDayState:
    status: str = PERSONNEL_STATUS_NORMAL
    label: str = ""
    action_id: int | None = None
    is_non_working: bool = False


def save_logstorm_attendance_result(
    *,
    employee: Employee,
    period_start: date,
    period_end: date,
    request_payload: dict[str, Any],
    response_payload: dict[str, Any],
    schedule_payload: dict[str, Any] | None = None,
    triggered_by: Employee | None = None,
) -> AttendanceAnalysisRun:
    records = response_payload.get("records")
    if not isinstance(records, list):
        records = []

    personnel_actions = list(
        employee.actions.filter(date__date__lte=period_end).order_by("date", "id")
    )

    with transaction.atomic():
        run = AttendanceAnalysisRun.objects.create(
            employee=employee,
            period_start=period_start,
            period_end=period_end,
            status=AttendanceAnalysisRun.STATUS_SUCCESS,
            schedule_payload=schedule_payload,
            request_payload=request_payload,
            response_payload=response_payload,
            triggered_by=triggered_by
            if getattr(triggered_by, "is_authenticated", False)
            else None,
        )

        for raw_record in records:
            if not isinstance(raw_record, dict):
                continue

            record_date = _parse_record_date(raw_record.get("date"))
            if record_date is None:
                continue
            personnel_state = resolve_employee_day_state(
                personnel_actions,
                record_date,
            )
            record_defaults = build_attendance_record_defaults(
                raw_record,
                personnel_state,
            )
            existing_record = AttendanceRecord.objects.filter(
                employee=employee,
                date=record_date,
            ).first()
            if (
                existing_record
                and existing_record.is_manually_edited
                and not raw_record.get("manual_edited")
            ):
                record_defaults = apply_manual_edit_payload_to_defaults(
                    record_defaults,
                    existing_record.manual_edit_payload,
                )
                record_defaults.update(
                    {
                        "is_manually_edited": True,
                        "manual_edit_payload": existing_record.manual_edit_payload,
                        "manual_edited_by": existing_record.manual_edited_by,
                        "manual_edited_at": existing_record.manual_edited_at,
                    }
                )

            AttendanceRecord.objects.update_or_create(
                employee=employee,
                date=record_date,
                defaults={"analysis_run": run, **record_defaults},
            )

    return run


def get_employee_work_schedule_payload(
    employee: Employee,
) -> dict[str, Any] | None:
    try:
        schedule = employee.work_schedule
    except EmployeeWorkSchedule.DoesNotExist:
        return None
    if schedule is None or not schedule.is_active:
        return None
    return schedule.to_logstorm_payload()


def get_default_work_schedule_payload() -> dict[str, Any]:
    return {
        **DEFAULT_WORK_SCHEDULE_PAYLOAD,
        "workdays": list(DEFAULT_WORK_SCHEDULE_PAYLOAD["workdays"]),
        "date_overrides": list(DEFAULT_WORK_SCHEDULE_PAYLOAD["date_overrides"]),
    }


def build_monthly_attendance_matrix(
    *,
    employees,
    records,
    year: int,
    month: int,
) -> dict[str, Any]:
    """Build an Excel-like monthly attendance matrix for API/UI usage."""
    employees = list(employees)
    records_by_key = {
        (record.employee_id, record.date): record
        for record in records
    }
    days_in_month = monthrange(year, month)[1]
    dates = [date(year, month, day) for day in range(1, days_in_month + 1)]

    rows = []
    for current_date in dates:
        row = {
            "date": current_date.isoformat(),
            "label": f"{current_date.day} ({DAYS_RU[current_date.weekday()]})",
            "weekday": DAYS_RU[current_date.weekday()],
            "is_weekend": current_date.weekday() >= 5,
            "cells": {},
        }
        for employee in employees:
            record = records_by_key.get((employee.id, current_date))
            row["cells"][str(employee.id)] = _monthly_matrix_cell(record)
        rows.append(row)

    summary_rows = [
        ("accounted_days", "Учтено(дней)", _summary_accounted_days),
        ("unaccounted_days", "Неучтено(дней)", _summary_unaccounted_days),
        ("worked_hours", "Отработано(часов)", _summary_worked_hours),
        ("late_days", "Опозданий", _summary_late_days),
        ("early_leave_days", "Ранних уходов", _summary_early_leave_days),
        ("overtime_days", "Переработок", _summary_overtime_days),
        ("absent_days", "Отсутствий", _summary_absent_days),
    ]
    summary = []
    for key, label, counter in summary_rows:
        summary.append(
            {
                "key": key,
                "label": label,
                "values": {
                    str(employee.id): counter(
                        [
                            records_by_key[(employee.id, current_date)]
                            for current_date in dates
                            if (employee.id, current_date) in records_by_key
                        ]
                    )
                    for employee in employees
                },
            }
        )

    return {
        "month": f"{year:04d}-{month:02d}",
        "month_label": f"{MONTHS_RU[month]} {year}",
        "employees": [
            {
                "id": employee.id,
                "name": _employee_display_name(employee),
                "email": getattr(employee, "email", "") or "",
            }
            for employee in employees
        ],
        "rows": rows,
        "summary": summary,
    }


def resolve_employee_day_state(
    personnel_actions,
    record_date: date,
) -> PersonnelDayState:
    day_actions = [
        action
        for action in personnel_actions
        if action.date and action.date.date() <= record_date
    ]
    if not day_actions:
        return PersonnelDayState()

    action = day_actions[-1]
    if action.action not in NON_WORKING_PERSONNEL_ACTIONS:
        return PersonnelDayState(action_id=action.id)

    return PersonnelDayState(
        status=action.action,
        label=action.get_action_display(),
        action_id=action.id,
        is_non_working=True,
    )


def build_attendance_record_defaults(
    raw_record: dict[str, Any],
    personnel_state: PersonnelDayState,
) -> dict[str, Any]:
    work_hours = _nullable_float(raw_record.get("work_hours"))
    has_work = bool(
        _nullable_string(raw_record.get("arrival_time"))
        or _nullable_string(raw_record.get("departure_time"))
        or (work_hours is not None and work_hours > 0)
    )
    is_workday = bool(raw_record.get("is_workday", True))
    if "effective_is_workday" in raw_record:
        effective_is_workday = bool(raw_record.get("effective_is_workday"))
    else:
        effective_is_workday = is_workday and not personnel_state.is_non_working
    is_overtime = bool(raw_record.get("is_overtime", False))
    overtime_hours = _nullable_float(raw_record.get("overtime_hours"))

    is_late = bool(raw_record.get("is_late", False))
    late_minutes = _nullable_int(raw_record.get("late_minutes"))
    is_early_leave = bool(raw_record.get("is_early_leave", False))
    early_leave_minutes = _nullable_int(raw_record.get("early_leave_minutes"))
    is_underwork = bool(raw_record.get("is_underwork", False))
    underwork_hours = _nullable_float(raw_record.get("underwork_hours"))
    is_absent = bool(raw_record.get("is_absent", False))

    statuses = _list_value(raw_record.get("statuses"))
    employee_issues = _list_value(raw_record.get("employee_issues"))
    technical_issues = _list_value(raw_record.get("technical_issues"))
    non_working_reason = _non_working_reason(
        is_workday=is_workday,
        effective_is_workday=effective_is_workday,
        personnel_state=personnel_state,
    )

    if not effective_is_workday:
        is_late = False
        late_minutes = None
        is_early_leave = False
        early_leave_minutes = None
        is_underwork = False
        underwork_hours = None
        is_absent = False
        statuses = _suppress_personnel_non_working_issues(statuses)
        employee_issues = _suppress_personnel_non_working_issues(employee_issues)
        technical_issues = _suppress_personnel_non_working_issues(technical_issues)

        if has_work:
            is_overtime = True
            if overtime_hours is None:
                overtime_hours = work_hours
            statuses = _append_unique(statuses, "work_outside_personnel_schedule")

    return {
        "display_name": str(raw_record.get("display_name") or ""),
        "arrival_time": _nullable_string(raw_record.get("arrival_time")),
        "departure_time": _nullable_string(raw_record.get("departure_time")),
        "work_hours": work_hours,
        "expected_hours": _nullable_float(raw_record.get("expected_hours")),
        "is_workday": is_workday,
        "effective_is_workday": effective_is_workday,
        "is_late": is_late,
        "late_minutes": late_minutes,
        "is_early_leave": is_early_leave,
        "early_leave_minutes": early_leave_minutes,
        "is_underwork": is_underwork,
        "underwork_hours": underwork_hours,
        "is_overtime": is_overtime,
        "overtime_hours": overtime_hours,
        "is_absent": is_absent,
        "statuses": statuses,
        "employee_issues": employee_issues,
        "technical_issues": technical_issues,
        "personnel_status": personnel_state.status,
        "personnel_status_label": personnel_state.label,
        "personnel_action_id": personnel_state.action_id,
        "is_manually_edited": bool(raw_record.get("manual_edited", False)),
        "manual_edit_payload": (
            raw_record.get("manual_edit_payload")
            if isinstance(raw_record.get("manual_edit_payload"), dict)
            else {}
        ),
        "raw_data": {**raw_record, "non_working_reason": non_working_reason},
    }


def apply_manual_edit_payload_to_defaults(
    defaults: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Apply saved manual fields to a freshly analyzed record payload."""
    if not isinstance(payload, dict):
        return defaults

    result = dict(defaults)
    editable_fields = {
        "arrival_time",
        "departure_time",
        "work_hours",
        "expected_hours",
        "is_workday",
        "effective_is_workday",
        "is_late",
        "late_minutes",
        "is_early_leave",
        "early_leave_minutes",
        "is_underwork",
        "underwork_hours",
        "is_overtime",
        "overtime_hours",
        "is_absent",
    }
    for field in editable_fields:
        if field in payload:
            result[field] = payload[field]

    _normalize_issues_after_manual_payload(result, payload)
    result["raw_data"] = {
        **result.get("raw_data", {}),
        "manual_edited": True,
        "manual_edit_payload": {
            key: value
            for key, value in payload.items()
            if key in editable_fields
        },
    }
    return result


def normalize_attendance_record_manual_issues(
    record: AttendanceRecord,
    payload: dict[str, Any],
) -> None:
    fields = {
        "statuses": list(record.statuses),
        "employee_issues": list(record.employee_issues),
    }
    _normalize_issues_after_manual_payload(fields, payload)
    record.statuses = fields["statuses"]
    record.employee_issues = fields["employee_issues"]


def _normalize_issues_after_manual_payload(
    defaults: dict[str, Any],
    payload: dict[str, Any],
) -> None:
    markers_by_flag = {
        "is_late": ("late", "опозд"),
        "is_early_leave": ("early", "ранн"),
        "is_underwork": ("underwork", "недоработ"),
        "is_absent": ("absence", "absent", "отсутств"),
    }
    for flag, markers in markers_by_flag.items():
        if payload.get(flag) is not False:
            continue
        for field in ("statuses", "employee_issues"):
            defaults[field] = [
                item
                for item in _list_value(defaults.get(field))
                if not any(marker in str(item).lower() for marker in markers)
            ]


def _parse_record_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if value is None:
        return None
    return parse_date(str(value))


def _nullable_string(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _nullable_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _nullable_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _suppress_personnel_non_working_issues(values: list[Any]) -> list[Any]:
    result = []
    for value in values:
        normalized = str(value).lower()
        if any(marker in normalized for marker in SUPPRESSED_EMPLOYEE_ISSUE_MARKERS):
            continue
        result.append(value)
    return result


def _append_unique(values: list[Any], value: str) -> list[Any]:
    if value in values:
        return values
    return [*values, value]


def _monthly_matrix_cell(record: AttendanceRecord | None) -> dict[str, Any]:
    if record is None:
        return {
            "record_id": None,
            "arrival_time": None,
            "departure_time": None,
            "work_hours": None,
            "expected_hours": None,
            "status": "empty",
            "issues": [],
            "is_workday": None,
            "effective_is_workday": None,
            "non_working_reason": "",
            "comments_count": 0,
        }

    issues = [
        *record.statuses,
        *record.employee_issues,
        *record.technical_issues,
    ]
    comments_count = getattr(record, "comments_count", 0) or 0
    return {
        "record_id": record.id,
        "arrival_time": record.arrival_time,
        "departure_time": record.departure_time,
        "work_hours": record.work_hours,
        "expected_hours": record.expected_hours,
        "status": _monthly_matrix_status(record),
        "issues": issues,
        "is_workday": record.is_workday,
        "effective_is_workday": record.effective_is_workday,
        "non_working_reason": record.raw_data.get("non_working_reason")
        or _record_non_working_reason(record),
        "is_late": record.is_late,
        "is_early_leave": record.is_early_leave,
        "is_underwork": record.is_underwork,
        "is_overtime": record.is_overtime,
        "is_absent": record.is_absent,
        "personnel_status": record.personnel_status,
        "personnel_status_label": record.personnel_status_label,
        "comments_count": comments_count,
    }


def _monthly_matrix_status(record: AttendanceRecord) -> str:
    if not record.effective_is_workday:
        if record.is_overtime:
            return "overtime"
        return "non_working"
    if record.technical_issues:
        return "technical"
    if record.is_underwork:
        return "underwork"
    if record.is_late:
        return "late"
    if record.is_overtime:
        return "overtime"
    if record.is_absent:
        return "absent"
    return "normal"


def _non_working_reason(
    *,
    is_workday: bool,
    effective_is_workday: bool,
    personnel_state: PersonnelDayState,
) -> str:
    if effective_is_workday:
        return ""
    if personnel_state.is_non_working:
        return personnel_state.label or "Кадровое нерабочее состояние"
    if not is_workday:
        return "Выходной по графику/календарю"
    return "Нерабочий день"


def _record_non_working_reason(record: AttendanceRecord) -> str:
    if record.effective_is_workday:
        return ""
    if record.personnel_status_label:
        return record.personnel_status_label
    if not record.is_workday:
        return "Выходной по графику/календарю"
    return "Нерабочий день"


def _is_valid_workday_record(record: AttendanceRecord) -> bool:
    return bool(record.effective_is_workday and not record.technical_issues)


def _summary_accounted_days(records: list[AttendanceRecord]) -> int:
    return sum(1 for record in records if _is_valid_workday_record(record))


def _summary_unaccounted_days(records: list[AttendanceRecord]) -> int:
    return sum(1 for record in records if record.effective_is_workday and record.technical_issues)


def _summary_worked_hours(records: list[AttendanceRecord]) -> float:
    total = sum(
        record.work_hours or 0
        for record in records
        if _is_valid_workday_record(record)
    )
    return round(total, 2)


def _summary_late_days(records: list[AttendanceRecord]) -> int:
    return sum(1 for record in records if _is_valid_workday_record(record) and record.is_late)


def _summary_early_leave_days(records: list[AttendanceRecord]) -> int:
    return sum(
        1
        for record in records
        if _is_valid_workday_record(record) and record.is_early_leave
    )


def _summary_overtime_days(records: list[AttendanceRecord]) -> int:
    return sum(1 for record in records if _is_valid_workday_record(record) and record.is_overtime)


def _summary_absent_days(records: list[AttendanceRecord]) -> int:
    return sum(1 for record in records if _is_valid_workday_record(record) and record.is_absent)


def _employee_display_name(employee: Employee) -> str:
    full_name = f"{employee.last_name or ''} {employee.first_name or ''}".strip()
    return full_name or employee.email or f"#{employee.id}"

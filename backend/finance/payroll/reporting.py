"""Read-only reporting projections for payroll administration."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Prefetch, Q
from django.utils import timezone
from payroll_core import DeterministicPayrollCalculator

from attendance.models import AttendanceRecord
from employees.constants import ACTIVATING_MARKER_ACTIONS
from employees.models import EmployeeAction
from employees.services.personnel_state import resolve_employee_personnel_state
from requests_app.enums import RequestStatus
from requests_app.models import Request

from finance.enums import ApprovalStatus
from finance.models import (
    EmployeePayRate,
    PayrollComponent,
    PayrollDailyWorkEntry,
    PayrollInputLine,
    PayrollPeriod,
    PayrollWorkRecord,
    PayrollWorkSettings,
)

from .adapter import POINT_BASE_COMPONENT_CODES, build_core_preview_request
from .attendance import (
    calculate_attendance_day_points,
    calculate_attendance_points_projection,
)
from .config import base_rate_code, build_rules
from .work_norm import (
    calculate_period_personnel_points,
    calculate_period_personnel_daily_points,
    calculate_period_target_points,
    period_workdates,
    resolve_employee_schedule,
)

Employee = get_user_model()

SYSTEM_COMPONENT_CODES = {"BASE", "POINT_EXCESS", "POINT_ADJUSTMENT"}


def _decimal_text(value):
    if value in (None, ""):
        return None
    return str(value)


def _in_norm_point_rate(amount, target_points, *, rounding):
    if amount in (None, "") or target_points in (None, ""):
        return None
    target = Decimal(str(target_points))
    if target <= 0:
        return None
    return str(
        (Decimal(str(amount)) / target).quantize(
            Decimal("0.0001"),
            rounding=rounding,
        )
    )


def _point_base_amount(rate_amount, component_amounts):
    if rate_amount in (None, ""):
        return None
    return Decimal(str(rate_amount)) + sum(
        (
            Decimal(str(component_amounts.get(code, "0")))
            for code in POINT_BASE_COMPONENT_CODES
        ),
        Decimal("0"),
    )


def _signed_point_amount(lines):
    point_line = next(
        (line for line in lines if line.code in {"POINT_EXCESS", "POINT_ADJUSTMENT"}),
        None,
    )
    if point_line is None:
        return Decimal("0")
    kind = getattr(point_line.kind, "value", point_line.kind)
    return -point_line.amount if kind == "adjustment_debit" else point_line.amount


def _employee_department(employee):
    links = getattr(employee, "_prefetched_objects_cache", {}).get(
        "departments_links",
        [],
    )
    active_links = sorted(
        (link for link in links if link.is_active),
        key=lambda link: (link.department.name, link.pk),
    )
    return active_links[0].department.name if active_links else None


def _employee_payload(employee):
    return {
        "id": employee.pk,
        "display_name": employee.get_full_name().strip() or f"Сотрудник #{employee.pk}",
        "position": employee.position.name if employee.position_id else None,
        "department": _employee_department(employee),
        "is_active": employee.is_active,
    }


def _latest_rate_by_employee(period, employee_ids):
    grouped = defaultdict(list)
    rates = EmployeePayRate.objects.filter(
        employee_id__in=employee_ids,
        rate_code=base_rate_code(),
        status__in=[ApprovalStatus.DRAFT, ApprovalStatus.APPROVED],
        effective_from__lte=period.date_from,
    ).order_by("employee_id", "effective_from", "revision", "id")
    for rate in rates:
        grouped[rate.employee_id].append(rate)
    return {
        employee_id: max(
            records,
            key=lambda record: (
                record.effective_from,
                record.revision,
                record.pk,
            ),
        )
        for employee_id, records in grouped.items()
    }


def _latest_work_by_employee(period, employee_ids):
    records = PayrollWorkRecord.objects.filter(
        period=period,
        employee_id__in=employee_ids,
        status__in=[ApprovalStatus.DRAFT, ApprovalStatus.APPROVED],
    ).order_by("employee_id", "revision", "id")
    selected = {}
    for record in records:
        selected[record.employee_id] = record
    return selected


def _input_lines_by_employee(period, employee_ids):
    grouped = defaultdict(list)
    records = (
        PayrollInputLine.objects.filter(
            period=period,
            employee_id__in=employee_ids,
            status__in=[ApprovalStatus.DRAFT, ApprovalStatus.APPROVED],
        )
        .select_related("component", "relates_to_period")
        .order_by("employee_id", "component__display_order", "id")
    )
    for record in records:
        grouped[record.employee_id].append(record)
    return grouped


def _component_definition(code, label, kind, order):
    return {
        "code": code,
        "label": label,
        "kind": kind,
        "display_order": order,
    }


def _component_amounts(lines, component_definitions, component_order):
    amounts = defaultdict(lambda: Decimal("0"))
    for line in lines:
        code = line.code
        if code in SYSTEM_COMPONENT_CODES:
            continue
        amounts[code] += line.amount
        component = component_definitions.get(code)
        component_order.setdefault(
            code,
            _component_definition(
                code,
                line.label,
                line.kind,
                component["display_order"] if component else 10_000,
            ),
        )
    return {code: str(amount) for code, amount in amounts.items()}


def _source_component_amounts(records, component_definitions, component_order):
    amounts = defaultdict(lambda: Decimal("0"))
    for record in records:
        component = record.component
        amounts[component.code] += record.amount
        component_order.setdefault(
            component.code,
            _component_definition(
                component.code,
                component.name,
                component.kind,
                component.display_order,
            ),
        )
    return {code: str(amount) for code, amount in amounts.items()}


def _row_money_total(rows, field):
    values = [Decimal(row[field]) for row in rows if row[field] is not None]
    return str(sum(values, Decimal("0"))) if values else None


def build_payroll_period_table(period: PayrollPeriod):
    """Include every active employee and inactive employees with period work."""

    current_run = period.current_run
    statements = {}
    if current_run is not None:
        statements = {
            statement.employee_id: statement
            for statement in current_run.statements.select_related(
                "employee",
                "employee__position",
            ).prefetch_related("lines")
        }

    period_employee_ids = set(
        PayrollWorkRecord.objects.filter(
            period=period,
            status__in=[ApprovalStatus.DRAFT, ApprovalStatus.APPROVED],
            actual_points__gt=0,
        ).values_list("employee_id", flat=True)
    )
    employee_ids = (
        set(Employee.objects.filter(is_active=True).values_list("id", flat=True))
        | period_employee_ids
    )
    employees = list(
        Employee.objects.filter(id__in=employee_ids)
        .select_related("position")
        .prefetch_related(
            "departments_links__department",
            Prefetch(
                "actions",
                queryset=EmployeeAction.objects.filter(
                    Q(source_request__isnull=True)
                    | Q(source_request__status=RequestStatus.APPROVED),
                ).select_related("source_request"),
                to_attr="payroll_personnel_actions",
            ),
        )
        .order_by("last_name", "first_name", "id")
    )

    attendance_by_employee = defaultdict(list)
    attendance_records = AttendanceRecord.objects.filter(
        employee_id__in=employee_ids,
        date__range=(period.date_from, period.date_to),
    ).select_related("analysis_run")
    for record in attendance_records:
        attendance_by_employee[record.employee_id].append(record)

    rates = _latest_rate_by_employee(period, employee_ids)
    work_records = _latest_work_by_employee(period, employee_ids)
    input_lines = _input_lines_by_employee(period, employee_ids)
    components = list(PayrollComponent.objects.all())
    component_definitions = {
        component.code: _component_definition(
            component.code,
            component.name,
            component.kind,
            component.display_order,
        )
        for component in components
    }
    component_order = {
        component.code: component_definitions[component.code]
        for component in components
        if component.is_active and component.code not in SYSTEM_COMPONENT_CODES
    }
    calculator = DeterministicPayrollCalculator()
    active_rules = build_rules()
    preview_rules = replace(active_rules, allow_negative_payable=True)
    daily_target_points = PayrollWorkSettings.get_daily_target_points()
    rows = []

    for employee in employees:
        statement = statements.get(employee.pk)
        rate = rates.get(employee.pk)
        work = work_records.get(employee.pk)
        source_lines = input_lines.get(employee.pk, [])
        schedule, target_points_source = resolve_employee_schedule(employee)
        automatic_target_points, scheduled_workdays, _ = calculate_period_target_points(
            period,
            employee=employee,
            daily_target_points=daily_target_points,
            schedule=schedule,
        )
        if statement is not None:
            snapshot = statement.input_snapshot or {}
            result_lines = list(statement.lines.all())
            point_amount = _signed_point_amount(result_lines)
            component_amounts = _component_amounts(
                result_lines,
                component_definitions,
                component_order,
            )
            status = "calculated"
            totals = {
                "gross_before_adjustments": str(statement.gross_before_adjustments),
                "adjustment_total": str(statement.adjustment_total),
                "gross_total": str(statement.gross_total),
                "deduction_total": str(statement.deduction_total),
                "net_pay": str(statement.net_pay),
                "payment_total": str(statement.payment_total),
                "payable": str(statement.payable),
            }
            rate_amount = snapshot.get("base_accrual")
            # Keep the configured value nullable in the editable projection.
            # The snapshot contains the effective value used historically.
            point_rate = _decimal_text(rate.point_rate) if rate else None
            target_points = snapshot.get("target_points")
            actual_points = snapshot.get("actual_points")
            point_delta = _decimal_text(statement.point_delta)
            target_points_automatic = bool(
                work is None or not work.target_points_overridden
            )
            totals_preliminary = False
        else:
            component_amounts = _source_component_amounts(
                source_lines,
                component_definitions,
                component_order,
            )
            rate_amount = _decimal_text(rate.amount) if rate else None
            point_rate = _decimal_text(rate.point_rate) if rate else None
            preview_target_points = (
                work.target_points if work else automatic_target_points
            )
            preview_actual_points = work.actual_points if work else Decimal("0")
            target_points = _decimal_text(preview_target_points)
            actual_points = _decimal_text(work.actual_points) if work else None
            target_points_automatic = bool(
                work is None or not work.target_points_overridden
            )
            point_delta = (
                str(preview_actual_points - preview_target_points)
                if work is not None
                else None
            )
            preview_request = build_core_preview_request(
                period=period,
                employee_id=employee.pk,
                rate=rate,
                target_points=preview_target_points,
                actual_points=preview_actual_points,
                input_lines=source_lines,
                rounding=preview_rules.rounding.value,
            )
            preview_result = calculator.calculate(preview_request, preview_rules)
            point_amount = _signed_point_amount(preview_result.lines)
            preview_totals = preview_result.totals
            totals = {
                "gross_before_adjustments": str(
                    preview_totals.gross_before_adjustments
                ),
                "adjustment_total": str(preview_totals.adjustment_total),
                "gross_total": str(preview_totals.gross_after_adjustments),
                "deduction_total": str(preview_totals.deduction_total),
                "net_pay": str(preview_totals.net_pay),
                "payment_total": str(preview_totals.payment_total),
                "payable": str(preview_totals.payable),
            }
            totals_preliminary = True
            has_draft = (
                getattr(rate, "status", None) == ApprovalStatus.DRAFT
                or getattr(work, "status", None) == ApprovalStatus.DRAFT
                or any(line.status == ApprovalStatus.DRAFT for line in source_lines)
            )
            if rate is None or work is None:
                status = "incomplete"
            elif has_draft:
                status = "draft"
            else:
                status = "ready"

        projection_target_points = Decimal(str(target_points or "0"))
        daily_point_value = (
            projection_target_points / Decimal(scheduled_workdays)
            if scheduled_workdays
            else Decimal("0")
        )
        attendance_records_for_employee = attendance_by_employee.get(employee.pk, [])
        attendance_points = (
            calculate_attendance_points_projection(
                attendance_records_for_employee,
                daily_point_value=daily_point_value,
            )
            if attendance_records_for_employee
            else None
        )
        personnel_points, _ = calculate_period_personnel_points(
            period,
            employee=employee,
            actions=employee.payroll_personnel_actions,
            period_target_points=projection_target_points,
            schedule=schedule,
        )

        point_base_amount = _point_base_amount(rate_amount, component_amounts)
        in_norm_point_rate = _in_norm_point_rate(
            point_base_amount,
            target_points,
            rounding=preview_rules.rounding.value,
        )

        rows.append(
            {
                "employee": _employee_payload(employee),
                "status": status,
                "rate_status": rate.status if rate else None,
                "work_status": work.status if work else None,
                "rate_amount": rate_amount,
                "in_norm_point_rate": in_norm_point_rate,
                "point_rate": point_rate,
                "target_points": target_points,
                "target_points_automatic": target_points_automatic,
                "target_points_source": target_points_source,
                "attendance_points": _decimal_text(attendance_points),
                "personnel_points": _decimal_text(personnel_points),
                "actual_points": actual_points,
                "point_delta": point_delta,
                "point_amount": _decimal_text(point_amount),
                "component_amounts": component_amounts,
                "totals_preliminary": totals_preliminary,
                **totals,
            }
        )

    status_counts = defaultdict(int)
    for row in rows:
        status_counts[row["status"]] += 1
    component_columns = sorted(
        component_order.values(),
        key=lambda item: (item["display_order"], item["label"], item["code"]),
    )

    return {
        "period_id": period.pk,
        "currency": period.currency,
        "calculation_rules": active_rules.to_dict(),
        "run": (
            {
                "id": current_run.pk,
                "revision": current_run.revision,
                "status": current_run.status,
            }
            if current_run is not None
            else None
        ),
        "component_columns": component_columns,
        "rows": rows,
        "summary": {
            "employee_count": len(rows),
            "calculated_count": status_counts["calculated"],
            "ready_count": status_counts["ready"],
            "draft_count": status_counts["draft"],
            "incomplete_count": status_counts["incomplete"],
            "preliminary_count": sum(1 for row in rows if row["totals_preliminary"]),
            "gross_total": _row_money_total(rows, "gross_total"),
            "deduction_total": _row_money_total(rows, "deduction_total"),
            "payable_total": _row_money_total(rows, "payable"),
        },
    }


def build_payroll_employee_point_breakdown(
    period: PayrollPeriod,
    employee,
):
    """Build a read-only day-by-day comparison of the three point sources."""

    actions = list(
        EmployeeAction.objects.filter(employee=employee)
        .filter(
            Q(source_request__isnull=True)
            | Q(source_request__status=RequestStatus.APPROVED)
        )
        .select_related("source_request")
        .order_by("date", "id")
    )
    employment_start_dates = [
        timezone.localtime(action.date).date()
        for action in actions
        if action.action in ACTIVATING_MARKER_ACTIONS and action.date
    ]
    first_employment_date = (
        min(employment_start_dates) if employment_start_dates else None
    )
    requests = list(
        Request.objects.filter(employee=employee)
        .filter(
            Q(
                date_from__lte=period.date_to,
                date_to__gte=period.date_from,
            )
            | Q(
                date_from__range=(period.date_from, period.date_to),
                date_to__isnull=True,
            )
            | Q(
                date_from__isnull=True,
                created_at__date__range=(period.date_from, period.date_to),
            )
        )
        .select_related("approver")
        .order_by("date_from", "created_at", "id")
    )
    schedule, _ = resolve_employee_schedule(employee)
    workdates = period_workdates(period, schedule)
    workdate_set = set(workdates)
    automatic_target_points, _, _ = calculate_period_target_points(
        period,
        employee=employee,
        schedule=schedule,
    )
    work = _latest_work_by_employee(period, [employee.pk]).get(employee.pk)
    statement = None
    if period.current_run_id:
        statement = period.current_run.statements.filter(employee=employee).first()

    if statement is not None:
        snapshot = statement.input_snapshot or {}
        target_points = Decimal(
            str(snapshot.get("target_points", automatic_target_points))
        )
        actual_points = Decimal(str(snapshot.get("actual_points", "0")))
    else:
        target_points = work.target_points if work else automatic_target_points
        actual_points = work.actual_points if work else None

    daily_target_points = (
        target_points / Decimal(len(workdates)) if workdates else Decimal("0")
    )
    attendance_records = {
        record.date: record
        for record in AttendanceRecord.objects.filter(
            employee=employee,
            date__range=(period.date_from, period.date_to),
        ).select_related("analysis_run")
    }
    personnel_points = calculate_period_personnel_daily_points(
        period,
        employee=employee,
        actions=actions,
        period_target_points=target_points,
        schedule=schedule,
    )
    work_entries = {
        entry.work_date: entry
        for entry in PayrollDailyWorkEntry.objects.filter(
            period=period,
            employee=employee,
        )
    }
    dated_work_points_total = sum(
        (entry.actual_points for entry in work_entries.values()),
        Decimal("0"),
    )
    undated_work_points = (
        (actual_points - dated_work_points_total).quantize(Decimal("0.0001"))
        if actual_points is not None
        else None
    )
    if undated_work_points == 0:
        undated_work_points = None
    if work_entries:
        work_points_mode = "daily_entries"
        work_points = {
            workdate: entry.actual_points
            for workdate, entry in work_entries.items()
        }
    else:
        work_points_mode = "unavailable"
        work_points = {}

    dates = []
    current = period.date_from
    while current <= period.date_to:
        attendance_record = attendance_records.get(current)
        attendance_day_points = (
            calculate_attendance_day_points(
                attendance_record,
                daily_point_value=daily_target_points,
            )
            if attendance_record is not None
            else None
        )
        personnel_state = resolve_employee_personnel_state(
            employee,
            current,
            actions=actions,
        )
        related_actions = []
        for action in actions:
            action_date = (
                timezone.localtime(action.date).date() if action.date else None
            )
            if action_date is None:
                continue
            action_is_related = action_date == current or (
                action.date_to is not None
                and action_date <= current <= action.date_to
            )
            if personnel_state.action_id == action.pk:
                action_is_related = True
            if not action_is_related:
                continue
            related_actions.append(
                {
                    "id": action.pk,
                    "action": action.action,
                    "label": action.get_action_display(),
                    "date": action_date.isoformat(),
                    "date_to": action.date_to.isoformat() if action.date_to else None,
                    "comment": action.comment,
                    "source_request_id": action.source_request_id,
                }
            )
        related_requests = []
        for personnel_request in requests:
            request_date_from = personnel_request.date_from
            request_date_to = personnel_request.date_to or request_date_from
            request_is_related = bool(
                request_date_from
                and request_date_to
                and request_date_from <= current <= request_date_to
            )
            if request_date_from is None:
                request_is_related = (
                    timezone.localtime(personnel_request.created_at).date() == current
                )
            if not request_is_related:
                continue
            related_requests.append(
                {
                    "id": personnel_request.pk,
                    "type": personnel_request.type,
                    "type_label": personnel_request.get_type_display(),
                    "title": personnel_request.display_title,
                    "status": personnel_request.status,
                    "status_label": personnel_request.get_status_display(),
                    "date_from": (
                        personnel_request.date_from.isoformat()
                        if personnel_request.date_from
                        else None
                    ),
                    "date_to": (
                        personnel_request.date_to.isoformat()
                        if personnel_request.date_to
                        else None
                    ),
                    "comment": personnel_request.comment,
                }
            )
        attendance_payload = None
        if attendance_record is not None:
            attendance_payload = {
                "id": attendance_record.pk,
                "arrival_time": attendance_record.arrival_time,
                "departure_time": attendance_record.departure_time,
                "work_hours": attendance_record.work_hours,
                "expected_hours": attendance_record.expected_hours,
                "status_label": (
                    attendance_record.personnel_status_label
                    or ("Отсутствие" if attendance_record.is_absent else "Рабочий день")
                ),
                "issues": list(
                    dict.fromkeys(
                        str(item)
                        for item in [
                            *(attendance_record.statuses or []),
                            *(attendance_record.employee_issues or []),
                            *(attendance_record.technical_issues or []),
                        ]
                        if str(item).strip()
                    )
                ),
                "is_manually_edited": attendance_record.is_manually_edited,
            }
        work_entry = work_entries.get(current)
        dates.append(
            {
                "date": current.isoformat(),
                "is_workday": current in workdate_set,
                "attendance_points": _decimal_text(attendance_day_points),
                "personnel_points": _decimal_text(personnel_points.get(current)),
                "work_points": _decimal_text(work_points.get(current)),
                "attendance_record": attendance_payload,
                "personnel_detail": {
                    "state": (
                        {
                            "status": "before_employment",
                            "label": "До приёма на работу",
                            "expects_attendance": False,
                        }
                        if first_employment_date is not None
                        and current < first_employment_date
                        else {
                            "status": personnel_state.status,
                            "label": personnel_state.label
                            or "Обычный рабочий день",
                            "expects_attendance": personnel_state.expects_attendance,
                        }
                    ),
                    "actions": related_actions,
                    "requests": related_requests,
                },
                "work_entry": (
                    {
                        "id": work_entry.pk,
                        "target_points": _decimal_text(work_entry.target_points),
                        "actual_points": _decimal_text(work_entry.actual_points),
                        "note": work_entry.note,
                        "created_at": work_entry.created_at.isoformat(),
                        "updated_at": work_entry.updated_at.isoformat(),
                    }
                    if work_entry is not None
                    else None
                ),
            }
        )
        current += timedelta(days=1)

    return {
        "period": {
            "id": period.pk,
            "name": period.name,
            "date_from": period.date_from.isoformat(),
            "date_to": period.date_to.isoformat(),
        },
        "employee": _employee_payload(employee),
        "target_points": _decimal_text(target_points),
        "actual_points": _decimal_text(actual_points),
        "undated_work_points": _decimal_text(undated_work_points),
        "undated_work_record": (
            {
                "id": work.pk,
                "actual_points": _decimal_text(undated_work_points),
                "note": work.reason,
                "created_at": work.created_at.isoformat(),
                "updated_at": work.updated_at.isoformat(),
            }
            if undated_work_points is not None and work is not None
            else None
        ),
        "work_points_mode": work_points_mode,
        "dates": dates,
    }

"""Mapping between approved Django records and payroll-core DTOs."""

from __future__ import annotations

from decimal import Decimal

from payroll_core import (
    ExpectedTotals,
    InputLine,
    LineKind,
    PayrollPeriod as CorePayrollPeriod,
    PayrollRequest,
)

from finance.models import (
    EmployeePayRate,
    PayrollInputLine,
    PayrollPeriod,
    PayrollWorkRecord,
)


def _core_period(period: PayrollPeriod) -> CorePayrollPeriod:
    return CorePayrollPeriod(start=period.date_from, end=period.date_to)


def _expected_totals(work_record: PayrollWorkRecord) -> ExpectedTotals | None:
    values = (
        work_record.expected_point_amount,
        work_record.expected_gross,
        work_record.expected_recalculated_gross,
        work_record.expected_payable,
    )
    if all(value is None for value in values):
        return None
    return ExpectedTotals(
        point_amount=work_record.expected_point_amount,
        gross=work_record.expected_gross,
        recalculated_gross=work_record.expected_recalculated_gross,
        payable=work_record.expected_payable,
    )


def _mapped_input_lines(input_lines: list[PayrollInputLine]) -> tuple[InputLine, ...]:
    mapped_lines = []
    for record in input_lines:
        source_period = None
        if record.relates_to_period_id:
            source_period = _core_period(record.relates_to_period)
        mapped_lines.append(
            InputLine(
                line_id=f"input:{record.pk}",
                code=record.component.code,
                label=record.component.name,
                kind=LineKind(record.component.kind),
                amount=record.amount,
                source_ref=(
                    record.source_ref or f"{record.source}:payroll-input:{record.pk}"
                ),
                reason=record.reason,
                source_period=source_period,
                is_retro=source_period is not None,
            )
        )
    return tuple(mapped_lines)


def build_core_request(
    *,
    period: PayrollPeriod,
    rate: EmployeePayRate,
    work_record: PayrollWorkRecord | None,
    input_lines: list[PayrollInputLine],
) -> PayrollRequest:
    return PayrollRequest(
        employee_ref=f"employee:{rate.employee_id}",
        period=_core_period(period),
        currency=period.currency,
        base_accrual=rate.amount,
        base_source_ref=f"pay-rate:{rate.pk}:revision:{rate.revision}",
        target_points=(work_record.target_points if work_record else None),
        actual_points=(work_record.actual_points if work_record else None),
        point_rate=rate.point_rate,
        lines=_mapped_input_lines(input_lines),
        expected_totals=(
            _expected_totals(work_record) if work_record is not None else None
        ),
    )


def build_core_preview_request(
    *,
    period: PayrollPeriod,
    employee_id: int,
    rate: EmployeePayRate | None,
    target_points: Decimal,
    actual_points: Decimal,
    input_lines: list[PayrollInputLine],
) -> PayrollRequest:
    """Build a non-persisted calculation request from draft or partial inputs."""

    return PayrollRequest(
        employee_ref=f"employee:{employee_id}",
        period=_core_period(period),
        currency=period.currency,
        base_accrual=rate.amount if rate is not None else Decimal("0"),
        base_source_ref=(
            f"pay-rate:{rate.pk}:revision:{rate.revision}"
            if rate is not None
            else "preview:missing-pay-rate"
        ),
        target_points=target_points,
        actual_points=actual_points,
        point_rate=rate.point_rate if rate is not None else Decimal("0"),
        lines=_mapped_input_lines(input_lines),
        expected_totals=None,
    )


def employee_snapshot(employee) -> dict[str, object]:
    """Return the minimum identity snapshot needed for a historical payslip."""

    display_name = employee.get_full_name().strip() or f"Сотрудник #{employee.pk}"
    position = getattr(employee, "position", None)
    return {
        "employee_id": employee.pk,
        "display_name": display_name,
        "position": ({"id": position.pk, "name": position.name} if position else None),
    }

"""Mapping between approved Django records and payroll-core DTOs."""

from __future__ import annotations

from decimal import Context, Decimal, ROUND_HALF_UP, localcontext

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

POINT_BASE_COMPONENT_CODES = frozenset({"BONUS"})


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


def _effective_point_rate(
    rate: EmployeePayRate | None,
    point_base_accrual: Decimal,
    target_points: Decimal | None,
    *,
    rounding: str = ROUND_HALF_UP,
) -> Decimal:
    """Resolve a nullable excess price without persisting the derived value."""

    if rate is not None and rate.point_rate is not None:
        return rate.point_rate
    if target_points is None or target_points <= 0:
        return Decimal("0")
    with localcontext(Context(prec=80, rounding=rounding)):
        return (point_base_accrual / target_points).quantize(
            Decimal("0.0001"),
            rounding=rounding,
        )


def _point_base_accrual(
    rate: EmployeePayRate | None,
    input_lines: list[PayrollInputLine],
) -> Decimal:
    """Reproduce the Excel point basis: base salary plus bonus inputs."""

    base_amount = rate.amount if rate is not None else Decimal("0")
    return base_amount + sum(
        (
            record.amount
            for record in input_lines
            if record.component.code in POINT_BASE_COMPONENT_CODES
        ),
        Decimal("0"),
    )


def build_core_request(
    *,
    period: PayrollPeriod,
    rate: EmployeePayRate,
    work_record: PayrollWorkRecord | None,
    input_lines: list[PayrollInputLine],
    rounding: str = ROUND_HALF_UP,
) -> PayrollRequest:
    target_points = work_record.target_points if work_record else None
    point_base_accrual = _point_base_accrual(rate, input_lines)
    return PayrollRequest(
        employee_ref=f"employee:{rate.employee_id}",
        period=_core_period(period),
        currency=period.currency,
        base_accrual=rate.amount,
        base_source_ref=f"pay-rate:{rate.pk}:revision:{rate.revision}",
        point_base_accrual=point_base_accrual,
        target_points=target_points,
        actual_points=(work_record.actual_points if work_record else None),
        point_rate=_effective_point_rate(
            rate,
            point_base_accrual,
            target_points,
            rounding=rounding,
        ),
        point_rate_overridden=rate.point_rate is not None,
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
    rounding: str = ROUND_HALF_UP,
) -> PayrollRequest:
    """Build a non-persisted calculation request from draft or partial inputs."""

    point_base_accrual = _point_base_accrual(rate, input_lines)
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
        point_base_accrual=point_base_accrual,
        target_points=target_points,
        actual_points=actual_points,
        point_rate=_effective_point_rate(
            rate,
            point_base_accrual,
            target_points,
            rounding=rounding,
        ),
        point_rate_overridden=bool(rate is not None and rate.point_rate is not None),
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

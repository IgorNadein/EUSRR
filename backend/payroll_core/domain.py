"""Immutable DTOs shared by payroll calculators and host adapters."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import date
from decimal import Decimal
from enum import Enum


class LineKind(str, Enum):
    """How a positive input amount affects payroll totals."""

    EARNING = "earning"
    ADJUSTMENT_CREDIT = "adjustment_credit"
    ADJUSTMENT_DEBIT = "adjustment_debit"
    DEDUCTION = "deduction"
    PAYMENT = "payment"


class PointPolicy(str, Enum):
    """Supported policies for the points-based component."""

    DISABLED = "disabled"
    EXCESS_ONLY = "excess_only"
    PROPORTIONAL_WITH_EXCESS = "proportional_with_excess"


class RoundingPolicy(str, Enum):
    """Explicit decimal rounding policies supported by the core."""

    HALF_UP = "ROUND_HALF_UP"
    HALF_EVEN = "ROUND_HALF_EVEN"
    DOWN = "ROUND_DOWN"


def decimal_text(value: Decimal) -> str:
    """Return a canonical non-scientific Decimal representation."""

    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError("Only finite Decimal values can be serialized")
    if value.is_zero():
        return "0"
    sign, digits_tuple, exponent = value.as_tuple()
    digits = "".join(str(digit) for digit in digits_tuple) or "0"
    if exponent >= 0:
        rendered = digits + ("0" * exponent)
    else:
        decimal_position = len(digits) + exponent
        if decimal_position <= 0:
            rendered = f"0.{('0' * -decimal_position)}{digits}"
        else:
            rendered = f"{digits[:decimal_position]}.{digits[decimal_position:]}"
        rendered = rendered.rstrip("0").rstrip(".")
    rendered = rendered.lstrip("0") or "0"
    if rendered.startswith("."):
        rendered = f"0{rendered}"
    return f"-{rendered}" if sign else rendered


@dataclass(frozen=True, slots=True)
class PayrollPeriod:
    start: date
    end: date

    def to_dict(self) -> dict[str, str]:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class InputLine:
    """An explicit, already-resolved payroll input line.

    Amounts are always non-negative. ``kind`` carries the direction so that a
    negative correction cannot accidentally become a double negative.
    """

    line_id: str
    code: str
    label: str
    kind: LineKind
    amount: Decimal
    source_ref: str
    reason: str = ""
    source_period: PayrollPeriod | None = None
    is_retro: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "line_id": self.line_id,
            "code": self.code,
            "label": self.label,
            "kind": self.kind.value,
            "amount": decimal_text(self.amount),
            "source_ref": self.source_ref,
            "reason": self.reason,
            "source_period": (
                self.source_period.to_dict() if self.source_period else None
            ),
            "is_retro": self.is_retro,
        }


@dataclass(frozen=True, slots=True)
class ExpectedTotals:
    """Legacy spreadsheet totals used only for reconciliation."""

    point_amount: Decimal | None = None
    gross: Decimal | None = None
    recalculated_gross: Decimal | None = None
    payable: Decimal | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "point_amount": (
                decimal_text(self.point_amount)
                if self.point_amount is not None
                else None
            ),
            "gross": (decimal_text(self.gross) if self.gross is not None else None),
            "recalculated_gross": (
                decimal_text(self.recalculated_gross)
                if self.recalculated_gross is not None
                else None
            ),
            "payable": (
                decimal_text(self.payable) if self.payable is not None else None
            ),
        }


@dataclass(frozen=True, slots=True)
class PayrollRequest:
    """Complete calculation input for one opaque employee reference."""

    employee_ref: str
    period: PayrollPeriod
    currency: str
    base_accrual: Decimal
    base_source_ref: str
    point_base_accrual: Decimal | None = None
    target_points: Decimal | None = None
    actual_points: Decimal | None = None
    point_rate: Decimal = Decimal("0")
    point_rate_overridden: bool = True
    lines: tuple[InputLine, ...] = dataclass_field(default_factory=tuple)
    expected_totals: ExpectedTotals | None = None

    def to_dict(self) -> dict[str, object]:
        ordered_lines = sorted(self.lines, key=lambda line: line.line_id)
        return {
            "employee_ref": self.employee_ref,
            "period": self.period.to_dict(),
            "currency": self.currency,
            "base_accrual": decimal_text(self.base_accrual),
            "base_source_ref": self.base_source_ref,
            "point_base_accrual": (
                decimal_text(self.point_base_accrual)
                if self.point_base_accrual is not None
                else None
            ),
            "target_points": (
                decimal_text(self.target_points)
                if self.target_points is not None
                else None
            ),
            "actual_points": (
                decimal_text(self.actual_points)
                if self.actual_points is not None
                else None
            ),
            "point_rate": decimal_text(self.point_rate),
            "point_rate_overridden": self.point_rate_overridden,
            "lines": [line.to_dict() for line in ordered_lines],
            "expected_totals": (
                self.expected_totals.to_dict()
                if self.expected_totals is not None
                else None
            ),
        }

    def calculation_dict(self) -> dict[str, object]:
        """Return inputs that affect money, excluding control checkpoints."""

        payload = self.to_dict()
        payload.pop("expected_totals")
        return payload


@dataclass(frozen=True, slots=True)
class PayrollRules:
    """Immutable, versioned rules selected by the host application."""

    ruleset_id: str
    version: str
    effective_from: date
    effective_to: date | None = None
    point_policy: PointPolicy = PointPolicy.DISABLED
    money_quantum: Decimal = Decimal("0.01")
    rounding: RoundingPolicy = RoundingPolicy.HALF_UP
    allow_negative_payable: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "ruleset_id": self.ruleset_id,
            "version": self.version,
            "effective_from": self.effective_from.isoformat(),
            "effective_to": (
                self.effective_to.isoformat() if self.effective_to else None
            ),
            "point_policy": self.point_policy.value,
            "money_quantum": decimal_text(self.money_quantum),
            "rounding": self.rounding.value,
            "allow_negative_payable": self.allow_negative_payable,
        }


@dataclass(frozen=True, slots=True)
class PayrollLine:
    line_id: str
    code: str
    label: str
    kind: LineKind
    amount: Decimal
    source_ref: str
    reason: str = ""
    source_period: PayrollPeriod | None = None
    is_retro: bool = False
    calculated: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "line_id": self.line_id,
            "code": self.code,
            "label": self.label,
            "kind": self.kind.value,
            "amount": decimal_text(self.amount),
            "source_ref": self.source_ref,
            "reason": self.reason,
            "source_period": (
                self.source_period.to_dict() if self.source_period else None
            ),
            "is_retro": self.is_retro,
            "calculated": self.calculated,
        }


@dataclass(frozen=True, slots=True)
class CalculationWarning:
    code: str
    message: str
    field: str | None = None
    context: tuple[tuple[str, str], ...] = dataclass_field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "field": self.field,
            "context": dict(self.context),
        }


@dataclass(frozen=True, slots=True)
class PayrollTotals:
    gross_before_adjustments: Decimal
    adjustment_total: Decimal
    gross_after_adjustments: Decimal
    deduction_total: Decimal
    net_pay: Decimal
    payment_total: Decimal
    payable: Decimal

    @property
    def recalculated_gross(self) -> Decimal:
        """Legacy UI alias; it is not another amount to add."""

        return self.gross_after_adjustments

    def to_dict(self) -> dict[str, str]:
        return {
            "gross_before_adjustments": decimal_text(self.gross_before_adjustments),
            "adjustment_total": decimal_text(self.adjustment_total),
            "gross_after_adjustments": decimal_text(self.gross_after_adjustments),
            "recalculated_gross": decimal_text(self.recalculated_gross),
            "deduction_total": decimal_text(self.deduction_total),
            "net_pay": decimal_text(self.net_pay),
            "payment_total": decimal_text(self.payment_total),
            "payable": decimal_text(self.payable),
        }


@dataclass(frozen=True, slots=True)
class PayrollResult:
    employee_ref: str
    period: PayrollPeriod
    currency: str
    lines: tuple[PayrollLine, ...]
    point_delta: Decimal | None
    totals: PayrollTotals
    ruleset_id: str
    ruleset_version: str
    ruleset_hash: str
    calculator_version: str
    rounding_policy: str
    input_hash: str
    result_hash: str
    reconciliation_hash: str
    warnings: tuple[CalculationWarning, ...] = dataclass_field(default_factory=tuple)

    def hash_payload(self) -> dict[str, object]:
        """Return the canonical payload covered by ``result_hash``."""

        return {
            "employee_ref": self.employee_ref,
            "period": self.period.to_dict(),
            "currency": self.currency,
            "lines": [line.to_dict() for line in self.lines],
            "point_delta": (
                decimal_text(self.point_delta) if self.point_delta is not None else None
            ),
            "totals": self.totals.to_dict(),
            "ruleset_id": self.ruleset_id,
            "ruleset_version": self.ruleset_version,
            "ruleset_hash": self.ruleset_hash,
            "calculator_version": self.calculator_version,
            "rounding_policy": self.rounding_policy,
            "input_hash": self.input_hash,
        }

    def to_dict(self) -> dict[str, object]:
        return {
            **self.hash_payload(),
            "result_hash": self.result_hash,
            "reconciliation_hash": self.reconciliation_hash,
            "warnings": [warning.to_dict() for warning in self.warnings],
        }

    def reconciliation_payload(self) -> dict[str, object]:
        """Return checkpoint warnings covered by ``reconciliation_hash``."""

        return {
            "result_hash": self.result_hash,
            "warnings": [warning.to_dict() for warning in self.warnings],
        }

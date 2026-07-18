"""Deterministic reference implementation of the payroll calculator."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from decimal import Context, Decimal, DecimalException, localcontext
from typing import Protocol

from .domain import (
    CalculationWarning,
    ExpectedTotals,
    InputLine,
    LineKind,
    PayrollLine,
    PayrollPeriod,
    PayrollRequest,
    PayrollResult,
    PayrollRules,
    PayrollTotals,
    PointPolicy,
    RoundingPolicy,
    decimal_text,
)
from .exceptions import PayrollIssue, PayrollValidationError

_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_.-]{0,63}$")
_SYSTEM_LINE_PREFIX = "system:"


class PayrollCalculator(Protocol):
    """Port implemented by any compatible calculation provider."""

    def calculate(
        self,
        request: PayrollRequest,
        rules: PayrollRules,
    ) -> PayrollResult: ...


def _canonical_hash(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _is_finite_decimal(value: object) -> bool:
    return isinstance(value, Decimal) and value.is_finite()


class DeterministicPayrollCalculator:
    """Pure calculator with explicit Decimal and rounding semantics."""

    CALCULATOR_VERSION = "1.0.0"
    DECIMAL_PRECISION = 80
    MAX_DECIMAL_DIGITS = 30
    MAX_FRACTIONAL_PLACES = 12
    MAX_INPUT_LINES = 10_000

    def calculate(
        self,
        request: PayrollRequest,
        rules: PayrollRules,
    ) -> PayrollResult:
        issues = self._validate(request, rules)
        if issues:
            raise PayrollValidationError(issues)

        decimal_context = Context(
            prec=self.DECIMAL_PRECISION,
            rounding=rules.rounding.value,
        )
        with localcontext(decimal_context):
            quantize = self._quantizer(rules)
            lines: list[PayrollLine] = [
                PayrollLine(
                    line_id="system:base",
                    code="BASE",
                    label="Base accrual",
                    kind=LineKind.EARNING,
                    amount=quantize(request.base_accrual),
                    source_ref=request.base_source_ref,
                    calculated=True,
                )
            ]
            warnings: list[CalculationWarning] = []
            point_delta: Decimal | None = None

            if rules.point_policy is PointPolicy.EXCESS_ONLY:
                point_delta = request.actual_points - request.target_points
                eligible_points = max(point_delta, Decimal("0"))
                point_amount = quantize(eligible_points * request.point_rate)
                lines.append(
                    PayrollLine(
                        line_id="system:point-excess",
                        code="POINT_EXCESS",
                        label="Points above target",
                        kind=LineKind.EARNING,
                        amount=point_amount,
                        source_ref="calculation:point-policy",
                        calculated=True,
                    )
                )
                if point_delta < 0:
                    warnings.append(
                        CalculationWarning(
                            code="POINTS_BELOW_TARGET_NO_DEDUCTION",
                            field="actual_points",
                            message=(
                                "Actual points are below target; the active "
                                "policy does not reduce pay."
                            ),
                            context=(("point_delta", decimal_text(point_delta)),),
                        )
                    )

            for input_line in sorted(
                request.lines,
                key=lambda item: item.line_id,
            ):
                lines.append(self._to_result_line(input_line, quantize))

            totals = self._calculate_totals(lines)
            if totals.payable < 0 and not rules.allow_negative_payable:
                raise PayrollValidationError(
                    [
                        PayrollIssue(
                            code="NEGATIVE_PAYABLE_NOT_ALLOWED",
                            field="lines",
                            message=(
                                "Deductions and recorded payments exceed available pay."
                            ),
                            context={"payable": decimal_text(totals.payable)},
                        )
                    ]
                )

            warnings.extend(
                self._reconcile_expected(
                    request.expected_totals,
                    lines,
                    totals,
                    quantize,
                )
            )

            input_hash = _canonical_hash(request.calculation_dict())
            rules_payload = rules.to_dict()
            ruleset_hash = _canonical_hash(rules_payload)
            result_payload = {
                "employee_ref": request.employee_ref,
                "period": request.period.to_dict(),
                "currency": request.currency,
                "lines": [line.to_dict() for line in lines],
                "point_delta": (
                    decimal_text(point_delta) if point_delta is not None else None
                ),
                "totals": totals.to_dict(),
                "ruleset_id": rules.ruleset_id,
                "ruleset_version": rules.version,
                "ruleset_hash": ruleset_hash,
                "calculator_version": self.CALCULATOR_VERSION,
                "rounding_policy": rules.rounding.value,
                "input_hash": input_hash,
            }
            result_hash = _canonical_hash(result_payload)
            reconciliation_hash = _canonical_hash(
                {
                    "result_hash": result_hash,
                    "warnings": [warning.to_dict() for warning in warnings],
                }
            )

            return PayrollResult(
                employee_ref=request.employee_ref,
                period=request.period,
                currency=request.currency,
                lines=tuple(lines),
                point_delta=point_delta,
                totals=totals,
                ruleset_id=rules.ruleset_id,
                ruleset_version=rules.version,
                ruleset_hash=ruleset_hash,
                calculator_version=self.CALCULATOR_VERSION,
                rounding_policy=rules.rounding.value,
                input_hash=input_hash,
                result_hash=result_hash,
                reconciliation_hash=reconciliation_hash,
                warnings=tuple(warnings),
            )

    @staticmethod
    def _quantizer(rules: PayrollRules):
        def quantize(value: Decimal) -> Decimal:
            try:
                units = (value / rules.money_quantum).quantize(
                    Decimal("1"),
                    rounding=rules.rounding.value,
                )
                return units * rules.money_quantum
            except DecimalException as exc:
                raise PayrollValidationError(
                    [
                        PayrollIssue(
                            code="ARITHMETIC_ERROR",
                            message="A monetary value cannot be rounded safely.",
                        )
                    ]
                ) from exc

        return quantize

    @staticmethod
    def _to_result_line(input_line: InputLine, quantize) -> PayrollLine:
        return PayrollLine(
            line_id=input_line.line_id,
            code=input_line.code,
            label=input_line.label,
            kind=input_line.kind,
            amount=quantize(input_line.amount),
            source_ref=input_line.source_ref,
            reason=input_line.reason,
            source_period=input_line.source_period,
            is_retro=input_line.is_retro,
            calculated=False,
        )

    @staticmethod
    def _calculate_totals(lines: list[PayrollLine]) -> PayrollTotals:
        earnings = sum(
            (line.amount for line in lines if line.kind is LineKind.EARNING),
            Decimal("0"),
        )
        adjustment_credits = sum(
            (line.amount for line in lines if line.kind is LineKind.ADJUSTMENT_CREDIT),
            Decimal("0"),
        )
        adjustment_debits = sum(
            (line.amount for line in lines if line.kind is LineKind.ADJUSTMENT_DEBIT),
            Decimal("0"),
        )
        deductions = sum(
            (line.amount for line in lines if line.kind is LineKind.DEDUCTION),
            Decimal("0"),
        )
        payments = sum(
            (line.amount for line in lines if line.kind is LineKind.PAYMENT),
            Decimal("0"),
        )
        adjustment_total = adjustment_credits - adjustment_debits
        gross = earnings + adjustment_total
        net_pay = gross - deductions
        return PayrollTotals(
            gross_before_adjustments=earnings,
            adjustment_total=adjustment_total,
            gross_after_adjustments=gross,
            deduction_total=deductions,
            net_pay=net_pay,
            payment_total=payments,
            payable=net_pay - payments,
        )

    @staticmethod
    def _reconcile_expected(
        expected: ExpectedTotals | None,
        lines: list[PayrollLine],
        totals: PayrollTotals,
        quantize,
    ) -> list[CalculationWarning]:
        if expected is None:
            return []

        point_amount = next(
            (line.amount for line in lines if line.line_id == "system:point-excess"),
            Decimal("0"),
        )
        checks = (
            ("point_amount", expected.point_amount, point_amount),
            ("gross", expected.gross, totals.gross_after_adjustments),
            (
                "recalculated_gross",
                expected.recalculated_gross,
                totals.recalculated_gross,
            ),
            ("payable", expected.payable, totals.payable),
        )
        warnings = []
        for field_name, expected_value, actual_value in checks:
            if expected_value is None:
                continue
            normalized_expected = quantize(expected_value)
            if normalized_expected != actual_value:
                warnings.append(
                    CalculationWarning(
                        code="LEGACY_EXPECTED_TOTAL_MISMATCH",
                        field=f"expected_totals.{field_name}",
                        message=(
                            "The calculated amount differs from the legacy "
                            "control total."
                        ),
                        context=(
                            ("expected", decimal_text(normalized_expected)),
                            ("actual", decimal_text(actual_value)),
                        ),
                    )
                )
        return warnings

    def _validate(
        self,
        request: PayrollRequest,
        rules: PayrollRules,
    ) -> list[PayrollIssue]:
        issues: list[PayrollIssue] = []

        if not isinstance(request, PayrollRequest):
            return [
                PayrollIssue(
                    code="INVALID_REQUEST",
                    field="request",
                    message="Request must be a PayrollRequest instance.",
                )
            ]
        if not isinstance(rules, PayrollRules):
            return [
                PayrollIssue(
                    code="INVALID_RULESET",
                    field="rules",
                    message="Rules must be a PayrollRules instance.",
                )
            ]

        if not self._is_nonempty_string(request.employee_ref):
            issues.append(
                PayrollIssue(
                    code="MISSING_EMPLOYEE_REF",
                    field="employee_ref",
                    message="Employee reference is required.",
                )
            )
        period_is_valid = self._validate_period(
            request.period,
            "period",
            issues,
        )
        if not isinstance(request.currency, str) or not _CURRENCY_RE.fullmatch(
            request.currency
        ):
            issues.append(
                PayrollIssue(
                    code="INVALID_CURRENCY",
                    field="currency",
                    message="Currency must be a three-letter uppercase code.",
                )
            )
        self._validate_decimal(
            request.base_accrual,
            "base_accrual",
            issues,
            minimum=Decimal("0"),
        )
        if not self._is_nonempty_string(request.base_source_ref):
            issues.append(
                PayrollIssue(
                    code="MISSING_SOURCE_REF",
                    field="base_source_ref",
                    message="Base accrual must identify its source.",
                )
            )
        self._validate_decimal(
            request.point_rate,
            "point_rate",
            issues,
            minimum=Decimal("0"),
        )

        if not self._is_nonempty_string(rules.ruleset_id):
            issues.append(
                PayrollIssue(
                    code="INVALID_RULESET",
                    field="rules.ruleset_id",
                    message="Ruleset identifier is required.",
                )
            )
        if not self._is_nonempty_string(rules.version):
            issues.append(
                PayrollIssue(
                    code="INVALID_RULESET",
                    field="rules.version",
                    message="Ruleset version is required.",
                )
            )
        rules_from_valid = isinstance(rules.effective_from, date) and not isinstance(
            rules.effective_from,
            datetime,
        )
        rules_to_valid = rules.effective_to is None or (
            isinstance(rules.effective_to, date)
            and not isinstance(rules.effective_to, datetime)
        )
        if not rules_from_valid:
            issues.append(
                PayrollIssue(
                    code="INVALID_RULESET_PERIOD",
                    field="rules.effective_from",
                    message="Ruleset effective_from must be a date.",
                )
            )
        if not rules_to_valid:
            issues.append(
                PayrollIssue(
                    code="INVALID_RULESET_PERIOD",
                    field="rules.effective_to",
                    message="Ruleset effective_to must be a date or None.",
                )
            )
        if (
            rules_from_valid
            and rules_to_valid
            and rules.effective_to is not None
            and rules.effective_from > rules.effective_to
        ):
            issues.append(
                PayrollIssue(
                    code="INVALID_RULESET_PERIOD",
                    field="rules.effective_to",
                    message="Ruleset effective dates are invalid.",
                )
            )
        rules_outside_period = False
        if period_is_valid and rules_from_valid and rules_to_valid:
            rules_outside_period = (
                request.period.start < rules.effective_from
                or rules.effective_to is not None
                and request.period.end > rules.effective_to
            )
        if rules_outside_period:
            issues.append(
                PayrollIssue(
                    code="RULESET_NOT_EFFECTIVE",
                    field="period",
                    message="Ruleset is not effective for the full period.",
                )
            )
        if not isinstance(rules.point_policy, PointPolicy):
            issues.append(
                PayrollIssue(
                    code="UNSUPPORTED_POINT_POLICY",
                    field="rules.point_policy",
                    message="Point policy is not supported.",
                )
            )
        if not isinstance(rules.rounding, RoundingPolicy):
            issues.append(
                PayrollIssue(
                    code="UNSUPPORTED_ROUNDING_POLICY",
                    field="rules.rounding",
                    message="Rounding policy is not supported.",
                )
            )
        if not isinstance(rules.allow_negative_payable, bool):
            issues.append(
                PayrollIssue(
                    code="INVALID_RULE_OPTION",
                    field="rules.allow_negative_payable",
                    message="allow_negative_payable must be a boolean.",
                )
            )
        self._validate_decimal(
            rules.money_quantum,
            "rules.money_quantum",
            issues,
            minimum=Decimal("0"),
            exclusive_minimum=True,
        )

        if rules.point_policy is PointPolicy.EXCESS_ONLY:
            self._validate_decimal(
                request.target_points,
                "target_points",
                issues,
                minimum=Decimal("0"),
                exclusive_minimum=True,
            )
            self._validate_decimal(
                request.actual_points,
                "actual_points",
                issues,
                minimum=Decimal("0"),
            )
        elif rules.point_policy is PointPolicy.DISABLED:
            has_target = request.target_points is not None
            has_actual = request.actual_points is not None
            if has_target != has_actual:
                issues.append(
                    PayrollIssue(
                        code="INCOMPLETE_POINT_METRICS",
                        field="target_points",
                        message="Target and actual points must be supplied together.",
                    )
                )
            if has_target:
                self._validate_decimal(
                    request.target_points,
                    "target_points",
                    issues,
                    minimum=Decimal("0"),
                    exclusive_minimum=True,
                )
            if has_actual:
                self._validate_decimal(
                    request.actual_points,
                    "actual_points",
                    issues,
                    minimum=Decimal("0"),
                )

        seen_line_ids: set[str] = set()
        if not isinstance(request.lines, tuple):
            issues.append(
                PayrollIssue(
                    code="INVALID_LINES_CONTAINER",
                    field="lines",
                    message="Input lines must be an immutable tuple.",
                )
            )
            lines = ()
        else:
            lines = request.lines
        if len(lines) > self.MAX_INPUT_LINES:
            issues.append(
                PayrollIssue(
                    code="TOO_MANY_INPUT_LINES",
                    field="lines",
                    message=f"At most {self.MAX_INPUT_LINES} input lines are allowed.",
                )
            )
        for index, line in enumerate(lines):
            prefix = f"lines[{index}]"
            if not isinstance(line, InputLine):
                issues.append(
                    PayrollIssue(
                        code="INVALID_COMPONENT",
                        field=prefix,
                        message="Every input line must be an InputLine instance.",
                    )
                )
                continue
            line_id_is_valid = self._is_nonempty_string(line.line_id)
            if not line_id_is_valid:
                issues.append(
                    PayrollIssue(
                        code="MISSING_COMPONENT_ID",
                        field=f"{prefix}.line_id",
                        message="Input line identifier is required.",
                    )
                )
            else:
                if line.line_id.startswith(_SYSTEM_LINE_PREFIX):
                    issues.append(
                        PayrollIssue(
                            code="RESERVED_COMPONENT_ID",
                            field=f"{prefix}.line_id",
                            message="Input line uses a reserved system prefix.",
                        )
                    )
                if line.line_id in seen_line_ids:
                    issues.append(
                        PayrollIssue(
                            code="DUPLICATE_COMPONENT_ID",
                            field=f"{prefix}.line_id",
                            message="Input line identifiers must be unique.",
                        )
                    )
                seen_line_ids.add(line.line_id)

            if not isinstance(line.code, str) or not _CODE_RE.fullmatch(line.code):
                issues.append(
                    PayrollIssue(
                        code="INVALID_COMPONENT_CODE",
                        field=f"{prefix}.code",
                        message="Component code must use canonical uppercase form.",
                    )
                )
            if not self._is_nonempty_string(line.label):
                issues.append(
                    PayrollIssue(
                        code="MISSING_COMPONENT_LABEL",
                        field=f"{prefix}.label",
                        message="Input line label is required.",
                    )
                )
            kind_is_valid = isinstance(line.kind, LineKind)
            if not kind_is_valid:
                issues.append(
                    PayrollIssue(
                        code="INVALID_COMPONENT_KIND",
                        field=f"{prefix}.kind",
                        message="Input line kind is not supported.",
                    )
                )
            self._validate_decimal(
                line.amount,
                f"{prefix}.amount",
                issues,
                minimum=Decimal("0"),
            )
            if not self._is_nonempty_string(line.source_ref):
                issues.append(
                    PayrollIssue(
                        code="MISSING_SOURCE_REF",
                        field=f"{prefix}.source_ref",
                        message="Every input line must identify its source.",
                    )
                )
            if (
                kind_is_valid
                and line.kind
                in {
                    LineKind.ADJUSTMENT_CREDIT,
                    LineKind.ADJUSTMENT_DEBIT,
                }
                and not self._is_nonempty_string(line.reason)
            ):
                issues.append(
                    PayrollIssue(
                        code="MISSING_ADJUSTMENT_REASON",
                        field=f"{prefix}.reason",
                        message="Adjustment reason is required.",
                    )
                )
            is_retro_valid = isinstance(line.is_retro, bool)
            if not is_retro_valid:
                issues.append(
                    PayrollIssue(
                        code="INVALID_RETRO_FLAG",
                        field=f"{prefix}.is_retro",
                        message="is_retro must be a boolean.",
                    )
                )
            if line.is_retro is True and line.source_period is None:
                issues.append(
                    PayrollIssue(
                        code="MISSING_RETRO_SOURCE_PERIOD",
                        field=f"{prefix}.source_period",
                        message="Retro input must reference the affected period.",
                    )
                )
            if line.source_period is not None:
                source_period_valid = self._validate_period(
                    line.source_period,
                    f"{prefix}.source_period",
                    issues,
                )
                if is_retro_valid and line.is_retro is not True:
                    issues.append(
                        PayrollIssue(
                            code="UNEXPECTED_SOURCE_PERIOD",
                            field=f"{prefix}.source_period",
                            message="A source period requires is_retro=True.",
                        )
                    )
                elif (
                    is_retro_valid
                    and line.is_retro is True
                    and source_period_valid
                    and period_is_valid
                    and line.source_period.end >= request.period.start
                ):
                    issues.append(
                        PayrollIssue(
                            code="INVALID_RETRO_SOURCE_PERIOD",
                            field=f"{prefix}.source_period",
                            message="Retro source period must end before this period.",
                        )
                    )

        if request.expected_totals is not None and not isinstance(
            request.expected_totals,
            ExpectedTotals,
        ):
            issues.append(
                PayrollIssue(
                    code="INVALID_EXPECTED_TOTALS",
                    field="expected_totals",
                    message="Expected totals must be an ExpectedTotals instance.",
                )
            )
        elif request.expected_totals is not None:
            for field_name in (
                "point_amount",
                "gross",
                "recalculated_gross",
                "payable",
            ):
                self._validate_decimal(
                    getattr(request.expected_totals, field_name),
                    f"expected_totals.{field_name}",
                    issues,
                    minimum=(
                        None
                        if field_name == "payable" and rules.allow_negative_payable
                        else Decimal("0")
                    ),
                    allow_none=True,
                )

        return issues

    @staticmethod
    def _is_nonempty_string(value: object) -> bool:
        return isinstance(value, str) and bool(value.strip())

    @staticmethod
    def _validate_period(
        value: object,
        field_name: str,
        issues: list[PayrollIssue],
    ) -> bool:
        if not isinstance(value, PayrollPeriod):
            issues.append(
                PayrollIssue(
                    code="INVALID_PERIOD",
                    field=field_name,
                    message="Period must be a PayrollPeriod instance.",
                )
            )
            return False
        if (
            not isinstance(value.start, date)
            or isinstance(value.start, datetime)
            or not isinstance(value.end, date)
            or isinstance(value.end, datetime)
        ):
            issues.append(
                PayrollIssue(
                    code="INVALID_PERIOD",
                    field=field_name,
                    message="Period boundaries must be dates.",
                )
            )
            return False
        if value.start > value.end:
            issues.append(
                PayrollIssue(
                    code="INVALID_PERIOD",
                    field=field_name,
                    message="Period start must not be after period end.",
                )
            )
            return False
        return True

    @staticmethod
    def _validate_decimal(
        value: object,
        field_name: str,
        issues: list[PayrollIssue],
        *,
        minimum: Decimal | None,
        exclusive_minimum: bool = False,
        allow_none: bool = False,
    ) -> None:
        if value is None and allow_none:
            return
        if not isinstance(value, Decimal):
            issues.append(
                PayrollIssue(
                    code="INVALID_DECIMAL_TYPE",
                    field=field_name,
                    message="Monetary and quantity values must use Decimal.",
                )
            )
            return
        if not _is_finite_decimal(value):
            issues.append(
                PayrollIssue(
                    code="NON_FINITE_DECIMAL",
                    field=field_name,
                    message="NaN and infinite values are not supported.",
                )
            )
            return
        decimal_tuple = value.as_tuple()
        fractional_places = max(-decimal_tuple.exponent, 0)
        integer_digits = max(value.adjusted() + 1, 0) if value else 0
        if (
            len(decimal_tuple.digits)
            > DeterministicPayrollCalculator.MAX_DECIMAL_DIGITS
            or integer_digits > DeterministicPayrollCalculator.MAX_DECIMAL_DIGITS
            or fractional_places > DeterministicPayrollCalculator.MAX_FRACTIONAL_PLACES
        ):
            issues.append(
                PayrollIssue(
                    code="DECIMAL_OUT_OF_RANGE",
                    field=field_name,
                    message="Decimal precision or scale exceeds safe limits.",
                )
            )
            return
        below_minimum = minimum is not None and value < minimum
        equals_exclusive_minimum = (
            minimum is not None and exclusive_minimum and value == minimum
        )
        if below_minimum or equals_exclusive_minimum:
            comparator = "greater than" if exclusive_minimum else "at least"
            issues.append(
                PayrollIssue(
                    code="NEGATIVE_OR_INVALID_AMOUNT",
                    field=field_name,
                    message=(f"Value must be {comparator} {decimal_text(minimum)}."),
                )
            )

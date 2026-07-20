from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal, ROUND_DOWN, getcontext, localcontext
import hashlib
import json

import pytest

from payroll_core import (
    DeterministicPayrollCalculator,
    ExpectedTotals,
    InputLine,
    LineKind,
    PayrollPeriod,
    PayrollRequest,
    PayrollRules,
    PayrollValidationError,
    PointPolicy,
)


@pytest.fixture
def period():
    return PayrollPeriod(date(2026, 6, 1), date(2026, 6, 30))


@pytest.fixture
def rules():
    return PayrollRules(
        ruleset_id="company-standard",
        version="2026.07.1",
        effective_from=date(2026, 1, 1),
        point_policy=PointPolicy.EXCESS_ONLY,
    )


def make_request(period, **overrides):
    values = {
        "employee_ref": "employee:42",
        "period": period,
        "currency": "RUB",
        "base_accrual": Decimal("80000"),
        "base_source_ref": "rate:42:revision:1",
        "target_points": Decimal("110"),
        "actual_points": Decimal("110"),
        "point_rate": Decimal("100"),
    }
    values.update(overrides)
    return PayrollRequest(**values)


def input_line(
    line_id,
    code,
    kind,
    amount,
    *,
    reason="",
    source_period=None,
    is_retro=False,
):
    return InputLine(
        line_id=line_id,
        code=code,
        label=code.replace("_", " ").title(),
        kind=kind,
        amount=Decimal(amount),
        source_ref=f"fixture:{line_id}",
        reason=reason,
        source_period=source_period,
        is_retro=is_retro,
    )


def issue_codes(error):
    return {issue.code for issue in error.value.issues}


def test_golden_excel_row_calculates_115000(period, rules):
    request = make_request(
        period,
        lines=(
            input_line(
                "bonus:1",
                "BONUS",
                LineKind.EARNING,
                "15000",
            ),
            input_line(
                "correction:1",
                "MANUAL_CORRECTION",
                LineKind.ADJUSTMENT_CREDIT,
                "20000",
                reason="Approved accounting correction",
            ),
        ),
        expected_totals=ExpectedTotals(
            point_amount=Decimal("0"),
            gross=Decimal("115000"),
            recalculated_gross=Decimal("115000"),
            payable=Decimal("115000"),
        ),
    )

    result = DeterministicPayrollCalculator().calculate(request, rules)

    assert result.point_delta == Decimal("0")
    assert result.totals.gross_before_adjustments == Decimal("95000.00")
    assert result.totals.adjustment_total == Decimal("20000.00")
    assert result.totals.gross_after_adjustments == Decimal("115000.00")
    assert result.totals.recalculated_gross == Decimal("115000.00")
    assert result.totals.payable == Decimal("115000.00")
    assert result.warnings == ()


def test_points_above_target_create_an_earning(period, rules):
    request = make_request(period, actual_points=Decimal("120"))

    result = DeterministicPayrollCalculator().calculate(request, rules)

    point_line = next(line for line in result.lines if line.code == "POINT_EXCESS")
    assert result.point_delta == Decimal("10")
    assert point_line.amount == Decimal("1000.00")
    assert result.totals.gross_after_adjustments == Decimal("81000.00")


def test_points_below_target_do_not_silently_reduce_pay(period, rules):
    request = make_request(period, actual_points=Decimal("100"))

    result = DeterministicPayrollCalculator().calculate(request, rules)

    point_line = next(line for line in result.lines if line.code == "POINT_EXCESS")
    assert point_line.amount == Decimal("0.00")
    assert result.totals.payable == Decimal("80000.00")
    assert [warning.code for warning in result.warnings] == [
        "POINTS_BELOW_TARGET_NO_DEDUCTION"
    ]


def test_proportional_policy_reduces_base_below_target(period, rules):
    proportional_rules = replace(
        rules,
        point_policy=PointPolicy.PROPORTIONAL_WITH_EXCESS,
    )
    request = make_request(
        period,
        base_accrual=Decimal("90000"),
        target_points=Decimal("115"),
        actual_points=Decimal("100"),
    )

    result = DeterministicPayrollCalculator().calculate(
        request,
        proportional_rules,
    )

    base_line = next(line for line in result.lines if line.code == "BASE")
    point_line = next(line for line in result.lines if line.code == "POINT_EXCESS")
    assert base_line.amount == Decimal("78260.87")
    assert point_line.amount == Decimal("0.00")
    assert result.point_delta == Decimal("-15")
    assert result.totals.payable == Decimal("78260.87")
    assert result.warnings == ()


def test_proportional_policy_keeps_full_base_and_pays_excess(period, rules):
    proportional_rules = replace(
        rules,
        point_policy=PointPolicy.PROPORTIONAL_WITH_EXCESS,
    )
    request = make_request(
        period,
        base_accrual=Decimal("90000"),
        target_points=Decimal("115"),
        actual_points=Decimal("120"),
        point_rate=Decimal("100"),
    )

    result = DeterministicPayrollCalculator().calculate(
        request,
        proportional_rules,
    )

    base_line = next(line for line in result.lines if line.code == "BASE")
    point_line = next(line for line in result.lines if line.code == "POINT_EXCESS")
    assert base_line.amount == Decimal("90000.00")
    assert point_line.amount == Decimal("500.00")
    assert result.totals.payable == Decimal("90500.00")


def test_debit_deduction_and_advance_have_distinct_effects(period, rules):
    request = make_request(
        period,
        lines=(
            input_line(
                "correction:debit",
                "CORRECTION_DEBIT",
                LineKind.ADJUSTMENT_DEBIT,
                "20000",
                reason="Reversal",
            ),
            input_line(
                "tax:1",
                "TAX",
                LineKind.DEDUCTION,
                "5000",
            ),
            input_line(
                "advance:1",
                "ADVANCE",
                LineKind.PAYMENT,
                "10000",
            ),
        ),
    )

    result = DeterministicPayrollCalculator().calculate(request, rules)

    assert result.totals.gross_after_adjustments == Decimal("60000.00")
    assert result.totals.net_pay == Decimal("55000.00")
    assert result.totals.payment_total == Decimal("10000.00")
    assert result.totals.payable == Decimal("45000.00")


def test_rounds_each_line_half_up_before_summing(period, rules):
    request = make_request(
        period,
        base_accrual=Decimal("0"),
        target_points=Decimal("1"),
        actual_points=Decimal("2"),
        point_rate=Decimal("0.005"),
        lines=(input_line("earning:1", "EARNING_ONE", LineKind.EARNING, "0.005"),),
    )

    result = DeterministicPayrollCalculator().calculate(request, rules)

    assert [line.amount for line in result.lines] == [
        Decimal("0.00"),
        Decimal("0.01"),
        Decimal("0.01"),
    ]
    assert result.totals.gross_after_adjustments == Decimal("0.02")


def test_rejects_float_and_non_finite_decimal(period, rules):
    request = make_request(
        period,
        base_accrual=80000.0,
        point_rate=Decimal("NaN"),
    )

    with pytest.raises(PayrollValidationError) as error:
        DeterministicPayrollCalculator().calculate(request, rules)

    assert issue_codes(error) == {
        "INVALID_DECIMAL_TYPE",
        "NON_FINITE_DECIMAL",
    }


def test_rejects_duplicate_ids_and_unsafe_adjustment(period, rules):
    duplicate_lines = (
        input_line("same", "BONUS", LineKind.EARNING, "1"),
        input_line(
            "same",
            "CORRECTION",
            LineKind.ADJUSTMENT_CREDIT,
            "1",
        ),
    )
    request = make_request(period, lines=duplicate_lines)

    with pytest.raises(PayrollValidationError) as error:
        DeterministicPayrollCalculator().calculate(request, rules)

    assert issue_codes(error) == {
        "DUPLICATE_COMPONENT_ID",
        "MISSING_ADJUSTMENT_REASON",
    }


def test_retro_line_requires_source_period(period, rules):
    request = make_request(
        period,
        lines=(
            input_line(
                "retro:1",
                "RETRO_BONUS",
                LineKind.ADJUSTMENT_CREDIT,
                "1000",
                reason="Late bonus",
                is_retro=True,
            ),
        ),
    )

    with pytest.raises(PayrollValidationError) as error:
        DeterministicPayrollCalculator().calculate(request, rules)

    assert issue_codes(error) == {"MISSING_RETRO_SOURCE_PERIOD"}


def test_negative_payable_is_an_explicit_error(period, rules):
    request = make_request(
        period,
        base_accrual=Decimal("100"),
        lines=(input_line("deduction:1", "DEDUCTION", LineKind.DEDUCTION, "101"),),
    )

    with pytest.raises(PayrollValidationError) as error:
        DeterministicPayrollCalculator().calculate(request, rules)

    assert issue_codes(error) == {"NEGATIVE_PAYABLE_NOT_ALLOWED"}


def test_legacy_totals_only_create_reconciliation_warnings(period, rules):
    request = make_request(
        period,
        expected_totals=ExpectedTotals(
            gross=Decimal("123"),
            recalculated_gross=Decimal("115000"),
        ),
    )

    result = DeterministicPayrollCalculator().calculate(request, rules)

    assert result.totals.gross_after_adjustments == Decimal("80000.00")
    assert [warning.field for warning in result.warnings] == [
        "expected_totals.gross",
        "expected_totals.recalculated_gross",
    ]


def test_result_is_invariant_to_input_order_and_global_context(period, rules):
    first = input_line("a", "BONUS_A", LineKind.EARNING, "1.235")
    second = input_line("b", "BONUS_B", LineKind.EARNING, "2.345")
    request_one = make_request(period, lines=(first, second))
    request_two = make_request(period, lines=(second, first))
    calculator = DeterministicPayrollCalculator()

    original_rounding = getcontext().rounding
    getcontext().rounding = ROUND_DOWN
    try:
        result_one = calculator.calculate(request_one, rules)
        result_two = calculator.calculate(request_two, rules)
    finally:
        getcontext().rounding = original_rounding

    assert result_one.input_hash == result_two.input_hash
    assert result_one.result_hash == result_two.result_hash
    assert result_one.lines == result_two.lines


def test_rule_version_changes_result_identity(period, rules):
    request = make_request(period)
    calculator = DeterministicPayrollCalculator()

    first = calculator.calculate(request, rules)
    second = calculator.calculate(request, replace(rules, version="2026.07.2"))

    assert first.input_hash == second.input_hash
    assert first.ruleset_hash != second.ruleset_hash
    assert first.result_hash != second.result_hash


def test_rules_must_cover_the_full_payroll_period(period, rules):
    request = make_request(period)
    late_rules = replace(rules, effective_from=date(2026, 6, 15))

    with pytest.raises(PayrollValidationError) as error:
        DeterministicPayrollCalculator().calculate(request, late_rules)

    assert issue_codes(error) == {"RULESET_NOT_EFFECTIVE"}


def test_money_quantum_is_a_real_step_not_only_a_decimal_scale(period, rules):
    step_rules = replace(rules, money_quantum=Decimal("0.05"))
    request = make_request(period, base_accrual=Decimal("1.03"))

    result = DeterministicPayrollCalculator().calculate(request, step_rules)

    assert result.lines[0].amount == Decimal("1.05")
    assert result.totals.payable == Decimal("1.05")


def test_equivalent_quantum_representations_have_same_identity(period, rules):
    request = make_request(period, base_accrual=Decimal("1.005"))
    calculator = DeterministicPayrollCalculator()

    first = calculator.calculate(
        request,
        replace(rules, money_quantum=Decimal("0.01")),
    )
    second = calculator.calculate(
        request,
        replace(rules, money_quantum=Decimal("0.010")),
    )

    assert first.lines == second.lines
    assert first.ruleset_hash == second.ruleset_hash
    assert first.result_hash == second.result_hash


def test_serialization_does_not_use_the_global_decimal_context(period, rules):
    request = make_request(period, base_accrual=Decimal("12345.67"))
    result = DeterministicPayrollCalculator().calculate(request, rules)

    with localcontext() as context:
        context.prec = 3
        payload = result.to_dict()

    assert payload["lines"][0]["amount"] == "12345.67"
    assert payload["totals"]["payable"] == "12345.67"


def test_disabled_point_policy_still_validates_supplied_metrics(period, rules):
    disabled_rules = replace(rules, point_policy=PointPolicy.DISABLED)
    request = make_request(
        period,
        target_points=float("nan"),
        actual_points=Decimal("1"),
    )

    with pytest.raises(PayrollValidationError) as error:
        DeterministicPayrollCalculator().calculate(request, disabled_rules)

    assert issue_codes(error) == {"INVALID_DECIMAL_TYPE"}


def test_rule_booleans_are_strict(period, rules):
    request = make_request(
        period,
        base_accrual=Decimal("0"),
        lines=(input_line("deduction:1", "DEDUCTION", LineKind.DEDUCTION, "1"),),
    )
    unsafe_rules = replace(rules, allow_negative_payable="false")

    with pytest.raises(PayrollValidationError) as error:
        DeterministicPayrollCalculator().calculate(request, unsafe_rules)

    assert "INVALID_RULE_OPTION" in issue_codes(error)


def test_large_valid_lines_sum_without_losing_minor_units(period, rules):
    request = make_request(
        period,
        base_accrual=Decimal("99999999999999999999999999.98"),
        lines=(input_line("earning:1", "EARNING", LineKind.EARNING, "0.03"),),
    )

    result = DeterministicPayrollCalculator().calculate(request, rules)

    assert result.totals.gross_after_adjustments == Decimal(
        "100000000000000000000000000.01"
    )


def test_retro_marker_survives_and_source_period_must_be_past(period, rules):
    old_period = PayrollPeriod(date(2026, 5, 1), date(2026, 5, 31))
    retro = input_line(
        "retro:1",
        "RETRO_BONUS",
        LineKind.ADJUSTMENT_CREDIT,
        "100",
        reason="Late approval",
        source_period=old_period,
        is_retro=True,
    )
    result = DeterministicPayrollCalculator().calculate(
        make_request(period, lines=(retro,)),
        rules,
    )
    saved_line = next(line for line in result.lines if line.line_id == "retro:1")
    assert saved_line.is_retro is True
    assert saved_line.source_period == old_period

    future_period = PayrollPeriod(date(2026, 7, 1), date(2026, 7, 31))
    invalid = replace(retro, source_period=future_period)
    with pytest.raises(PayrollValidationError) as error:
        DeterministicPayrollCalculator().calculate(
            make_request(period, lines=(invalid,)),
            rules,
        )
    assert "INVALID_RETRO_SOURCE_PERIOD" in issue_codes(error)


def test_control_totals_do_not_change_calculation_identity(period, rules):
    calculator = DeterministicPayrollCalculator()
    request = make_request(period)
    matching = replace(
        request,
        expected_totals=ExpectedTotals(
            gross=Decimal("80000"),
            payable=Decimal("80000"),
        ),
    )
    mismatching = replace(
        request,
        expected_totals=ExpectedTotals(gross=Decimal("1")),
    )

    plain_result = calculator.calculate(request, rules)
    matching_result = calculator.calculate(matching, rules)
    mismatching_result = calculator.calculate(mismatching, rules)

    assert plain_result.input_hash == matching_result.input_hash
    assert plain_result.input_hash == mismatching_result.input_hash
    assert plain_result.result_hash == matching_result.result_hash
    assert plain_result.result_hash == mismatching_result.result_hash
    assert plain_result.reconciliation_hash == matching_result.reconciliation_hash
    assert plain_result.reconciliation_hash != mismatching_result.reconciliation_hash
    assert mismatching_result.warnings[0].code == "LEGACY_EXPECTED_TOTAL_MISMATCH"


def test_result_hash_is_reproducible_from_returned_result(period, rules):
    result = DeterministicPayrollCalculator().calculate(make_request(period), rules)
    encoded = json.dumps(
        result.hash_payload(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    assert hashlib.sha256(encoded).hexdigest() == result.result_hash

    reconciliation_encoded = json.dumps(
        result.reconciliation_payload(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assert (
        hashlib.sha256(reconciliation_encoded).hexdigest() == result.reconciliation_hash
    )


def test_retro_flag_must_be_a_real_boolean(period, rules):
    old_period = PayrollPeriod(date(2026, 5, 1), date(2026, 5, 31))
    invalid = input_line(
        "retro:wrong-flag",
        "RETRO_BONUS",
        LineKind.ADJUSTMENT_CREDIT,
        "1",
        reason="Late approval",
        source_period=old_period,
        is_retro="false",
    )

    with pytest.raises(PayrollValidationError) as error:
        DeterministicPayrollCalculator().calculate(
            make_request(period, lines=(invalid,)),
            rules,
        )

    assert issue_codes(error) == {"INVALID_RETRO_FLAG"}


def test_negative_expected_payable_is_allowed_when_rules_allow_it(period, rules):
    negative_rules = replace(rules, allow_negative_payable=True)
    request = make_request(
        period,
        base_accrual=Decimal("0"),
        lines=(input_line("deduction:1", "DEDUCTION", LineKind.DEDUCTION, "1"),),
        expected_totals=ExpectedTotals(payable=Decimal("-1")),
    )

    result = DeterministicPayrollCalculator().calculate(request, negative_rules)

    assert result.totals.payable == Decimal("-1.00")
    assert result.warnings == ()


@pytest.mark.parametrize(
    "invalid_period",
    [
        PayrollPeriod(datetime(2026, 6, 1), date(2026, 6, 30)),
        PayrollPeriod(date(2026, 6, 1), datetime(2026, 6, 30)),
    ],
)
def test_datetime_is_not_accepted_as_a_payroll_date(invalid_period, rules):
    with pytest.raises(PayrollValidationError) as error:
        DeterministicPayrollCalculator().calculate(
            make_request(invalid_period),
            rules,
        )

    assert "INVALID_PERIOD" in issue_codes(error)


def test_invalid_expected_totals_are_reported_without_attribute_error(period, rules):
    with pytest.raises(PayrollValidationError) as error:
        DeterministicPayrollCalculator().calculate(
            make_request(period, expected_totals={"gross": "80000"}),
            rules,
        )

    assert issue_codes(error) == {"INVALID_EXPECTED_TOTALS"}


def test_unhashable_line_fields_are_reported_without_type_error(period, rules):
    invalid = replace(
        input_line("line:1", "BONUS", LineKind.EARNING, "1"),
        line_id=["not", "hashable"],
        kind=["not", "hashable"],
    )

    with pytest.raises(PayrollValidationError) as error:
        DeterministicPayrollCalculator().calculate(
            make_request(period, lines=(invalid,)),
            rules,
        )

    assert issue_codes(error) == {
        "MISSING_COMPONENT_ID",
        "INVALID_COMPONENT_KIND",
    }

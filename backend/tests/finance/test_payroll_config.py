from decimal import Decimal

import pytest
from django.core.exceptions import ImproperlyConfigured

from finance.payroll.config import build_rules
from payroll_core import PointPolicy, RoundingPolicy


@pytest.mark.parametrize(
    ("configured_value", "expected"),
    [
        ("half_up", RoundingPolicy.HALF_UP),
        ("ROUND_HALF_UP", RoundingPolicy.HALF_UP),
        ("half_even", RoundingPolicy.HALF_EVEN),
        ("down", RoundingPolicy.DOWN),
    ],
)
def test_rounding_accepts_environment_and_canonical_names(
    settings,
    configured_value,
    expected,
):
    settings.FINANCE_PAYROLL = {
        "ROUNDING": configured_value,
        "POINT_POLICY": PointPolicy.DISABLED.value,
    }

    assert build_rules().rounding is expected


def test_payroll_adapter_is_safe_by_default(settings):
    settings.FINANCE_PAYROLL = {}

    rules = build_rules()

    assert rules.point_policy is PointPolicy.DISABLED
    assert rules.money_quantum == Decimal("0.01")
    assert rules.allow_negative_payable is False


def test_config_accepts_enum_values(settings):
    settings.FINANCE_PAYROLL = {
        "POINT_POLICY": PointPolicy.DISABLED,
        "ROUNDING": RoundingPolicy.HALF_UP,
    }

    rules = build_rules()

    assert rules.point_policy is PointPolicy.DISABLED
    assert rules.rounding is RoundingPolicy.HALF_UP


@pytest.mark.parametrize(
    "override",
    [
        {"MONEY_QUANTUM": "0.001"},
        {"ALLOW_NEGATIVE_PAYABLE": "true"},
        {"ROUNDING": "bankers-ish"},
        {"POINT_POLICY": "invented"},
    ],
)
def test_adapter_rejects_rules_that_cannot_be_persisted(settings, override):
    settings.FINANCE_PAYROLL = override

    with pytest.raises(ImproperlyConfigured):
        build_rules()

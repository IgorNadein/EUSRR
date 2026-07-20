"""Host configuration translated into immutable payroll-core rules."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from payroll_core import PayrollRules, PointPolicy, RoundingPolicy

DEFAULT_CONFIG = {
    "RULESET_ID": "eusrr-standard",
    "RULESET_VERSION": "2026.07.2",
    "EFFECTIVE_FROM": "2026-01-01",
    "EFFECTIVE_TO": None,
    "POINT_POLICY": PointPolicy.PROPORTIONAL_WITH_EXCESS.value,
    "MONEY_QUANTUM": "0.01",
    "ROUNDING": RoundingPolicy.HALF_UP.value,
    "ALLOW_NEGATIVE_PAYABLE": False,
    "BASE_RATE_CODE": "BASE",
    # Temporary pilot mode: portal administrators receive every payroll
    # operation while the granular role matrix is being tested.
    "SIMPLE_ADMIN_ACCESS": True,
}


def get_config() -> dict[str, object]:
    config = DEFAULT_CONFIG.copy()
    overrides = getattr(settings, "FINANCE_PAYROLL", {})
    if not isinstance(overrides, Mapping):
        raise ImproperlyConfigured("FINANCE_PAYROLL must be a mapping")
    config.update(overrides)
    return config


def _parse_date(value, key: str, *, optional: bool = False):
    if value is None and optional:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ImproperlyConfigured(
            f"FINANCE_PAYROLL[{key!r}] must be an ISO date"
        ) from exc


def _parse_bool(value, key: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    raise ImproperlyConfigured(f"FINANCE_PAYROLL[{key!r}] must be a boolean")


def _parse_rounding(value) -> RoundingPolicy:
    if isinstance(value, RoundingPolicy):
        return value
    raw_value = str(value).strip()
    aliases = {
        "half_up": RoundingPolicy.HALF_UP,
        "half_even": RoundingPolicy.HALF_EVEN,
        "down": RoundingPolicy.DOWN,
    }
    try:
        return aliases.get(raw_value.lower()) or RoundingPolicy(raw_value)
    except ValueError as exc:
        raise ImproperlyConfigured(
            "FINANCE_PAYROLL['ROUNDING'] must be half_up, half_even, down "
            "or a canonical Decimal rounding name"
        ) from exc


def _parse_point_policy(value) -> PointPolicy:
    if isinstance(value, PointPolicy):
        return value
    try:
        return PointPolicy(str(value).strip().lower())
    except ValueError as exc:
        raise ImproperlyConfigured(
            "FINANCE_PAYROLL['POINT_POLICY'] must be disabled, excess_only "
            "or proportional_with_excess"
        ) from exc


def build_rules() -> PayrollRules:
    config = get_config()
    try:
        quantum = Decimal(str(config["MONEY_QUANTUM"]))
    except (KeyError, ValueError, InvalidOperation) as exc:
        raise ImproperlyConfigured(
            "FINANCE_PAYROLL contains an unsupported calculation setting"
        ) from exc
    point_policy = _parse_point_policy(config["POINT_POLICY"])
    rounding = _parse_rounding(config["ROUNDING"])
    allow_negative_payable = _parse_bool(
        config["ALLOW_NEGATIVE_PAYABLE"],
        "ALLOW_NEGATIVE_PAYABLE",
    )
    if quantum != Decimal("0.01"):
        raise ImproperlyConfigured(
            "The finance adapter persists two decimal places; "
            "MONEY_QUANTUM must be 0.01"
        )
    if allow_negative_payable:
        raise ImproperlyConfigured(
            "The finance adapter does not persist negative payable amounts"
        )

    return PayrollRules(
        ruleset_id=str(config["RULESET_ID"]),
        version=str(config["RULESET_VERSION"]),
        effective_from=_parse_date(config["EFFECTIVE_FROM"], "EFFECTIVE_FROM"),
        effective_to=_parse_date(
            config.get("EFFECTIVE_TO"),
            "EFFECTIVE_TO",
            optional=True,
        ),
        point_policy=point_policy,
        money_quantum=quantum,
        rounding=rounding,
        allow_negative_payable=allow_negative_payable,
    )


def rules_cover_period(
    rules: PayrollRules,
    *,
    period_from: date,
    period_to: date,
) -> bool:
    """Return whether one ruleset is effective for the complete payroll period."""

    return period_from >= rules.effective_from and (
        rules.effective_to is None or period_to <= rules.effective_to
    )


def ruleset_not_effective_message(rules: PayrollRules) -> str:
    """Build an operator-facing explanation that remains useful without details."""

    effective_range = f"с {rules.effective_from:%d.%m.%Y}"
    if rules.effective_to is not None:
        effective_range += f" по {rules.effective_to:%d.%m.%Y}"
    return (
        "Для выбранного периода нет действующих правил расчёта. "
        f"Набор {rules.ruleset_id}, версия {rules.version}, применяется "
        f"{effective_range}. Измените период или подключите историческую "
        "версию правил."
    )


def ruleset_period_details(
    rules: PayrollRules,
    *,
    period_from: date,
    period_to: date,
) -> dict[str, object]:
    """Stable diagnostics shared by readiness and calculation errors."""

    ruleset_details = {
        "id": rules.ruleset_id,
        "version": rules.version,
        "effective_from": rules.effective_from.isoformat(),
    }
    if rules.effective_to is not None:
        ruleset_details["effective_to"] = rules.effective_to.isoformat()
    return {
        "period": {
            "date_from": period_from.isoformat(),
            "date_to": period_to.isoformat(),
        },
        "ruleset": ruleset_details,
    }


def base_rate_code() -> str:
    return str(get_config()["BASE_RATE_CODE"])


def simple_admin_access_enabled() -> bool:
    """Return whether staff administrators bypass the granular payroll matrix."""

    return _parse_bool(
        get_config()["SIMPLE_ADMIN_ACCESS"],
        "SIMPLE_ADMIN_ACCESS",
    )

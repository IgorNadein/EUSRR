"""Transactional orchestration around the pure payroll calculation core."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import defaultdict
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max, Sum
from django.utils import timezone

from payroll_core import (
    DeterministicPayrollCalculator,
    PayrollValidationError,
)

from finance.enums import (
    ApprovalStatus,
    InputSource,
    PayrollPeriodStatus,
    PayrollRunStatus,
)
from finance.models import (
    EmployeePayRate,
    PayrollAuditEvent,
    PayrollComponent,
    PayrollDailyWorkEntry,
    PayrollInputLine,
    PayrollPeriod,
    PayrollRun,
    PayrollStatement,
    PayrollStatementAcknowledgement,
    PayrollStatementLine,
    PayrollWorkSettings,
    PayrollWorkRecord,
)

from .adapter import build_core_request, employee_snapshot
from .access import (
    SELF_APPROVAL_OVERRIDE_PERMISSION,
    can_self_approve_payroll,
    has_payroll_permission,
    has_simple_admin_access,
)
from .config import (
    base_rate_code,
    build_rules,
    ruleset_not_effective_message,
    ruleset_period_details,
)
from .exceptions import PayrollOperationError, PayrollPermissionDenied
from .work_norm import calculate_period_target_points

Employee = get_user_model()


def _require_permission(actor, permission: str) -> None:
    if (
        actor is None
        or not getattr(actor, "is_authenticated", False)
        or not has_payroll_permission(actor, permission)
    ):
        raise PayrollPermissionDenied(permission)


def _approval_audit_metadata(actor, *, self_approval: bool) -> dict[str, object]:
    """Keep legacy separation metadata only outside the temporary admin mode."""

    if has_simple_admin_access(actor):
        return {}
    if not self_approval:
        return {
            "self_approval_overridden": False,
            "approval_mode": "maker_checker",
        }
    return {
        "self_approval_overridden": True,
        "approval_mode": "self_override",
        "override_permission": SELF_APPROVAL_OVERRIDE_PERMISSION,
    }


def _hash_items(items: list[str]) -> str:
    payload = json.dumps(sorted(items), separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _audit(
    *,
    actor,
    action: str,
    instance,
    period: PayrollPeriod | None,
    before_hash: str = "",
    after_hash: str = "",
    metadata: dict[str, object] | None = None,
) -> None:
    PayrollAuditEvent.objects.create(
        actor=actor,
        action=action,
        object_type=instance._meta.label_lower,
        object_id=str(instance.pk),
        period=period,
        before_hash=before_hash,
        after_hash=after_hash,
        metadata=metadata or {},
    )


def _operation_error(code: str, message: str, **details):
    raise PayrollOperationError(code, message, details=details)


def _resolve_rates(
    period: PayrollPeriod,
    employee_ids: list[int],
) -> list[EmployeePayRate]:
    rates = list(
        EmployeePayRate.objects.filter(
            employee_id__in=employee_ids,
            rate_code=base_rate_code(),
            status=ApprovalStatus.APPROVED,
            effective_from__lte=period.date_to,
        )
        .select_related("employee", "employee__position")
        .order_by("employee_id", "effective_from", "revision")
    )
    grouped = defaultdict(list)
    for rate in rates:
        grouped[rate.employee_id].append(rate)

    selected = []
    for employee_id in employee_ids:
        employee_rates = grouped.get(employee_id, [])
        period_start_rates = [
            rate for rate in employee_rates if rate.effective_from <= period.date_from
        ]
        if not period_start_rates:
            _operation_error(
                "MISSING_RATE_AT_PERIOD_START",
                "Нет утверждённой ставки на начало периода.",
                employee_id=employee_id,
            )
        mid_period_rates = [
            rate
            for rate in employee_rates
            if period.date_from < rate.effective_from <= period.date_to
        ]
        if mid_period_rates:
            _operation_error(
                "MID_PERIOD_RATE_CHANGE_UNSUPPORTED",
                "Изменение ставки внутри периода требует правила пропорционирования.",
                employee_id=employee_id,
                rate_ids=[rate.pk for rate in mid_period_rates],
            )
        selected.append(
            max(
                period_start_rates,
                key=lambda rate: (
                    rate.effective_from,
                    rate.revision,
                    rate.pk,
                ),
            )
        )

    if not selected:
        _operation_error(
            "NO_APPROVED_RATES",
            "Для периода нет ни одной утверждённой базовой ставки.",
        )
    return sorted(selected, key=lambda rate: rate.employee_id)


def _current_work_records(period):
    return {
        record.employee_id: record
        for record in PayrollWorkRecord.objects.filter(
            period=period,
            status=ApprovalStatus.APPROVED,
        ).select_related("employee")
    }


def _input_lines_by_employee(period, employee_ids):
    grouped = defaultdict(list)
    records = (
        PayrollInputLine.objects.filter(
            period=period,
            employee_id__in=employee_ids,
            status=ApprovalStatus.APPROVED,
        )
        .select_related("component", "relates_to_period")
        .order_by("employee_id", "component__display_order", "id")
    )
    for record in records:
        grouped[record.employee_id].append(record)
    return grouped


def _calculate_current_period_inputs(
    period: PayrollPeriod,
    *,
    calculator=None,
    rules=None,
):
    """Resolve and calculate the currently approved source-of-truth inputs."""

    active_rules = rules or build_rules()
    active_calculator = calculator or DeterministicPayrollCalculator()
    work_records = _current_work_records(period)
    if not work_records:
        _operation_error(
            "NO_APPROVED_WORK_RECORDS",
            "Не задан утверждённый состав сотрудников за период.",
        )
    employee_ids = sorted(work_records)
    rates = _resolve_rates(period, employee_ids)
    outside_roster = list(
        PayrollInputLine.objects.filter(
            period=period,
            status=ApprovalStatus.APPROVED,
        )
        .exclude(employee_id__in=employee_ids)
        .values_list("employee_id", flat=True)
        .distinct()[:20]
    )
    if outside_roster:
        _operation_error(
            "INPUT_EMPLOYEE_NOT_IN_ROSTER",
            "Утверждённые строки найдены для сотрудников вне состава периода.",
            employee_ids=outside_roster,
        )
    input_lines = _input_lines_by_employee(period, employee_ids)

    requests = []
    results = []
    for rate in rates:
        if rate.currency != period.currency:
            _operation_error(
                "RATE_CURRENCY_MISMATCH",
                "Валюта ставки не совпадает с валютой периода.",
                employee_id=rate.employee_id,
                rate_id=rate.pk,
            )
        work_record = work_records.get(rate.employee_id)
        if work_record is None:
            _operation_error(
                "MISSING_APPROVED_WORK_RECORD",
                "Нет утверждённых показателей за период.",
                employee_id=rate.employee_id,
            )
        request = build_core_request(
            period=period,
            rate=rate,
            work_record=work_record,
            input_lines=input_lines[rate.employee_id],
        )
        try:
            result = active_calculator.calculate(request, active_rules)
        except PayrollValidationError as exc:
            issues = [issue.to_dict() for issue in exc.issues]
            if any(issue.code == "RULESET_NOT_EFFECTIVE" for issue in exc.issues):
                raise PayrollOperationError(
                    "RULESET_NOT_EFFECTIVE",
                    ruleset_not_effective_message(active_rules),
                    details={
                        "employee_id": rate.employee_id,
                        "issues": issues,
                        **ruleset_period_details(
                            active_rules,
                            period_from=period.date_from,
                            period_to=period.date_to,
                        ),
                    },
                ) from exc
            raise PayrollOperationError(
                "CALCULATION_VALIDATION_FAILED",
                "Ядро отклонило входные данные сотрудника.",
                details={
                    "employee_id": rate.employee_id,
                    "issues": issues,
                },
            ) from exc
        requests.append(request)
        results.append((rate, result))

    return active_rules, requests, results


def _ensure_run_is_fresh(run: PayrollRun, period: PayrollPeriod) -> None:
    """Fail closed if approved inputs, rules or persisted snapshots changed."""

    _, _, results = _calculate_current_period_inputs(period)
    current_input_hash = _hash_items([result.input_hash for _, result in results])
    current_result_hash = _hash_items([result.result_hash for _, result in results])
    first_result = results[0][1]
    statements = {
        statement.employee_id: statement for statement in run.statements.all()
    }
    current_employee_ids = {rate.employee_id for rate, _ in results}
    snapshots_match = set(statements) == current_employee_ids
    if snapshots_match:
        for rate, result in results:
            statement = statements[rate.employee_id]
            stored_warnings = statement.result_snapshot.get("warnings")
            current_warnings = [warning.to_dict() for warning in result.warnings]
            if (
                statement.input_hash != result.input_hash
                or statement.result_hash != result.result_hash
                or statement.result_snapshot.get("result_hash") != result.result_hash
                or statement.result_snapshot.get("reconciliation_hash")
                != result.reconciliation_hash
                or stored_warnings != current_warnings
            ):
                snapshots_match = False
                break
    if (
        run.employee_count != len(results)
        or run.input_hash != current_input_hash
        or run.result_hash != current_result_hash
        or run.ruleset_id != first_result.ruleset_id
        or run.ruleset_version != first_result.ruleset_version
        or run.ruleset_hash != first_result.ruleset_hash
        or run.calculator_version != first_result.calculator_version
        or not snapshots_match
    ):
        _operation_error(
            "RUN_STALE_RECALCULATION_REQUIRED",
            "Утверждённые данные или правила изменились; выполните новый расчёт.",
            run_id=run.pk,
        )


@transaction.atomic
def calculate_period(
    period_id: int,
    *,
    actor,
    idempotency_key: uuid.UUID | None = None,
    recalculation_reason: str = "",
    calculator=None,
    rules=None,
) -> PayrollRun:
    """Calculate a complete period and persist a new immutable revision."""

    _require_permission(actor, "finance.calculate_payroll")
    period = PayrollPeriod.objects.select_for_update().get(pk=period_id)
    previous_current = None
    if period.current_run_id is not None:
        previous_current = PayrollRun.objects.select_for_update().get(
            pk=period.current_run_id
        )
    if idempotency_key is not None:
        existing = PayrollRun.objects.filter(idempotency_key=idempotency_key).first()
        if existing is not None:
            if existing.period_id != period_id:
                _operation_error(
                    "IDEMPOTENCY_KEY_CONFLICT",
                    "Ключ уже использован для другого периода.",
                )
            return existing
    if period.status == PayrollPeriodStatus.CLOSED:
        _operation_error(
            "PERIOD_CLOSED",
            "Закрытый период нельзя пересчитать.",
            period_id=period.pk,
        )
    if period.status in {
        PayrollPeriodStatus.REVIEW,
        PayrollPeriodStatus.APPROVED,
    }:
        _operation_error(
            "PERIOD_UNDER_APPROVAL",
            "Сначала верните текущую ревизию на исправление.",
            period_id=period.pk,
        )
    if previous_current is not None and not recalculation_reason.strip():
        _operation_error(
            "RECALCULATION_REASON_REQUIRED",
            "Для новой ревизии расчёта требуется основание.",
            period_id=period.pk,
        )

    active_rules, requests, results = _calculate_current_period_inputs(
        period,
        calculator=calculator,
        rules=rules,
    )
    employee_ids = [rate.employee_id for rate, _ in results]

    next_revision = (
        PayrollRun.objects.filter(period=period).aggregate(Max("revision"))[
            "revision__max"
        ]
        or 0
    ) + 1
    aggregate_input_hash = _hash_items([result.input_hash for _, result in results])
    aggregate_result_hash = _hash_items([result.result_hash for _, result in results])
    gross_total = sum(
        (result.totals.gross_after_adjustments for _, result in results),
        Decimal("0"),
    )
    deduction_total = sum(
        (result.totals.deduction_total for _, result in results),
        Decimal("0"),
    )
    payable_total = sum(
        (result.totals.payable for _, result in results),
        Decimal("0"),
    )
    first_result = results[0][1]
    run = PayrollRun(
        period=period,
        revision=next_revision,
        status=PayrollRunStatus.CALCULATED,
        supersedes=previous_current,
        recalculation_reason=recalculation_reason.strip(),
        idempotency_key=idempotency_key or uuid.uuid4(),
        ruleset_id=first_result.ruleset_id,
        ruleset_version=first_result.ruleset_version,
        ruleset_hash=first_result.ruleset_hash,
        calculator_version=first_result.calculator_version,
        input_hash=aggregate_input_hash,
        result_hash=aggregate_result_hash,
        employee_count=len(results),
        gross_total=gross_total,
        deduction_total=deduction_total,
        payable_total=payable_total,
        requested_by=actor,
    )
    run.clean()
    try:
        with transaction.atomic():
            run.save(force_insert=True)
    except IntegrityError as exc:
        existing = None
        if idempotency_key is not None:
            existing = PayrollRun.objects.filter(
                idempotency_key=idempotency_key
            ).first()
        if existing is not None and existing.period_id == period_id:
            return existing
        if existing is not None:
            raise PayrollOperationError(
                "IDEMPOTENCY_KEY_CONFLICT",
                "Ключ уже использован для другого периода.",
            ) from exc
        raise PayrollOperationError(
            "CONCURRENT_CALCULATION_CONFLICT",
            "Параллельный расчёт создал конфликт ревизий; повторите операцию.",
        ) from exc

    prior_statements = {}
    if previous_current is not None:
        prior_statements = {
            statement.employee_id: statement
            for statement in PayrollStatement.objects.filter(
                run=previous_current,
                employee_id__in=employee_ids,
            )
        }

    for request, (rate, result) in zip(requests, results, strict=True):
        totals = result.totals
        statement = PayrollStatement(
            run=run,
            employee=rate.employee,
            supersedes=prior_statements.get(rate.employee_id),
            employee_snapshot=employee_snapshot(rate.employee),
            currency=result.currency,
            point_delta=result.point_delta,
            gross_before_adjustments=totals.gross_before_adjustments,
            adjustment_total=totals.adjustment_total,
            gross_total=totals.gross_after_adjustments,
            deduction_total=totals.deduction_total,
            net_pay=totals.net_pay,
            payment_total=totals.payment_total,
            payable=totals.payable,
            input_hash=result.input_hash,
            result_hash=result.result_hash,
            input_snapshot=request.to_dict(),
            result_snapshot=result.to_dict(),
        )
        statement.clean()
        statement.save(force_insert=True)
        PayrollStatementLine.objects.bulk_create(
            [
                PayrollStatementLine(
                    statement=statement,
                    position=position,
                    line_id=line.line_id,
                    code=line.code,
                    label=line.label,
                    kind=line.kind.value,
                    amount=line.amount,
                    source_ref=line.source_ref,
                    reason=line.reason,
                    source_period_from=(
                        line.source_period.start if line.source_period else None
                    ),
                    source_period_to=(
                        line.source_period.end if line.source_period else None
                    ),
                    is_retro=line.is_retro,
                    calculated=line.calculated,
                )
                for position, line in enumerate(result.lines, start=1)
            ]
        )

    if previous_current and previous_current.status != PayrollRunStatus.PUBLISHED:
        previous_status = previous_current.status
        previous_current.status = PayrollRunStatus.SUPERSEDED
        previous_current.save(update_fields=["status"])
        _audit(
            actor=actor,
            action="payroll.run_superseded",
            instance=previous_current,
            period=period,
            before_hash=previous_current.result_hash,
            after_hash=run.result_hash,
            metadata={"previous_status": previous_status},
        )

    period.current_run = run
    period.status = PayrollPeriodStatus.CALCULATED
    period.lock_version += 1
    period.save(update_fields=["current_run", "status", "lock_version", "updated_at"])
    _audit(
        actor=actor,
        action="payroll.calculated",
        instance=run,
        period=period,
        after_hash=run.result_hash,
        metadata={
            "revision": run.revision,
            "employee_count": run.employee_count,
            "is_recalculation": previous_current is not None,
        },
    )
    return run


def _lock_current_run(run_id: int) -> tuple[PayrollRun, PayrollPeriod]:
    run_reference = PayrollRun.objects.only("period_id").get(pk=run_id)
    period = PayrollPeriod.objects.select_for_update().get(pk=run_reference.period_id)
    run = PayrollRun.objects.select_for_update().get(pk=run_id)
    if period.current_run_id != run.pk:
        _operation_error(
            "RUN_NOT_CURRENT",
            "Операция разрешена только для текущей ревизии.",
            run_id=run.pk,
        )
    return run, period


@transaction.atomic
def submit_run_for_review(run_id: int, *, actor) -> PayrollRun:
    _require_permission(actor, "finance.calculate_payroll")
    run, period = _lock_current_run(run_id)
    if run.status != PayrollRunStatus.CALCULATED:
        _operation_error("INVALID_RUN_STATE", "Расчёт уже передан дальше.")
    _ensure_run_is_fresh(run, period)
    reconciliation_errors = []
    for statement in run.statements.only(
        "employee_id",
        "result_snapshot",
    ):
        warning_codes = {
            warning.get("code")
            for warning in statement.result_snapshot.get("warnings", [])
        }
        if "LEGACY_EXPECTED_TOTAL_MISMATCH" in warning_codes:
            reconciliation_errors.append(statement.employee_id)
    if reconciliation_errors:
        _operation_error(
            "RECONCILIATION_MISMATCH",
            "Контрольные итоги Excel не совпадают с расчётом.",
            employee_ids=reconciliation_errors[:20],
        )
    run.status = PayrollRunStatus.REVIEW
    run.save(update_fields=["status"])
    period.status = PayrollPeriodStatus.REVIEW
    period.save(update_fields=["status", "updated_at"])
    _audit(actor=actor, action="payroll.review_requested", instance=run, period=period)
    return run


@transaction.atomic
def return_run_for_correction(
    run_id: int,
    *,
    actor,
    reason: str,
) -> PayrollRun:
    """Return a reviewed run so the operator can create a new revision."""

    if not reason.strip():
        _operation_error(
            "RETURN_REASON_REQUIRED",
            "Укажите причину возврата расчёта.",
        )
    run, period = _lock_current_run(run_id)
    if run.status == PayrollRunStatus.CALCULATED:
        _require_permission(actor, "finance.calculate_payroll")
    else:
        _require_permission(actor, "finance.approve_payroll")
    if run.status not in {
        PayrollRunStatus.CALCULATED,
        PayrollRunStatus.REVIEW,
        PayrollRunStatus.APPROVED,
    }:
        _operation_error(
            "INVALID_RUN_STATE",
            "Вернуть можно расчёт на проверке или после утверждения.",
        )
    previous_status = run.status
    run.status = PayrollRunStatus.RETURNED
    run.save(update_fields=["status"])
    period.status = PayrollPeriodStatus.CALCULATED
    period.save(update_fields=["status", "updated_at"])
    _audit(
        actor=actor,
        action="payroll.returned_for_correction",
        instance=run,
        period=period,
        metadata={
            "previous_status": previous_status,
            "reason": reason.strip(),
        },
    )
    return run


@transaction.atomic
def approve_run(run_id: int, *, actor) -> PayrollRun:
    _require_permission(actor, "finance.approve_payroll")
    run, period = _lock_current_run(run_id)
    if run.status != PayrollRunStatus.REVIEW:
        _operation_error("INVALID_RUN_STATE", "Расчёт не находится на проверке.")
    _ensure_run_is_fresh(run, period)
    self_approval_overridden = run.requested_by_id == actor.pk
    if self_approval_overridden and not can_self_approve_payroll(actor):
        _operation_error(
            "SELF_APPROVAL_FORBIDDEN",
            "Автор расчёта не может сам его утвердить.",
        )
    run.status = PayrollRunStatus.APPROVED
    run.approved_by = actor
    run.approved_at = timezone.now()
    run.self_approval_overridden = self_approval_overridden
    run.save(
        update_fields=[
            "status",
            "approved_by",
            "approved_at",
            "self_approval_overridden",
        ]
    )
    period.status = PayrollPeriodStatus.APPROVED
    period.save(update_fields=["status", "updated_at"])
    _audit(
        actor=actor,
        action="payroll.approved",
        instance=run,
        period=period,
        metadata=_approval_audit_metadata(
            actor,
            self_approval=self_approval_overridden,
        ),
    )
    return run


@transaction.atomic
def publish_run(run_id: int, *, actor) -> PayrollRun:
    _require_permission(actor, "finance.publish_payroll")
    run, period = _lock_current_run(run_id)
    if run.status != PayrollRunStatus.APPROVED:
        _operation_error("INVALID_RUN_STATE", "Расчёт ещё не утверждён.")
    _ensure_run_is_fresh(run, period)

    prior_published_runs = list(
        PayrollRun.objects.select_for_update()
        .filter(
            period=period,
            status=PayrollRunStatus.PUBLISHED,
        )
        .exclude(pk=run.pk)
    )
    for prior_run in prior_published_runs:
        prior_run.status = PayrollRunStatus.SUPERSEDED
        prior_run.save(update_fields=["status"])
        _audit(
            actor=actor,
            action="payroll.run_superseded_on_publish",
            instance=prior_run,
            period=period,
            before_hash=prior_run.result_hash,
            after_hash=run.result_hash,
            metadata={"replacement_run_id": run.pk},
        )
    now = timezone.now()
    run.status = PayrollRunStatus.PUBLISHED
    run.published_by = actor
    run.published_at = now
    run.save(update_fields=["status", "published_by", "published_at"])
    period.status = PayrollPeriodStatus.PUBLISHED
    period.save(update_fields=["status", "updated_at"])
    _audit(
        actor=actor,
        action="payroll.published",
        instance=run,
        period=period,
        after_hash=run.result_hash,
        metadata={"revision": run.revision, "employee_count": run.employee_count},
    )
    return run


@transaction.atomic
def close_period(period_id: int, *, actor) -> PayrollPeriod:
    _require_permission(actor, "finance.publish_payroll")
    period = PayrollPeriod.objects.select_for_update().get(pk=period_id)
    if period.status != PayrollPeriodStatus.PUBLISHED:
        _operation_error(
            "INVALID_PERIOD_STATE",
            "Закрыть можно только опубликованный период.",
        )
    period.status = PayrollPeriodStatus.CLOSED
    period.save(update_fields=["status", "updated_at"])
    _audit(actor=actor, action="payroll.period_closed", instance=period, period=period)
    return period


@transaction.atomic
def bulk_set_point_rate(
    period_id: int,
    *,
    actor,
    employee_ids: list[int],
    mode: str = "fixed",
    point_rate: Decimal | None = None,
    reason: str,
) -> dict[str, object]:
    """Set a fixed excess price or copy each employee's in-norm point price."""

    _require_permission(actor, "finance.manage_payroll_inputs")
    period = PayrollPeriod.objects.select_for_update().get(pk=period_id)
    _ensure_period_accepts_approvals(period)

    selected_employee_ids = sorted(set(employee_ids))
    rates = list(
        EmployeePayRate.objects.select_for_update(of=("self",))
        .filter(
            employee_id__in=selected_employee_ids,
            rate_code=base_rate_code(),
            effective_from__lte=period.date_to,
        )
        .exclude(status=ApprovalStatus.VOIDED)
        .select_related("employee", "replaces")
        .order_by("employee_id", "effective_from", "revision", "pk")
    )
    rates_by_employee: dict[int, list[EmployeePayRate]] = defaultdict(list)
    for rate in rates:
        rates_by_employee[rate.employee_id].append(rate)

    work_by_employee: dict[int, PayrollWorkRecord] = {}
    for record in PayrollWorkRecord.objects.filter(
        period=period,
        employee_id__in=selected_employee_ids,
        status__in=[ApprovalStatus.DRAFT, ApprovalStatus.APPROVED],
    ).order_by("employee_id", "revision", "pk"):
        work_by_employee[record.employee_id] = record

    target_by_employee: dict[int, Decimal] = {}
    if mode == "in_norm":
        for employee_id in selected_employee_ids:
            work = work_by_employee.get(employee_id)
            if work is not None:
                target_by_employee[employee_id] = work.target_points
                continue
            employee_rates = rates_by_employee.get(employee_id, [])
            if not employee_rates:
                continue
            target_by_employee[employee_id] = calculate_period_target_points(
                period,
                employee=employee_rates[-1].employee,
            )[0]

    summary = {
        "selected_employees": len(selected_employee_ids),
        "updated_drafts": 0,
        "created_revisions": 0,
        "unchanged": 0,
        "skipped": 0,
    }
    changed_records: list[EmployeePayRate] = []

    for employee_id in selected_employee_ids:
        employee_rates = rates_by_employee.get(employee_id, [])
        period_start_dates = [
            rate.effective_from
            for rate in employee_rates
            if rate.effective_from <= period.date_from
        ]
        relevant_dates = set()
        if period_start_dates:
            relevant_dates.add(max(period_start_dates))
        relevant_dates.update(
            rate.effective_from
            for rate in employee_rates
            if period.date_from < rate.effective_from <= period.date_to
        )

        if not relevant_dates:
            summary["skipped"] += 1
            continue

        for effective_from in sorted(relevant_dates):
            current = max(
                (
                    rate
                    for rate in employee_rates
                    if rate.effective_from == effective_from
                ),
                key=lambda rate: (rate.revision, rate.pk),
            )
            if mode == "in_norm":
                target_points = target_by_employee[employee_id]
                resolved_point_rate = (current.amount / target_points).quantize(
                    Decimal("0.0001"),
                    rounding=build_rules().rounding.value,
                )
            else:
                resolved_point_rate = point_rate
            if resolved_point_rate is None:
                _operation_error(
                    "POINT_RATE_REQUIRED",
                    "Не задана фиксированная цена балла сверх нормы.",
                )
            if current.point_rate == resolved_point_rate:
                summary["unchanged"] += 1
                continue

            if current.status == ApprovalStatus.DRAFT:
                if (
                    not has_simple_admin_access(actor)
                    and current.created_by_id != actor.pk
                ):
                    summary["skipped"] += 1
                    continue
                previous_point_rate = current.point_rate
                current.point_rate = resolved_point_rate
                current._expected_lock_version = current.lock_version
                try:
                    current.full_clean()
                    current.save()
                except ValidationError as exc:
                    _operation_error(
                        "INPUT_VALIDATION_FAILED",
                        "Цена балла не прошла проверку.",
                        errors=(
                            exc.message_dict
                            if hasattr(exc, "message_dict")
                            else exc.messages
                        ),
                    )
                _audit(
                    actor=actor,
                    action="payroll.rate_bulk_point_rate_updated",
                    instance=current,
                    period=period,
                    metadata={
                        "previous_point_rate": str(previous_point_rate),
                        "point_rate": str(resolved_point_rate),
                        "point_rate_mode": mode,
                        "reason": reason,
                    },
                )
                summary["updated_drafts"] += 1
                changed_records.append(current)
                continue

            if current.status != ApprovalStatus.APPROVED:
                summary["skipped"] += 1
                continue

            revision = EmployeePayRate(
                employee=current.employee,
                rate_code=current.rate_code,
                amount=current.amount,
                point_rate=resolved_point_rate,
                currency=current.currency,
                effective_from=current.effective_from,
                revision=current.revision + 1,
                replaces=current,
                reason=reason,
                status=ApprovalStatus.DRAFT,
                source=InputSource.MANUAL,
                created_by=actor,
            )
            try:
                revision.full_clean()
                revision.save(force_insert=True)
            except ValidationError as exc:
                _operation_error(
                    "INPUT_VALIDATION_FAILED",
                    "Новая версия ставки не прошла проверку.",
                    errors=(
                        exc.message_dict
                        if hasattr(exc, "message_dict")
                        else exc.messages
                    ),
                )
            except IntegrityError:
                _operation_error(
                    "RATE_REVISION_CONFLICT",
                    (
                        "Для одной из ставок уже создана новая версия; "
                        "обновите данные."
                    ),
                    rate_id=current.pk,
                )
            _audit(
                actor=actor,
                action="payroll.rate_bulk_point_rate_revision_created",
                instance=revision,
                period=period,
                metadata={
                    "replaces_id": current.pk,
                    "previous_point_rate": str(current.point_rate),
                    "point_rate": str(resolved_point_rate),
                    "point_rate_mode": mode,
                    "reason": reason,
                },
            )
            summary["created_revisions"] += 1
            changed_records.append(revision)

    return {
        "mode": mode,
        "point_rate": point_rate,
        "summary": summary,
        "records": changed_records,
    }


@transaction.atomic
def bulk_set_pay_rate(
    period_id: int,
    *,
    actor,
    employee_ids: list[int],
    amount: Decimal,
    effective_from,
    reason: str,
) -> dict[str, object]:
    """Create or revise one base rate for each selected employee."""

    _require_permission(actor, "finance.manage_payroll_inputs")
    period = PayrollPeriod.objects.select_for_update().get(pk=period_id)
    _ensure_period_accepts_approvals(period)
    if not period.date_from <= effective_from <= period.date_to:
        _operation_error(
            "RATE_DATE_OUTSIDE_PERIOD",
            "Дата начала ставки должна входить в выбранный расчётный период.",
            period_date_from=str(period.date_from),
            period_date_to=str(period.date_to),
        )

    selected_employee_ids = sorted(set(employee_ids))
    employees = {
        employee.pk: employee
        for employee in Employee.objects.filter(
            pk__in=selected_employee_ids,
            is_active=True,
        ).order_by("pk")
    }
    rates = list(
        EmployeePayRate.objects.select_for_update(of=("self",))
        .filter(
            employee_id__in=employees,
            rate_code=base_rate_code(),
            effective_from__lte=effective_from,
        )
        .select_related("employee", "replaces")
        .order_by("employee_id", "effective_from", "revision", "pk")
    )
    rates_by_employee: dict[int, list[EmployeePayRate]] = defaultdict(list)
    for rate in rates:
        rates_by_employee[rate.employee_id].append(rate)

    summary = {
        "selected_employees": len(selected_employee_ids),
        "created_drafts": 0,
        "updated_drafts": 0,
        "created_revisions": 0,
        "unchanged": 0,
        "skipped": 0,
    }
    changed_records: list[EmployeePayRate] = []

    for employee_id in selected_employee_ids:
        employee = employees.get(employee_id)
        if employee is None:
            summary["skipped"] += 1
            continue

        employee_rates = rates_by_employee.get(employee_id, [])
        exact_rates = [
            rate
            for rate in employee_rates
            if rate.effective_from == effective_from
        ]
        current_rates = [
            rate for rate in exact_rates if rate.status != ApprovalStatus.VOIDED
        ]
        current = (
            max(current_rates, key=lambda rate: (rate.revision, rate.pk))
            if current_rates
            else None
        )

        if current is not None and current.amount == amount:
            summary["unchanged"] += 1
            continue

        if current is not None and current.status == ApprovalStatus.DRAFT:
            if (
                not has_simple_admin_access(actor)
                and current.created_by_id != actor.pk
            ):
                summary["skipped"] += 1
                continue
            previous_amount = current.amount
            current.amount = amount
            current._expected_lock_version = current.lock_version
            try:
                current.full_clean()
                current.save()
            except ValidationError as exc:
                _operation_error(
                    "INPUT_VALIDATION_FAILED",
                    "Ставка не прошла проверку.",
                    errors=(
                        exc.message_dict
                        if hasattr(exc, "message_dict")
                        else exc.messages
                    ),
                )
            _audit(
                actor=actor,
                action="payroll.rate_bulk_amount_updated",
                instance=current,
                period=period,
                metadata={
                    "previous_amount": str(previous_amount),
                    "amount": str(amount),
                    "reason": reason,
                },
            )
            summary["updated_drafts"] += 1
            changed_records.append(current)
            continue

        if current is not None and current.status == ApprovalStatus.APPROVED:
            rate = EmployeePayRate(
                employee=current.employee,
                rate_code=current.rate_code,
                amount=amount,
                point_rate=current.point_rate,
                currency=current.currency,
                effective_from=current.effective_from,
                revision=current.revision + 1,
                replaces=current,
                reason=reason,
                status=ApprovalStatus.DRAFT,
                source=InputSource.MANUAL,
                created_by=actor,
            )
            action = "payroll.rate_bulk_amount_revision_created"
            metadata = {
                "replaces_id": current.pk,
                "previous_amount": str(current.amount),
                "amount": str(amount),
                "reason": reason,
            }
            summary_key = "created_revisions"
        else:
            previous_rates = [
                rate
                for rate in employee_rates
                if rate.status != ApprovalStatus.VOIDED
                and rate.effective_from < effective_from
            ]
            previous = (
                max(
                    previous_rates,
                    key=lambda rate: (
                        rate.effective_from,
                        rate.revision,
                        rate.pk,
                    ),
                )
                if previous_rates
                else None
            )
            rate = EmployeePayRate(
                employee=employee,
                rate_code=base_rate_code(),
                amount=amount,
                point_rate=(previous.point_rate if previous else Decimal("0")),
                currency=period.currency,
                effective_from=effective_from,
                revision=max((item.revision for item in exact_rates), default=0) + 1,
                reason=reason,
                status=ApprovalStatus.DRAFT,
                source=InputSource.MANUAL,
                created_by=actor,
            )
            action = "payroll.rate_bulk_created"
            metadata = {
                "amount": str(amount),
                "point_rate": str(rate.point_rate),
                "reason": reason,
            }
            summary_key = "created_drafts"

        try:
            rate.full_clean()
            rate.save(force_insert=True)
        except ValidationError as exc:
            _operation_error(
                "INPUT_VALIDATION_FAILED",
                "Новая ставка не прошла проверку.",
                errors=(
                    exc.message_dict
                    if hasattr(exc, "message_dict")
                    else exc.messages
                ),
            )
        except IntegrityError:
            _operation_error(
                "RATE_BULK_CONFLICT",
                "Одна из ставок уже изменена; обновите экран и повторите.",
                employee_id=employee_id,
            )
        _audit(
            actor=actor,
            action=action,
            instance=rate,
            period=period,
            metadata=metadata,
        )
        summary[summary_key] += 1
        changed_records.append(rate)

    return {
        "amount": amount,
        "effective_from": effective_from,
        "summary": summary,
        "records": changed_records,
    }


def _sync_daily_work_record(
    *,
    period: PayrollPeriod,
    actor,
) -> PayrollWorkRecord:
    totals = PayrollDailyWorkEntry.objects.filter(
        period=period,
        employee=actor,
    ).aggregate(
        actual_points=Sum("actual_points"),
    )
    actual_points = totals["actual_points"] or Decimal("0")

    records = list(
        PayrollWorkRecord.objects.select_for_update()
        .filter(period=period, employee=actor)
        .order_by("revision", "pk")
    )
    active_records = [
        record for record in records if record.status != ApprovalStatus.VOIDED
    ]
    current = (
        max(active_records, key=lambda record: (record.revision, record.pk))
        if active_records
        else None
    )
    calculated_target, workdays_count, target_source = (
        calculate_period_target_points(period, employee=actor)
    )
    uses_saved_target = (
        current is not None and current.target_points_overridden
    )
    target_points = current.target_points if uses_saved_target else calculated_target
    if target_points <= 0:
        _operation_error(
            "DAILY_WORK_EMPTY",
            "Для периода не удалось определить положительную норму выработки.",
        )
    if (
        current is not None
        and current.target_points == target_points
        and current.actual_points == actual_points
    ):
        return current

    reason = "Агрегация ежедневной выработки сотрудника"
    if current is not None and current.status == ApprovalStatus.DRAFT:
        previous_target = current.target_points
        previous_actual = current.actual_points
        current.target_points = target_points
        current.actual_points = actual_points
        current.expected_point_amount = None
        current.expected_gross = None
        current.expected_recalculated_gross = None
        current.expected_payable = None
        if not uses_saved_target:
            current.reason = reason
            current.source = InputSource.API
            current.source_ref = (
                f"daily-work:{period.pk}:{actor.pk}:r{current.revision}"
            )
            current.target_points_overridden = False
        current._expected_lock_version = current.lock_version
        try:
            current.full_clean()
            current.save()
        except ValidationError as exc:
            _operation_error(
                "INPUT_VALIDATION_FAILED",
                "Итоговая выработка не прошла проверку.",
                errors=(
                    exc.message_dict
                    if hasattr(exc, "message_dict")
                    else exc.messages
                ),
            )
        _audit(
            actor=actor,
            action="payroll.daily_work_aggregate_updated",
            instance=current,
            period=period,
            metadata={
                "channel": "employee_api",
                "previous_target_points": str(previous_target),
                "previous_actual_points": str(previous_actual),
                "target_points": str(target_points),
                "actual_points": str(actual_points),
                "target_source": (
                    "saved_record" if uses_saved_target else target_source
                ),
                "workdays_count": workdays_count,
            },
        )
        return current

    if current is not None and current.status == ApprovalStatus.APPROVED:
        if PayrollWorkRecord.objects.filter(replaces=current).exists():
            _operation_error(
                "WORK_REVISION_CONFLICT",
                "Для итоговой выработки уже создавалась новая версия.",
                record_id=current.pk,
            )
        revision = current.revision + 1
        record = PayrollWorkRecord(
            period=period,
            employee=actor,
            target_points=target_points,
            target_points_overridden=uses_saved_target,
            actual_points=actual_points,
            revision=revision,
            replaces=current,
            reason=reason,
            status=ApprovalStatus.DRAFT,
            source=(current.source if uses_saved_target else InputSource.API),
            source_ref=f"daily-work:{period.pk}:{actor.pk}:r{revision}",
            created_by=actor,
        )
        action = "payroll.daily_work_aggregate_revision_created"
        metadata = {
            "channel": "employee_api",
            "replaces_id": current.pk,
            "target_points": str(target_points),
            "actual_points": str(actual_points),
            "target_source": (
                "saved_record" if uses_saved_target else target_source
            ),
            "workdays_count": workdays_count,
        }
    elif current is None:
        revision = max((record.revision for record in records), default=0) + 1
        record = PayrollWorkRecord(
            period=period,
            employee=actor,
            target_points=target_points,
            target_points_overridden=False,
            actual_points=actual_points,
            revision=revision,
            reason=reason,
            status=ApprovalStatus.DRAFT,
            source=InputSource.API,
            source_ref=f"daily-work:{period.pk}:{actor.pk}:r{revision}",
            created_by=actor,
        )
        action = "payroll.daily_work_aggregate_created"
        metadata = {
            "channel": "employee_api",
            "target_points": str(target_points),
            "actual_points": str(actual_points),
            "target_source": target_source,
            "workdays_count": workdays_count,
        }
    else:
        _operation_error(
            "WORK_RECORD_STATE_INVALID",
            "Итоговую запись выработки нельзя изменить.",
            record_status=current.status,
        )

    try:
        record.full_clean()
        record.save(force_insert=True)
    except ValidationError as exc:
        _operation_error(
            "INPUT_VALIDATION_FAILED",
            "Итоговая выработка не прошла проверку.",
            errors=(
                exc.message_dict
                if hasattr(exc, "message_dict")
                else exc.messages
            ),
        )
    except IntegrityError:
        _operation_error(
            "WORK_RECORD_CONFLICT",
            "Итоговая выработка уже изменена; обновите данные и повторите.",
        )
    _audit(
        actor=actor,
        action=action,
        instance=record,
        period=period,
        metadata=metadata,
    )
    return record


@transaction.atomic
def save_own_daily_work_entry(
    period_id: int,
    *,
    actor,
    work_date,
    actual_points: Decimal,
    note: str = "",
    expected_lock_version: int | None = None,
) -> tuple[PayrollDailyWorkEntry, PayrollWorkRecord, str]:
    """Upsert one daily entry and refresh the employee's period aggregate."""

    if actor is None or not getattr(actor, "is_authenticated", False):
        _operation_error(
            "AUTHENTICATION_REQUIRED",
            "Для сохранения выработки необходимо войти в систему.",
        )
    period = (
        PayrollPeriod.objects.select_for_update(of=("self",))
        .select_related("current_run")
        .get(pk=period_id)
    )
    if period.status != PayrollPeriodStatus.OPEN:
        _operation_error(
            "WORK_PERIOD_LOCKED",
            "Выработка за этот период уже закрыта для изменений.",
            period_status=period.status,
        )
    if not period.date_from <= work_date <= period.date_to:
        _operation_error(
            "WORK_DATE_OUTSIDE_PERIOD",
            "Дата выработки должна входить в выбранный расчётный период.",
            period_date_from=str(period.date_from),
            period_date_to=str(period.date_to),
        )
    if work_date > timezone.localdate():
        _operation_error(
            "WORK_DATE_IN_FUTURE",
            "Нельзя указать выработку за будущую дату.",
        )

    entry = (
        PayrollDailyWorkEntry.objects.select_for_update()
        .filter(period=period, employee=actor, work_date=work_date)
        .first()
    )
    note = note.strip()
    if entry is not None:
        if expected_lock_version is None:
            _operation_error(
                "DAILY_WORK_VERSION_REQUIRED",
                "Обновите данные и повторите сохранение.",
            )
        if entry.lock_version != expected_lock_version:
            _operation_error(
                "STALE_DAILY_WORK_ENTRY",
                "Запись уже изменена; обновите данные и повторите.",
                expected_lock_version=expected_lock_version,
                actual_lock_version=entry.lock_version,
            )
        if entry.actual_points == actual_points and entry.note == note:
            aggregate = _sync_daily_work_record(period=period, actor=actor)
            return entry, aggregate, "unchanged"

        previous_actual = entry.actual_points
        entry.actual_points = actual_points
        entry.note = note
        entry.lock_version += 1
        operation = "updated"
        action = "payroll.daily_work_entry_updated"
        metadata = {
            "channel": "employee_api",
            "work_date": str(work_date),
            "previous_actual_points": str(previous_actual),
            "target_points": str(entry.target_points),
            "actual_points": str(actual_points),
        }
    else:
        target_points = PayrollWorkSettings.get_daily_target_points()
        entry = PayrollDailyWorkEntry(
            period=period,
            employee=actor,
            work_date=work_date,
            target_points=target_points,
            actual_points=actual_points,
            note=note,
        )
        operation = "created"
        action = "payroll.daily_work_entry_created"
        metadata = {
            "channel": "employee_api",
            "work_date": str(work_date),
            "target_points": str(target_points),
            "actual_points": str(actual_points),
        }

    try:
        entry.full_clean()
        entry.save()
    except ValidationError as exc:
        _operation_error(
            "INPUT_VALIDATION_FAILED",
            "Ежедневная выработка не прошла проверку.",
            errors=(
                exc.message_dict
                if hasattr(exc, "message_dict")
                else exc.messages
            ),
        )
    except IntegrityError:
        _operation_error(
            "DAILY_WORK_ENTRY_CONFLICT",
            "Запись за эту дату уже создана; обновите данные.",
        )
    _audit(
        actor=actor,
        action=action,
        instance=entry,
        period=period,
        metadata=metadata,
    )
    aggregate = _sync_daily_work_record(period=period, actor=actor)
    return entry, aggregate, operation


def _approve_record(
    record,
    *,
    actor,
    object_label: str,
    expected_lock_version: int,
):
    if (
        not isinstance(expected_lock_version, int)
        or isinstance(expected_lock_version, bool)
        or expected_lock_version < 0
    ):
        _operation_error(
            "APPROVAL_VERSION_REQUIRED",
            "Укажите версию черновика, которую проверил утверждающий.",
        )
    if record.lock_version != expected_lock_version:
        _operation_error(
            "APPROVAL_VERSION_CONFLICT",
            "Черновик изменился после проверки; откройте и проверьте его заново.",
            expected_lock_version=expected_lock_version,
            actual_lock_version=record.lock_version,
        )
    if record.status != ApprovalStatus.DRAFT:
        _operation_error("INVALID_INPUT_STATE", "Утвердить можно только черновик.")
    self_approval_overridden = record.created_by_id == actor.pk
    if self_approval_overridden and not can_self_approve_payroll(actor):
        _operation_error(
            "SELF_APPROVAL_FORBIDDEN",
            "Автор входных данных не может сам их утвердить.",
        )
    now = timezone.now()
    replaced = None
    replaces_id = getattr(record, "replaces_id", None)
    if replaces_id:
        replaced = record.__class__.objects.select_for_update().get(pk=replaces_id)
        record._state.fields_cache["replaces"] = replaced
    previous_status = replaced.status if replaced is not None else ""
    if replaced is not None and replaced.status != ApprovalStatus.APPROVED:
        _operation_error(
            "REPLACEMENT_SOURCE_NOT_APPROVED",
            "Заменить можно только действующую утверждённую запись.",
            replaced_id=replaced.pk,
        )
    if replaced:
        replaced.status = ApprovalStatus.VOIDED
        replaced.voided_by = actor
        replaced.voided_at = now
        replaced.save(update_fields=["status", "voided_by", "voided_at"])
    record.status = ApprovalStatus.APPROVED
    record.approved_by = actor
    record.approved_at = now
    record.self_approval_overridden = self_approval_overridden
    try:
        record.full_clean()
    except ValidationError as exc:
        raise PayrollOperationError(
            "INPUT_VALIDATION_FAILED",
            "Входные данные не прошли проверку.",
            details={
                "errors": exc.message_dict
                if hasattr(exc, "message_dict")
                else exc.messages
            },
        ) from exc
    record.save(
        update_fields=[
            "status",
            "approved_by",
            "approved_at",
            "self_approval_overridden",
        ]
    )
    period = getattr(record, "period", None)
    if replaced is not None:
        _audit(
            actor=actor,
            action=f"payroll.{object_label}_voided_on_replacement",
            instance=replaced,
            period=period,
            metadata={
                "previous_status": previous_status,
                "replacement_id": record.pk,
            },
        )
    _audit(
        actor=actor,
        action=f"payroll.{object_label}_approved",
        instance=record,
        period=period,
        metadata={
            "approved_lock_version": record.lock_version,
            **_approval_audit_metadata(
                actor,
                self_approval=self_approval_overridden,
            ),
        },
    )
    return record


def _ensure_period_accepts_approvals(period: PayrollPeriod) -> None:
    if period.status == PayrollPeriodStatus.CLOSED:
        _operation_error(
            "PERIOD_INPUTS_LOCKED",
            "Данные закрытого периода заблокированы.",
        )
    if period.current_run_id is None:
        return
    current_run = PayrollRun.objects.select_for_update().get(pk=period.current_run_id)
    if current_run.status in {
        PayrollRunStatus.CALCULATED,
        PayrollRunStatus.REVIEW,
        PayrollRunStatus.APPROVED,
    }:
        _operation_error(
            "PERIOD_INPUTS_LOCKED",
            "Сначала верните текущий расчёт на исправление.",
            run_id=current_run.pk,
        )


@transaction.atomic
def approve_pay_rate(
    rate_id: int,
    *,
    actor,
    expected_lock_version: int,
) -> EmployeePayRate:
    _require_permission(actor, "finance.approve_payroll_inputs")
    # A rate can affect any open period. Lock periods before runs and the rate,
    # matching the global payroll lock order and serializing against calculate.
    periods = list(
        PayrollPeriod.objects.select_for_update()
        .exclude(status=PayrollPeriodStatus.CLOSED)
        .order_by("pk")
    )
    current_run_ids = [
        period.current_run_id for period in periods if period.current_run_id is not None
    ]
    current_runs = list(
        PayrollRun.objects.select_for_update()
        .filter(pk__in=current_run_ids)
        .order_by("pk")
    )
    record = EmployeePayRate.objects.select_for_update().get(pk=rate_id)
    for run in current_runs:
        if (
            run.status
            in {
                PayrollRunStatus.CALCULATED,
                PayrollRunStatus.REVIEW,
                PayrollRunStatus.APPROVED,
            }
            and run.statements.filter(employee_id=record.employee_id).exists()
        ):
            _operation_error(
                "RATE_USED_BY_ACTIVE_RUN",
                "Ставку нельзя утвердить, пока расчёт сотрудника согласуется.",
                run_id=run.pk,
            )
    return _approve_record(
        record,
        actor=actor,
        object_label="rate",
        expected_lock_version=expected_lock_version,
    )


@transaction.atomic
def approve_work_record(
    record_id: int,
    *,
    actor,
    expected_lock_version: int,
) -> PayrollWorkRecord:
    _require_permission(actor, "finance.approve_payroll_inputs")
    reference = PayrollWorkRecord.objects.only("period_id").get(pk=record_id)
    period = PayrollPeriod.objects.select_for_update().get(pk=reference.period_id)
    _ensure_period_accepts_approvals(period)
    record = PayrollWorkRecord.objects.select_for_update().get(pk=record_id)
    if period.status == PayrollPeriodStatus.PUBLISHED and not record.replaces_id:
        _operation_error(
            "PUBLISHED_WORK_REPLACEMENT_REQUIRED",
            "После публикации показатели меняются только новой ревизией.",
        )
    return _approve_record(
        record,
        actor=actor,
        object_label="work_record",
        expected_lock_version=expected_lock_version,
    )


@transaction.atomic
def approve_input_line(
    line_id: int,
    *,
    actor,
    expected_lock_version: int,
) -> PayrollInputLine:
    _require_permission(actor, "finance.approve_payroll_inputs")
    reference = PayrollInputLine.objects.only("period_id", "component_id").get(
        pk=line_id
    )
    period = PayrollPeriod.objects.select_for_update().get(pk=reference.period_id)
    _ensure_period_accepts_approvals(period)
    component = PayrollComponent.objects.select_for_update().get(
        pk=reference.component_id
    )
    if not component.is_active:
        _operation_error(
            "PAYROLL_COMPONENT_INACTIVE",
            "Нельзя утвердить строку с неактивным компонентом.",
            component_id=component.pk,
        )
    record = PayrollInputLine.objects.select_for_update().get(pk=line_id)
    record._state.fields_cache["component"] = component
    return _approve_record(
        record,
        actor=actor,
        object_label="input_line",
        expected_lock_version=expected_lock_version,
    )


@transaction.atomic
def acknowledge_statement(
    statement_id: int,
    *,
    actor,
    idempotency_key: uuid.UUID | None = None,
) -> PayrollStatementAcknowledgement:
    """Acknowledge receiving a current published statement, idempotently."""

    if actor is None or not getattr(actor, "is_authenticated", False):
        raise PayrollPermissionDenied("finance.acknowledge_own_statement")
    statement_reference = PayrollStatement.objects.only(
        "run_id",
        "employee_id",
    ).get(pk=statement_id)
    run_reference = PayrollRun.objects.only("period_id").get(
        pk=statement_reference.run_id
    )
    period = PayrollPeriod.objects.select_for_update().get(pk=run_reference.period_id)
    run = PayrollRun.objects.select_for_update().get(pk=statement_reference.run_id)
    statement = PayrollStatement.objects.select_for_update().get(pk=statement_id)
    if statement.employee_id != actor.pk:
        _operation_error(
            "STATEMENT_NOT_FOUND",
            "Расчётный листок не найден.",
        )
    latest_published = (
        PayrollRun.objects.filter(
            period_id=period.pk,
            status=PayrollRunStatus.PUBLISHED,
        )
        .order_by("-revision")
        .first()
    )
    if latest_published is None or latest_published.pk != run.pk:
        _operation_error(
            "STATEMENT_NOT_CURRENT",
            "Подтвердить можно только актуальный опубликованный листок.",
        )

    if idempotency_key is not None:
        keyed_acknowledgement = PayrollStatementAcknowledgement.objects.filter(
            idempotency_key=idempotency_key
        ).first()
        if keyed_acknowledgement is not None:
            if keyed_acknowledgement.statement_id != statement.pk:
                _operation_error(
                    "IDEMPOTENCY_KEY_CONFLICT",
                    "Ключ уже использован для другого листка.",
                )
            return keyed_acknowledgement

    acknowledgement = PayrollStatementAcknowledgement.objects.filter(
        statement=statement
    ).first()
    if acknowledgement and acknowledgement.acknowledged_at:
        return acknowledgement

    now = timezone.now()
    if acknowledgement is None:
        acknowledgement = PayrollStatementAcknowledgement(
            statement=statement,
            employee=actor,
            content_hash=statement.result_hash,
            idempotency_key=idempotency_key or uuid.uuid4(),
            viewed_at=now,
            acknowledged_at=now,
        )
    else:
        acknowledgement.viewed_at = acknowledgement.viewed_at or now
        acknowledgement.acknowledged_at = now
    acknowledgement.full_clean()
    try:
        with transaction.atomic():
            acknowledgement.save()
    except IntegrityError as exc:
        existing = None
        if idempotency_key is not None:
            existing = PayrollStatementAcknowledgement.objects.filter(
                idempotency_key=idempotency_key
            ).first()
        if existing is not None and existing.statement_id == statement.pk:
            return existing
        raise PayrollOperationError(
            "ACKNOWLEDGEMENT_CONFLICT",
            "Подтверждение уже обработано другой операцией.",
        ) from exc
    _audit(
        actor=actor,
        action="payroll.statement_acknowledged",
        instance=acknowledgement,
        period=period,
        after_hash=statement.result_hash,
    )
    return acknowledgement

"""Host adapter that turns verified attendance hours into payroll work drafts.

The deterministic payroll core remains unaware of the portal's attendance
models.  This adapter is deliberately conservative: it only imports complete,
unambiguous attendance and never approves a payroll record automatically.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from attendance.models import AttendanceRecord
from attendance.services import ABSENCE_ISSUE_MARKERS
from employees.constants import ACTION_REMOTE
from payroll_core import PointPolicy

from finance.enums import (
    ApprovalStatus,
    InputSource,
    PayrollPeriodStatus,
    PayrollRunStatus,
)
from finance.models import PayrollAuditEvent, PayrollPeriod, PayrollWorkRecord

from .access import has_payroll_permission, has_simple_admin_access
from .config import build_rules
from .exceptions import PayrollOperationError, PayrollPermissionDenied

Employee = get_user_model()

ATTENDANCE_WORK_POLICY_CODE = "hours_as_work_units_v1"
ATTENDANCE_WORK_POLICY = {
    "code": ATTENDANCE_WORK_POLICY_CODE,
    "label": "1 час = 1 единица выработки",
    "description": (
        "Норма равна сумме плановых часов, факт — сумме отработанных часов "
        "по проверенным рабочим дням. Импорт создаёт только черновики."
    ),
}
ATTENDANCE_IMPORT_MODES = {"missing_only", "replace_existing"}
ACTION_KEYS = ("create", "update", "revise", "unchanged", "skip", "blocked")
QUANTUM = Decimal("0.0001")


def _operation_error(code: str, message: str, **details):
    raise PayrollOperationError(code, message, details=details)


def _issue(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _date_range(period: PayrollPeriod) -> list:
    days = (period.date_to - period.date_from).days
    return [period.date_from + timedelta(days=offset) for offset in range(days + 1)]


def _finite_decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not number.is_finite() or not math.isfinite(float(number)):
        return None
    return number


def _is_explicit_absence(record: AttendanceRecord) -> bool:
    if record.is_absent:
        return True
    values = [*record.statuses, *record.employee_issues]
    return any(
        marker in str(value).strip().lower()
        for value in values
        for marker in ABSENCE_ISSUE_MARKERS
    )


def _employee_payload(employee) -> dict:
    position = getattr(employee, "position", None)
    links = list(getattr(employee, "departments_links", []).all())
    department_link = next((link for link in links if link.is_active), None)
    return {
        "id": employee.pk,
        "display_name": employee.get_full_name().strip() or f"Сотрудник #{employee.pk}",
        "position": position.name if position is not None else None,
        "department": (
            department_link.department.name if department_link is not None else None
        ),
    }


def _existing_payload(record: PayrollWorkRecord | None) -> dict | None:
    if record is None:
        return None
    return {
        "id": record.pk,
        "revision": record.revision,
        "status": record.status,
        "source": record.source,
        "target_points": str(record.target_points),
        "actual_points": str(record.actual_points),
        "created_by": {
            "id": record.created_by_id,
            "display_name": (
                record.created_by.get_full_name().strip()
                or f"Сотрудник #{record.created_by_id}"
            ),
        },
    }


def _attendance_snapshot_hash(records: list[AttendanceRecord]) -> str:
    payload = [
        {
            "id": record.pk,
            "run": record.analysis_run_id,
            "run_status": record.analysis_run.status,
            "schedule": record.analysis_run.schedule_payload,
            "date": record.date.isoformat(),
            "expected": record.expected_hours,
            "worked": record.work_hours,
            "workday": record.is_workday,
            "effective_workday": record.effective_is_workday,
            "arrival": record.arrival_time,
            "departure": record.departure_time,
            "absent": record.is_absent,
            "technical": record.technical_issues,
            "employee_issues": record.employee_issues,
            "statuses": record.statuses,
            "personnel_status": record.personnel_status,
            "manual": record.is_manually_edited,
            "updated_at": record.updated_at.isoformat(),
        }
        for record in records
    ]
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


def _analyze_attendance(period: PayrollPeriod, records: list[AttendanceRecord]):
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    expected_dates = set(_date_range(period))
    actual_dates = {record.date for record in records}
    missing_dates = sorted(expected_dates - actual_dates)
    if missing_dates:
        blockers.append(
            _issue(
                "MISSING_ATTENDANCE_DAYS",
                f"Не хватает записей посещаемости за {len(missing_dates)} дн.",
            )
        )
    if period.date_to >= timezone.localdate():
        blockers.append(
            _issue(
                "PERIOD_NOT_COMPLETE",
                "Период ещё не завершён; итоговую выработку рассчитывать рано.",
            )
        )

    target = Decimal("0")
    actual = Decimal("0")
    effective_workdays = 0
    technical_issue_days = 0
    absence_days = 0
    manual_days = 0
    overtime_days = 0
    missing_schedule = False

    for record in records:
        if record.analysis_run.status != record.analysis_run.STATUS_SUCCESS:
            blockers.append(
                _issue(
                    "ATTENDANCE_ANALYSIS_FAILED",
                    "Один из дней получен из неуспешного анализа посещаемости.",
                )
            )
        if not record.analysis_run.schedule_payload:
            missing_schedule = True

        worked = _finite_decimal(record.work_hours)
        expected = _finite_decimal(record.expected_hours)
        if worked is not None and worked > 0 and not record.effective_is_workday:
            blockers.append(
                _issue(
                    "OUTSIDE_SCHEDULE_WORK_REQUIRES_REVIEW",
                    "Есть работа вне рабочего графика; её нужно проверить вручную.",
                )
            )
            continue
        if not record.effective_is_workday:
            continue

        effective_workdays += 1
        if record.technical_issues:
            technical_issue_days += 1
            continue
        if record.personnel_status == ACTION_REMOTE and not (
            record.is_manually_edited
            and "work_hours" in (record.manual_edit_payload or {})
        ):
            blockers.append(
                _issue(
                    "REMOTE_ATTENDANCE_UNMEASURABLE",
                    "Удалённый рабочий день не подтверждён ручной записью часов.",
                )
            )
            continue
        if bool(record.arrival_time) != bool(record.departure_time):
            blockers.append(
                _issue(
                    "OPEN_SHIFT",
                    f"За {record.date:%d.%m.%Y} не закрыта смена.",
                )
            )
            continue
        if (
            expected is None
            or worked is None
            or expected <= 0
            or expected > 24
            or worked < 0
            or worked > 24
        ):
            blockers.append(
                _issue(
                    "INVALID_ATTENDANCE_HOURS",
                    f"За {record.date:%d.%m.%Y} указаны некорректные часы.",
                )
            )
            continue
        explicit_absence = _is_explicit_absence(record)
        if worked == 0 and not record.arrival_time and not explicit_absence:
            blockers.append(
                _issue(
                    "UNCLASSIFIED_ZERO_DAY",
                    f"Нулевые часы за {record.date:%d.%m.%Y} не объяснены отсутствием.",
                )
            )
            continue

        target += expected
        actual += worked
        absence_days += int(explicit_absence)
        manual_days += int(record.is_manually_edited)
        overtime_days += int(record.is_overtime)

    if technical_issue_days:
        blockers.append(
            _issue(
                "TECHNICAL_ATTENDANCE_ISSUES",
                f"Технические проблемы обнаружены за {technical_issue_days} дн.",
            )
        )
    if target <= 0:
        blockers.append(
            _issue(
                "ZERO_TARGET_WORK_UNITS",
                "По посещаемости не удалось получить положительную норму часов.",
            )
        )
    if missing_schedule:
        warnings.append(
            _issue(
                "NO_SCHEDULE_SNAPSHOT",
                "В старых данных нет снимка графика; проверьте норму часов.",
            )
        )
    if absence_days:
        warnings.append(
            _issue(
                "ATTENDANCE_ABSENCES_INCLUDED",
                f"Подтверждённые отсутствия учтены как 0 часов: {absence_days} дн.",
            )
        )
    if manual_days:
        warnings.append(
            _issue(
                "MANUAL_ATTENDANCE_INCLUDED",
                f"Использованы ручные исправления посещаемости: {manual_days} дн.",
            )
        )
    if overtime_days:
        warnings.append(
            _issue(
                "ATTENDANCE_OVERTIME_INCLUDED",
                f"Факт включает переработку в рабочие дни: {overtime_days} дн.",
            )
        )

    return {
        "target_points": str(target.quantize(QUANTUM)),
        "actual_points": str(actual.quantize(QUANTUM)),
        "expected_hours": str(target.quantize(QUANTUM)),
        "worked_hours": str(actual.quantize(QUANTUM)),
        "attendance_days": len(records),
        "effective_workdays": effective_workdays,
        "technical_issue_days": technical_issue_days,
        "warnings": _deduplicate_issues(warnings),
        "blockers": _deduplicate_issues(blockers),
        "source_hash": _attendance_snapshot_hash(records),
    }


def _deduplicate_issues(issues: list[dict[str, str]]) -> list[dict[str, str]]:
    result = []
    seen = set()
    for issue in issues:
        key = (issue["code"], issue["message"])
        if key not in seen:
            seen.add(key)
            result.append(issue)
    return result


def _active_work_record(records: list[PayrollWorkRecord]) -> PayrollWorkRecord | None:
    drafts = [record for record in records if record.status == ApprovalStatus.DRAFT]
    if drafts:
        return max(drafts, key=lambda record: (record.revision, record.pk))
    approved = [
        record for record in records if record.status == ApprovalStatus.APPROVED
    ]
    if approved:
        return max(approved, key=lambda record: (record.revision, record.pk))
    return None


def _same_metrics(record: PayrollWorkRecord, metrics: dict) -> bool:
    return record.target_points == Decimal(
        metrics["target_points"]
    ) and record.actual_points == Decimal(metrics["actual_points"])


def _actions_for_item(
    *,
    period: PayrollPeriod,
    actor,
    existing: PayrollWorkRecord | None,
    metrics: dict,
) -> dict[str, str]:
    if metrics["blockers"]:
        return {"missing_only": "blocked", "replace_existing": "blocked"}
    if existing is None:
        if period.status == PayrollPeriodStatus.PUBLISHED:
            return {"missing_only": "blocked", "replace_existing": "blocked"}
        return {"missing_only": "create", "replace_existing": "create"}
    if existing.status == ApprovalStatus.DRAFT:
        replacement = (
            "blocked"
            if existing.created_by_id != actor.pk and not has_simple_admin_access(actor)
            else ("unchanged" if _same_metrics(existing, metrics) else "update")
        )
        return {"missing_only": "skip", "replace_existing": replacement}
    replacement = "unchanged" if _same_metrics(existing, metrics) else "revise"
    return {"missing_only": "skip", "replace_existing": replacement}


def _mode_summaries(items: list[dict]) -> dict:
    summaries = {}
    for mode in sorted(ATTENDANCE_IMPORT_MODES):
        summary = {key: 0 for key in ACTION_KEYS}
        for item in items:
            summary[item["actions"][mode]] += 1
        summary["changes"] = summary["create"] + summary["update"] + summary["revise"]
        summaries[mode] = summary
    return summaries


def _preview_token(period: PayrollPeriod, actor, items: list[dict]) -> str:
    canonical_items = [
        {
            "employee_id": item["employee"]["id"],
            "target": item["target_points"],
            "actual": item["actual_points"],
            "source_hash": item["_source_hash"],
            "blockers": item["blockers"],
            "actions": item["actions"],
            "existing": item["_existing_state"],
        }
        for item in items
    ]
    payload = {
        "policy": ATTENDANCE_WORK_POLICY_CODE,
        "period": period.pk,
        "period_lock_version": period.lock_version,
        "period_status": period.status,
        "actor": actor.pk,
        "items": canonical_items,
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


def build_attendance_work_preview(
    period: PayrollPeriod,
    *,
    actor,
    lock: bool = False,
) -> dict:
    """Build a deterministic, non-mutating attendance import preview."""

    if build_rules().point_policy not in {
        PointPolicy.DISABLED,
        PointPolicy.PROPORTIONAL_WITH_EXCESS,
    }:
        _operation_error(
            "ATTENDANCE_UNIT_POLICY_CONFLICT",
            "Текущая политика начисления несовместима с импортом часов.",
        )

    attendance = AttendanceRecord.objects.filter(
        date__gte=period.date_from,
        date__lte=period.date_to,
    ).select_related("analysis_run", "employee", "employee__position")
    work = PayrollWorkRecord.objects.filter(period=period).select_related(
        "employee", "employee__position", "created_by"
    )
    if lock:
        # Both projections contain nullable outer joins (analysis run and
        # employee position).  Lock only the source rows being imported.
        attendance = attendance.select_for_update(of=("self",))
        work = work.select_for_update(of=("self",))
    attendance_records = list(attendance.order_by("employee_id", "date", "id"))
    work_records = list(work.order_by("employee_id", "revision", "id"))

    attendance_by_employee = defaultdict(list)
    work_by_employee = defaultdict(list)
    for record in attendance_records:
        attendance_by_employee[record.employee_id].append(record)
    for record in work_records:
        work_by_employee[record.employee_id].append(record)
    employee_ids = sorted(set(attendance_by_employee) | set(work_by_employee))
    employees = {
        employee.pk: employee
        for employee in Employee.objects.filter(pk__in=employee_ids)
        .select_related("position")
        .prefetch_related("departments_links__department")
    }

    items = []
    for employee_id in employee_ids:
        records = attendance_by_employee[employee_id]
        metrics = _analyze_attendance(period, records)
        if not records:
            metrics["blockers"].append(
                _issue(
                    "NO_ATTENDANCE_DATA",
                    "За выбранный период нет данных посещаемости.",
                )
            )
        existing = _active_work_record(work_by_employee[employee_id])
        actions = _actions_for_item(
            period=period,
            actor=actor,
            existing=existing,
            metrics=metrics,
        )
        if (
            existing is not None
            and existing.status == ApprovalStatus.DRAFT
            and existing.created_by_id != actor.pk
            and not has_simple_admin_access(actor)
        ):
            metrics["warnings"].append(
                _issue(
                    "FOREIGN_DRAFT_PROTECTED",
                    "Черновик создан другим сотрудником и не будет перезаписан.",
                )
            )
        if period.status == PayrollPeriodStatus.PUBLISHED and existing is None:
            metrics["blockers"].append(
                _issue(
                    "PUBLISHED_WORK_REPLACEMENT_REQUIRED",
                    "В опубликованный период можно добавить только ревизию существующей записи.",
                )
            )
        existing_state = (
            {
                "id": existing.pk,
                "status": existing.status,
                "revision": existing.revision,
                "lock_version": existing.lock_version,
                "created_by": existing.created_by_id,
                "replaces": existing.replaces_id,
                "target": str(existing.target_points),
                "actual": str(existing.actual_points),
            }
            if existing is not None
            else None
        )
        items.append(
            {
                "employee": _employee_payload(employees[employee_id]),
                **{
                    key: value for key, value in metrics.items() if key != "source_hash"
                },
                "existing_record": _existing_payload(existing),
                "actions": actions,
                "_source_hash": metrics["source_hash"],
                "_existing_state": existing_state,
            }
        )

    token = _preview_token(period, actor, items)
    summaries = _mode_summaries(items)
    public_items = [
        {key: value for key, value in item.items() if not key.startswith("_")}
        for item in items
    ]
    return {
        "period_id": period.pk,
        "generated_at": timezone.now().isoformat(),
        "preview_token": token,
        "policy": ATTENDANCE_WORK_POLICY,
        "summary": {
            "attendance_employees": len(attendance_by_employee),
            "existing": sum(item["existing_record"] is not None for item in items),
            "blocked": sum(bool(item["blockers"]) for item in items),
            "modes": summaries,
        },
        "items": public_items,
        "_internal_items": items,
    }


def _ensure_period_accepts_attendance_import(period: PayrollPeriod):
    if period.status == PayrollPeriodStatus.CLOSED:
        _operation_error(
            "PERIOD_INPUTS_LOCKED", "Данные закрытого периода заблокированы."
        )
    if period.current_run is not None and period.current_run.status in {
        PayrollRunStatus.CALCULATED,
        PayrollRunStatus.REVIEW,
        PayrollRunStatus.APPROVED,
    }:
        _operation_error(
            "PERIOD_INPUTS_LOCKED",
            "Сначала верните текущий расчёт на исправление.",
            run_id=period.current_run_id,
        )


def _audit_mutation(*, actor, action, record, period, metadata):
    PayrollAuditEvent.objects.create(
        actor=actor,
        action=action,
        object_type=record._meta.label_lower,
        object_id=str(record.pk),
        period=period,
        metadata={"channel": "attendance_import", **metadata},
    )


@transaction.atomic
def apply_attendance_work_preview(
    period_id: int,
    *,
    actor,
    mode: str,
    preview_token: str,
    expected_period_lock_version: int,
    reason: str = "",
) -> dict:
    """Atomically apply a previously inspected preview as payroll drafts."""

    if (
        not actor
        or not actor.is_authenticated
        or not has_payroll_permission(actor, "finance.manage_payroll_inputs")
    ):
        raise PayrollPermissionDenied("finance.manage_payroll_inputs")
    if mode not in ATTENDANCE_IMPORT_MODES:
        _operation_error("INVALID_ATTENDANCE_IMPORT_MODE", "Неизвестный режим импорта.")
    reason = reason.strip()
    if mode == "replace_existing" and not reason:
        _operation_error(
            "ATTENDANCE_RECALCULATION_REASON_REQUIRED",
            "Для пересчёта существующих записей укажите причину.",
        )

    period = (
        PayrollPeriod.objects.select_for_update(of=("self",))
        .select_related("current_run")
        .get(pk=period_id)
    )
    _ensure_period_accepts_attendance_import(period)
    if period.lock_version != expected_period_lock_version:
        _operation_error(
            "STALE_PERIOD",
            "Период уже изменён; обновите предпросмотр.",
            expected_lock_version=expected_period_lock_version,
            actual_lock_version=period.lock_version,
        )
    preview = build_attendance_work_preview(period, actor=actor, lock=True)
    if preview["preview_token"] != preview_token:
        _operation_error(
            "ATTENDANCE_PREVIEW_STALE",
            "Посещаемость или выработка изменились; обновите предпросмотр.",
        )

    records_by_id = {
        record.pk: record
        for record in PayrollWorkRecord.objects.select_for_update().filter(
            period=period
        )
    }
    summary = {
        "created": 0,
        "updated": 0,
        "revised": 0,
        "unchanged": 0,
        "skipped": 0,
        "blocked": 0,
    }
    changed_records = []
    default_reason = (
        f"Заполнено по посещаемости за {period.date_from:%d.%m.%Y}–"
        f"{period.date_to:%d.%m.%Y}."
    )
    try:
        for item in preview["_internal_items"]:
            action = item["actions"][mode]
            if action == "blocked":
                summary["blocked"] += 1
                continue
            if action == "skip":
                summary["skipped"] += 1
                continue
            if action == "unchanged":
                summary["unchanged"] += 1
                continue

            employee_id = item["employee"]["id"]
            existing_data = item["existing_record"]
            existing = records_by_id.get(existing_data["id"]) if existing_data else None
            prior_max = max(
                (
                    record.revision
                    for record in records_by_id.values()
                    if record.employee_id == employee_id
                ),
                default=0,
            )
            revision = (
                existing.revision
                if action == "update"
                else existing.revision + 1
                if existing is not None
                else prior_max + 1
            )
            source_ref = (
                f"attendance-hours-v1:{period.pk}:{employee_id}:r{revision}:"
                f"{preview_token[:24]}"
            )
            metrics = {
                "target_points": Decimal(item["target_points"]),
                "actual_points": Decimal(item["actual_points"]),
            }
            mutation_reason = reason or default_reason

            if action == "create":
                record = PayrollWorkRecord(
                    period=period,
                    employee_id=employee_id,
                    revision=revision,
                    status=ApprovalStatus.DRAFT,
                    source=InputSource.ATTENDANCE,
                    source_ref=source_ref,
                    reason=mutation_reason,
                    created_by=actor,
                    **metrics,
                )
                record.full_clean()
                record.save(force_insert=True)
                summary["created"] += 1
                audit_action = "payroll.work_record_attendance_draft_created"
            elif action == "update":
                record = existing
                record._expected_lock_version = record.lock_version
                record.target_points = metrics["target_points"]
                record.actual_points = metrics["actual_points"]
                record.source = InputSource.ATTENDANCE
                record.source_ref = source_ref
                record.reason = mutation_reason
                record.full_clean()
                record.save()
                summary["updated"] += 1
                audit_action = "payroll.work_record_attendance_draft_updated"
            else:
                record = PayrollWorkRecord(
                    period=period,
                    employee_id=employee_id,
                    revision=existing.revision + 1,
                    replaces=existing,
                    status=ApprovalStatus.DRAFT,
                    source=InputSource.ATTENDANCE,
                    source_ref=source_ref,
                    reason=mutation_reason,
                    created_by=actor,
                    expected_point_amount=existing.expected_point_amount,
                    expected_gross=existing.expected_gross,
                    expected_recalculated_gross=existing.expected_recalculated_gross,
                    expected_payable=existing.expected_payable,
                    **metrics,
                )
                record.full_clean()
                record.save(force_insert=True)
                summary["revised"] += 1
                audit_action = "payroll.work_record_attendance_revision_created"

            records_by_id[record.pk] = record
            changed_records.append(record)
            _audit_mutation(
                actor=actor,
                action=audit_action,
                record=record,
                period=period,
                metadata={
                    "policy": ATTENDANCE_WORK_POLICY_CODE,
                    "mode": mode,
                    "preview_token": preview_token,
                    "attendance_input_hash": item["_source_hash"],
                    "target_points": item["target_points"],
                    "actual_points": item["actual_points"],
                    "replaces_id": record.replaces_id,
                },
            )
    except ValidationError as exc:
        _operation_error(
            "ATTENDANCE_IMPORT_VALIDATION_FAILED",
            "Черновик выработки не прошёл проверку.",
            errors=(exc.message_dict if hasattr(exc, "message_dict") else exc.messages),
        )
    except IntegrityError:
        _operation_error(
            "ATTENDANCE_IMPORT_CONFLICT",
            "Параллельная операция уже изменила выработку; обновите предпросмотр.",
        )

    PayrollAuditEvent.objects.create(
        actor=actor,
        action="payroll.attendance_work_imported",
        object_type=period._meta.label_lower,
        object_id=str(period.pk),
        period=period,
        metadata={
            "channel": "attendance_import",
            "policy": ATTENDANCE_WORK_POLICY_CODE,
            "mode": mode,
            "preview_token": preview_token,
            "summary": summary,
        },
    )
    return {"mode": mode, "summary": summary, "records": changed_records}

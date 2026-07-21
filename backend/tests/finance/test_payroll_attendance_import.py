from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import timezone

from attendance.models import AttendanceAnalysisRun, AttendanceRecord
from finance.enums import ApprovalStatus, InputSource
from finance.models import PayrollAuditEvent, PayrollPeriod, PayrollWorkRecord
from finance.payroll.attendance import calculate_attendance_day_points

pytestmark = pytest.mark.django_db


def grant(user, *codenames):
    permissions = Permission.objects.filter(
        content_type__app_label="finance",
        codename__in=codenames,
    )
    assert permissions.count() == len(codenames)
    user.user_permissions.add(*permissions)
    for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
        if hasattr(user, cache_name):
            delattr(user, cache_name)


def endpoint(period):
    return reverse(
        "api:v1:finance-payroll:admin-period-attendance-work-records",
        kwargs={"pk": period.pk},
    )


def make_period(creator, *, suffix="base"):
    return PayrollPeriod.objects.create(
        code=f"2024-01-{suffix}",
        name="Тестовый период",
        date_from=date(2024, 1, 1),
        date_to=date(2024, 1, 3),
        pay_date=date(2024, 1, 5),
        created_by=creator,
    )


def make_attendance(employee, *, technical=False):
    run = AttendanceAnalysisRun.objects.create(
        employee=employee,
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 3),
        status=AttendanceAnalysisRun.STATUS_SUCCESS,
        schedule_payload={
            "expected_hours": 8,
            "workdays": ["Monday", "Tuesday"],
        },
    )
    rows = [
        {
            "date": date(2024, 1, 1),
            "work_hours": 8,
            "expected_hours": 8,
            "is_workday": True,
            "effective_is_workday": True,
            "arrival_time": "09:00",
            "departure_time": "17:00",
            "technical_issues": ["Нет данных СКУД"] if technical else [],
        },
        {
            "date": date(2024, 1, 2),
            "work_hours": 0,
            "expected_hours": 8,
            "is_workday": True,
            "effective_is_workday": True,
            "is_absent": True,
        },
        {
            "date": date(2024, 1, 3),
            "work_hours": 0,
            "expected_hours": 8,
            "is_workday": False,
            "effective_is_workday": False,
        },
    ]
    return [
        AttendanceRecord.objects.create(
            analysis_run=run,
            employee=employee,
            **row,
        )
        for row in rows
    ]


def apply_payload(preview, period, *, mode="missing_only", reason=""):
    return {
        "mode": mode,
        "preview_token": preview["preview_token"],
        "expected_period_lock_version": period.lock_version,
        "reason": reason,
    }


def test_attendance_preview_and_missing_only_create_audited_draft(
    user_factory,
    auth_client_factory,
):
    manager = user_factory(email="attendance.manager@example.test")
    employee = user_factory(email="attendance.employee@example.test")
    grant(manager, "manage_payroll_inputs")
    period = make_period(manager)
    make_attendance(employee)
    client = auth_client_factory(manager)

    preview_response = client.get(endpoint(period))

    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["policy"] == {
        "code": "attendance_to_daily_points_v2",
        "label": "Посещаемость переводится в баллы дневной нормы",
        "description": (
            "Полностью отработанный день даёт дневную норму баллов. "
            "Неполный день и переработка рассчитываются пропорционально "
            "плановым часам."
        ),
        "formula": ("Баллы дня = дневная норма × отработанные часы ÷ плановые часы"),
        "daily_target_points": "5.0000",
    }
    assert preview["summary"] == {
        "attendance_employees": 1,
        "existing": 0,
        "blocked": 0,
        "modes": {
            "missing_only": {
                "create": 1,
                "update": 0,
                "revise": 0,
                "unchanged": 0,
                "skip": 0,
                "blocked": 0,
                "changes": 1,
            },
            "replace_existing": {
                "create": 1,
                "update": 0,
                "revise": 0,
                "unchanged": 0,
                "skip": 0,
                "blocked": 0,
                "changes": 1,
            },
        },
    }
    item = preview["items"][0]
    assert item["expected_hours"] == "16.0000"
    assert item["worked_hours"] == "8.0000"
    assert item["daily_target_points"] == "5.0000"
    assert item["target_points"] == "10.0000"
    assert item["actual_points"] == "5.0000"
    assert item["actions"] == {
        "missing_only": "create",
        "replace_existing": "create",
    }
    assert item["warnings"][0]["code"] == "ATTENDANCE_ABSENCES_INCLUDED"

    applied = client.post(
        endpoint(period),
        apply_payload(preview, period),
        format="json",
    )

    assert applied.status_code == 200
    assert applied.json()["summary"] == {
        "created": 1,
        "updated": 0,
        "revised": 0,
        "unchanged": 0,
        "skipped": 0,
        "blocked": 0,
    }
    record = PayrollWorkRecord.objects.get(period=period, employee=employee)
    assert record.status == ApprovalStatus.DRAFT
    assert record.source == InputSource.ATTENDANCE
    assert record.target_points == Decimal("10.0000")
    assert record.target_points_overridden is False
    assert record.actual_points == Decimal("5.0000")
    assert record.created_by == manager
    assert record.approved_by is None
    assert PayrollAuditEvent.objects.filter(
        action="payroll.work_record_attendance_draft_created",
        object_id=str(record.pk),
    ).exists()


def test_personnel_non_working_day_keeps_verified_attendance_points(
    user_factory,
    auth_client_factory,
):
    manager = user_factory(email="attendance.personnel.manager@example.test")
    employee = user_factory(email="attendance.personnel.employee@example.test")
    grant(manager, "manage_payroll_inputs")
    period = make_period(manager, suffix="personnel-separation")
    records = make_attendance(employee)
    worked_record = records[0]
    worked_record.effective_is_workday = False
    worked_record.personnel_status = "on_leave"
    worked_record.personnel_status_label = "В отпуске"
    worked_record.statuses = ["work_outside_personnel_schedule"]
    worked_record.is_overtime = True
    worked_record.overtime_hours = worked_record.work_hours
    worked_record.save()

    assert calculate_attendance_day_points(
        worked_record,
        daily_point_value=Decimal("5"),
    ) == Decimal("5.0000")

    preview_response = auth_client_factory(manager).get(endpoint(period))

    assert preview_response.status_code == 200
    item = preview_response.json()["items"][0]
    assert item["target_points"] == "10.0000"
    assert item["actual_points"] == "5.0000"
    assert item["blockers"] == []
    assert {warning["code"] for warning in item["warnings"]} >= {
        "ATTENDANCE_OVERTIME_INCLUDED",
        "ATTENDANCE_PERSONNEL_CONFLICT_INCLUDED",
    }


def test_replace_mode_revises_approved_and_preserves_excel_controls(
    user_factory,
    auth_client_factory,
):
    manager = user_factory(email="attendance.revise.manager@example.test")
    maker = user_factory(email="attendance.revise.maker@example.test")
    checker = user_factory(email="attendance.revise.checker@example.test")
    employee = user_factory(email="attendance.revise.employee@example.test")
    grant(manager, "manage_payroll_inputs")
    period = make_period(manager, suffix="revise")
    make_attendance(employee)
    approved = PayrollWorkRecord.objects.create(
        period=period,
        employee=employee,
        target_points="10",
        actual_points="9",
        expected_payable="1234.50",
        status=ApprovalStatus.APPROVED,
        created_by=maker,
        approved_by=checker,
        approved_at=timezone.now(),
    )
    client = auth_client_factory(manager)
    preview = client.get(endpoint(period)).json()
    assert preview["items"][0]["actions"] == {
        "missing_only": "skip",
        "replace_existing": "revise",
    }

    skipped = client.post(
        endpoint(period),
        apply_payload(preview, period),
        format="json",
    )
    assert skipped.status_code == 200
    assert skipped.json()["summary"]["skipped"] == 1
    assert PayrollWorkRecord.objects.filter(period=period).count() == 1

    replace_preview = client.get(endpoint(period)).json()
    revised_response = client.post(
        endpoint(period),
        apply_payload(
            replace_preview,
            period,
            mode="replace_existing",
            reason="Сверка с посещаемостью",
        ),
        format="json",
    )

    assert revised_response.status_code == 200
    assert revised_response.json()["summary"]["revised"] == 1
    revision = PayrollWorkRecord.objects.get(replaces=approved)
    assert revision.status == ApprovalStatus.DRAFT
    assert revision.revision == 2
    assert revision.source == InputSource.ATTENDANCE
    assert revision.expected_payable == Decimal("1234.50")
    approved.refresh_from_db()
    assert approved.status == ApprovalStatus.APPROVED


def test_replace_updates_only_own_draft_and_protects_foreign_draft(
    user_factory,
    auth_client_factory,
):
    manager = user_factory(email="attendance.draft.manager@example.test")
    other = user_factory(email="attendance.draft.other@example.test")
    own_employee = user_factory(email="attendance.draft.own@example.test")
    foreign_employee = user_factory(email="attendance.draft.foreign@example.test")
    grant(manager, "manage_payroll_inputs")
    period = make_period(manager, suffix="drafts")
    make_attendance(own_employee)
    make_attendance(foreign_employee)
    own = PayrollWorkRecord.objects.create(
        period=period,
        employee=own_employee,
        target_points="1",
        actual_points="1",
        created_by=manager,
    )
    foreign = PayrollWorkRecord.objects.create(
        period=period,
        employee=foreign_employee,
        target_points="1",
        actual_points="1",
        created_by=other,
    )
    client = auth_client_factory(manager)
    preview = client.get(endpoint(period)).json()
    actions = {
        item["employee"]["id"]: item["actions"]["replace_existing"]
        for item in preview["items"]
    }
    assert actions == {own_employee.pk: "update", foreign_employee.pk: "blocked"}

    response = client.post(
        endpoint(period),
        apply_payload(
            preview,
            period,
            mode="replace_existing",
            reason="Повторная сверка",
        ),
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["summary"]["updated"] == 1
    assert response.json()["summary"]["blocked"] == 1
    own.refresh_from_db()
    foreign.refresh_from_db()
    assert own.target_points == Decimal("10.0000")
    assert own.target_points_overridden is False
    assert own.actual_points == Decimal("5.0000")
    assert own.lock_version == 1
    assert own.source == InputSource.ATTENDANCE
    assert foreign.target_points == Decimal("1")
    assert foreign.lock_version == 0


def test_staff_admin_can_refresh_a_foreign_attendance_draft(
    user_factory,
    auth_client_factory,
):
    administrator = user_factory(
        email="attendance.simple.admin@example.test",
        staff=True,
    )
    creator = user_factory(email="attendance.simple.creator@example.test")
    employee = user_factory(email="attendance.simple.employee@example.test")
    period = make_period(administrator, suffix="simple-admin")
    make_attendance(employee)
    record = PayrollWorkRecord.objects.create(
        period=period,
        employee=employee,
        target_points="1",
        actual_points="1",
        created_by=creator,
    )
    client = auth_client_factory(administrator)
    preview = client.get(endpoint(period)).json()

    assert preview["items"][0]["actions"]["replace_existing"] == "update"
    assert not any(
        issue["code"] == "FOREIGN_DRAFT_PROTECTED"
        for issue in preview["items"][0]["warnings"]
    )

    response = client.post(
        endpoint(period),
        apply_payload(
            preview,
            period,
            mode="replace_existing",
            reason="Обновление администратором",
        ),
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["summary"]["updated"] == 1
    record.refresh_from_db()
    assert record.target_points == Decimal("10.0000")
    assert record.target_points_overridden is False
    assert record.actual_points == Decimal("5.0000")
    assert record.lock_version == 1


def test_preview_blocks_technical_days_and_rejects_stale_source(
    user_factory,
    auth_client_factory,
):
    manager = user_factory(email="attendance.stale.manager@example.test")
    blocked_employee = user_factory(email="attendance.blocked@example.test")
    ready_employee = user_factory(email="attendance.ready@example.test")
    grant(manager, "manage_payroll_inputs")
    period = make_period(manager, suffix="stale")
    make_attendance(blocked_employee, technical=True)
    ready_records = make_attendance(ready_employee)
    client = auth_client_factory(manager)
    preview = client.get(endpoint(period)).json()
    blocked = next(
        item
        for item in preview["items"]
        if item["employee"]["id"] == blocked_employee.pk
    )
    assert blocked["actions"]["missing_only"] == "blocked"
    assert "TECHNICAL_ATTENDANCE_ISSUES" in {
        issue["code"] for issue in blocked["blockers"]
    }

    ready_records[0].work_hours = 7
    ready_records[0].save(update_fields=["work_hours", "updated_at"])
    stale = client.post(
        endpoint(period),
        apply_payload(preview, period),
        format="json",
    )

    assert stale.status_code == 409
    assert stale.json()["code"] == "ATTENDANCE_PREVIEW_STALE"
    assert PayrollWorkRecord.objects.count() == 0


def test_attendance_import_permission_and_point_policy_guards(
    settings,
    user_factory,
    auth_client_factory,
):
    manager = user_factory(email="attendance.policy.manager@example.test")
    outsider = user_factory(email="attendance.policy.outsider@example.test")
    employee = user_factory(email="attendance.policy.employee@example.test")
    grant(manager, "manage_payroll_inputs")
    period = make_period(manager, suffix="policy")
    make_attendance(employee)

    forbidden = auth_client_factory(outsider).get(endpoint(period))
    assert forbidden.status_code == 403

    settings.FINANCE_PAYROLL = {"POINT_POLICY": "excess_only"}
    incompatible = auth_client_factory(manager).get(endpoint(period))
    assert incompatible.status_code == 409
    assert incompatible.json()["code"] == "ATTENDANCE_UNIT_POLICY_CONFLICT"


def test_period_lock_version_is_checked_before_import(
    user_factory,
    auth_client_factory,
):
    manager = user_factory(email="attendance.lock.manager@example.test")
    employee = user_factory(email="attendance.lock.employee@example.test")
    grant(manager, "manage_payroll_inputs")
    period = make_period(manager, suffix="lock")
    make_attendance(employee)
    client = auth_client_factory(manager)
    preview = client.get(endpoint(period)).json()

    payload = apply_payload(preview, period)
    payload["expected_period_lock_version"] = period.lock_version + 1
    response = client.post(endpoint(period), payload, format="json")

    assert response.status_code == 409
    assert response.json()["code"] == "STALE_PERIOD"
    assert PayrollWorkRecord.objects.count() == 0

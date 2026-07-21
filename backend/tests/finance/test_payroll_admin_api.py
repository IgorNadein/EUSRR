import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import Permission
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from attendance.models import AttendanceAnalysisRun, AttendanceRecord
from employees.constants import ACTION_DISMISSED, ACTION_HIRED, ACTION_REHIRED
from employees.models import EmployeeAction
from finance.models import (
    EmployeePayRate,
    PayrollAuditEvent,
    PayrollComponent,
    PayrollDailyWorkEntry,
    PayrollInputLine,
    PayrollPeriod,
    PayrollRun,
    PayrollWorkRecord,
)
from requests_app.enums import RequestStatus, RequestType
from requests_app.models import Request

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


def api_url(name, **kwargs):
    return reverse(f"api:v1:finance-payroll:{name}", kwargs=kwargs or None)


def assert_no_store(response):
    assert "no-store" in response["Cache-Control"]


def make_period(*, creator, code="2026-06"):
    return PayrollPeriod.objects.create(
        code=code,
        name="Июнь 2026",
        date_from="2026-06-01",
        date_to="2026-06-30",
        pay_date="2026-07-05",
        currency="RUB",
        created_by=creator,
    )


def test_work_record_target_is_optional_and_can_return_to_automatic(
    user_factory,
    auth_client_factory,
):
    manager = user_factory(email="automatic.work.manager@example.test")
    employee = user_factory(email="automatic.work.employee@example.test")
    grant(manager, "manage_payroll_inputs")
    period = make_period(creator=manager)
    client = auth_client_factory(manager)

    created = client.post(
        api_url("admin-work-record-list"),
        {
            "period_id": period.pk,
            "employee_id": employee.pk,
            "target_points": None,
            "actual_points": "12.0000",
            "reason": "",
        },
        format="json",
    )

    assert created.status_code == 201, created.content
    assert created.json()["target_points"] == "110.0000"
    assert created.json()["target_points_overridden"] is False

    manual = client.patch(
        api_url("admin-work-record-detail", pk=created.json()["id"]),
        {
            "target_points": "77.0000",
            "expected_lock_version": created.json()["lock_version"],
        },
        format="json",
    )

    assert manual.status_code == 200, manual.content
    assert manual.json()["target_points"] == "77.0000"
    assert manual.json()["target_points_overridden"] is True

    automatic = client.patch(
        api_url("admin-work-record-detail", pk=created.json()["id"]),
        {
            "target_points": None,
            "expected_lock_version": manual.json()["lock_version"],
        },
        format="json",
    )

    assert automatic.status_code == 200, automatic.content
    assert automatic.json()["target_points"] == "110.0000"
    assert automatic.json()["target_points_overridden"] is False


def test_admin_workspace_rejects_anonymous_and_generic_model_permission(
    user_factory,
    auth_client_factory,
):
    url = api_url("admin-workspace")
    anonymous = auth_client_factory()
    anonymous_response = anonymous.get(url)
    assert anonymous_response.status_code in {401, 403}
    assert_no_store(anonymous_response)

    generic_viewer = user_factory(email="generic.payroll.viewer@example.test")
    generic_permission = Permission.objects.get(
        content_type__app_label="finance",
        codename="view_payrollperiod",
    )
    generic_viewer.user_permissions.add(generic_permission)
    response = auth_client_factory(generic_viewer).get(url)

    assert response.status_code == 403
    assert response.json()["code"] == "PERMISSION_DENIED"
    assert_no_store(response)

    override_only = user_factory(email="override.only@example.test")
    grant(override_only, "override_payroll_approval")
    override_response = auth_client_factory(override_only).get(url)
    assert override_response.status_code == 403
    assert override_response.json()["code"] == "PERMISSION_DENIED"


def test_workspace_contract_is_minimal_and_redacts_money_without_view_all(
    user_factory,
    auth_client_factory,
):
    manager = user_factory(
        email="workspace.manager@example.test",
        first_name="Мария",
        last_name="Расчётова",
    )
    grant(manager, "manage_payroll_inputs")
    response = auth_client_factory(manager).get(api_url("admin-workspace"))

    assert response.status_code == 200
    assert_no_store(response)
    body = response.json()
    assert set(body["permissions"]) == {
        "full_access",
        "manage_inputs",
        "approve_inputs",
        "calculate",
        "approve_run",
        "override_approval",
        "publish",
        "view_all",
        "audit",
    }
    assert body["permissions"]["manage_inputs"] is True
    assert body["permissions"]["full_access"] is False
    assert body["permissions"]["override_approval"] is False
    assert body["summary"] is None
    assert set(body["readiness"]) == {
        "rates",
        "work_records",
        "input_lines",
        "calculation",
    }
    employee = next(item for item in body["employees"] if item["id"] == manager.pk)
    assert employee == {
        "id": manager.pk,
        "display_name": "Мария Расчётова",
        "position": None,
        "department": None,
    }


def test_period_table_lists_all_employees_and_requires_view_all(
    user_factory,
    auth_client_factory,
):
    manager = user_factory(email="table.manager@example.test")
    viewer = user_factory(email="table.viewer@example.test")
    employee = user_factory(
        email="table.employee@example.test",
        first_name="Анна",
        last_name="Итогова",
    )
    missing_employee = user_factory(email="table.missing@example.test")
    grant(manager, "manage_payroll_inputs")
    grant(viewer, "view_all_payroll")
    period = make_period(creator=manager)
    EmployeePayRate.objects.create(
        employee=employee,
        amount="80000",
        point_rate="150",
        effective_from="2026-01-01",
        created_by=manager,
    )
    PayrollWorkRecord.objects.create(
        period=period,
        employee=employee,
        target_points="110",
        actual_points="115",
        created_by=manager,
    )
    bonus = PayrollComponent.objects.get(code="BONUS")
    PayrollInputLine.objects.create(
        period=period,
        employee=employee,
        component=bonus,
        amount="1000",
        reason="Премия",
        created_by=manager,
    )
    url = api_url("admin-period-table", pk=period.pk)

    denied = auth_client_factory(manager).get(url)
    assert denied.status_code == 403
    assert denied.json()["code"] == "PERMISSION_DENIED"

    response = auth_client_factory(viewer).get(url)

    assert response.status_code == 200, response.content
    assert_no_store(response)
    body = response.json()
    assert body["period_id"] == period.pk
    assert body["calculation_rules"]["point_policy"] == "proportional_with_excess"
    assert body["calculation_rules"]["money_quantum"] == "0.01"
    assert body["calculation_rules"]["rounding"] == "ROUND_HALF_UP"
    assert body["run"] is None
    assert body["summary"]["employee_count"] >= 4
    assert {column["code"] for column in body["component_columns"]} == set(
        PayrollComponent.objects.filter(is_active=True)
        .exclude(code__in={"BASE", "POINT_EXCESS"})
        .values_list("code", flat=True)
    )
    row = next(item for item in body["rows"] if item["employee"]["id"] == employee.pk)
    assert row["employee"]["display_name"] == "Анна Итогова"
    assert row["status"] == "draft"
    assert row["rate_amount"] == "80000.0000"
    assert row["in_norm_point_rate"] == "736.3636"
    assert row["target_points"] == "110.0000"
    assert row["attendance_points"] is None
    assert row["personnel_points"] == "0.0000"
    assert row["actual_points"] == "115.0000"
    assert row["point_delta"] == "5.0000"
    assert row["point_amount"] == "750.00"
    assert row["component_amounts"] == {"BONUS": "1000.00"}
    assert row["gross_total"] == "81750.00"
    assert row["payable"] == "81750.00"
    assert row["totals_preliminary"] is True
    assert body["summary"]["preliminary_count"] == body["summary"]["employee_count"]
    missing_row = next(
        item for item in body["rows"] if item["employee"]["id"] == missing_employee.pk
    )
    assert missing_row["status"] == "incomplete"
    assert missing_row["rate_amount"] is None
    assert missing_row["target_points"] == "110.0000"
    assert missing_row["target_points_automatic"] is True
    assert missing_row["actual_points"] is None
    assert missing_row["payable"] == "0.00"


def test_period_table_projects_attendance_and_official_personnel_points(
    user_factory,
    auth_client_factory,
    monkeypatch,
):
    manager = user_factory(email="table.projections.manager@example.test")
    employee = user_factory(
        email="table.projections.employee@example.test",
        first_name="Иван",
        last_name="Проекционный",
    )
    grant(manager, "view_all_payroll")
    period = make_period(creator=manager)
    attendance_run = AttendanceAnalysisRun.objects.create(
        employee=employee,
        period_start="2026-06-01",
        period_end="2026-06-30",
        status=AttendanceAnalysisRun.STATUS_SUCCESS,
        schedule_payload={
            "workdays": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        },
    )
    AttendanceRecord.objects.create(
        analysis_run=attendance_run,
        employee=employee,
        date="2026-06-01",
        arrival_time="08:00",
        departure_time="17:00",
        work_hours=9,
        expected_hours=9,
        effective_is_workday=True,
    )
    PayrollWorkRecord.objects.create(
        period=period,
        employee=employee,
        target_points="220",
        target_points_overridden=True,
        actual_points="0",
        created_by=manager,
    )
    EmployeeAction.objects.create(
        employee=employee,
        action=ACTION_HIRED,
        date=timezone.make_aware(datetime(2026, 6, 1)),
    )
    AttendanceRecord.objects.create(
        analysis_run=attendance_run,
        employee=employee,
        date="2026-06-02",
        arrival_time="08:00",
        departure_time="12:30",
        work_hours=4.5,
        expected_hours=9,
        effective_is_workday=True,
    )

    vacation = Request.objects.create(
        employee=employee,
        type=RequestType.VACATION,
        date_from=date(2026, 6, 3),
        date_to=date(2026, 6, 3),
        status=RequestStatus.PENDING,
    )
    vacation.status = RequestStatus.APPROVED
    vacation.approver = manager
    vacation.decided_at = timezone.now()
    vacation.save(update_fields=["status", "approver", "decided_at", "updated_at"])

    action = EmployeeAction.objects.get(source_request=vacation)
    assert action.date.date() == date(2026, 6, 3)
    monkeypatch.setattr(
        "finance.payroll.work_norm.timezone.localdate",
        lambda: date(2026, 6, 4),
    )

    response = auth_client_factory(manager).get(
        api_url("admin-period-table", pk=period.pk),
    )

    assert response.status_code == 200, response.content
    row = next(
        item
        for item in response.json()["rows"]
        if item["employee"]["id"] == employee.pk
    )
    assert row["target_points"] == "220.0000"
    assert row["attendance_points"] == "15.0000"
    assert row["personnel_points"] == "20.0000"


def test_period_table_personnel_points_respect_employment_boundaries(
    user_factory,
    auth_client_factory,
    monkeypatch,
):
    manager = user_factory(email="table.employment.manager@example.test")
    employee = user_factory(email="table.employment.employee@example.test")
    grant(manager, "view_all_payroll")
    period = make_period(creator=manager)
    PayrollWorkRecord.objects.create(
        period=period,
        employee=employee,
        target_points="220",
        target_points_overridden=True,
        actual_points="0",
        created_by=manager,
    )
    for action, action_date in (
        (ACTION_HIRED, datetime(2026, 6, 5)),
        (ACTION_DISMISSED, datetime(2026, 6, 10)),
        (ACTION_REHIRED, datetime(2026, 6, 15)),
    ):
        EmployeeAction.objects.create(
            employee=employee,
            action=action,
            date=timezone.make_aware(action_date),
        )
    monkeypatch.setattr(
        "finance.payroll.work_norm.timezone.localdate",
        lambda: date(2026, 7, 1),
    )

    response = auth_client_factory(manager).get(
        api_url("admin-period-table", pk=period.pk),
    )

    assert response.status_code == 200, response.content
    row = next(
        item
        for item in response.json()["rows"]
        if item["employee"]["id"] == employee.pk
    )
    assert row["personnel_points"] == "150.0000"


def test_period_point_breakdown_returns_daily_sources(
    user_factory,
    auth_client_factory,
    monkeypatch,
):
    viewer = user_factory(email="point.breakdown.viewer@example.test")
    employee = user_factory(
        email="point.breakdown.employee@example.test",
        first_name="Ирина",
        last_name="Подневная",
    )
    grant(viewer, "view_all_payroll")
    period = make_period(creator=viewer)
    attendance_run = AttendanceAnalysisRun.objects.create(
        employee=employee,
        period_start="2026-06-01",
        period_end="2026-06-30",
        status=AttendanceAnalysisRun.STATUS_SUCCESS,
        schedule_payload={
            "workdays": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        },
    )
    for day, worked in ((date(2026, 6, 1), 9), (date(2026, 6, 2), 4.5)):
        AttendanceRecord.objects.create(
            analysis_run=attendance_run,
            employee=employee,
            date=day,
            arrival_time="08:00",
            departure_time="17:00" if worked == 9 else "12:30",
            work_hours=worked,
            expected_hours=9,
            effective_is_workday=True,
        )
    PayrollWorkRecord.objects.create(
        period=period,
        employee=employee,
        target_points="220",
        target_points_overridden=True,
        actual_points="15",
        created_by=viewer,
    )
    PayrollDailyWorkEntry.objects.create(
        period=period,
        employee=employee,
        work_date=date(2026, 6, 1),
        target_points="10",
        actual_points="15",
    )
    EmployeeAction.objects.create(
        employee=employee,
        action=ACTION_HIRED,
        date=timezone.make_aware(datetime(2026, 6, 1)),
    )
    vacation = Request.objects.create(
        employee=employee,
        type=RequestType.VACATION,
        date_from=date(2026, 6, 2),
        date_to=date(2026, 6, 2),
        status=RequestStatus.PENDING,
    )
    vacation.status = RequestStatus.APPROVED
    vacation.approver = viewer
    vacation.decided_at = timezone.now()
    vacation.save(update_fields=["status", "approver", "decided_at", "updated_at"])
    assert EmployeeAction.objects.filter(source_request=vacation).exists()
    monkeypatch.setattr(
        "finance.payroll.work_norm.timezone.localdate",
        lambda: date(2026, 6, 3),
    )

    response = auth_client_factory(viewer).get(
        api_url(
            "admin-period-point-breakdown",
            pk=period.pk,
            employee_id=employee.pk,
        )
    )

    assert response.status_code == 200, response.content
    assert_no_store(response)
    body = response.json()
    assert body["employee"]["display_name"] == "Ирина Подневная"
    assert body["target_points"] == "220.0000"
    assert body["actual_points"] == "15.0000"
    assert body["undated_work_points"] is None
    assert body["work_points_mode"] == "daily_entries"
    june_first = next(item for item in body["dates"] if item["date"] == "2026-06-01")
    june_second = next(item for item in body["dates"] if item["date"] == "2026-06-02")
    weekend = next(item for item in body["dates"] if item["date"] == "2026-06-06")
    assert {key: june_first[key] for key in (
        "date",
        "is_workday",
        "attendance_points",
        "personnel_points",
        "work_points",
    )} == {
        "date": "2026-06-01",
        "is_workday": True,
        "attendance_points": "10.0000",
        "personnel_points": "10.0000",
        "work_points": "15.0000",
    }
    assert june_first["attendance_record"]["id"] == AttendanceRecord.objects.get(
        employee=employee,
        date="2026-06-01",
    ).pk
    assert june_first["work_entry"]["actual_points"] == "15.0000"
    assert june_first["work_entry"]["note"] == ""
    assert [item["action"] for item in june_first["personnel_detail"]["actions"]] == [
        ACTION_HIRED
    ]
    assert {key: june_second[key] for key in (
        "date",
        "is_workday",
        "attendance_points",
        "personnel_points",
        "work_points",
    )} == {
        "date": "2026-06-02",
        "is_workday": True,
        "attendance_points": "5.0000",
        "personnel_points": "0.0000",
        "work_points": None,
    }
    assert june_second["work_entry"] is None
    assert [item["id"] for item in june_second["personnel_detail"]["requests"]] == [
        vacation.pk
    ]
    assert june_second["personnel_detail"]["requests"][0]["status"] == "approved"
    assert {key: weekend[key] for key in (
        "date",
        "is_workday",
        "attendance_points",
        "personnel_points",
        "work_points",
    )} == {
        "date": "2026-06-06",
        "is_workday": False,
        "attendance_points": None,
        "personnel_points": None,
        "work_points": None,
    }

    undated_employee = user_factory(email="point.breakdown.undated@example.test")
    PayrollWorkRecord.objects.create(
        period=period,
        employee=undated_employee,
        target_points="220",
        target_points_overridden=True,
        actual_points="42",
        created_by=viewer,
    )
    undated_response = auth_client_factory(viewer).get(
        api_url(
            "admin-period-point-breakdown",
            pk=period.pk,
            employee_id=undated_employee.pk,
        )
    )
    assert undated_response.status_code == 200, undated_response.content
    undated_body = undated_response.json()
    assert undated_body["undated_work_points"] == "42.0000"
    assert undated_body["undated_work_record"]["actual_points"] == "42.0000"
    assert undated_body["work_points_mode"] == "unavailable"
    assert all(item["work_points"] is None for item in undated_body["dates"])


def test_component_cell_can_be_cleared_and_voids_all_active_lines(
    user_factory,
    auth_client_factory,
):
    manager = user_factory(email="table.clear.manager@example.test")
    employee = user_factory(email="table.clear.employee@example.test")
    grant(manager, "manage_payroll_inputs", "view_all_payroll")
    period = make_period(creator=manager)
    bonus = PayrollComponent.objects.get(code="BONUS")
    vacation = PayrollComponent.objects.get(code="VACATION_PAY")
    draft = PayrollInputLine.objects.create(
        period=period,
        employee=employee,
        component=bonus,
        amount="3000",
        reason="Черновая премия",
        created_by=manager,
    )
    approved = PayrollInputLine.objects.create(
        period=period,
        employee=employee,
        component=bonus,
        amount="7000",
        reason="Утверждённая премия",
        status="approved",
        created_by=manager,
        approved_by=manager,
        approved_at=timezone.now(),
        self_approval_overridden=True,
    )
    unrelated = PayrollInputLine.objects.create(
        period=period,
        employee=employee,
        component=vacation,
        amount="500",
        reason="Отпускные",
        created_by=manager,
    )
    client = auth_client_factory(manager)

    response = client.post(
        api_url("admin-component-cell-clear", pk=period.pk),
        {"employee_id": employee.pk, "component_id": bonus.pk},
        format="json",
    )

    assert response.status_code == 200, response.content
    assert response.json() == {"draft": 1, "approved": 1, "total": 2}
    draft.refresh_from_db()
    approved.refresh_from_db()
    unrelated.refresh_from_db()
    for line in (draft, approved):
        assert line.status == "voided"
        assert line.voided_by_id == manager.pk
        assert line.voided_at is not None
        assert line.void_reason == "Значение очищено в итоговой таблице"
    assert unrelated.status == "draft"
    assert (
        PayrollAuditEvent.objects.filter(
            action="payroll.input_line_voided_from_table",
            object_id__in=[str(draft.pk), str(approved.pk)],
        ).count()
        == 2
    )

    table_response = client.get(api_url("admin-period-table", pk=period.pk))
    assert table_response.status_code == 200, table_response.content
    row = next(
        item
        for item in table_response.json()["rows"]
        if item["employee"]["id"] == employee.pk
    )
    assert "BONUS" not in row["component_amounts"]
    assert row["component_amounts"] == {"VACATION_PAY": "500.00"}

    repeated = client.post(
        api_url("admin-component-cell-clear", pk=period.pk),
        {"employee_id": employee.pk, "component_id": bonus.pk},
        format="json",
    )
    assert repeated.status_code == 200
    assert repeated.json() == {"draft": 0, "approved": 0, "total": 0}


def test_period_table_includes_all_active_and_only_inactive_employees_with_work(
    user_factory,
    auth_client_factory,
):
    manager = user_factory(email="table.scope.manager@example.test")
    viewer = user_factory(email="table.scope.viewer@example.test")
    active_without_work = user_factory(
        email="table.scope.active@example.test",
        first_name="Активный",
        last_name="Сотрудник",
    )
    inactive_with_work = user_factory(
        email="table.scope.inactive.with.work@example.test",
        first_name="Уволенный",
        last_name="С Выработкой",
        active=False,
    )
    inactive_without_work = user_factory(
        email="table.scope.inactive.without.work@example.test",
        first_name="Уволенный",
        last_name="Без Выработки",
        active=False,
    )
    inactive_with_zero_work = user_factory(
        email="table.scope.inactive.zero.work@example.test",
        first_name="Уволенный",
        last_name="С Нулевой Выработкой",
        active=False,
    )
    grant(viewer, "view_all_payroll")
    period = make_period(creator=manager)
    PayrollWorkRecord.objects.create(
        period=period,
        employee=inactive_with_work,
        target_points="110",
        actual_points="25",
        created_by=manager,
    )
    PayrollWorkRecord.objects.create(
        period=period,
        employee=inactive_with_zero_work,
        target_points="110",
        actual_points="0",
        created_by=manager,
    )
    EmployeePayRate.objects.create(
        employee=inactive_without_work,
        amount="80000",
        effective_from="2026-01-01",
        created_by=manager,
    )
    bonus = PayrollComponent.objects.get(code="BONUS")
    PayrollInputLine.objects.create(
        period=period,
        employee=inactive_without_work,
        component=bonus,
        amount="1000",
        reason="Начисление без выработки",
        created_by=manager,
    )

    response = auth_client_factory(viewer).get(
        api_url("admin-period-table", pk=period.pk),
    )

    assert response.status_code == 200, response.content
    employee_ids = {row["employee"]["id"] for row in response.json()["rows"]}
    assert active_without_work.pk in employee_ids
    assert inactive_with_work.pk in employee_ids
    assert inactive_without_work.pk not in employee_ids
    assert inactive_with_zero_work.pk not in employee_ids


def test_period_table_preview_matches_excel_point_formula_with_bonus(
    user_factory,
    auth_client_factory,
):
    manager = user_factory(email="table.excel.formula.manager@example.test")
    employee = user_factory(email="table.excel.formula.employee@example.test")
    grant(manager, "view_all_payroll")
    period = make_period(creator=manager)
    EmployeePayRate.objects.create(
        employee=employee,
        amount="30000",
        point_rate=None,
        effective_from=period.date_from,
        created_by=manager,
    )
    PayrollWorkRecord.objects.create(
        period=period,
        employee=employee,
        target_points="110",
        actual_points="90",
        created_by=manager,
    )
    PayrollInputLine.objects.create(
        period=period,
        employee=employee,
        component=PayrollComponent.objects.get(code="BONUS"),
        amount="10000",
        created_by=manager,
    )

    response = auth_client_factory(manager).get(
        api_url("admin-period-table", pk=period.pk),
    )

    assert response.status_code == 200, response.content
    row = next(
        item
        for item in response.json()["rows"]
        if item["employee"]["id"] == employee.pk
    )
    assert row["in_norm_point_rate"] == "363.6364"
    assert row["point_rate"] is None
    assert row["point_amount"] == "-7272.73"
    assert row["gross_before_adjustments"] == "40000.00"
    assert row["adjustment_total"] == "-7272.73"
    assert row["gross_total"] == "32727.27"
    assert row["payable"] == "32727.27"


def test_staff_admin_gets_full_pilot_access_and_can_manage_any_draft(
    user_factory,
    auth_client_factory,
):
    administrator = user_factory(
        email="simple.payroll.admin@example.test",
        staff=True,
    )
    creator = user_factory(email="simple.payroll.creator@example.test")
    first_employee = user_factory(email="simple.payroll.employee.one@example.test")
    second_employee = user_factory(email="simple.payroll.employee.two@example.test")
    client = auth_client_factory(administrator)

    workspace = client.get(api_url("admin-workspace"))

    assert workspace.status_code == 200
    assert workspace.json()["permissions"] == {
        "manage_inputs": True,
        "approve_inputs": True,
        "calculate": True,
        "approve_run": True,
        "override_approval": True,
        "publish": True,
        "view_all": True,
        "audit": True,
        "full_access": True,
    }

    foreign_rate = EmployeePayRate.objects.create(
        employee=first_employee,
        amount="80000",
        effective_from="2026-01-01",
        created_by=creator,
    )
    patched = client.patch(
        api_url("admin-pay-rate-detail", pk=foreign_rate.pk),
        {"amount": "81000.0000", "expected_lock_version": 0},
        format="json",
    )
    assert patched.status_code == 200
    assert patched.json()["amount"] == "81000.0000"

    own_rate = client.post(
        api_url("admin-pay-rate-list"),
        {
            "employee_id": second_employee.pk,
            "rate_code": "BASE",
            "amount": "90000.0000",
            "point_rate": "0.0000",
            "currency": "RUB",
            "effective_from": "2026-01-01",
            "reason": "",
        },
        format="json",
    )
    assert own_rate.status_code == 201
    approved = client.post(
        api_url("admin-pay-rate-approve", pk=own_rate.json()["id"]),
        {"expected_lock_version": own_rate.json()["lock_version"]},
        format="json",
    )
    assert approved.status_code == 200
    assert approved.json()["approved_by_id"] == administrator.pk
    assert "self_approval_overridden" not in approved.json()


def test_staff_admin_can_approve_all_period_drafts_atomically(
    user_factory,
    auth_client_factory,
):
    administrator = user_factory(email="bulk.approval.admin@example.test", staff=True)
    employee = user_factory(email="bulk.approval.employee@example.test")
    period = make_period(creator=administrator)
    bonus = PayrollComponent.objects.get(code="BONUS")
    client = auth_client_factory(administrator)

    rate = EmployeePayRate.objects.create(
        employee=employee,
        amount="80000.0000",
        point_rate=None,
        effective_from=period.date_from,
        created_by=administrator,
    )
    work_record = PayrollWorkRecord.objects.create(
        period=period,
        employee=employee,
        target_points="110.0000",
        actual_points="105.0000",
        created_by=administrator,
    )
    input_line = PayrollInputLine.objects.create(
        period=period,
        employee=employee,
        component=bonus,
        amount="5000.00",
        created_by=administrator,
    )

    response = client.post(
        api_url("admin-period-approve-drafts", pk=period.pk),
        {},
        format="json",
    )

    assert response.status_code == 200, response.content
    assert response.json() == {
        "period_id": period.pk,
        "summary": {
            "rates": 1,
            "work_records": 1,
            "input_lines": 1,
            "total": 3,
        },
    }
    rate.refresh_from_db()
    work_record.refresh_from_db()
    input_line.refresh_from_db()
    assert rate.status == "approved"
    assert work_record.status == "approved"
    assert input_line.status == "approved"
    assert rate.approved_by_id == administrator.pk
    assert work_record.approved_by_id == administrator.pk
    assert input_line.approved_by_id == administrator.pk
    assert_no_store(response)


def test_approve_all_period_drafts_rolls_back_when_one_draft_is_invalid(
    user_factory,
    auth_client_factory,
):
    administrator = user_factory(email="bulk.rollback.admin@example.test", staff=True)
    employee = user_factory(email="bulk.rollback.employee@example.test")
    period = make_period(creator=administrator)
    bonus = PayrollComponent.objects.get(code="BONUS")
    rate = EmployeePayRate.objects.create(
        employee=employee,
        amount="80000.0000",
        effective_from=period.date_from,
        created_by=administrator,
    )
    PayrollInputLine.objects.create(
        period=period,
        employee=employee,
        component=bonus,
        amount="5000.00",
        created_by=administrator,
    )
    bonus.is_active = False
    bonus.save(update_fields=["is_active"])

    response = auth_client_factory(administrator).post(
        api_url("admin-period-approve-drafts", pk=period.pk),
        {},
        format="json",
    )

    assert response.status_code == 409
    assert response.json()["code"] == "PAYROLL_COMPONENT_INACTIVE"
    rate.refresh_from_db()
    assert rate.status == "draft"


def test_staff_without_finance_permissions_is_denied_when_simple_mode_is_disabled(
    settings,
    user_factory,
    auth_client_factory,
):
    settings.FINANCE_PAYROLL = {"SIMPLE_ADMIN_ACCESS": False}
    administrator = user_factory(
        email="granular.payroll.admin@example.test",
        staff=True,
    )

    response = auth_client_factory(administrator).get(api_url("admin-workspace"))

    assert response.status_code == 403
    assert response.json()["code"] == "PERMISSION_DENIED"
    assert_no_store(response)


def test_workspace_blocks_period_outside_ruleset_effective_dates(
    settings,
    user_factory,
    auth_client_factory,
):
    settings.FINANCE_PAYROLL = {"EFFECTIVE_FROM": "2026-07-01"}
    operator = user_factory(email="ruleset.operator@example.test")
    checker = user_factory(email="ruleset.checker@example.test")
    employee = user_factory(email="ruleset.employee@example.test")
    grant(operator, "calculate_payroll")
    period = make_period(creator=operator)
    approved_at = timezone.now()
    EmployeePayRate.objects.create(
        employee=employee,
        amount="80000",
        effective_from="2026-01-01",
        status="approved",
        created_by=operator,
        approved_by=checker,
        approved_at=approved_at,
    )
    PayrollWorkRecord.objects.create(
        period=period,
        employee=employee,
        target_points="100",
        actual_points="100",
        status="approved",
        created_by=operator,
        approved_by=checker,
        approved_at=approved_at,
    )
    client = auth_client_factory(operator)

    workspace = client.get(
        api_url("admin-workspace"),
        {"period_id": period.pk},
    )

    assert workspace.status_code == 200
    readiness = workspace.json()["readiness"]
    assert readiness["rates"]["ready"] is True
    assert readiness["work_records"]["ready"] is True
    assert readiness["calculation"]["ready"] is False
    ruleset_blocker = next(
        blocker
        for blocker in readiness["calculation"]["blockers"]
        if blocker["code"] == "RULESET_NOT_EFFECTIVE"
    )
    assert ruleset_blocker == {
        "code": "RULESET_NOT_EFFECTIVE",
        "message": (
            "Для выбранного периода нет действующих правил расчёта. "
            "Набор eusrr-standard, версия 2026.07.4, применяется с 01.07.2026. "
            "Измените период или подключите историческую версию правил."
        ),
        "details": {
            "period": {
                "date_from": "2026-06-01",
                "date_to": "2026-06-30",
            },
            "ruleset": {
                "id": "eusrr-standard",
                "version": "2026.07.4",
                "effective_from": "2026-07-01",
            },
        },
    }

    calculation = client.post(
        api_url("admin-period-calculate", pk=period.pk),
        {
            "expected_lock_version": period.lock_version,
            "idempotency_key": str(uuid.uuid4()),
            "recalculation_reason": "",
        },
        format="json",
    )
    assert calculation.status_code == 409
    assert calculation.json()["code"] == "RULESET_NOT_EFFECTIVE"
    assert calculation.json()["message"] == ruleset_blocker["message"]
    assert (
        calculation.json()["details"]["period"] == ruleset_blocker["details"]["period"]
    )
    assert (
        calculation.json()["details"]["ruleset"]
        == ruleset_blocker["details"]["ruleset"]
    )
    assert PayrollRun.objects.count() == 0


def test_period_and_rate_drafts_use_exact_optimistic_versions_and_maker_checker(
    user_factory,
    auth_client_factory,
):
    maker = user_factory(email="rate.maker@example.test")
    other_maker = user_factory(email="other.rate.maker@example.test")
    approver = user_factory(email="rate.approver@example.test")
    employee = user_factory(
        email="paid.employee@example.test",
        first_name="Игорь",
        last_name="Надеин",
    )
    inactive_employee = user_factory(
        email="inactive.paid.employee@example.test",
        active=False,
    )
    grant(maker, "manage_payroll_inputs", "approve_payroll_inputs")
    grant(other_maker, "manage_payroll_inputs")
    grant(approver, "approve_payroll_inputs")
    maker_client = auth_client_factory(maker)

    period_response = maker_client.post(
        api_url("admin-period-list"),
        {
            "code": "2026-06",
            "name": "Июнь 2026",
            "date_from": "2026-06-01",
            "date_to": "2026-06-30",
            "pay_date": "2026-07-05",
            "currency": "RUB",
        },
        format="json",
    )
    assert period_response.status_code == 201
    assert period_response.json()["lock_version"] == 0
    assert_no_store(period_response)
    period_id = period_response.json()["id"]

    period_patch_url = api_url("admin-period-detail", pk=period_id)
    patched_period = maker_client.patch(
        period_patch_url,
        {"name": "Зарплата за июнь", "expected_lock_version": 0},
        format="json",
    )
    assert patched_period.status_code == 200
    assert patched_period.json()["lock_version"] == 1
    stale_period = maker_client.patch(
        period_patch_url,
        {"name": "Устаревшее название", "expected_lock_version": 0},
        format="json",
    )
    assert stale_period.status_code == 409
    assert stale_period.json()["code"] == "STALE_PERIOD"
    assert PayrollPeriod.objects.get(pk=period_id).name == "Зарплата за июнь"

    rate_list_url = api_url("admin-pay-rate-list")
    inactive_response = maker_client.post(
        rate_list_url,
        {
            "employee_id": inactive_employee.pk,
            "rate_code": "BASE",
            "amount": "80000.0000",
            "point_rate": "0.0000",
            "currency": "RUB",
            "effective_from": "2026-06-01",
            "reason": "",
        },
        format="json",
    )
    assert inactive_response.status_code == 400

    created = maker_client.post(
        rate_list_url,
        {
            "employee_id": employee.pk,
            "rate_code": "BASE",
            "amount": "80000.0000",
            "point_rate": "0.0000",
            "currency": "RUB",
            "effective_from": "2026-06-01",
            "reason": "",
        },
        format="json",
    )
    assert created.status_code == 201
    rate_id = created.json()["id"]
    assert created.json()["created_by"] == {
        "id": maker.pk,
        "display_name": maker.get_full_name(),
    }
    assert created.json()["employee"]["position"] is None
    assert "source_ref" not in created.json()
    assert "idempotency_key" not in created.json()

    detail_url = api_url("admin-pay-rate-detail", pk=rate_id)
    first_patch = maker_client.patch(
        detail_url,
        {"amount": "81000.0000", "expected_lock_version": 0},
        format="json",
    )
    assert first_patch.status_code == 200
    assert first_patch.json()["lock_version"] == 1

    stale_patch = maker_client.patch(
        detail_url,
        {"amount": "999999.0000", "expected_lock_version": 0},
        format="json",
    )
    assert stale_patch.status_code == 409
    assert stale_patch.json()["code"] == "STALE_DRAFT"
    assert_no_store(stale_patch)
    assert EmployeePayRate.objects.get(pk=rate_id).amount == Decimal("81000")

    hidden_from_other_maker = auth_client_factory(other_maker).patch(
        detail_url,
        {"amount": "82000.0000", "expected_lock_version": 1},
        format="json",
    )
    assert hidden_from_other_maker.status_code == 404

    stale_approval = auth_client_factory(approver).post(
        api_url("admin-pay-rate-approve", pk=rate_id),
        {"expected_lock_version": 0},
        format="json",
    )
    assert stale_approval.status_code == 409
    assert stale_approval.json()["code"] == "APPROVAL_VERSION_CONFLICT"
    assert EmployeePayRate.objects.get(pk=rate_id).status == "draft"

    self_approval = maker_client.post(
        api_url("admin-pay-rate-approve", pk=rate_id),
        {"expected_lock_version": 1},
        format="json",
    )
    assert self_approval.status_code == 409
    assert self_approval.json()["code"] == "SELF_APPROVAL_FORBIDDEN"

    approved = auth_client_factory(approver).post(
        api_url("admin-pay-rate-approve", pk=rate_id),
        {"expected_lock_version": 1},
        format="json",
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["approved_by"]["id"] == approver.pk

    immutable_patch = maker_client.patch(
        detail_url,
        {"amount": "83000.0000", "expected_lock_version": 1},
        format="json",
    )
    assert immutable_patch.status_code == 404
    assert EmployeePayRate.objects.get(pk=rate_id).amount == Decimal("81000")

    revision = maker_client.post(
        api_url("admin-pay-rate-revise", pk=rate_id),
        {"reason": "Новая согласованная ставка"},
        format="json",
    )
    assert revision.status_code == 201
    assert revision.json()["status"] == "draft"
    assert revision.json()["revision"] == 2
    assert revision.json()["replaces_id"] == rate_id


def test_bulk_point_rate_updates_drafts_and_revises_approved_rates(
    user_factory,
    auth_client_factory,
):
    manager = user_factory(email="bulk.point.manager@example.test")
    approver = user_factory(email="bulk.point.approver@example.test")
    draft_employee = user_factory(email="bulk.point.draft@example.test")
    approved_employee = user_factory(email="bulk.point.approved@example.test")
    unchanged_employee = user_factory(email="bulk.point.unchanged@example.test")
    untouched_employee = user_factory(email="bulk.point.untouched@example.test")
    grant(manager, "manage_payroll_inputs")
    period = make_period(creator=manager)
    approved_at = timezone.now()

    draft = EmployeePayRate.objects.create(
        employee=draft_employee,
        amount="80000",
        point_rate="10",
        effective_from="2026-01-01",
        reason="Исходный черновик",
        created_by=manager,
    )
    approved = EmployeePayRate.objects.create(
        employee=approved_employee,
        amount="90000",
        point_rate="20",
        effective_from="2026-01-01",
        status="approved",
        created_by=approver,
        approved_by=manager,
        approved_at=approved_at,
    )
    unchanged = EmployeePayRate.objects.create(
        employee=unchanged_employee,
        amount="95000",
        point_rate="125",
        effective_from="2026-01-01",
        status="approved",
        created_by=approver,
        approved_by=manager,
        approved_at=approved_at,
    )
    untouched = EmployeePayRate.objects.create(
        employee=untouched_employee,
        amount="100000",
        point_rate="30",
        effective_from="2026-01-01",
        created_by=manager,
    )

    response = auth_client_factory(manager).post(
        api_url("admin-period-bulk-point-rate", pk=period.pk),
        {
            "employee_ids": [
                draft_employee.pk,
                approved_employee.pk,
                unchanged_employee.pk,
            ],
            "point_rate": "125.0000",
            "reason": "Единая цена балла на период",
        },
        format="json",
    )

    assert response.status_code == 200, response.content
    assert_no_store(response)
    assert response.json() == {
        "mode": "fixed",
        "point_rate": "125.0000",
        "summary": {
            "selected_employees": 3,
            "updated_drafts": 1,
            "created_revisions": 1,
            "unchanged": 1,
            "skipped": 0,
        },
    }
    draft.refresh_from_db()
    approved.refresh_from_db()
    unchanged.refresh_from_db()
    untouched.refresh_from_db()
    assert draft.point_rate == Decimal("125")
    assert draft.lock_version == 1
    assert draft.reason == "Исходный черновик"
    assert approved.status == "approved"
    assert unchanged.status == "approved"
    assert untouched.point_rate == Decimal("30")

    revision = EmployeePayRate.objects.get(replaces=approved)
    assert revision.point_rate == Decimal("125")
    assert revision.amount == approved.amount
    assert revision.status == "draft"
    assert revision.created_by == manager
    assert revision.reason == "Единая цена балла на период"
    assert not EmployeePayRate.objects.filter(replaces=unchanged).exists()

    assert (
        PayrollAuditEvent.objects.filter(
            action="payroll.rate_bulk_point_rate_updated",
            object_id=str(draft.pk),
            period=period,
        ).count()
        == 1
    )
    assert (
        PayrollAuditEvent.objects.filter(
            action="payroll.rate_bulk_point_rate_revision_created",
            object_id=str(revision.pk),
            period=period,
        ).count()
        == 1
    )


def test_bulk_point_rate_uses_in_norm_price_without_persisting_derived_value(
    user_factory,
    auth_client_factory,
):
    manager = user_factory(email="bulk.point.in.norm.manager@example.test")
    first_employee = user_factory(email="bulk.point.in.norm.first@example.test")
    second_employee = user_factory(email="bulk.point.in.norm.second@example.test")
    grant(manager, "manage_payroll_inputs", "view_all_payroll")
    period = make_period(creator=manager)
    first_rate = EmployeePayRate.objects.create(
        employee=first_employee,
        amount="80000",
        point_rate="0",
        effective_from="2026-01-01",
        created_by=manager,
    )
    second_rate = EmployeePayRate.objects.create(
        employee=second_employee,
        amount="90000",
        point_rate="0",
        effective_from="2026-01-01",
        created_by=manager,
    )
    PayrollWorkRecord.objects.create(
        period=period,
        employee=first_employee,
        target_points="100",
        actual_points="110",
        created_by=manager,
    )
    PayrollWorkRecord.objects.create(
        period=period,
        employee=second_employee,
        target_points="120",
        actual_points="120",
        created_by=manager,
    )

    response = auth_client_factory(manager).post(
        api_url("admin-period-bulk-point-rate", pk=period.pk),
        {
            "employee_ids": [first_employee.pk, second_employee.pk],
            "mode": "in_norm",
            "reason": "Сверх нормы оплачивать по основной цене балла",
        },
        format="json",
    )

    assert response.status_code == 200, response.content
    assert response.json() == {
        "mode": "in_norm",
        "point_rate": None,
        "summary": {
            "selected_employees": 2,
            "updated_drafts": 2,
            "created_revisions": 0,
            "unchanged": 0,
            "skipped": 0,
        },
    }
    first_rate.refresh_from_db()
    second_rate.refresh_from_db()
    assert first_rate.point_rate is None
    assert second_rate.point_rate is None

    table = auth_client_factory(manager).get(
        api_url("admin-period-table", pk=period.pk),
    )
    assert table.status_code == 200, table.content
    first_row = next(
        row
        for row in table.json()["rows"]
        if row["employee"]["id"] == first_employee.pk
    )
    assert first_row["point_rate"] is None
    assert first_row["in_norm_point_rate"] == "800.0000"
    assert first_row["point_amount"] == "8000.00"
    assert first_row["gross_total"] == "88000.00"
    first_rate.refresh_from_db()
    assert first_rate.point_rate is None


def test_bulk_point_rate_defaults_an_omitted_price_to_automatic(
    user_factory,
    auth_client_factory,
):
    manager = user_factory(email="bulk.point.zero.manager@example.test")
    employee = user_factory(email="bulk.point.zero.employee@example.test")
    grant(manager, "manage_payroll_inputs")
    period = make_period(creator=manager)
    rate = EmployeePayRate.objects.create(
        employee=employee,
        amount="80000",
        point_rate="125",
        effective_from="2026-01-01",
        created_by=manager,
    )

    response = auth_client_factory(manager).post(
        api_url("admin-period-bulk-point-rate", pk=period.pk),
        {
            "employee_ids": [employee.pk],
            "reason": "Использовать автоматическую цену сверх нормы",
        },
        format="json",
    )

    assert response.status_code == 200, response.content
    assert response.json()["mode"] == "in_norm"
    assert response.json()["point_rate"] is None
    rate.refresh_from_db()
    assert rate.point_rate is None


def test_bulk_point_rate_rejects_locked_period_without_partial_changes(
    user_factory,
    auth_client_factory,
):
    manager = user_factory(email="bulk.point.locked.manager@example.test")
    employee = user_factory(email="bulk.point.locked.employee@example.test")
    grant(manager, "manage_payroll_inputs")
    period = make_period(creator=manager)
    period.status = "closed"
    period.save(update_fields=["status"])
    rate = EmployeePayRate.objects.create(
        employee=employee,
        amount="80000",
        point_rate="10",
        effective_from="2026-01-01",
        created_by=manager,
    )

    response = auth_client_factory(manager).post(
        api_url("admin-period-bulk-point-rate", pk=period.pk),
        {
            "employee_ids": [employee.pk],
            "point_rate": "125.0000",
            "reason": "Не должно примениться",
        },
        format="json",
    )

    assert response.status_code == 409
    assert response.json()["code"] == "PERIOD_INPUTS_LOCKED"
    rate.refresh_from_db()
    assert rate.point_rate == Decimal("10")
    assert rate.lock_version == 0


def test_bulk_target_points_creates_updates_and_revises_work_records(
    user_factory,
    auth_client_factory,
):
    manager = user_factory(email="bulk.target.manager@example.test")
    approver = user_factory(email="bulk.target.approver@example.test")
    draft_employee = user_factory(email="bulk.target.draft@example.test")
    approved_employee = user_factory(email="bulk.target.approved@example.test")
    missing_employee = user_factory(email="bulk.target.missing@example.test")
    unchanged_employee = user_factory(email="bulk.target.unchanged@example.test")
    grant(manager, "manage_payroll_inputs")
    period = make_period(creator=manager)
    draft = PayrollWorkRecord.objects.create(
        period=period,
        employee=draft_employee,
        target_points="100",
        actual_points="80",
        created_by=manager,
    )
    approved = PayrollWorkRecord.objects.create(
        period=period,
        employee=approved_employee,
        target_points="120",
        actual_points="90",
        status="approved",
        created_by=approver,
        approved_by=manager,
        approved_at=timezone.now(),
    )
    unchanged = PayrollWorkRecord.objects.create(
        period=period,
        employee=unchanged_employee,
        target_points="115",
        actual_points="70",
        created_by=manager,
    )

    response = auth_client_factory(manager).post(
        api_url("admin-period-bulk-target-points", pk=period.pk),
        {
            "employee_ids": [
                draft_employee.pk,
                approved_employee.pk,
                missing_employee.pk,
                unchanged_employee.pk,
            ],
            "mode": "fixed",
            "target_points": "115.0000",
            "reason": "Единая норма на период",
        },
        format="json",
    )

    assert response.status_code == 200, response.content
    assert response.json() == {
        "mode": "fixed",
        "target_points": "115.0000",
        "summary": {
            "selected_employees": 4,
            "created_drafts": 1,
            "updated_drafts": 1,
            "created_revisions": 1,
            "unchanged": 1,
            "skipped": 0,
        },
    }
    draft.refresh_from_db()
    unchanged.refresh_from_db()
    assert draft.target_points == Decimal("115")
    assert draft.target_points_overridden is True
    assert draft.actual_points == Decimal("80")
    assert draft.lock_version == 1
    assert unchanged.lock_version == 0

    revision = PayrollWorkRecord.objects.get(replaces=approved)
    assert revision.target_points == Decimal("115")
    assert revision.target_points_overridden is True
    assert revision.actual_points == Decimal("90")
    assert revision.status == "draft"
    assert revision.reason == "Единая норма на период"

    created = PayrollWorkRecord.objects.get(employee=missing_employee, period=period)
    assert created.target_points == Decimal("115")
    assert created.target_points_overridden is True
    assert created.actual_points == Decimal("0")
    assert created.status == "draft"


def test_bulk_target_points_restores_automatic_norm_without_empty_records(
    user_factory,
    auth_client_factory,
):
    manager = user_factory(email="bulk.target.auto.manager@example.test")
    employee = user_factory(email="bulk.target.auto.employee@example.test")
    missing_employee = user_factory(email="bulk.target.auto.missing@example.test")
    grant(manager, "manage_payroll_inputs")
    period = make_period(creator=manager)
    record = PayrollWorkRecord.objects.create(
        period=period,
        employee=employee,
        target_points="77",
        actual_points="50",
        created_by=manager,
    )

    response = auth_client_factory(manager).post(
        api_url("admin-period-bulk-target-points", pk=period.pk),
        {
            "employee_ids": [employee.pk, missing_employee.pk],
            "mode": "automatic",
            "reason": "Вернуть норму по рабочему графику",
        },
        format="json",
    )

    assert response.status_code == 200, response.content
    assert response.json() == {
        "mode": "automatic",
        "target_points": None,
        "summary": {
            "selected_employees": 2,
            "created_drafts": 0,
            "updated_drafts": 1,
            "created_revisions": 0,
            "unchanged": 1,
            "skipped": 0,
        },
    }
    record.refresh_from_db()
    assert record.target_points == Decimal("110")
    assert record.target_points_overridden is False
    assert record.actual_points == Decimal("50")
    assert not PayrollWorkRecord.objects.filter(
        employee=missing_employee,
        period=period,
    ).exists()


def test_bulk_pay_rate_creates_updates_and_revises_selected_employee_rates(
    user_factory,
    auth_client_factory,
):
    manager = user_factory(email="bulk.rate.manager@example.test")
    approver = user_factory(email="bulk.rate.approver@example.test")
    new_employee = user_factory(email="bulk.rate.new@example.test")
    inherited_employee = user_factory(email="bulk.rate.inherited@example.test")
    draft_employee = user_factory(email="bulk.rate.draft@example.test")
    approved_employee = user_factory(email="bulk.rate.approved@example.test")
    unchanged_employee = user_factory(email="bulk.rate.unchanged@example.test")
    untouched_employee = user_factory(email="bulk.rate.untouched@example.test")
    grant(manager, "manage_payroll_inputs")
    period = make_period(creator=manager)
    approved_at = timezone.now()

    EmployeePayRate.objects.create(
        employee=inherited_employee,
        amount="80000",
        point_rate="75",
        effective_from="2026-05-01",
        status="approved",
        created_by=approver,
        approved_by=manager,
        approved_at=approved_at,
    )
    draft = EmployeePayRate.objects.create(
        employee=draft_employee,
        amount="85000",
        point_rate="20",
        effective_from="2026-06-01",
        reason="Исходный черновик",
        created_by=manager,
    )
    approved = EmployeePayRate.objects.create(
        employee=approved_employee,
        amount="90000",
        point_rate="30",
        effective_from="2026-06-01",
        status="approved",
        created_by=approver,
        approved_by=manager,
        approved_at=approved_at,
    )
    unchanged = EmployeePayRate.objects.create(
        employee=unchanged_employee,
        amount="100000",
        point_rate="40",
        effective_from="2026-06-01",
        status="approved",
        created_by=approver,
        approved_by=manager,
        approved_at=approved_at,
    )
    untouched = EmployeePayRate.objects.create(
        employee=untouched_employee,
        amount="70000",
        point_rate="15",
        effective_from="2026-06-01",
        created_by=manager,
    )

    response = auth_client_factory(manager).post(
        api_url("admin-period-bulk-pay-rate", pk=period.pk),
        {
            "employee_ids": [
                new_employee.pk,
                inherited_employee.pk,
                draft_employee.pk,
                approved_employee.pk,
                unchanged_employee.pk,
            ],
            "amount": "100000.0000",
            "effective_from": "2026-06-01",
            "reason": "Единая ставка на период",
        },
        format="json",
    )

    assert response.status_code == 200, response.content
    assert_no_store(response)
    assert response.json() == {
        "amount": "100000.0000",
        "effective_from": "2026-06-01",
        "summary": {
            "selected_employees": 5,
            "created_drafts": 2,
            "updated_drafts": 1,
            "created_revisions": 1,
            "unchanged": 1,
            "skipped": 0,
        },
    }

    created = EmployeePayRate.objects.get(
        employee=new_employee,
        effective_from="2026-06-01",
    )
    inherited = EmployeePayRate.objects.get(
        employee=inherited_employee,
        effective_from="2026-06-01",
    )
    revision = EmployeePayRate.objects.get(replaces=approved)
    draft.refresh_from_db()
    unchanged.refresh_from_db()
    untouched.refresh_from_db()

    assert created.amount == Decimal("100000")
    assert created.point_rate is None
    assert created.status == "draft"
    assert inherited.amount == Decimal("100000")
    assert inherited.point_rate == Decimal("75")
    assert inherited.revision == 1
    assert draft.amount == Decimal("100000")
    assert draft.point_rate == Decimal("20")
    assert draft.reason == "Исходный черновик"
    assert draft.lock_version == 1
    assert revision.amount == Decimal("100000")
    assert revision.point_rate == Decimal("30")
    assert revision.replaces == approved
    assert revision.status == "draft"
    assert revision.reason == "Единая ставка на период"
    assert unchanged.status == "approved"
    assert untouched.amount == Decimal("70000")

    assert (
        PayrollAuditEvent.objects.filter(
            action="payroll.rate_bulk_created",
            period=period,
        ).count()
        == 2
    )
    assert (
        PayrollAuditEvent.objects.filter(
            action="payroll.rate_bulk_amount_updated",
            object_id=str(draft.pk),
            period=period,
        ).count()
        == 1
    )
    assert (
        PayrollAuditEvent.objects.filter(
            action="payroll.rate_bulk_amount_revision_created",
            object_id=str(revision.pk),
            period=period,
        ).count()
        == 1
    )


def test_bulk_pay_rate_rejects_date_outside_selected_period(
    user_factory,
    auth_client_factory,
):
    manager = user_factory(email="bulk.rate.date.manager@example.test")
    employee = user_factory(email="bulk.rate.date.employee@example.test")
    grant(manager, "manage_payroll_inputs")
    period = make_period(creator=manager)

    response = auth_client_factory(manager).post(
        api_url("admin-period-bulk-pay-rate", pk=period.pk),
        {
            "employee_ids": [employee.pk],
            "amount": "100000.0000",
            "effective_from": "2026-07-01",
            "reason": "Дата вне периода",
        },
        format="json",
    )

    assert response.status_code == 409
    assert response.json()["code"] == "RATE_DATE_OUTSIDE_PERIOD"
    assert not EmployeePayRate.objects.filter(employee=employee).exists()


def test_native_api_runs_complete_service_workflow_and_redacts_aggregate_money(
    user_factory,
    auth_client_factory,
):
    maker = user_factory(email="workflow.maker@example.test")
    input_approver = user_factory(email="workflow.input.approver@example.test")
    operator = user_factory(email="workflow.operator@example.test")
    run_approver = user_factory(email="workflow.run.approver@example.test")
    publisher = user_factory(email="workflow.publisher@example.test")
    viewer = user_factory(email="workflow.viewer@example.test")
    employee = user_factory(email="workflow.employee@example.test")
    grant(maker, "manage_payroll_inputs")
    grant(input_approver, "approve_payroll_inputs")
    grant(operator, "calculate_payroll")
    grant(run_approver, "approve_payroll")
    grant(publisher, "publish_payroll")
    grant(viewer, "view_all_payroll")
    period = make_period(creator=maker)

    maker_client = auth_client_factory(maker)
    rate_response = maker_client.post(
        api_url("admin-pay-rate-list"),
        {
            "employee_id": employee.pk,
            "rate_code": "BASE",
            "amount": "80000.0000",
            "point_rate": "0.0000",
            "currency": "RUB",
            "effective_from": "2026-06-01",
            "reason": "",
        },
        format="json",
    )
    assert rate_response.status_code == 201
    work_response = maker_client.post(
        api_url("admin-work-record-list"),
        {
            "period_id": period.pk,
            "employee_id": employee.pk,
            "target_points": "110.0000",
            "actual_points": "110.0000",
            "reason": "",
        },
        format="json",
    )
    assert work_response.status_code == 201
    bonus = PayrollComponent.objects.get(code="BONUS")
    input_response = maker_client.post(
        api_url("admin-input-line-list"),
        {
            "period_id": period.pk,
            "employee_id": employee.pk,
            "component_id": bonus.pk,
            "amount": "100.00",
            "reason": "Премия за месяц",
        },
        format="json",
    )
    assert input_response.status_code == 201
    assert input_response.json()["component"]["code"] == "BONUS"

    checker_client = auth_client_factory(input_approver)
    for route_name, object_response in (
        ("admin-pay-rate-approve", rate_response),
        ("admin-work-record-approve", work_response),
        ("admin-input-line-approve", input_response),
    ):
        approval = checker_client.post(
            api_url(route_name, pk=object_response.json()["id"]),
            {"expected_lock_version": object_response.json()["lock_version"]},
            format="json",
        )
        assert approval.status_code == 200
        assert approval.json()["status"] == "approved"
        assert "self_approval_overridden" not in approval.json()

    operator_client = auth_client_factory(operator)
    workspace_before = operator_client.get(
        api_url("admin-workspace"),
        {"period_id": period.pk},
    )
    assert workspace_before.status_code == 200
    assert workspace_before.json()["readiness"]["calculation"]["ready"] is True
    assert workspace_before.json()["summary"] is None

    calculation = operator_client.post(
        api_url("admin-period-calculate", pk=period.pk),
        {
            "expected_lock_version": period.lock_version,
            "idempotency_key": str(uuid.uuid4()),
            "recalculation_reason": "",
        },
        format="json",
    )
    assert calculation.status_code == 201
    assert calculation.json()["status"] == "calculated"
    assert calculation.json()["gross_total"] is None
    assert calculation.json()["requested_by"]["id"] == operator.pk
    assert "input_hash" not in calculation.json()
    assert_no_store(calculation)
    run_id = calculation.json()["id"]

    table = auth_client_factory(viewer).get(
        api_url("admin-period-table", pk=period.pk),
    )
    assert table.status_code == 200, table.content
    table_body = table.json()
    assert table_body["run"] == {
        "id": run_id,
        "revision": 1,
        "status": "calculated",
    }
    employee_row = next(
        row for row in table_body["rows"] if row["employee"]["id"] == employee.pk
    )
    assert employee_row["status"] == "calculated"
    assert employee_row["rate_amount"] == "80000"
    assert employee_row["target_points"] == "110"
    assert employee_row["actual_points"] == "110"
    assert employee_row["component_amounts"] == {"BONUS": "100.00"}
    assert employee_row["gross_total"] == "80100.00"
    assert employee_row["deduction_total"] == "0.00"
    assert employee_row["payable"] == "80100.00"
    assert employee_row["totals_preliminary"] is False
    assert table_body["summary"]["calculated_count"] == 1
    assert table_body["summary"]["gross_total"] == "80100.00"

    blocked_draft = maker_client.post(
        api_url("admin-input-line-list"),
        {
            "period_id": period.pk,
            "employee_id": employee.pk,
            "component_id": bonus.pk,
            "amount": "50.00",
            "reason": "Поздняя премия",
        },
        format="json",
    )
    assert blocked_draft.status_code == 409
    assert blocked_draft.json()["code"] == "PERIOD_INPUTS_LOCKED"

    viewer_workspace = auth_client_factory(viewer).get(
        api_url("admin-workspace"),
        {"period_id": period.pk},
    )
    assert viewer_workspace.status_code == 200
    assert viewer_workspace.json()["summary"] == {
        "employee_count": 1,
        "gross_total": "80100.00",
        "deduction_total": "0.00",
        "payable_total": "80100.00",
    }

    submitted = operator_client.post(
        api_url("admin-run-submit-review", pk=run_id),
        {},
        format="json",
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "review"

    approved = auth_client_factory(run_approver).post(
        api_url("admin-run-approve", pk=run_id),
        {},
        format="json",
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["approved_by"]["id"] == run_approver.pk
    assert "self_approval_overridden" not in approved.json()

    published = auth_client_factory(publisher).post(
        api_url("admin-run-publish", pk=run_id),
        {},
        format="json",
    )
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    assert published.json()["published_by"]["id"] == publisher.pk

    closed = auth_client_factory(publisher).post(
        api_url("admin-period-close", pk=period.pk),
        {},
        format="json",
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"
    blocked_closed_draft = maker_client.post(
        api_url("admin-input-line-list"),
        {
            "period_id": period.pk,
            "employee_id": employee.pk,
            "component_id": bonus.pk,
            "amount": "50.00",
            "reason": "После закрытия",
        },
        format="json",
    )
    assert blocked_closed_draft.status_code == 409
    assert blocked_closed_draft.json()["code"] == "PERIOD_INPUTS_LOCKED"
    assert PayrollRun.objects.get(pk=run_id).status == "published"
    assert (
        PayrollWorkRecord.objects.filter(period=period, status="approved").count() == 1
    )
    assert (
        PayrollInputLine.objects.filter(period=period, status="approved").count() == 1
    )


def test_override_holder_can_self_approve_every_serialized_payroll_object(
    user_factory,
    auth_client_factory,
):
    operator = user_factory(email="self.approver@example.test")
    employee = user_factory(email="self.approval.employee@example.test")
    grant(
        operator,
        "manage_payroll_inputs",
        "approve_payroll_inputs",
        "calculate_payroll",
        "approve_payroll",
        "override_payroll_approval",
    )
    client = auth_client_factory(operator)
    period = make_period(creator=operator, code="2026-07")

    workspace = client.get(
        api_url("admin-workspace"),
        {"period_id": period.pk},
    )
    assert workspace.status_code == 200
    assert workspace.json()["permissions"]["override_approval"] is True

    rate = client.post(
        api_url("admin-pay-rate-list"),
        {
            "employee_id": employee.pk,
            "rate_code": "BASE",
            "amount": "90000.0000",
            "point_rate": "0.0000",
            "currency": "RUB",
            "effective_from": "2026-06-01",
            "reason": "",
        },
        format="json",
    )
    work_record = client.post(
        api_url("admin-work-record-list"),
        {
            "period_id": period.pk,
            "employee_id": employee.pk,
            "target_points": "100.0000",
            "actual_points": "100.0000",
            "reason": "",
        },
        format="json",
    )
    bonus = PayrollComponent.objects.get(code="BONUS")
    input_line = client.post(
        api_url("admin-input-line-list"),
        {
            "period_id": period.pk,
            "employee_id": employee.pk,
            "component_id": bonus.pk,
            "amount": "1000.00",
            "reason": "Премия",
        },
        format="json",
    )
    assert {rate.status_code, work_record.status_code, input_line.status_code} == {201}

    approved_objects = []
    for route_name, response in (
        ("admin-pay-rate-approve", rate),
        ("admin-work-record-approve", work_record),
        ("admin-input-line-approve", input_line),
    ):
        approval = client.post(
            api_url(route_name, pk=response.json()["id"]),
            {"expected_lock_version": response.json()["lock_version"]},
            format="json",
        )
        assert approval.status_code == 200
        assert approval.json()["approved_by_id"] == operator.pk
        assert "self_approval_overridden" not in approval.json()
        approved_objects.append(approval.json())

    calculation = client.post(
        api_url("admin-period-calculate", pk=period.pk),
        {
            "expected_lock_version": period.lock_version,
            "idempotency_key": str(uuid.uuid4()),
            "recalculation_reason": "",
        },
        format="json",
    )
    assert calculation.status_code == 201
    run_id = calculation.json()["id"]
    submitted = client.post(api_url("admin-run-submit-review", pk=run_id), {})
    assert submitted.status_code == 200
    run_approval = client.post(api_url("admin-run-approve", pk=run_id), {})
    assert run_approval.status_code == 200
    assert run_approval.json()["approved_by_id"] == operator.pk
    assert "self_approval_overridden" not in run_approval.json()

    records = (
        (EmployeePayRate, approved_objects[0]["id"]),
        (PayrollWorkRecord, approved_objects[1]["id"]),
        (PayrollInputLine, approved_objects[2]["id"]),
        (PayrollRun, run_id),
    )
    for model, object_id in records:
        instance = model.objects.get(pk=object_id)
        assert instance.self_approval_overridden is True
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                model.objects.filter(pk=object_id).update(
                    self_approval_overridden=False
                )

    events = PayrollAuditEvent.objects.filter(
        actor=operator,
        action__in={
            "payroll.rate_approved",
            "payroll.work_record_approved",
            "payroll.input_line_approved",
            "payroll.approved",
        },
    )
    assert events.count() == 4
    for event in events:
        assert event.metadata["self_approval_overridden"] is True
        assert event.metadata["approval_mode"] == "self_override"
        assert (
            event.metadata["override_permission"] == "finance.override_payroll_approval"
        )

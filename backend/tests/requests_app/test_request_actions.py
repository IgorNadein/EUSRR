from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from employees.constants import ACTION_DISMISSED, ACTION_HIRED
from employees.models import (
    Department,
    DepartmentRole,
    EmployeeAction,
    EmployeeDepartment,
    RoleAssignment,
)
from employees.services.request_actions import create_request_action
from requests_app.enums import RequestStatus
from requests_app.models import Request
from requests_app.tasks import (
    create_scheduled_action,
    process_due_personnel_actions,
    schedule_auto_return,
)


pytestmark = pytest.mark.django_db


def _approved_request(
    *,
    employee,
    approver,
    type_: str = "vacation",
    date_from: date | None = None,
    date_to: date | None = None,
) -> Request:
    return Request.objects.create(
        employee=employee,
        approver=approver,
        type=type_,
        status=RequestStatus.APPROVED,
        date_from=date_from,
        date_to=date_to,
    )


def test_scheduled_task_is_idempotent(user_factory):
    employee = user_factory()
    approver = user_factory()
    start_date = date(2026, 4, 20)
    request = _approved_request(
        employee=employee,
        approver=approver,
        date_from=start_date,
        date_to=start_date + timedelta(days=5),
    )

    create_scheduled_action.apply(args=[request.id])
    create_scheduled_action.apply(args=[request.id])

    actions = EmployeeAction.objects.filter(
        source_request=request,
        action="on_leave",
    )
    assert actions.count() == 1

    action = actions.get()
    assert action.extra["request_id"] == request.id
    assert action.extra["scheduled"] is True
    assert action.date.date() == start_date
    assert action.date_to == start_date + timedelta(days=5)


def test_scheduled_task_supports_maternity(user_factory):
    employee = user_factory()
    approver = user_factory()
    start_date = date(2026, 4, 20)
    end_date = date(2026, 9, 6)
    request = _approved_request(
        employee=employee,
        approver=approver,
        type_="maternity",
        date_from=start_date,
        date_to=end_date,
    )

    create_scheduled_action.apply(args=[request.id])

    action = EmployeeAction.objects.get(
        source_request=request,
        action="on_maternity",
    )
    assert action.date.date() == start_date
    assert action.date_to == end_date
    assert action.extra["scheduled"] is True


def test_auto_return_task_is_legacy_noop(user_factory):
    employee = user_factory()
    approver = user_factory()
    end_date = date(2026, 4, 25)
    request = _approved_request(
        employee=employee,
        approver=approver,
        date_from=date(2026, 4, 20),
        date_to=end_date,
    )

    first = schedule_auto_return.apply(args=[request.id])
    second = schedule_auto_return.apply(args=[request.id])

    assert first.result == "Auto-return disabled"
    assert second.result == "Auto-return disabled"
    assert not EmployeeAction.objects.filter(
        source_request=request,
        action="returned_from_leave",
    ).exists()


def test_immediate_approval_is_idempotent(user_factory):
    employee = user_factory()
    approver = user_factory()
    request = Request.objects.create(
        employee=employee,
        type="transfer",
        status=RequestStatus.PENDING,
        date_from=date(2026, 5, 1),
    )

    request.status = RequestStatus.APPROVED
    request.approver = approver
    request.save()
    request.comment = "Повторное сохранение"
    request.save()

    actions = EmployeeAction.objects.filter(
        source_request=request,
        action="transferred",
    )
    assert actions.count() == 1
    assert actions.get().extra["request_id"] == request.id


@patch("api.v1.employees.views.actions.EmployeeActionViewSet._ensure_ldap_dn_location")
@patch("employees.signals.ldap.employee._is_ldap_enabled", return_value=True)
@patch("employees.signals.ldap.employee.UserService.update_user")
def test_same_day_dismissal_request_deactivates_profile_and_ldap(
    mock_update,
    mock_is_enabled,
    mock_ensure_dn,
    user_factory,
):
    from employees.models import LdapSyncState

    employee = user_factory(is_ldap_managed=True)
    approver = user_factory()
    today = timezone.localdate()
    department = Department.objects.create(name="Today Dismissal Dept")
    link = EmployeeDepartment.objects.create(
        employee=employee,
        department=department,
        is_active=True,
        date_from=today - timedelta(days=30),
    )
    LdapSyncState.objects.create(
        model="employee",
        object_pk=str(employee.pk),
        ldap_dn=f"CN={employee.email},OU=Users,DC=example,DC=com",
        last_sync_dir="ldap",
    )
    request = Request.objects.create(
        employee=employee,
        type="dismissal",
        status=RequestStatus.PENDING,
        date_from=today,
    )

    request.status = RequestStatus.APPROVED
    request.approver = approver
    request.save()

    action = EmployeeAction.objects.get(
        source_request=request,
        action=ACTION_DISMISSED,
    )
    employee.refresh_from_db()
    link.refresh_from_db()
    assert action.date.date() == today
    assert employee.is_active is False
    assert link.is_active is False
    assert link.date_to == today
    mock_update.assert_called_once()
    assert mock_update.call_args.kwargs["emp"].id == employee.id
    assert mock_update.call_args.kwargs["changes"] == {"is_active": False}
    mock_ensure_dn.assert_called_once()
    assert mock_ensure_dn.call_args.args[0].id == employee.id


@patch("api.v1.employees.views.actions.EmployeeActionViewSet._ensure_ldap_dn_location")
@patch("employees.signals.ldap.employee._is_ldap_enabled", return_value=True)
@patch("employees.signals.ldap.employee.UserService.update_user")
def test_past_dismissal_request_deactivates_immediately_with_request_date(
    mock_update,
    mock_is_enabled,
    mock_ensure_dn,
    user_factory,
):
    from employees.models import LdapSyncState

    employee = user_factory(is_ldap_managed=True)
    approver = user_factory()
    dismissal_date = timezone.localdate() - timedelta(days=3)
    EmployeeAction.objects.filter(
        employee=employee,
        action=ACTION_HIRED,
    ).update(date=timezone.now() - timedelta(days=30))
    department = Department.objects.create(name="Past Dismissal Dept")
    link = EmployeeDepartment.objects.create(
        employee=employee,
        department=department,
        is_active=True,
        date_from=dismissal_date - timedelta(days=30),
    )
    LdapSyncState.objects.create(
        model="employee",
        object_pk=str(employee.pk),
        ldap_dn=f"CN={employee.email},OU=Users,DC=example,DC=com",
        last_sync_dir="ldap",
    )
    request = Request.objects.create(
        employee=employee,
        type="dismissal",
        status=RequestStatus.PENDING,
        date_from=dismissal_date,
    )

    request.status = RequestStatus.APPROVED
    request.approver = approver
    request.save()

    action = EmployeeAction.objects.get(
        source_request=request,
        action=ACTION_DISMISSED,
    )
    employee.refresh_from_db()
    link.refresh_from_db()
    assert action.date.date() == dismissal_date
    assert employee.is_active is False
    assert link.is_active is False
    assert link.date_to == dismissal_date
    mock_update.assert_called_once()
    assert mock_update.call_args.kwargs["emp"].id == employee.id
    assert mock_update.call_args.kwargs["changes"] == {"is_active": False}
    mock_ensure_dn.assert_called_once()
    assert mock_ensure_dn.call_args.args[0].id == employee.id


def test_future_dismissal_request_deactivates_on_effective_date(
    user_factory,
    monkeypatch,
):
    employee = user_factory()
    approver = user_factory()
    today = timezone.localdate()
    dismissal_date = today + timedelta(days=1)
    department = Department.objects.create(name="Dismissal Dept", head=employee)
    link = EmployeeDepartment.objects.create(
        employee=employee,
        department=department,
        is_active=True,
        date_from=today - timedelta(days=30),
    )
    role = DepartmentRole.objects.create(
        department=department,
        name="Dismissal Role",
    )
    assignment = RoleAssignment.objects.create(
        employee=employee,
        role=role,
        is_active=True,
    )
    request = Request.objects.create(
        employee=employee,
        type="dismissal",
        status=RequestStatus.PENDING,
        date_from=dismissal_date,
    )

    request.status = RequestStatus.APPROVED
    request.approver = approver
    request.save()

    action = EmployeeAction.objects.get(
        source_request=request,
        action=ACTION_DISMISSED,
    )
    assert action.date.date() == dismissal_date
    employee.refresh_from_db()
    link.refresh_from_db()
    assignment.refresh_from_db()
    department.refresh_from_db()
    assert employee.is_active is True
    assert link.is_active is True
    assert assignment.is_active is True
    assert department.head_id == employee.id

    monkeypatch.setattr(
        "requests_app.tasks.timezone.localdate",
        lambda: dismissal_date,
    )
    monkeypatch.setattr(
        "api.v1.employees.views.actions.timezone.localdate",
        lambda: dismissal_date,
    )

    result = process_due_personnel_actions.apply()

    assert result.result == 1
    employee.refresh_from_db()
    link.refresh_from_db()
    assignment.refresh_from_db()
    department.refresh_from_db()
    assert employee.is_active is False
    assert link.is_active is False
    assert link.date_to == dismissal_date
    assert assignment.is_active is False
    assert department.head_id is None
    assert process_due_personnel_actions.apply().result == 0


def test_helper_returns_existing_legacy_action(user_factory):
    employee = user_factory()
    approver = user_factory()
    request = _approved_request(
        employee=employee,
        approver=approver,
        type_="transfer",
        date_from=date(2026, 5, 1),
    )
    existing = EmployeeAction.objects.create(
        employee=employee,
        action="transferred",
        date=timezone.datetime(
            2026,
            5,
            1,
            12,
            tzinfo=timezone.get_current_timezone(),
        ),
        comment="legacy",
        extra={"request_id": request.id, "legacy": True},
    )

    action, created = create_request_action(
        request=request,
        action_type="transferred",
        action_date=request.date_from,
        comment="new",
        extra={"immediate": True},
    )

    assert created is False
    assert action.id == existing.id
    action.refresh_from_db()
    assert action.source_request_id == request.id
    assert action.extra["request_id"] == request.id


@pytest.mark.django_db(transaction=True)
def test_migration_0049_backfills_source_request_and_removes_duplicates():
    def migrate_to(target):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(target)
        return executor.loader.project_state(target).apps

    def migrate_to_latest():
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    try:
        old_apps = migrate_to(
            [
                ("employees", "0048_alter_employeeaction_action_and_more"),
                ("requests_app", "0011_remove_requestcomment_model"),
            ]
        )
        Employee = old_apps.get_model("employees", "Employee")
        OldRequest = old_apps.get_model("requests_app", "Request")
        OldEmployeeAction = old_apps.get_model("employees", "EmployeeAction")

        employee = Employee.objects.create(
            email="migration-employee@example.com",
            phone_number="+79990000001",
            first_name="Migration",
            last_name="Employee",
            is_active=True,
            email_verified=True,
        )
        approver = Employee.objects.create(
            email="migration-approver@example.com",
            phone_number="+79990000002",
            first_name="Migration",
            last_name="Approver",
            is_active=True,
            email_verified=True,
        )
        request = OldRequest.objects.create(
            employee=employee,
            approver=approver,
            type="vacation",
            status="approved",
            date_from=date(2026, 4, 20),
            date_to=date(2026, 4, 25),
        )
        first = OldEmployeeAction.objects.create(
            employee=employee,
            action="on_leave",
            date=timezone.datetime(
                2026,
                4,
                20,
                12,
                tzinfo=timezone.get_current_timezone(),
            ),
            comment="first",
            extra={"request_id": request.id},
        )
        OldEmployeeAction.objects.create(
            employee=employee,
            action="on_leave",
            date=timezone.datetime(
                2026,
                4,
                20,
                12,
                tzinfo=timezone.get_current_timezone(),
            ),
            comment="duplicate",
            extra={"request_id": request.id},
        )

        apps_0049 = migrate_to(
            [("employees", "0049_employeeaction_source_request")]
        )
        EmployeeAction0049 = apps_0049.get_model("employees", "EmployeeAction")

        actions = EmployeeAction0049.objects.filter(
            source_request_id=request.id,
            action="on_leave",
        )
        assert actions.count() == 1
        assert actions.get().id == first.id

        migrate_to_latest()
        action = EmployeeAction.objects.get(
            source_request_id=request.id,
            action="on_leave",
        )
        assert action.date_to == date(2026, 4, 25)
    finally:
        migrate_to_latest()

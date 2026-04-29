from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from employees.models import EmployeeAction
from employees.services.request_actions import create_request_action
from requests_app.enums import RequestStatus
from requests_app.models import Request
from requests_app.tasks import create_scheduled_action, schedule_auto_return


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

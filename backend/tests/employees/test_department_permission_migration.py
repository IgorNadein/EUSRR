from __future__ import annotations

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


pytestmark = pytest.mark.django_db(transaction=True)


def _migrate_to(target):
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(target)
    return executor.loader.project_state(target).apps


def _migrate_to_latest():
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(executor.loader.graph.leaf_nodes())


def test_migration_0047_removes_obsolete_department_permissions():
    try:
        old_apps = _migrate_to(
            [("employees", "0046_alter_ldapsyncqueue_operation")]
        )
        DepartmentPermission = old_apps.get_model(
            "employees", "DepartmentPermission"
        )

        DepartmentPermission.objects.create(
            code="manage_department_events",
            name="Управлять календарём отдела",
        )
        DepartmentPermission.objects.create(
            code="publish_department_post",
            name="Публиковать новости на странице отдела",
        )
        DepartmentPermission.objects.create(
            code="manage_department",
            name="Управлять отделом",
        )

        _migrate_to([("employees", "0047_alter_departmentpermission_code")])

        from employees.models import (
            DepartmentPermission as CurrentDepartmentPermission,
        )

        codes = set(
            CurrentDepartmentPermission.objects.values_list("code", flat=True)
        )
        assert "manage_department_events" not in codes
        assert "publish_department_post" not in codes
        assert "manage_department" in codes
    finally:
        _migrate_to_latest()


def test_migration_0053_removes_obsolete_request_department_permissions():
    try:
        old_apps = _migrate_to([("employees", "0052_employee_attendance_aliases")])
        Department = old_apps.get_model("employees", "Department")
        DepartmentRole = old_apps.get_model("employees", "DepartmentRole")
        DepartmentPermission = old_apps.get_model(
            "employees", "DepartmentPermission"
        )

        dept = Department.objects.create(name="Dept")
        role = DepartmentRole.objects.create(department=dept, name="Legacy")
        obsolete_perms = [
            DepartmentPermission.objects.create(
                code="view_request",
                name="Просмотр заявлений отдела",
            ),
            DepartmentPermission.objects.create(
                code="view_requestcomment",
                name="Просмотр комментариев по заявлениям",
            ),
            DepartmentPermission.objects.create(
                code="add_requestcomment",
                name="Добавление коментариев по заявлениям",
            ),
        ]
        procurement_perm = DepartmentPermission.objects.create(
            code="can_process_requests",
            name="Рассмотрение заявлений отдела",
        )
        role.scoped_permissions.add(*obsolete_perms, procurement_perm)

        _migrate_to([("employees", "0053_cleanup_department_role_permissions")])

        from employees.models import (
            DepartmentPermission as CurrentDepartmentPermission,
            DepartmentRole as CurrentDepartmentRole,
        )

        codes = set(
            CurrentDepartmentPermission.objects.values_list("code", flat=True)
        )
        assert "view_request" not in codes
        assert "view_requestcomment" not in codes
        assert "add_requestcomment" not in codes
        assert "can_process_requests" in codes
        assert (
            CurrentDepartmentPermission.objects.get(
                code="can_process_requests"
            ).name
            == "Согласование закупок отдела"
        )

        role_codes = set(
            CurrentDepartmentRole.objects.get(pk=role.pk)
            .scoped_permissions.values_list("code", flat=True)
        )
        assert role_codes == {"can_process_requests"}
    finally:
        _migrate_to_latest()

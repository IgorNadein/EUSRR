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


def test_migration_0047_removes_obsolete_department_permissions():
    old_apps = _migrate_to([("employees", "0046_alter_ldapsyncqueue_operation")])
    DepartmentPermission = old_apps.get_model("employees", "DepartmentPermission")

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

    from employees.models import DepartmentPermission as CurrentDepartmentPermission

    codes = set(
        CurrentDepartmentPermission.objects.values_list("code", flat=True)
    )
    assert "manage_department_events" not in codes
    assert "publish_department_post" not in codes
    assert "manage_department" in codes

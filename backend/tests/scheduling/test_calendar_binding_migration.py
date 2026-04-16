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


def test_migration_0002_backfills_department_binding_by_slug():
    try:
        old_apps = _migrate_to(
            [
                ("employees", "0047_alter_departmentpermission_code"),
                ("schedule", "0015_rename_indexes"),
                ("scheduling", "0001_initial"),
            ]
        )
        Department = old_apps.get_model("employees", "Department")
        Calendar = old_apps.get_model("schedule", "Calendar")

        department = Department.objects.create(name="Finance")
        calendar = Calendar.objects.create(
            name="Finance",
            slug=f"department-{department.id}",
        )

        _migrate_to([("scheduling", "0002_calendarbinding")])

        from scheduling.models import CalendarBinding

        binding = CalendarBinding.objects.get(calendar_id=calendar.id)
        assert binding.type == CalendarBinding.BindingType.DEPARTMENT
        assert binding.context_object_id == department.id
        assert binding.context_content_type.app_label == "employees"
        assert binding.context_content_type.model == "department"
    finally:
        _migrate_to_latest()

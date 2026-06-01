from datetime import date

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


def test_expected_delivery_date_migrates_to_dates_list():
    try:
        old_apps = _migrate_to(
            [("procurement", "0011_item_quantities_defective_optional_price")]
        )
        Department = old_apps.get_model("employees", "Department")
        Employee = old_apps.get_model("employees", "Employee")
        ProcurementRequest = old_apps.get_model("procurement", "ProcurementRequest")
        ProcurementItem = old_apps.get_model("procurement", "ProcurementItem")

        department = Department.objects.create(name="Migration procurement")
        employee = Employee.objects.create(
            email="procurement-migration@example.com",
            phone_number="+79990001001",
            first_name="Migration",
            last_name="Procurement",
            is_active=True,
            email_verified=True,
        )
        procurement_request = ProcurementRequest.objects.create(
            title="Migration request",
            description="Migration request description",
            department=department,
            requestor=employee,
        )
        item_with_date = ProcurementItem.objects.create(
            request=procurement_request,
            name="With date",
            quantity=1,
            unit="шт",
            expected_delivery_date=date(2026, 5, 25),
        )
        item_without_date = ProcurementItem.objects.create(
            request=procurement_request,
            name="Without date",
            quantity=1,
            unit="шт",
        )

        new_apps = _migrate_to([("procurement", "0012_expected_delivery_dates")])
        MigratedItem = new_apps.get_model("procurement", "ProcurementItem")

        migrated_with_date = MigratedItem.objects.get(id=item_with_date.id)
        migrated_without_date = MigratedItem.objects.get(id=item_without_date.id)

        assert migrated_with_date.expected_delivery_dates == ["2026-05-25"]
        assert migrated_without_date.expected_delivery_dates == []
        assert not any(
            field.name == "expected_delivery_date"
            for field in MigratedItem._meta.get_fields()
        )
    finally:
        _migrate_to_latest()

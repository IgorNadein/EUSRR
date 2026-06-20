from django.db import migrations, models


GUEST_ID_MIN = 900_000_000_000_000
EMPLOYEE_ID_MAX = GUEST_ID_MIN - 1


def cap_employee_sequence(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_get_serial_sequence('employees_employee', 'id')"
        )
        row = cursor.fetchone()
        sequence_name = row[0] if row else None
        if sequence_name:
            cursor.execute(f"ALTER SEQUENCE {sequence_name} MAXVALUE {EMPLOYEE_ID_MAX}")


def uncap_employee_sequence(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_get_serial_sequence('employees_employee', 'id')"
        )
        row = cursor.fetchone()
        sequence_name = row[0] if row else None
        if sequence_name:
            cursor.execute(f"ALTER SEQUENCE {sequence_name} NO MAXVALUE")


class Migration(migrations.Migration):

    dependencies = [
        ("employees", "0053_cleanup_department_role_permissions"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="employee",
            constraint=models.CheckConstraint(
                condition=models.Q(("id__lt", GUEST_ID_MIN)),
                name="employee_id_below_guest_range",
            ),
        ),
        migrations.RunPython(cap_employee_sequence, uncap_employee_sequence),
    ]

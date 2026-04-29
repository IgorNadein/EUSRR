from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("employees", "0050_employeeaction_date_to"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                "DROP TABLE IF EXISTS employees_employeebasestatusevent",
                "DROP TABLE IF EXISTS employees_employeestatusinterval",
            ],
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]

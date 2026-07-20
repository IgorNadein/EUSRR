from decimal import Decimal

from django.db import migrations, models
import django.core.validators


def use_automatic_price_for_legacy_defaults(apps, schema_editor):
    employee_pay_rate = apps.get_model("finance", "EmployeePayRate")
    employee_pay_rate.objects.filter(point_rate=Decimal("0")).update(point_rate=None)


def restore_legacy_zero_price(apps, schema_editor):
    employee_pay_rate = apps.get_model("finance", "EmployeePayRate")
    employee_pay_rate.objects.filter(point_rate__isnull=True).update(
        point_rate=Decimal("0")
    )


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0013_alter_payrollauditevent_period_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="employeepayrate",
            name="point_rate",
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                max_digits=19,
                null=True,
                validators=[django.core.validators.MinValueValidator(Decimal("0"))],
                verbose_name="Цена балла сверх нормы",
            ),
        ),
        migrations.RunPython(
            use_automatic_price_for_legacy_defaults,
            restore_legacy_zero_price,
        ),
    ]

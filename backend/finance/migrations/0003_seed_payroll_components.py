from django.db import migrations


COMPONENTS = (
    ("VACATION_PAY", "Отпускные", "earning", False, 20),
    ("BONUS", "Премия", "earning", False, 30),
    (
        "CORRECTION_CREDIT",
        "Положительная корректировка",
        "adjustment_credit",
        True,
        40,
    ),
    (
        "CORRECTION_DEBIT",
        "Отрицательная корректировка",
        "adjustment_debit",
        True,
        41,
    ),
    ("ONE_TIME_PAYMENT", "Разовое начисление", "earning", True, 50),
    ("DEDUCTION", "Удержание", "deduction", True, 60),
    ("ADVANCE", "Аванс", "payment", False, 70),
)


def seed_components(apps, schema_editor):
    component_model = apps.get_model("finance", "PayrollComponent")
    for code, name, kind, requires_reason, display_order in COMPONENTS:
        component_model.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "kind": kind,
                "requires_reason": requires_reason,
                "is_active": True,
                "display_order": display_order,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0002_employeepayrate_pay_rate_approval_complete_and_more")
    ]

    operations = [
        migrations.RunPython(seed_components, migrations.RunPython.noop),
    ]

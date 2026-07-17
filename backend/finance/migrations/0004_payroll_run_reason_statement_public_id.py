import uuid

from django.db import migrations, models


def populate_statement_public_ids(apps, schema_editor):
    statement_model = apps.get_model("finance", "PayrollStatement")
    for statement in statement_model.objects.filter(public_id__isnull=True).iterator():
        statement.public_id = uuid.uuid4()
        statement.save(update_fields=["public_id"])


class Migration(migrations.Migration):
    dependencies = [("finance", "0003_seed_payroll_components")]

    operations = [
        migrations.AddField(
            model_name="payrollrun",
            name="recalculation_reason",
            field=models.TextField(blank=True, verbose_name="Основание перерасчёта"),
        ),
        migrations.AddField(
            model_name="payrollstatement",
            name="public_id",
            field=models.UUIDField(
                editable=False,
                null=True,
                verbose_name="Публичный идентификатор",
            ),
        ),
        migrations.RunPython(
            populate_statement_public_ids,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="payrollstatement",
            name="public_id",
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                unique=True,
                verbose_name="Публичный идентификатор",
            ),
        ),
    ]

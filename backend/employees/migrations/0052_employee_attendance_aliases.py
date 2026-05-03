from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("employees", "0051_drop_legacy_state_tables"),
    ]

    operations = [
        migrations.AddField(
            model_name="employee",
            name="attendance_aliases",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Дополнительные идентификаторы сотрудника в LogStorm",
                verbose_name="Алиасы посещаемости",
            ),
        ),
    ]

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0016_document_is_regulation"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="document",
            name="acknowledgement_required",
            field=models.BooleanField(
                default=True,
                help_text="Если включено — сотрудники должны подтвердить ознакомление",
                verbose_name="Требуется ознакомление",
            ),
        ),
        migrations.AddField(
            model_name="document",
            name="acknowledgement_for_all",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Если включено — ознакомиться должны все сотрудники, "
                    "которым доступен документ"
                ),
                verbose_name="Ознакомление для всех с доступом",
            ),
        ),
        migrations.AddField(
            model_name="document",
            name="acknowledgement_departments",
            field=models.ManyToManyField(
                blank=True,
                help_text=(
                    "Сотрудники выбранных отделов должны ознакомиться с документом"
                ),
                related_name="documents_requiring_acknowledgement",
                to="employees.department",
                verbose_name="Отделы для ознакомления",
            ),
        ),
        migrations.AddField(
            model_name="document",
            name="acknowledgement_recipients",
            field=models.ManyToManyField(
                blank=True,
                help_text="Выбранные сотрудники должны ознакомиться с документом",
                related_name="documents_requiring_acknowledgement",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Сотрудники для ознакомления",
            ),
        ),
    ]

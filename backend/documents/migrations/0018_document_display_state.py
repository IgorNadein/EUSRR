import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0017_document_acknowledgement_audience"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DocumentDisplayState",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "is_maximally_hidden",
                    models.BooleanField(
                        default=True,
                        verbose_name="Максимально скрыт",
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True,
                        verbose_name="Обновлено",
                    ),
                ),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="display_states",
                        to="documents.document",
                        verbose_name="Документ",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="document_display_states",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Сотрудник",
                    ),
                ),
            ],
            options={
                "verbose_name": "Настройка отображения документа",
                "verbose_name_plural": "Настройки отображения документов",
            },
        ),
        migrations.AddConstraint(
            model_name="documentdisplaystate",
            constraint=models.UniqueConstraint(
                fields=("document", "user"),
                name="unique_document_display_state_user",
            ),
        ),
    ]

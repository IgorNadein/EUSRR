from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("attendance", "0005_standardworkschedule"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AttendanceAutoSyncSettings",
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
                    "singleton",
                    models.BooleanField(default=True, editable=False, unique=True),
                ),
                ("enabled", models.BooleanField(default=False, verbose_name="Включено")),
                (
                    "frequency_minutes",
                    models.PositiveIntegerField(
                        choices=[
                            (5, "5 минут"),
                            (15, "15 минут"),
                            (30, "30 минут"),
                            (60, "1 час"),
                            (1440, "1 сутки"),
                        ],
                        default=1440,
                        verbose_name="Периодичность",
                    ),
                ),
                (
                    "lookback_days",
                    models.PositiveIntegerField(
                        choices=[(1, "1 день"), (3, "3 дня"), (7, "7 дней")],
                        default=3,
                        verbose_name="Глубина обновления",
                    ),
                ),
                (
                    "next_run_at",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                        verbose_name="Следующий запуск",
                    ),
                ),
                (
                    "last_started_at",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                        verbose_name="Последний старт",
                    ),
                ),
                (
                    "last_finished_at",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                        verbose_name="Последнее завершение",
                    ),
                ),
                (
                    "last_status",
                    models.CharField(
                        choices=[
                            ("idle", "Ожидание"),
                            ("running", "Выполняется"),
                            ("success", "Успешно"),
                            ("partial", "Частично"),
                            ("failed", "Ошибка"),
                        ],
                        default="idle",
                        max_length=16,
                        verbose_name="Последний статус",
                    ),
                ),
                (
                    "last_error",
                    models.TextField(blank=True, verbose_name="Последняя ошибка"),
                ),
                (
                    "last_success_count",
                    models.PositiveIntegerField(default=0, verbose_name="Успешно"),
                ),
                (
                    "last_error_count",
                    models.PositiveIntegerField(default=0, verbose_name="Ошибок"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="Обновлено"),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_attendance_auto_sync_settings",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Изменил",
                    ),
                ),
            ],
            options={
                "verbose_name": "Автообновление посещаемости",
                "verbose_name_plural": "Автообновление посещаемости",
            },
        ),
    ]

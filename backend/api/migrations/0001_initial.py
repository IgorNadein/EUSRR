# Generated manually for auth session registry.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UserAuthSession",
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
                    "session_id",
                    models.UUIDField(
                        db_index=True,
                        default=uuid.uuid4,
                        editable=False,
                        unique=True,
                        verbose_name="Session ID",
                    ),
                ),
                (
                    "refresh_token_hash",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=128,
                        verbose_name="Хеш refresh token",
                    ),
                ),
                (
                    "ip_address",
                    models.GenericIPAddressField(
                        blank=True,
                        null=True,
                        verbose_name="IP адрес",
                    ),
                ),
                (
                    "user_agent",
                    models.TextField(blank=True, default="", verbose_name="User-Agent"),
                ),
                (
                    "device_name",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=255,
                        verbose_name="Устройство",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Создана"),
                ),
                (
                    "last_seen_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        verbose_name="Последняя активность",
                    ),
                ),
                (
                    "revoked_at",
                    models.DateTimeField(
                        blank=True,
                        db_index=True,
                        null=True,
                        verbose_name="Отозвана",
                    ),
                ),
                (
                    "revoked_reason",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=64,
                        verbose_name="Причина отзыва",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="auth_sessions",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Пользователь",
                    ),
                ),
            ],
            options={
                "verbose_name": "Сессия аутентификации",
                "verbose_name_plural": "Сессии аутентификации",
                "ordering": ["-last_seen_at", "-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="userauthsession",
            index=models.Index(
                fields=["user", "revoked_at"],
                name="api_useraut_user_id_1e9721_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="userauthsession",
            index=models.Index(
                fields=["user", "-last_seen_at"],
                name="api_useraut_user_id_82cdaa_idx",
            ),
        ),
    ]

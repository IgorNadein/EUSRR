# Generated manually for QR login tokens.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0002_rename_api_useraut_user_id_1e9721_idx_api_useraut_user_id_70da51_idx_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="QrLoginToken",
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
                    "token_hash",
                    models.CharField(
                        db_index=True,
                        max_length=128,
                        unique=True,
                        verbose_name="Хеш QR-токена",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Создан"),
                ),
                (
                    "expires_at",
                    models.DateTimeField(db_index=True, verbose_name="Истекает"),
                ),
                (
                    "used_at",
                    models.DateTimeField(
                        blank=True,
                        db_index=True,
                        null=True,
                        verbose_name="Использован",
                    ),
                ),
                (
                    "created_ip_address",
                    models.GenericIPAddressField(
                        blank=True,
                        null=True,
                        verbose_name="IP создания",
                    ),
                ),
                (
                    "created_user_agent",
                    models.TextField(
                        blank=True,
                        default="",
                        verbose_name="User-Agent создания",
                    ),
                ),
                (
                    "used_ip_address",
                    models.GenericIPAddressField(
                        blank=True,
                        null=True,
                        verbose_name="IP использования",
                    ),
                ),
                (
                    "used_user_agent",
                    models.TextField(
                        blank=True,
                        default="",
                        verbose_name="User-Agent использования",
                    ),
                ),
                (
                    "created_by_session",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_qr_login_tokens",
                        to="api.userauthsession",
                        verbose_name="Сессия-источник",
                    ),
                ),
                (
                    "used_session",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="used_qr_login_tokens",
                        to="api.userauthsession",
                        verbose_name="Созданная сессия",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="qr_login_tokens",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Пользователь",
                    ),
                ),
            ],
            options={
                "verbose_name": "QR-токен входа",
                "verbose_name_plural": "QR-токены входа",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="qrlogintoken",
            index=models.Index(
                fields=["user", "used_at", "expires_at"],
                name="api_qrlogin_user_id_8e45eb_idx",
            ),
        ),
    ]

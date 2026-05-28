# Generated manually for QR login requests.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0003_qrlogintoken"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="QrLoginRequest",
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
                    "scan_token_hash",
                    models.CharField(
                        db_index=True,
                        max_length=128,
                        unique=True,
                        verbose_name="Хеш токена сканирования",
                    ),
                ),
                (
                    "client_secret_hash",
                    models.CharField(
                        db_index=True,
                        max_length=128,
                        unique=True,
                        verbose_name="Хеш секрета клиента",
                    ),
                ),
                (
                    "requester_ip_address",
                    models.GenericIPAddressField(
                        blank=True,
                        null=True,
                        verbose_name="IP запрашивающего устройства",
                    ),
                ),
                (
                    "requester_user_agent",
                    models.TextField(
                        blank=True,
                        default="",
                        verbose_name="User-Agent запрашивающего устройства",
                    ),
                ),
                (
                    "requester_device_name",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=255,
                        verbose_name="Запрашивающее устройство",
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
                    "approved_at",
                    models.DateTimeField(
                        blank=True,
                        db_index=True,
                        null=True,
                        verbose_name="Подтвержден",
                    ),
                ),
                (
                    "denied_at",
                    models.DateTimeField(
                        blank=True,
                        db_index=True,
                        null=True,
                        verbose_name="Отклонен",
                    ),
                ),
                (
                    "claimed_at",
                    models.DateTimeField(
                        blank=True,
                        db_index=True,
                        null=True,
                        verbose_name="Получен клиентом",
                    ),
                ),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="approved_qr_login_requests",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Подтвердил пользователь",
                    ),
                ),
                (
                    "approved_by_session",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="approved_qr_login_requests",
                        to="api.userauthsession",
                        verbose_name="Подтвердила сессия",
                    ),
                ),
                (
                    "denied_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="denied_qr_login_requests",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Отклонил пользователь",
                    ),
                ),
                (
                    "used_session",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="qr_login_requests",
                        to="api.userauthsession",
                        verbose_name="Созданная сессия",
                    ),
                ),
            ],
            options={
                "verbose_name": "QR-запрос входа",
                "verbose_name_plural": "QR-запросы входа",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="qrloginrequest",
            index=models.Index(
                fields=["expires_at", "approved_at", "denied_at"],
                name="api_qrlogin_expires_48a8f2_idx",
            ),
        ),
    ]

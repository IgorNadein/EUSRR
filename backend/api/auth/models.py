from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class UserAuthSession(models.Model):
    session_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
        verbose_name="Session ID",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="auth_sessions",
        verbose_name="Пользователь",
    )
    refresh_token_hash = models.CharField(
        max_length=128,
        blank=True,
        default="",
        verbose_name="Хеш refresh token",
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP адрес",
    )
    user_agent = models.TextField(blank=True, default="", verbose_name="User-Agent")
    device_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Устройство",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создана")
    last_seen_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Последняя активность",
    )
    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Отозвана",
    )
    revoked_reason = models.CharField(
        max_length=64,
        blank=True,
        default="",
        verbose_name="Причина отзыва",
    )

    class Meta:
        ordering = ["-last_seen_at", "-created_at"]
        indexes = [
            models.Index(fields=["user", "revoked_at"]),
            models.Index(fields=["user", "-last_seen_at"]),
        ]
        verbose_name = "Сессия аутентификации"
        verbose_name_plural = "Сессии аутентификации"

    def __str__(self) -> str:
        return f"{self.user_id}:{self.session_id}"

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def revoke(self, *, reason: str = "manual", commit: bool = True) -> None:
        if self.revoked_at:
            return
        self.revoked_at = timezone.now()
        self.revoked_reason = reason
        if commit:
            self.save(update_fields=["revoked_at", "revoked_reason"])

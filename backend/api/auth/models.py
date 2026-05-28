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


class QrLoginToken(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="qr_login_tokens",
        verbose_name="Пользователь",
    )
    token_hash = models.CharField(
        max_length=128,
        unique=True,
        db_index=True,
        verbose_name="Хеш QR-токена",
    )
    created_by_session = models.ForeignKey(
        UserAuthSession,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_qr_login_tokens",
        verbose_name="Сессия-источник",
    )
    used_session = models.ForeignKey(
        UserAuthSession,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="used_qr_login_tokens",
        verbose_name="Созданная сессия",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")
    expires_at = models.DateTimeField(db_index=True, verbose_name="Истекает")
    used_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Использован",
    )
    created_ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP создания",
    )
    created_user_agent = models.TextField(
        blank=True,
        default="",
        verbose_name="User-Agent создания",
    )
    used_ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP использования",
    )
    used_user_agent = models.TextField(
        blank=True,
        default="",
        verbose_name="User-Agent использования",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "used_at", "expires_at"]),
        ]
        verbose_name = "QR-токен входа"
        verbose_name_plural = "QR-токены входа"

    def __str__(self) -> str:
        return f"{self.user_id}:{self.created_at:%Y-%m-%d %H:%M:%S}"

    @property
    def is_used(self) -> bool:
        return self.used_at is not None

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at


class QrLoginRequest(models.Model):
    scan_token_hash = models.CharField(
        max_length=128,
        unique=True,
        db_index=True,
        verbose_name="Хеш токена сканирования",
    )
    client_secret_hash = models.CharField(
        max_length=128,
        unique=True,
        db_index=True,
        verbose_name="Хеш секрета клиента",
    )
    requester_ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP запрашивающего устройства",
    )
    requester_user_agent = models.TextField(
        blank=True,
        default="",
        verbose_name="User-Agent запрашивающего устройства",
    )
    requester_device_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Запрашивающее устройство",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="approved_qr_login_requests",
        verbose_name="Подтвердил пользователь",
    )
    approved_by_session = models.ForeignKey(
        UserAuthSession,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_qr_login_requests",
        verbose_name="Подтвердила сессия",
    )
    used_session = models.ForeignKey(
        UserAuthSession,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="qr_login_requests",
        verbose_name="Созданная сессия",
    )
    denied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="denied_qr_login_requests",
        verbose_name="Отклонил пользователь",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")
    expires_at = models.DateTimeField(db_index=True, verbose_name="Истекает")
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Подтвержден",
    )
    denied_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Отклонен",
    )
    claimed_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Получен клиентом",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["expires_at", "approved_at", "denied_at"]),
        ]
        verbose_name = "QR-запрос входа"
        verbose_name_plural = "QR-запросы входа"

    def __str__(self) -> str:
        return f"{self.requester_device_name or 'unknown'}:{self.created_at:%Y-%m-%d %H:%M:%S}"

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @property
    def status(self) -> str:
        if self.claimed_at is not None:
            return "claimed"
        if self.denied_at is not None:
            return "denied"
        if self.is_expired:
            return "expired"
        if self.approved_at is not None:
            return "approved"
        return "pending"

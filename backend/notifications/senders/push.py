"""
Web Push отправитель для browser push notifications
"""

import json

from django.conf import settings
from push_notifications.models import WebPushDevice

from .base import BaseNotificationSender
from ..config import get


class PushNotificationSender(BaseNotificationSender):
    """
    Отправитель Web Push уведомлений через django-push-notifications.
    Доставляет уведомления в браузер даже когда вкладка закрыта.
    """

    CHAT_NOTIFICATION_VERBS = {
        "chat_new_message",
        "chat_mention",
        "chat_reply",
        "announcement_new_message",
    }
    DEFAULT_TITLE = "Новое уведомление"

    def can_send(self, notification, user_preferences) -> bool:
        """Проверяет, включены ли push уведомления"""
        if not user_preferences.push_enabled:
            self.log_skip(notification, "push_enabled=False")
            return False
        return True

    def _get_actor_name(self, notification) -> str:
        actor = notification.actor
        if not actor:
            return ""
        return str(actor).strip()

    def _get_data_title(self, notification) -> str:
        data = notification.data if isinstance(notification.data, dict) else {}
        title = data.get("title")
        if not isinstance(title, str):
            return ""
        return title.strip()

    def _get_site_url(self) -> str:
        site_url = getattr(settings, "SITE_URL", "").strip()
        if site_url:
            return site_url.rstrip("/")

        if settings.ALLOWED_HOSTS and settings.ALLOWED_HOSTS[0] != "*":
            protocol = (
                "https"
                if getattr(settings, "SECURE_SSL_REDIRECT", False)
                else "http"
            )
            return f"{protocol}://{settings.ALLOWED_HOSTS[0]}"

        return "http://localhost:9000"

    def _get_actor_avatar_url(self, notification) -> str:
        actor = notification.actor
        if not actor:
            return ""

        try:
            avatar = getattr(actor, "avatar", None)
            if not avatar:
                return ""
            avatar_url = avatar.url
        except Exception:
            return ""

        if not avatar_url:
            return ""
        if avatar_url.startswith(("http://", "https://")):
            return avatar_url
        if avatar_url.startswith("/"):
            return f"{self._get_site_url()}{avatar_url}"
        return f"{self._get_site_url()}/{avatar_url}"

    def _build_title(self, notification) -> str:
        if notification.verb in self.CHAT_NOTIFICATION_VERBS:
            return self._get_actor_name(notification) or self.DEFAULT_TITLE

        return self._get_data_title(notification) or self.DEFAULT_TITLE

    def _is_permanent_device_error(self, error: Exception) -> bool:
        error_text = str(error).lower()
        permanent_markers = (
            "expired",
            "unregistered",
            "invalid subscription",
            "invalidregistration",
            "not found",
            "gone",
            "404",
            "410",
            "400 bad request",
        )
        return any(marker in error_text for marker in permanent_markers)

    def _deactivate_device(self, device, reason: str) -> None:
        if not device.active:
            return
        device.active = False
        device.save(update_fields=["active"])
        self.logger.info(
            "Push device %s deactivated after permanent delivery error: %s",
            device.id,
            reason,
        )

    def send(self, notification, **kwargs) -> bool:
        """
        Отправляет Web Push уведомление.

        Args:
            notification: Объект Notification
            **kwargs: Дополнительные параметры

        Returns:
            True если отправлено успешно, False иначе
        """
        try:
            user = notification.recipient

            # Получаем активные устройства через django-push-notifications
            devices = WebPushDevice.objects.filter(user=user, active=True)

            if not devices.exists():
                self.log_skip(notification, "no active push devices")
                return False

            # Формируем данные для push без технических verb в видимом тексте.
            title = self._build_title(notification)

            # Ограничиваем длину body.
            # Web Push имеет лимит ~4KB на весь payload.
            # Оставляем 300 символов для body, чтобы гарантировать что весь
            # message
            # поместится
            body = notification.description or ""
            if len(body) > 300:
                body = body[:297] + "..."

            # Получаем иконки из конфигурации (None = browser default)
            actor_icon = (
                self._get_actor_avatar_url(notification)
                if notification.verb in self.CHAT_NOTIFICATION_VERBS
                else ""
            )
            default_icon = get("PUSH_DEFAULT_ICON")
            default_badge = get("PUSH_DEFAULT_BADGE")

            # django-push-notifications использует другой формат
            # Формируем данные для Web Push API
            message_data = {
                "title": title,
                "head": title,
                "body": body,
                "url": notification.action_url or "/",
                "tag": f"notification-{notification.id}",
                "requireInteraction": False,
                "data": {
                    "url": notification.action_url or "/",
                    "notification_id": notification.id,
                },
            }

            # Для сообщений используем аватар автора, иначе текущую иконку.
            if actor_icon:
                message_data["icon"] = actor_icon
            elif default_icon:
                message_data["icon"] = default_icon
            if default_badge:
                message_data["badge"] = default_badge

            # Преобразуем в JSON-строку для send_message()
            message = json.dumps(message_data)

            sent_count = 0
            failed_count = 0

            # Отправляем через все устройства пользователя
            for device in devices:
                try:
                    device.send_message(message)
                    sent_count += 1
                    self.logger.debug(
                        f"Push отправлен на device {device.id} ({
                            device.browser
                        })"
                    )
                except Exception as e:
                    failed_count += 1
                    # Вычисляем размер payload для диагностики
                    message_size = len(message.encode("utf-8"))
                    error_text = str(e)
                    self.logger.error(
                        f"Ошибка отправки push на device {device.id}: {e} "
                        f"(payload size: {message_size} bytes)"
                    )
                    if self._is_permanent_device_error(e):
                        self._deactivate_device(device, error_text)

            if sent_count > 0:
                self.log_success(notification, f"{sent_count} devices")
                if failed_count > 0:
                    self.logger.warning(
                        f"Push отправлен частично: {sent_count} успешно, "
                        f"{failed_count} ошибок"
                    )
                return True
            else:
                self.log_skip(
                    notification,
                    f"no successful sends ({failed_count} failures)",
                )
                return False

        except ImportError:
            self.log_skip(
                notification, "django-push-notifications not installed"
            )
            return False
        except Exception as e:
            self.log_error(notification, e, f"user_{notification.recipient.id}")
            return False

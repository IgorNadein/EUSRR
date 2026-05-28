"""
Web Push отправитель для browser push notifications
"""

import json

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

    def _build_title(self, notification) -> str:
        if notification.verb in self.CHAT_NOTIFICATION_VERBS:
            return self._get_actor_name(notification) or self.DEFAULT_TITLE

        return self._get_data_title(notification) or self.DEFAULT_TITLE

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

            # Добавляем иконки только если они настроены
            if default_icon:
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
                    self.logger.error(
                        f"Ошибка отправки push на device {device.id}: {e} "
                        f"(payload size: {message_size} bytes)"
                    )
                    # Деактивируем устройство если ошибка
                    if (
                        "expired" in str(e).lower()
                        or "unregistered" in str(e).lower()
                    ):
                        device.active = False
                        device.save()
                        self.logger.info(f"Device {device.id} деактивирован")

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

"""
Email отправитель для системы уведомлений

TODO: Создать email шаблоны:
      - templates/notifications/email/notification.html
      - templates/notifications/email/notification.txt
      - templates/notifications/email/digest.html
      - templates/notifications/email/digest.txt
"""

from django.conf import settings
from django.template.loader import render_to_string
from django.core.mail import send_mail

from .base import BaseNotificationSender
from notifications import config
from notifications.models import Notification


class EmailNotificationSender(BaseNotificationSender):
    """
    Отправитель email уведомлений.
    Использует HTML шаблоны для красивого оформления.
    """

    # Маппинг verb на эмодзи для email
    VERB_ICONS = {
        "liked": "❤️",
        "commented": "💬",
        "mentioned": "@",
        "approved": "✅",
        "rejected": "❌",
        "created": "📝",
        "updated": "🔄",
        "deleted": "🗑️",
        "shared": "🔗",
        "followed": "👥",
    }

    def can_send(self, notification, user_preferences) -> bool:
        """Проверяет, включена ли отправка email"""
        if not user_preferences.email_enabled:
            self.log_skip(notification, "email_enabled=False")
            return False

        if user_preferences.email_frequency != "instant":
            self.log_skip(
                notification,
                f"email_frequency={user_preferences.email_frequency}",
            )
            return False

        return True

    def send(self, notification, **kwargs) -> bool:
        """
        Отправляет email уведомление.

        Args:
            notification: Объект Notification
            **kwargs:
                custom_subject: кастомная тема письма (опционально)
                recipient_email: явный email получателя (опционально)

        Returns:
            True если отправлено успешно, False иначе
        """
        try:
            user = notification.recipient
            recipient_email = kwargs.get("recipient_email", user.email)

            if not recipient_email:
                self.log_skip(notification, "no email address")
                return False

            # Формируем тему письма
            custom_subject = kwargs.get("custom_subject")
            if custom_subject:
                subject = custom_subject
            else:
                icon = self.VERB_ICONS.get(notification.verb, "🔔")
                actor_str = (
                    str(notification.actor) if notification.actor else "Система"
                )
                subject = f"{icon} {actor_str} {notification.verb}"

            # Формируем контекст для шаблона
            context = {
                "notification": notification,
                "actor": notification.actor,
                "verb": notification.verb,
                "description": notification.description,
                "action_url": self._get_full_url(
                    notification.action_url, notification
                ),
                "action_text": "Посмотреть",
                "site_name": config.site_name(),
                "site_url": self._get_site_url(notification),
                "verb_icon": self.VERB_ICONS.get(notification.verb, "🔔"),
            }

            # Рендерим HTML и текстовую версию
            html_message = self._render_template(
                "notifications/email/notification.html", context
            )
            text_message = self._render_template(
                "notifications/email/notification.txt", context
            )

            # Отправляем email
            send_mail(
                subject=subject,
                message=text_message,
                from_email=config.from_email(),
                recipient_list=[recipient_email],
                html_message=html_message,
                fail_silently=False,
            )

            # Отмечаем что отправлено
            notification.emailed = True
            notification.save(update_fields=["emailed"])

            self.log_success(notification, recipient_email)
            return True

        except Exception as e:
            self.log_error(notification, e, recipient_email)
            return False

    def send_digest(self, user, notifications, frequency: str = "daily") -> bool:
        """
        Отправляет email дайджест уведомлений.

        Args:
            user: User объект
            notifications: Список объектов Notification
            frequency: 'daily' или 'weekly'

        Returns:
            True если отправлено успешно, False иначе
        """
        try:
            notifications = list(notifications)
            if not notifications:
                return False

            recipient_email = user.email
            if not recipient_email:
                return False

            # Формируем тему
            digest_name = (
                "Ежедневный" if frequency == "daily" else "Еженедельный"
            )
            subject = (
                f"📬 {digest_name} дайджест уведомлений ({len(notifications)})"
            )

            # Группируем по verb
            grouped = {}
            for notif in notifications:
                verb = notif.verb
                if verb not in grouped:
                    grouped[verb] = []
                grouped[verb].append(notif)

            # Формируем контекст
            context = {
                "user": user,
                "notifications": notifications,
                "grouped_notifications": grouped,
                "frequency": frequency,
                "digest_name": digest_name,
                "total_count": len(notifications),
                "verb_icons": self.VERB_ICONS,
                "site_name": config.site_name(),
                "site_url": self._get_site_url(
                    notifications[0] if notifications else None
                ),
            }

            # Рендерим шаблоны
            html_message = self._render_template(
                "notifications/email/digest.html", context
            )
            text_message = self._render_template(
                "notifications/email/digest.txt", context
            )

            # Отправляем дайджест
            send_mail(
                subject=subject,
                message=text_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient_email],
                html_message=html_message,
                fail_silently=False,
            )

            # Отмечаем как отправленные. На вход может прийти как QuerySet,
            # так и список из Celery-задачи, поэтому обновляем по id.
            notification_ids = [item.id for item in notifications if item.id]
            if notification_ids:
                Notification.objects.filter(id__in=notification_ids).update(
                    emailed=True
                )

            self.logger.info(
                f"✅ Email дайджест отправлен: "
                f"user={user.id}, "
                f"count={len(notifications)}, "
                f"frequency={frequency}, "
                f"recipient={recipient_email}"
            )
            return True

        except Exception as e:
            self.logger.error(
                f"❌ Ошибка отправки дайджеста: "
                f"user={user.id}, "
                f"frequency={frequency}, "
                f"error={type(e).__name__}: {e}",
                exc_info=True,
            )
            return False

    def _render_template(self, template_name: str, context: dict) -> str:
        """Рендерит шаблон с контекстом"""
        try:
            return render_to_string(template_name, context)
        except Exception:
            # Если шаблон не найден, возвращаем простой текст
            notif = context.get("notification")
            if notif:
                return f"{notif.description}\n\n{context.get('action_url', '')}"
            return ""

    def _get_site_url(self, notification=None) -> str:
        """
        Получает базовый URL сайта.

        Приоритет:
        1. notification.data['site_url'] - если передан при создании
        2. settings.SITE_URL - статическая настройка
        3. settings.ALLOWED_HOSTS[0] - автоопределение из разрешенных хостов
        4. 'http://localhost:9000' - fallback для разработки

        Args:
            notification: Объект Notification (опционально)

        Returns:
            Базовый URL сайта (например, 'https://example.com')
        """
        # 1. Проверяем данные уведомления
        if (
            notification
            and hasattr(notification, "data")
            and isinstance(notification.data, dict)
        ):
            if "site_url" in notification.data:
                return notification.data["site_url"]

        # 2. Проверяем settings.SITE_URL
        if hasattr(settings, "SITE_URL"):
            return settings.SITE_URL

        # 3. Автоопределение из ALLOWED_HOSTS
        if settings.ALLOWED_HOSTS and settings.ALLOWED_HOSTS[0] != "*":
            host = settings.ALLOWED_HOSTS[0]
            protocol = (
                "https"
                if getattr(settings, "SECURE_SSL_REDIRECT", False)
                else "http"
            )
            return f"{protocol}://{host}"

        # 4. Fallback для разработки
        return "http://localhost:9000"

    def _get_full_url(self, path: str, notification=None) -> str:
        """
        Преобразует относительный URL в абсолютный.

        Args:
            path: Относительный или абсолютный URL
            notification: Объект Notification для получения site_url

        Returns:
            Абсолютный URL
        """
        if not path:
            return ""

        if path.startswith("http://") or path.startswith("https://"):
            return path

        site_url = self._get_site_url(notification)
        return f"{site_url}{path}"

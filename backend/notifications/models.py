"""
Упрощенная универсальная система уведомлений
Основана на архитектуре django-notifications-hq, адаптирована для Django 5.2+

Ключевые изменения:
- Одна модель Notification вместо 6
- GenericForeignKey для универсальности
- Простой API через сигналы
- Multi-channel поддержка (Web, Email, Push)

TODO: Добавить тесты для моделей:
      - NotificationQuerySet методы (unread, read, mark_all_as_*)
      - Notification.mark_as_read/unread()
      - Notification.timesince()
      - UserChannelPreferences.is_verb_enabled()
      - UserChannelPreferences.is_in_dnd_period()
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db.models.query import QuerySet


class NotificationQuerySet(QuerySet):
    """QuerySet с удобными методами фильтрации"""

    def unread(self):
        """Непрочитанные уведомления"""
        return self.filter(unread=True)

    def read(self):
        """Прочитанные уведомления"""
        return self.filter(unread=False)

    def mark_all_as_read(self, recipient=None):
        """Отметить все как прочитанные"""
        qs = self.unread()
        if recipient:
            qs = qs.filter(recipient=recipient)

        return qs.update(unread=False, timestamp_read=timezone.now())

    def mark_all_as_unread(self, recipient=None):
        """Отметить все как непрочитанные"""
        qs = self.read()
        if recipient:
            qs = qs.filter(recipient=recipient)

        return qs.update(unread=True, timestamp_read=None)

    def deleted(self):
        """Удаленные уведомления"""
        return self.filter(deleted=True)

    def active(self):
        """Активные (не удаленные) уведомления"""
        return self.filter(deleted=False)

    def public(self):
        """Публичные уведомления"""
        return self.filter(public=True)

    def for_user(self, user):
        """Уведомления для конкретного пользователя"""
        return self.filter(recipient=user).active()


class Notification(models.Model):
    """
    Универсальная модель уведомления

    Структура по образу django-notifications-hq:
    - actor performed verb on action_object at target

    Примеры:
    - John (actor) commented (verb) on photo (target)
    - Mary (actor) liked (verb) your comment (action_object) on post (target)
    - System (actor) approved (verb) your request (action_object)
    """

    # === Базовые поля ===

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="Получатель",
        help_text="Кому адресовано уведомление",
    )

    # Кто совершил действие (GenericForeignKey)
    actor_content_type = models.ForeignKey(
        ContentType,
        related_name="notify_actor",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Тип актора",
    )
    actor_object_id = models.CharField(
        max_length=255, null=True, blank=True, verbose_name="ID актора"
    )
    actor = GenericForeignKey("actor_content_type", "actor_object_id")

    # Что произошло
    verb = models.CharField(
        max_length=255,
        default="notification",
        verbose_name="Действие",
        help_text="Например: liked, commented, approved, mentioned",
        db_index=True,
    )

    # Объект действия (GenericForeignKey) - опционально
    action_object_content_type = models.ForeignKey(
        ContentType,
        related_name="notify_action_object",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Тип объекта действия",
    )
    action_object_object_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="ID объекта действия",
    )
    action_object = GenericForeignKey(
        "action_object_content_type", "action_object_object_id"
    )

    # Целевой объект (GenericForeignKey) - опционально
    target_content_type = models.ForeignKey(
        ContentType,
        related_name="notify_target",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Тип целевого объекта",
    )
    target_object_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="ID целевого объекта",
    )
    target = GenericForeignKey("target_content_type", "target_object_id")

    # === Контент ===

    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Описание",
        help_text="Человекочитаемое описание уведомления",
    )

    # URL для перехода
    action_url = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="URL действия",
        help_text="Куда перейти при клике на уведомление",
    )

    # Дополнительные данные (JSON)
    data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Дополнительные данные",
        help_text="Любые метаданные для рендеринга или логики",
    )

    # === Статусы ===

    unread = models.BooleanField(
        default=True, db_index=True, verbose_name="Непрочитано"
    )

    timestamp_read = models.DateTimeField(
        null=True, blank=True, verbose_name="Время прочтения"
    )

    public = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Публичное",
        help_text="Можно показывать другим пользователям",
    )

    deleted = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Удалено",
        help_text="Мягкое удаление",
    )

    emailed = models.BooleanField(
        default=False, db_index=True, verbose_name="Отправлено на email"
    )

    # === Временные метки ===

    timestamp = models.DateTimeField(
        default=timezone.now, db_index=True, verbose_name="Создано"
    )

    # === Manager ===

    objects = NotificationQuerySet.as_manager()

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["recipient", "-timestamp"]),
            models.Index(fields=["recipient", "unread", "-timestamp"]),
            models.Index(fields=["verb", "-timestamp"]),
            models.Index(fields=["-timestamp"]),
        ]
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"
        db_table = "notifications_notification_v2"  # Новая таблица для миграции

    def __str__(self):
        actor_str = str(self.actor) if self.actor else "Система"
        target_str = f" → {self.target}" if self.target else ""
        return f"{actor_str} {self.verb}{target_str}"

    # === Методы ===

    def mark_as_read(self):
        """Отметить уведомление как прочитанное"""
        if self.unread:
            self.unread = False
            self.timestamp_read = timezone.now()
            self.save(update_fields=["unread", "timestamp_read"])
            from .cache import invalidate_unread_summary

            invalidate_unread_summary(self.recipient_id)

    def mark_as_unread(self):
        """Отметить уведомление как непрочитанное"""
        if not self.unread:
            self.unread = True
            self.timestamp_read = None
            self.save(update_fields=["unread", "timestamp_read"])
            from .cache import invalidate_unread_summary

            invalidate_unread_summary(self.recipient_id)

    @property
    def timesince(self, now=None):
        """
        Возвращает человекочитаемое время с момента создания
        Например: "5 минут назад", "2 часа назад"
        """
        from django.utils.timesince import timesince as timesince_

        return timesince_(self.timestamp, now)

    @property
    def slug(self):
        """
        Создает slug для уведомления (для URL)
        Формат: id-verb-target
        """
        return f"{self.id or ''}-{self.verb}-{self.target_object_id or ''}"


class UserChannelPreferences(models.Model):
    """
    Настройки каналов доставки для пользователя

    Упрощенная модель вместо UserNotificationSettings
    Один пользователь - одна запись с настройками для всех каналов
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="channel_preferences",
        verbose_name="Пользователь",
    )

    # === Каналы доставки ===

    web_enabled = models.BooleanField(
        default=True,
        verbose_name="Веб уведомления",
        help_text="Показывать в интерфейсе сайта",
    )

    email_enabled = models.BooleanField(
        default=False, verbose_name="Email уведомления"
    )

    push_enabled = models.BooleanField(
        default=False,
        verbose_name="Push уведомления",
        help_text="Web Push для браузера",
    )

    # === Email настройки ===

    EMAIL_FREQUENCY_CHOICES = [
        ("instant", "Мгновенно"),
        ("daily", "Ежедневный дайджест"),
        ("weekly", "Еженедельный дайджест"),
        ("never", "Никогда"),
    ]

    email_frequency = models.CharField(
        max_length=20,
        choices=EMAIL_FREQUENCY_CHOICES,
        default="instant",
        verbose_name="Частота email",
    )

    # === Тихий режим (Do Not Disturb) ===

    dnd_enabled = models.BooleanField(
        default=False,
        verbose_name='Режим "Не беспокоить"',
        help_text="Отключить все уведомления в определенное время",
    )

    dnd_start_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name="Начало тихого режима",
        help_text="Например, 22:00",
    )

    dnd_end_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name="Конец тихого режима",
        help_text="Например, 08:00",
    )

    # === Фильтры по типам (verb) ===

    disabled_verbs = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Отключенные типы",
        help_text=(
            'Список verb для которых не показывать уведомления. '
            'Например: ["liked", "followed"]'
        ),
    )

    class Meta:
        verbose_name = "Настройки каналов пользователя"
        verbose_name_plural = "Настройки каналов пользователей"
        db_table = "notifications_userchannelpreferences"

    def __str__(self):
        return f"{self.user.get_short_name()} - настройки каналов"

    def is_verb_enabled(self, verb):
        """Проверить, включен ли этот тип уведомлений"""
        return verb not in self.disabled_verbs

    def disable_verb(self, verb):
        """Отключить определенный тип уведомлений"""
        if verb not in self.disabled_verbs:
            self.disabled_verbs.append(verb)
            self.save(update_fields=["disabled_verbs"])

    def enable_verb(self, verb):
        """Включить определенный тип уведомлений"""
        if verb in self.disabled_verbs:
            self.disabled_verbs.remove(verb)
            self.save(update_fields=["disabled_verbs"])

    def is_in_dnd_period(self):
        """Проверить, находимся ли в режиме "Не беспокоить"""
        if (
            not self.dnd_enabled
            or not self.dnd_start_time
            or not self.dnd_end_time
        ):
            return False

        now = timezone.now().time()

        # Простой случай: начало < конец (например, 09:00 - 18:00)
        if self.dnd_start_time < self.dnd_end_time:
            return self.dnd_start_time <= now <= self.dnd_end_time

        # Через полночь: начало > конец (например, 22:00 - 08:00)
        return now >= self.dnd_start_time or now <= self.dnd_end_time


# === Web Push устройства управляются через django-push-notifications ===
# Используйте: from push_notifications.models import WebPushDevice

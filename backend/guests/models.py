from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, models
from django.db.models import Max, Q
from django.utils import timezone

from .constants import (
    EDITABLE_BY_AUTHOR_STATUSES,
    GUEST_ID_MAX,
    GUEST_ID_MIN,
    GUEST_ID_START,
    GuestVisitEventType,
    GuestVisitStatus,
)


def _setting_int(name: str, default: int) -> int:
    return int(getattr(settings, name, default))


class Guest(models.Model):
    id = models.BigIntegerField(primary_key=True, editable=False)
    last_name = models.CharField("Фамилия", max_length=150)
    first_name = models.CharField("Имя", max_length=150)
    patronymic = models.CharField("Отчество", max_length=150, blank=True)
    birth_date = models.DateField("Дата рождения", null=True, blank=True)
    phone = models.CharField("Телефон", max_length=64, blank=True)
    email = models.EmailField("Email", blank=True)
    organization = models.CharField("Организация", max_length=255, blank=True)
    position = models.CharField("Должность", max_length=255, blank=True)
    comment = models.TextField("Комментарий", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_guests",
        verbose_name="Создал",
    )
    is_active = models.BooleanField("Активен", default=True)
    ldap_enabled = models.BooleanField("LDAP в Active OU", default=False)
    ldap_username = models.CharField("LDAP username", max_length=150, blank=True)
    ldap_upn = models.CharField("LDAP UPN", max_length=255, blank=True)
    ldap_last_synced_at = models.DateTimeField(
        "Последняя LDAP синхронизация",
        null=True,
        blank=True,
    )
    ldap_last_error = models.TextField("Последняя LDAP ошибка", blank=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Гость"
        verbose_name_plural = "Гости"
        ordering = ["last_name", "first_name", "id"]
        indexes = [
            models.Index(fields=["last_name", "first_name"], name="guest_name_idx"),
            models.Index(fields=["email"], name="guest_email_idx"),
            models.Index(fields=["phone"], name="guest_phone_idx"),
            models.Index(fields=["ldap_enabled"], name="guest_ldap_enabled_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                name="guest_id_in_guest_range",
                condition=Q(id__gte=GUEST_ID_START) & Q(id__lte=GUEST_ID_MAX),
            ),
        ]

    def __str__(self) -> str:
        return self.full_name

    @property
    def full_name(self) -> str:
        return " ".join(
            part
            for part in [self.last_name, self.first_name, self.patronymic]
            if part
        ).strip()

    @classmethod
    def next_guest_id(cls) -> int:
        start = _setting_int("GUESTS_ID_START", GUEST_ID_START)
        max_value = _setting_int("GUESTS_ID_MAX", GUEST_ID_MAX)

        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT nextval('guests_guest_id_seq')")
                value = int(cursor.fetchone()[0])
        else:
            current = cls.objects.aggregate(max_id=Max("id"))["max_id"]
            value = start if current is None or current < start else int(current) + 1

        if value < start or value > max_value:
            raise ValidationError("Диапазон идентификаторов гостей исчерпан.")
        return value

    def clean(self):
        super().clean()
        if self.id is not None and not (GUEST_ID_START <= int(self.id) <= GUEST_ID_MAX):
            raise ValidationError(
                {"id": "ID гостя должен находиться в гостевом диапазоне."}
            )

    def save(self, *args, **kwargs):
        if self.pk is None:
            self.pk = self.next_guest_id()
        self.clean()
        super().save(*args, **kwargs)


class GuestVisit(models.Model):
    guest = models.ForeignKey(
        Guest,
        on_delete=models.PROTECT,
        related_name="visits",
        verbose_name="Гость",
    )
    inviter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="guest_visits",
        verbose_name="Приглашающий",
    )
    inviter_snapshot_name = models.CharField(
        "ФИО приглашающего на момент создания",
        max_length=255,
        blank=True,
    )
    inviter_snapshot_email = models.EmailField(
        "Email приглашающего на момент создания",
        blank=True,
    )
    host_department = models.ForeignKey(
        "employees.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="guest_visits",
        verbose_name="Отдел приглашающего",
    )
    purpose = models.TextField("Цель приглашения")
    visit_comment = models.TextField("Комментарий заявителя", blank=True)
    admin_comment = models.TextField("Комментарий администратора", blank=True)
    status = models.CharField(
        "Статус",
        max_length=24,
        choices=GuestVisitStatus.choices,
        default=GuestVisitStatus.DRAFT,
        db_index=True,
    )
    access_starts_at = models.DateTimeField(
        "Начало доступа",
        null=True,
        blank=True,
    )
    access_expires_at = models.DateTimeField(
        "Окончание доступа",
        null=True,
        blank=True,
    )
    all_day = models.BooleanField("Полные сутки", default=True)
    unlimited = models.BooleanField("Бессрочно", default=False)
    documents = models.ManyToManyField(
        "documents.Document",
        blank=True,
        related_name="guest_visits",
        verbose_name="Документы",
    )
    submitted_at = models.DateTimeField(
        "Отправлено на рассмотрение",
        null=True,
        blank=True,
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="decided_guest_visits",
        verbose_name="Решение принял",
    )
    decided_at = models.DateTimeField("Решение принято", null=True, blank=True)
    decision_comment = models.TextField("Комментарий к решению", blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cancelled_guest_visits",
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.TextField(blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revoked_guest_visits",
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoke_reason = models.TextField(blank=True)
    expired_at = models.DateTimeField(null=True, blank=True)
    inviter_inactive = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Гостевой визит"
        verbose_name_plural = "Гостевые визиты"
        ordering = ["-created_at"]
        permissions = [
            ("view_all_guestvisit", "Может просматривать все гостевые визиты"),
            ("decide_guestvisit", "Может принимать решения по гостевым визитам"),
            ("manage_guestaccount", "Может управлять гостевыми учетками"),
        ]
        indexes = [
            models.Index(
                fields=["status", "created_at"],
                name="guestvisit_status_created_idx",
            ),
            models.Index(
                fields=["inviter", "created_at"],
                name="guestvisit_inviter_created_idx",
            ),
            models.Index(
                fields=["access_starts_at", "access_expires_at"],
                name="guestvisit_access_idx",
            ),
            models.Index(fields=["guest", "status"], name="guestvisit_guest_status_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                name="guest_visit_access_range_valid",
                condition=Q(unlimited=True)
                | Q(access_expires_at__isnull=True)
                | Q(access_starts_at__isnull=True)
                | Q(access_starts_at__lt=models.F("access_expires_at")),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.guest} — {self.get_status_display()}"

    @property
    def is_active_now(self) -> bool:
        if self.status != GuestVisitStatus.APPROVED:
            return False
        if self.unlimited:
            return True
        now = timezone.now()
        if self.access_starts_at and self.access_starts_at > now:
            return False
        if self.access_expires_at and self.access_expires_at <= now:
            return False
        return True

    @property
    def is_expired(self) -> bool:
        return bool(
            not self.unlimited
            and self.access_expires_at
            and self.access_expires_at <= timezone.now()
        )

    def can_edit_by(self, user) -> bool:
        if not user or not user.is_authenticated:
            return False
        if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
            return True
        return (
            self.inviter_id == user.id
            and self.status in EDITABLE_BY_AUTHOR_STATUSES
        )


class GuestVisitEvent(models.Model):
    visit = models.ForeignKey(
        GuestVisit,
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name="Визит",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="guest_visit_events",
        verbose_name="Автор события",
    )
    event_type = models.CharField(
        "Тип события",
        max_length=48,
        choices=GuestVisitEventType.choices,
        db_index=True,
    )
    from_status = models.CharField(max_length=24, blank=True)
    to_status = models.CharField(max_length=24, blank=True)
    comment = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Событие гостевого визита"
        verbose_name_plural = "События гостевых визитов"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["visit", "-created_at"], name="guestevent_visit_created_idx"),
            models.Index(
                fields=["event_type", "-created_at"],
                name="guestevent_type_created_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.visit_id}: {self.event_type}"

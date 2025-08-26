# backend/calendar_app/models.py
from django.contrib.auth import get_user_model
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class Recurrence(models.TextChoices):
    ONE_TIME = "one_time", _("Одноразовое")
    ANNUAL = "annual", _("Ежегодно")


class CompanyEvent(models.Model):
    title = models.CharField(_("Название"), max_length=200)
    description = models.TextField(_("Описание"), blank=True)
    date = models.DateField(_("Дата события"))
    recurrence = models.CharField(
        _("Повторение"),
        max_length=20,
        choices=Recurrence.choices,
        default=Recurrence.ONE_TIME,
    )
    color = models.CharField(
        _("Цвет (hex)"), max_length=7, blank=True, help_text="#RRGGBB"
    )
    location = models.CharField(_("Локация"), max_length=200, blank=True)

    created_by = models.ForeignKey(
        User,
        verbose_name=_("Создал"),
        on_delete=models.SET_NULL,  # ← ожидаемое поведение при удалении автора
        null=True,
        blank=True,
        related_name="company_events_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Событие компании")
        verbose_name_plural = _("События компании")
        ordering = ["recurrence", "date"]
        indexes = [
            models.Index(fields=["date"]),
            models.Index(
                fields=["recurrence", "date"]
            ),  # ← для сортировок по Meta.ordering
        ]

    def __str__(self):
        return f"{self.title} — {self.date:%d.%m.%Y}"

    def get_absolute_url(self):
        return reverse("calendar_app:company_calendar")


class DepartmentEvent(models.Model):
    department = models.ForeignKey(
        "employees.Department",  # ← строковая ссылка без импорта
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name=_("Отдел"),
    )
    title = models.CharField(_("Название"), max_length=200)
    description = models.TextField(_("Описание"), blank=True)

    start_date = models.DateField(_("Дата начала"))
    end_date = models.DateField(_("Дата окончания"), null=True, blank=True)
    all_day = models.BooleanField(_("Весь день"), default=True)

    recurrence = models.CharField(
        _("Повторение"),
        max_length=20,
        choices=Recurrence.choices,
        default=Recurrence.ONE_TIME,
    )
    color = models.CharField(
        _("Цвет (hex)"), max_length=7, blank=True, help_text="#RRGGBB"
    )
    location = models.CharField(_("Локация"), max_length=200, blank=True)

    created_by = models.ForeignKey(
        User,
        verbose_name=_("Создал"),
        on_delete=models.SET_NULL,  # ← автор может быть удалён
        null=True,
        blank=True,
        related_name="department_events_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Событие отдела")
        verbose_name_plural = _("События отделов")
        ordering = ["department", "start_date"]
        indexes = [
            models.Index(fields=["department", "start_date"]),
            models.Index(
                fields=["department", "recurrence", "start_date"]
            ),  # ← фильтр/сорт по отделу+типу
            models.Index(fields=["start_date", "end_date"]),
        ]
        constraints = [
            models.CheckConstraint(
                name="dept_event_date_range_valid",
                condition=(
                    models.Q(end_date__isnull=True)
                    | models.Q(start_date__isnull=True)
                    | models.Q(start_date__lte=models.F("end_date"))
                ),
            ),
        ]
        permissions = [
            ("manage_department_events", "Может создавать/обновлять/ удалять события отдела"),
        ]

    def __str__(self):
        if self.end_date:
            return f"{self.department}: {self.title} ({self.start_date:%d.%m.%Y}–{self.end_date:%d.%m.%Y})"
        return f"{self.department}: {self.title} ({self.start_date:%d.%m.%Y})"

    def clean(self):
        # UX-валидация до попытки сохранить в БД
        if self.end_date and self.start_date and self.end_date < self.start_date:
            from django.core.exceptions import ValidationError

            raise ValidationError(
                {"end_date": _("Дата окончания не может быть раньше даты начала.")}
            )

    def get_absolute_url(self):
        return reverse("calendar_app:department_calendar", args=[self.department_id])

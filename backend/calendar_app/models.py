# backend/calendar_app/models.py
from __future__ import annotations

from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class Recurrence(models.TextChoices):
    """Типы повторяемости события календаря."""

    ONE_TIME = "one_time", _("Одноразовое")
    HOURLY = "hourly", _("Ежечасно")
    DAILY = "daily", _("Ежедневно")
    WEEKLY = "weekly", _("Еженедельно")
    MONTHLY = "monthly", _("Ежемесячно")
    ANNUAL = "annual", _("Ежегодно")


class CalendarEvent(models.Model):
    """Событие календаря (компании или отдела) с поддержкой повторяемости.

    Если `department` = NULL → событие компании (глобальное).
    Если `department` задан → событие конкретного отдела.
    """

    # Область
    department = models.ForeignKey(
        "employees.Department",
        on_delete=models.CASCADE,
        related_name="calendar_events",
        verbose_name=_("Отдел"),
        null=True,
        blank=True,
        help_text=_("Пусто — событие компании; задано — событие отдела."),
    )

    # Основное
    title = models.CharField(_("Название"), max_length=200)
    description = models.TextField(_("Описание"), blank=True)

    # Даты/время
    start_date = models.DateField(_("Дата начала"))
    end_date = models.DateField(_("Дата окончания"), null=True, blank=True)
    start_time = models.TimeField(_("Время начала"), null=True, blank=True)
    end_time = models.TimeField(_("Время окончания"), null=True, blank=True)
    all_day = models.BooleanField(_("Весь день"), default=True)

    # Повторяемость
    recurrence = models.CharField(
        _("Повторение"),
        max_length=20,
        choices=Recurrence.choices,
        default=Recurrence.ONE_TIME,
    )
    recurrence_interval = models.PositiveSmallIntegerField(
        _("Интервал повторения"),
        default=1,
        help_text=_("Шаг повторения (каждые N часов/дней/недель/месяцев)."),
    )
    recurrence_count = models.PositiveIntegerField(
        _("Количество повторений"),
        null=True,
        blank=True,
        help_text=_("Максимум создаваемых вхождений; нельзя вместе с датой окончания."),
    )
    recurrence_until = models.DateField(
        _("Повторять до (включительно)"),
        null=True,
        blank=True,
        help_text=_(
            "Дата, до которой повторять. Нельзя вместе с количеством повторов."
        ),
    )
    weekdays_mask = models.PositiveSmallIntegerField(
        _("Дни недели (битовая маска)"),
        default=0,
        help_text=_(
            "Для еженедельных событий: 1=Пн,2=Вт,4=Ср,8=Чт,16=Пт,32=Сб,64=Вс; можно суммировать."
        ),
    )

    # Отображение
    color = models.CharField(
        _("Цвет (hex)"), max_length=7, blank=True, help_text="#RRGGBB"
    )
    location = models.CharField(_("Локация"), max_length=200, blank=True)

    # Служебное
    created_by = models.ForeignKey(
        User,
        verbose_name=_("Создал"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calendar_events_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    source = models.CharField(
        _("Источник события"),
        max_length=120,
        blank=True,
        db_index=True,
        help_text=_(
            "Технический ключ связи с внешним объектом, напр. 'employee:<id>:birthday'"
        ),
    )

    class Meta:
        verbose_name = _("Событие календаря")
        verbose_name_plural = _("События календаря")
        ordering = ["department", "start_date", "start_time"]
        indexes = [
            models.Index(fields=["department", "start_date"]),
            models.Index(fields=["department", "recurrence", "start_date"]),
            models.Index(fields=["start_date", "end_date"]),
            models.Index(fields=["start_date", "start_time"]),
            models.Index(fields=["source"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["source"],
                name="cal_event_source_unique",
                condition=~models.Q(source=""),
            ),
        ]
        permissions = [
            ("manage_department_events", "Может управлять событиями отдела"),
        ]

    def __str__(self) -> str:
        scope = self.department or _("Компания")
        if self.end_date:
            return f"{scope}: {self.title} ({self.start_date:%d.%m.%Y}–{self.end_date:%d.%m.%Y})"
        return f"{scope}: {self.title} ({self.start_date:%d.%m.%Y})"

    @property
    def is_company(self) -> bool:
        """True если событие глобальное (без отдела)."""
        return self.department_id is None

    @property
    def has_time(self) -> bool:
        """True если задано точное время (оба поля времени)."""
        return self.start_time is not None and self.end_time is not None

    # ---------- Валидация ----------
    def clean(self) -> None:
        """Валидирует согласованность дат/времени и повторяемости.

        Raises:
            ValidationError: При некорректных датах/времени или настройках повторения.
        """
        # База дат
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError(
                {"end_date": _("Дата окончания не может быть раньше даты начала.")}
            )

        # Время — либо оба, либо ни одного
        if (self.start_time is None) ^ (self.end_time is None):
            raise ValidationError(
                _("Если указываете время, заполните и начало, и окончание.")
            )

        # В пределах одного дня: end_time >= start_time
        if (
            self.has_time
            and self.end_date
            and self.start_date == self.end_date
            and self.end_time < self.start_time
        ):
            raise ValidationError(
                {"end_time": _("Время окончания не может быть раньше времени начала.")}
            )

        # Согласование all_day
        if self.has_time and self.all_day:
            self.all_day = False
        if (not self.has_time) and (not self.all_day):
            self.all_day = True

        # Повторяемость: ограничения
        if self.recurrence in {Recurrence.HOURLY} and not self.has_time:
            raise ValidationError(
                _("Ежечасное событие требует указания времени начала и окончания.")
            )

        if (
            self.recurrence in {Recurrence.HOURLY, Recurrence.DAILY}
            and self.recurrence_interval < 1
        ):
            raise ValidationError(
                {"recurrence_interval": _("Интервал должен быть ≥ 1.")}
            )

        if self.recurrence == Recurrence.WEEKLY:
            if self.recurrence_interval < 1:
                raise ValidationError(
                    {"recurrence_interval": _("Интервал должен быть ≥ 1.")}
                )
            # Если маска не задана — используем день недели start_date
            if self.weekdays_mask == 0 and self.start_date:
                self.weekdays_mask = 1 << (
                    (self.start_date.weekday()) % 7
                )  # 0=Mon...6=Sun

        if self.recurrence == Recurrence.MONTHLY and self.recurrence_interval < 1:
            raise ValidationError(
                {"recurrence_interval": _("Интервал должен быть ≥ 1.")}
            )

        # until/count взаимоисключительны
        if self.recurrence_until and self.recurrence_count:
            raise ValidationError(
                _("Нельзя одновременно задавать 'до даты' и 'количество повторов'.")
            )

    # ----- Утилиты для фронта -----
    def iso_start(self) -> str:
        """Возвращает ISO-строку начала (date или datetime)."""
        if self.has_time:
            dt = datetime.combine(self.start_date, self.start_time)
            return dt.isoformat()
        return self.start_date.isoformat()

    def iso_end(self) -> str:
        """Возвращает ISO-строку конца (date или datetime). Если end_date пустая — возвращает start."""
        d = self.end_date or self.start_date
        if self.has_time and self.end_date:
            dt = datetime.combine(d, self.end_time)
            return dt.isoformat()
        return d.isoformat()

    def get_absolute_url(self) -> str:
        """URL календаря по области события."""
        if self.department_id:
            return reverse(
                "calendar_app:department_calendar", args=[self.department_id]
            )
        return reverse("calendar_app:company_calendar")

    def save(self, *args, **kwargs) -> None:
        """Приводит маску дней недели к 0, если она не задана.

        Это нужно для фикстур/сырого .create(...), чтобы не падать на NOT NULL.
        """
        if self.weekdays_mask is None:
            self.weekdays_mask = 0
        super().save(*args, **kwargs)

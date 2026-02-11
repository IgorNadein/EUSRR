# backend/calendar_app/models.py
from __future__ import annotations

from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
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


class CalendarVisibility(models.TextChoices):
    """Видимость календаря."""
    PUBLIC = "public", _("Публичный (все видят)")
    DEPARTMENT = "department", _("Отдел (только члены отдела)")
    PRIVATE = "private", _("Приватный (только владелец)")
    CUSTOM = "custom", _("Настраиваемый (через права)")


class CalendarManager(models.Manager):
    """Менеджер для модели Calendar с дополнительными методами."""
    
    def get_available_for_user(self, user):
        """Возвращает календари, доступные для просмотра пользователю."""
        if user.is_superuser or user.is_staff:
            # Админы видят все активные календари
            return self.filter(is_active=True)
        
        # Публичные календари
        q = Q(visibility=CalendarVisibility.PUBLIC, is_active=True)
        
        # Календари, где пользователь владелец
        q |= Q(owner_user=user, is_active=True)
        
        # Календари отделов, где пользователь член
        user_departments = user.employee_departments.filter(
            is_active=True
        ).values_list("department_id", flat=True)
        
        q |= Q(
            owner_department_id__in=user_departments,
            visibility=CalendarVisibility.DEPARTMENT,
            is_active=True
        )
        
        # Календари с подпиской пользователя
        subscribed_calendar_ids = user.calendar_subscriptions.values_list(
            "calendar_id", flat=True
        )
        q |= Q(id__in=subscribed_calendar_ids, is_active=True)
        
        return self.filter(q).distinct()


class Calendar(models.Model):
    """Настраиваемый календарь (опциональный, расширенная функциональность).
    
    Если событие создано БЕЗ calendar → работает старая логика (department/employee).
    Если событие создано С calendar → игнорируются department/employee, используются настройки календаря.
    """
    
    # Основное
    title = models.CharField(_("Название"), max_length=200)
    description = models.TextField(_("Описание"), blank=True)
    color = models.CharField(_("Цвет"), max_length=7, default="#0d6efd", help_text="#RRGGBB")
    icon = models.CharField(
        _("Иконка"),
        max_length=50,
        blank=True,
        help_text=_("Bootstrap icon, например: calendar-event")
    )
    
    # Владение (опциональное)
    owner_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="owned_calendars",
        null=True,
        blank=True,
        verbose_name=_("Владелец"),
        help_text=_("Если задано — личный календарь пользователя"),
    )
    
    owner_department = models.ForeignKey(
        "employees.Department",
        on_delete=models.CASCADE,
        related_name="owned_calendars",
        null=True,
        blank=True,
        verbose_name=_("Отдел-владелец"),
        help_text=_("Если задано — календарь отдела"),
    )
    
    # Настройки видимости
    visibility = models.CharField(
        _("Видимость"),
        max_length=20,
        choices=CalendarVisibility.choices,
        default=CalendarVisibility.CUSTOM,
    )
    
    # Права по умолчанию для новых подписчиков
    default_can_edit = models.BooleanField(
        _("Могут редактировать по умолчанию"),
        default=False,
        help_text=_("Если True, все подписчики могут создавать/редактировать события"),
    )
    
    # Автоподписка
    auto_subscribe_new_users = models.BooleanField(
        _("Автоподписка для новых пользователей"),
        default=False,
        help_text=_("Автоматически подписывать новых сотрудников"),
    )
    
    auto_subscribe_department_members = models.BooleanField(
        _("Автоподписка для членов отдела"),
        default=False,
        help_text=_("Автоматически подписывать членов отдела-владельца"),
    )
    
    # Служебное
    is_active = models.BooleanField(_("Активен"), default=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calendars_created",
        verbose_name=_("Создал"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = CalendarManager()
    
    class Meta:
        verbose_name = _("Календарь")
        verbose_name_plural = _("Календари")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner_user", "is_active"]),
            models.Index(fields=["owner_department", "is_active"]),
            models.Index(fields=["visibility"]),
        ]
    
    def __str__(self):
        if self.owner_user:
            return f"{self.title} ({self.owner_user.username})"
        if self.owner_department:
            return f"{self.title} ({self.owner_department.name})"
        return f"{self.title} (Глобальный)"
    
    def clean(self):
        # Нельзя одновременно user и department
        if self.owner_user and self.owner_department:
            raise ValidationError(
                _("Календарь не может одновременно принадлежать пользователю и отделу.")
            )
    
    @property
    def is_global(self):
        """Глобальный календарь (без владельца)."""
        return not self.owner_user_id and not self.owner_department_id
    
    @property
    def is_personal(self):
        """Личный календарь пользователя."""
        return bool(self.owner_user_id)
    
    @property
    def is_department(self):
        """Календарь отдела."""
        return bool(self.owner_department_id)
    
    def is_owner(self, user):
        """Проверяет, является ли пользователь владельцем календаря."""
        if self.owner_user_id:
            return self.owner_user_id == user.id
        if self.owner_department_id:
            # Владелец отдела = руководитель отдела
            return self.owner_department.head_id == user.id if hasattr(self.owner_department, 'head_id') else False
        # Глобальный календарь — владелец только админы
        return user.is_superuser or user.is_staff
    
    def can_user_view(self, user):
        """Проверяет, может ли пользователь просматривать календарь."""
        if not self.is_active:
            return False
        
        if user.is_superuser or user.is_staff:
            return True
        
        # Владелец всегда может просматривать
        if self.is_owner(user):
            return True
        
        # Публичный календарь
        if self.visibility == CalendarVisibility.PUBLIC:
            return True
        
        # Календарь отдела
        if self.visibility == CalendarVisibility.DEPARTMENT and self.owner_department_id:
            # Проверяем, является ли пользователь членом отдела
            return user.employee_departments.filter(
                department_id=self.owner_department_id,
                is_active=True
            ).exists()
        
        # Приватный или настраиваемый — проверяем подписку
        if self.visibility in [CalendarVisibility.PRIVATE, CalendarVisibility.CUSTOM]:
            return self.subscriptions.filter(user=user).exists()
        
        return False
    
    def can_user_edit(self, user):
        """Проверяет, может ли пользователь редактировать события в календаре."""
        if user.is_superuser or user.is_staff:
            return True
        
        # Владелец всегда может редактировать
        if self.is_owner(user):
            return True
        
        # Проверяем подписку с правом редактирования
        subscription = self.subscriptions.filter(user=user).first()
        if subscription:
            return subscription.can_edit
        
        return False
    
    def can_user_manage(self, user):
        """Проверяет, может ли пользователь управлять календарем."""
        if user.is_superuser or user.is_staff:
            return True
        
        # Владелец всегда может управлять
        if self.is_owner(user):
            return True
        
        # Проверяем подписку с правом управления
        subscription = self.subscriptions.filter(user=user).first()
        if subscription:
            return subscription.can_manage
        
        return False


class CalendarSubscription(models.Model):
    """Подписка пользователя на календарь с настройками отображения."""
    
    calendar = models.ForeignKey(
        Calendar,
        on_delete=models.CASCADE,
        related_name="subscriptions",
        verbose_name=_("Календарь"),
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="calendar_subscriptions",
        verbose_name=_("Пользователь"),
    )
    
    # Настройки отображения
    is_visible = models.BooleanField(_("Отображать"), default=True)
    color_override = models.CharField(
        _("Свой цвет"),
        max_length=7,
        blank=True,
        help_text=_("Переопределяет цвет календаря"),
    )
    
    # Права подписчика
    can_edit = models.BooleanField(
        _("Может редактировать"),
        default=False,
        help_text=_("Может создавать/редактировать события в этом календаре"),
    )
    
    can_manage = models.BooleanField(
        _("Может управлять"),
        default=False,
        help_text=_("Может управлять правами других пользователей"),
    )
    
    # Уведомления
    notify_on_new_event = models.BooleanField(_("Уведомлять о новых событиях"), default=True)
    notify_on_event_change = models.BooleanField(_("Уведомлять об изменениях"), default=True)
    
    subscribed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _("Подписка на календарь")
        verbose_name_plural = _("Подписки на календари")
        unique_together = [["calendar", "user"]]
        indexes = [
            models.Index(fields=["user", "is_visible"]),
            models.Index(fields=["calendar", "can_edit"]),
        ]
    
    def __str__(self):
        return f"{self.user.username} → {self.calendar.title}"


class CalendarEvent(models.Model):
    """Событие календаря с поддержкой повторяемости.
    
    ОБРАТНАЯ СОВМЕСТИМОСТЬ:
    - Если calendar = NULL → используется старая логика (department/employee)
    - Если calendar задан → игнорируются department/employee
    
    LEGACY (старая логика):
    - department = NULL и employee = NULL → событие компании (глобальное)
    - department задан и employee = NULL → событие отдела
    - employee задан и department = NULL → личное событие сотрудника
    """

    # ✨ НОВОЕ: Опциональная привязка к настраиваемому календарю
    calendar = models.ForeignKey(
        Calendar,
        on_delete=models.CASCADE,
        related_name="events",
        null=True,
        blank=True,
        verbose_name=_("Календарь"),
        help_text=_(
            "Если не задан — используется стандартная логика "
            "(department/employee)"
        ),
    )
    
    # ✅ LEGACY: Старые поля для обратной совместимости
    department = models.ForeignKey(
        "employees.Department",
        on_delete=models.CASCADE,
        related_name="calendar_events",
        verbose_name=_("Отдел"),
        null=True,
        blank=True,
        help_text=_("LEGACY: используется если calendar=NULL"),
    )
    
    employee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="personal_calendar_events",
        verbose_name=_("Сотрудник"),
        null=True,
        blank=True,
        help_text=_("LEGACY: используется если calendar=NULL"),
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
        ordering = ["start_date", "start_time"]
        indexes = [
            # Новые индексы для calendar
            models.Index(fields=["calendar", "start_date"]),
            models.Index(fields=["calendar", "recurrence", "start_date"]),
            # Legacy индексы для обратной совместимости
            models.Index(fields=["department", "start_date"]),
            models.Index(fields=["department", "recurrence", "start_date"]),
            models.Index(fields=["employee", "start_date"]),
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

    def __str__(self) -> str:
        # НОВОЕ: Приоритет calendar
        if self.calendar_id:
            return (
                f"[{self.calendar.title}] {self.title} "
                f"({self.start_date:%d.%m.%Y})"
            )
        
        # LEGACY: Старая логика
        if self.employee_id:
            scope = f"Личный ({self.employee})"
        elif self.department_id:
            scope = str(self.department)
        else:
            scope = _("Компания")
        
        if self.end_date:
            return (
                f"{scope}: {self.title} "
                f"({self.start_date:%d.%m.%Y}–{self.end_date:%d.%m.%Y})"
            )
        return f"{scope}: {self.title} ({self.start_date:%d.%m.%Y})"

    @property
    def is_legacy_event(self) -> bool:
        """True если событие использует старую логику (без calendar)."""
        return self.calendar_id is None
    
    @property
    def is_modern_event(self) -> bool:
        """True если событие использует новую логику (с calendar)."""
        return self.calendar_id is not None

    @property
    def is_company(self) -> bool:
        """True если событие глобальное (LEGACY: без отдела и сотрудника)."""
        return (
            self.calendar_id is None and
            self.department_id is None and
            self.employee_id is None
        )
    
    @property
    def is_personal(self) -> bool:
        """True если событие личное (LEGACY или calendar.is_personal)."""
        if self.calendar_id:
            return self.calendar.is_personal
        return self.employee_id is not None

    @property
    def has_time(self) -> bool:
        """True если задано точное время (оба поля времени)."""
        return self.start_time is not None and self.end_time is not None

    # ---------- Валидация ----------
    def clean(self) -> None:
        """Валидирует согласованность дат/времени и повторяемости.

        Raises:
            ValidationError: При некорректных датах/времени или настройках.
        """
        # НОВОЕ: Если указан calendar, department и employee должны быть пусты
        if self.calendar_id:
            if self.department_id or self.employee_id:
                raise ValidationError(
                    _(
                        "При использовании календаря нельзя указывать "
                        "department или employee."
                    )
                )
        
        # LEGACY: Проверка взаимоисключающих полей (только если calendar=NULL)
        if not self.calendar_id:
            if self.department_id and self.employee_id:
                raise ValidationError(
                    _(
                        "Событие не может одновременно принадлежать "
                        "отделу и сотруднику."
                    )
                )
        
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

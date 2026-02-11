# backend/calendar_app/admin.py
from __future__ import annotations

from typing import Iterable

from django.contrib import admin, messages
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .admin_calendar import CalendarAdmin  # noqa: F401
from .admin_subscription import (  # noqa: F401
    CalendarSubscriptionAdmin,
    CalendarSubscriptionInline,
)
from .models import Calendar, CalendarEvent, CalendarSubscription, Recurrence


class ScopeListFilter(admin.SimpleListFilter):
    """Фильтр области события: компания или отдел.

    Values:
        - 'company' → department IS NULL
        - 'dept'    → department IS NOT NULL
    """
    title = _("Область")
    parameter_name = "scope"

    def lookups(self, request: HttpRequest, model_admin: admin.ModelAdmin) -> Iterable[tuple[str, str]]:
        """Возвращает варианты выбора фильтра.

        Args:
            request: Текущий запрос.
            model_admin: Админ-класс.

        Returns:
            Iterable[tuple[str, str]]: (value, label)
        """
        return (
            ("company", _("Компания")),
            ("dept", _("Отдел")),
        )

    def queryset(self, request: HttpRequest, queryset):
        """Применяет фильтр к queryset.

        Args:
            request: Текущий запрос.
            queryset: Исходный queryset.

        Returns:
            QuerySet: Отфильтрованный queryset.
        """
        val = self.value()
        if val == "company":
            return queryset.filter(department__isnull=True)
        if val == "dept":
            return queryset.filter(department__isnull=False)
        return queryset


class HasTimeListFilter(admin.SimpleListFilter):
    """Фильтр наличия времени у события (есть оба time или нет ни одного)."""
    title = _("Есть время")
    parameter_name = "has_time"

    def lookups(self, request: HttpRequest, model_admin: admin.ModelAdmin) -> Iterable[tuple[str, str]]:
        """Опции фильтра (Да/Нет)."""
        return (
            ("yes", _("Да")),
            ("no", _("Нет")),
        )

    def queryset(self, request: HttpRequest, queryset):
        """Применяет фильтр к queryset."""
        val = self.value()
        if val == "yes":
            return queryset.filter(start_time__isnull=False, end_time__isnull=False)
        if val == "no":
            return queryset.filter(start_time__isnull=True, end_time__isnull=True)
        return queryset


@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    """Админка для модели CalendarEvent (события календаря компании и отделов)."""

    # ===== Список =====
    list_display = (
        "id",
        "title",
        "calendar_display",
        "scope_display",
        "start_date",
        "end_date",
        "start_time",
        "end_time",
        "all_day",
        "recurrence",
        "color_swatch",
        "created_by",
        "created_at",
    )
    list_select_related = ("calendar", "department", "employee", "created_by")
    list_per_page = 50
    ordering = ("start_date", "start_time")

    # ===== Поиск/Фильтры/Иерархия =====
    search_fields = (
        "title",
        "description",
        "location",
        "calendar__title",
        "department__name",
        "department__title",
        "department__code",
        "employee__username",
        "employee__first_name",
        "employee__last_name",
    )
    list_filter = (
        "calendar",
        "department",
        "recurrence",
        "all_day",
        ("start_date", admin.DateFieldListFilter),
        ("created_at", admin.DateFieldListFilter),
        HasTimeListFilter,
        ScopeListFilter,
    )
    date_hierarchy = "start_date"

    # ===== Поля формы =====
    readonly_fields = ("created_at",)
    raw_id_fields = ("calendar", "department", "employee", "created_by")
    fieldsets = (
        (_("Календарь"), {
            "fields": ("calendar",),
            "description": _(
                "Если указан календарь, поля department и employee "
                "игнорируются (новый режим)"
            ),
        }),
        (_("Основное (LEGACY)"), {
            "fields": ("title", "description", "department", "employee", "location"),
            "description": _("Department/Employee используются только если calendar=NULL"),
        }),
        (_("Даты и время"), {
            "fields": (
                ("start_date", "end_date"),
                ("start_time", "end_time"),
                "all_day",
            ),
        }),
        (_("Отображение"), {
            "fields": ("recurrence", "color"),
        }),
        (_("Служебное"), {
            "fields": ("created_by", "created_at"),
        }),
    )

    # ===== Экшены =====
    actions = ("make_all_day", "clear_time", "set_annual", "set_one_time")

    @admin.display(description=_("Календарь"), ordering="calendar__title")
    def calendar_display(self, obj: CalendarEvent) -> str:
        """Возвращает название календаря или '—'."""
        if obj.calendar:
            return str(obj.calendar)
        return "—"

    @admin.display(description=_("Область (LEGACY)"), ordering="department_id")
    def scope_display(self, obj: CalendarEvent) -> str:
        """Возвращает область для legacy событий.

        Args:
            obj: Объект CalendarEvent.

        Returns:
            str: Человекочитаемое имя области.
        """
        if obj.calendar_id:
            return _("→ используется Calendar")
        if obj.employee_id:
            return f"Личный ({obj.employee})"
        if obj.department_id:
            return str(obj.department)
        return _("Компания")

    @admin.display(description=_("Цвет"))
    def color_swatch(self, obj: CalendarEvent) -> str:
        """Отрисовывает mini-swatch цвета + hex-код.

        Args:
            obj: Объект CalendarEvent.

        Returns:
            str: HTML.
        """
        if not obj.color:
            return "—"
        return format_html(
            '<span style="display:inline-block;width:12px;height:12px;'
            'border-radius:2px;border:1px solid #ccc;vertical-align:-2px;'
            'background:{};margin-right:6px;"></span><code>{}</code>',
            obj.color, obj.color
        )

    # ===== Экшены логика =====
    @admin.action(description=_("Сделать целодневными (очистить время)"))
    def make_all_day(self, request: HttpRequest, queryset: QuerySet[CalendarEvent]) -> None:
        """Делает выбранные события целодневными.

        Args:
            request: Запрос администратора.
            queryset: Выбранные события.
        """
        updated = queryset.update(start_time=None, end_time=None, all_day=True)
        self.message_user(request, _(f"Обновлено событий: {updated}"), level=messages.SUCCESS)

    @admin.action(description=_("Очистить время (оставить даты как есть)"))
    def clear_time(self, request: HttpRequest, queryset: QuerySet[CalendarEvent]) -> None:
        """Очищает время начала/окончания у выбранных событий.

        Args:
            request: Запрос администратора.
            queryset: Выбранные события.
        """
        updated = queryset.update(start_time=None, end_time=None)
        self.message_user(request, _(f"Очищено время у событий: {updated}"), level=messages.SUCCESS)

    @admin.action(description=_("Пометить как ежегодные"))
    def set_annual(self, request: HttpRequest, queryset: QuerySet[CalendarEvent]) -> None:
        """Ставит повторяемость 'Ежегодно' у выбранных событий."""
        updated = queryset.update(recurrence=Recurrence.ANNUAL)
        self.message_user(request, _(f"Обновлено: {updated}"), level=messages.SUCCESS)

    @admin.action(description=_("Пометить как одноразовые"))
    def set_one_time(self, request: HttpRequest, queryset: QuerySet[CalendarEvent]) -> None:
        """Ставит повторяемость 'Одноразовое' у выбранных событий."""
        updated = queryset.update(recurrence=Recurrence.ONE_TIME)
        self.message_user(request, _(f"Обновлено: {updated}"), level=messages.SUCCESS)

    # ===== Сохранение =====
    def save_model(self, request: HttpRequest, obj: CalendarEvent, form, change: bool) -> None:
        """Проставляет автора при первом сохранении.

        Args:
            request: Текущий запрос.
            obj: Объект события.
            form: Форма админки.
            change: True, если редактирование; False, если создание.
        """
        if not change and obj.created_by_id is None:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# Добавляем инлайн подписок в админку календаря после импорта
CalendarAdmin.inlines = [CalendarSubscriptionInline]


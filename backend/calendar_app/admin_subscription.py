"""Админка для модели CalendarSubscription."""

from django.contrib import admin
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from .models import CalendarSubscription


@admin.register(CalendarSubscription)
class CalendarSubscriptionAdmin(admin.ModelAdmin):
    """Админка для управления подписками на календари."""

    # ===== Список =====
    list_display = (
        "id",
        "user_display",
        "calendar_display",
        "is_visible",
        "can_edit",
        "can_manage",
        "color_display",
        "notify_on_new_event",
        "notify_on_event_change",
        "subscribed_at",
    )
    list_select_related = ("user", "calendar")
    list_per_page = 50
    ordering = ("-subscribed_at",)

    # ===== Поиск/Фильтры =====
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "calendar__title",
    )
    list_filter = (
        "is_visible",
        "can_edit",
        "can_manage",
        "notify_on_new_event",
        "notify_on_event_change",
        ("subscribed_at", admin.DateFieldListFilter),
    )
    date_hierarchy = "subscribed_at"

    # ===== Поля формы =====
    readonly_fields = ("subscribed_at",)
    raw_id_fields = ("user", "calendar")
    fieldsets = (
        (
            _("Подписка"),
            {
                "fields": ("user", "calendar"),
            },
        ),
        (
            _("Отображение"),
            {
                "fields": ("is_visible", "color_override"),
            },
        ),
        (
            _("Права доступа"),
            {
                "fields": ("can_edit", "can_manage"),
                "description": _(
                    "can_edit - может создавать/редактировать события; "
                    "can_manage - может управлять календарем и правами"
                ),
            },
        ),
        (
            _("Уведомления"),
            {
                "fields": (
                    "notifications_enabled",
                    "notify_on_new_event",
                    "notify_on_event_change",
                    "notify_on_event_delete",
                ),
            },
        ),
        (
            _("Служебное"),
            {
                "fields": ("subscribed_at",),
            },
        ),
    )

    @admin.display(description=_("Пользователь"), ordering="user__username")
    def user_display(self, obj: CalendarSubscription) -> str:
        """Возвращает имя пользователя."""
        return str(obj.user)

    @admin.display(description=_("Календарь"), ordering="calendar__title")
    def calendar_display(self, obj: CalendarSubscription) -> str:
        """Возвращает название календаря."""
        return str(obj.calendar)

    @admin.display(description=_("Цвет"))
    def color_display(self, obj: CalendarSubscription) -> str:
        """Возвращает цвет с учетом переопределения."""
        color = obj.color_override or obj.calendar.color
        return (
            f'<div style="width:20px;height:20px;background-color:{color};'
            f'border:1px solid #ccc;display:inline-block;"></div> {color}'
        )

    color_display.allow_tags = True  # type: ignore[attr-defined]

    def save_model(
        self,
        request: HttpRequest,
        obj: CalendarSubscription,
        form,
        change: bool,
    ) -> None:
        """Валидация перед сохранением.

        Args:
            request: Текущий запрос.
            obj: Объект подписки.
            form: Форма админки.
            change: True, если редактирование.
        """
        # Проверка: can_manage требует can_edit
        if obj.can_manage and not obj.can_edit:
            from django.core.exceptions import ValidationError

            raise ValidationError(_("can_manage требует can_edit=True"))

        super().save_model(request, obj, form, change)


class CalendarSubscriptionInline(admin.TabularInline):
    """Инлайн для отображения подписок в календаре."""

    model = CalendarSubscription
    extra = 0
    raw_id_fields = ("user",)
    fields = (
        "user",
        "is_visible",
        "can_edit",
        "can_manage",
        "color_override",
        "subscribed_at",
    )
    readonly_fields = ("subscribed_at",)

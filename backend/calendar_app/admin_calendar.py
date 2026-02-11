"""Админка для модели Calendar."""

from django.contrib import admin
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from .models import Calendar


@admin.register(Calendar)
class CalendarAdmin(admin.ModelAdmin):
    """Админка для управления календарями."""

    # ===== Инлайны =====
    inlines = []  # Будет заполнено после импорта CalendarSubscriptionInline

    # ===== Список =====
    list_display = (
        "id",
        "title",
        "visibility_display",
        "owner_display",
        "color_swatch",
        "is_active",
        "event_count",
        "subscriber_count",
        "created_at",
    )
    list_select_related = ("owner_user", "owner_department")
    list_per_page = 50
    ordering = ("-created_at",)

    # ===== Поиск/Фильтры =====
    search_fields = (
        "title",
        "description",
        "owner_user__username",
        "owner_user__first_name",
        "owner_user__last_name",
        "owner_department__name",
        "owner_department__title",
    )
    list_filter = (
        "visibility",
        "is_active",
        "auto_subscribe_new_users",
        "auto_subscribe_department_members",
        ("created_at", admin.DateFieldListFilter),
    )
    date_hierarchy = "created_at"

    # ===== Поля формы =====
    readonly_fields = ("created_at", "updated_at", "event_count", "subscriber_count")
    raw_id_fields = ("owner_user", "owner_department", "created_by")
    fieldsets = (
        (_("Основное"), {
            "fields": ("title", "description", "icon"),
        }),
        (_("Владелец"), {
            "fields": ("owner_user", "owner_department"),
            "description": _("Указывается либо пользователь, либо отдел"),
        }),
        (_("Видимость"), {
            "fields": ("visibility",),
        }),
        (_("Отображение"), {
            "fields": ("color", "sort_order"),
        }),
        (_("Автоподписка"), {
            "fields": (
                "auto_subscribe_new_users",
                "auto_subscribe_department_members",
            ),
        }),
        (_("Статус"), {
            "fields": ("is_active",),
        }),
        (_("Статистика"), {
            "fields": ("event_count", "subscriber_count", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description=_("Видимость"), ordering="visibility")
    def visibility_display(self, obj: Calendar) -> str:
        """Возвращает человекочитаемое название видимости."""
        return obj.get_visibility_display()

    @admin.display(description=_("Владелец"))
    def owner_display(self, obj: Calendar) -> str:
        """Возвращает владельца календаря."""
        if obj.owner_user_id:
            return f"👤 {obj.owner_user}"
        if obj.owner_department_id:
            return f"🏢 {obj.owner_department}"
        return _("🌐 Система")

    @admin.display(description=_("Цвет"))
    def color_swatch(self, obj: Calendar) -> str:
        """Возвращает HTML со свотчем цвета."""
        return (
            f'<div style="width:20px;height:20px;background-color:{obj.color};'
            f'border:1px solid #ccc;display:inline-block;"></div> {obj.color}'
        )

    color_swatch.allow_tags = True  # type: ignore[attr-defined]

    @admin.display(description=_("События"))
    def event_count(self, obj: Calendar) -> int:
        """Возвращает количество событий в календаре."""
        return obj.events.count()

    @admin.display(description=_("Подписчики"))
    def subscriber_count(self, obj: Calendar) -> int:
        """Возвращает количество подписчиков календаря."""
        return obj.subscriptions.count()

    def save_model(
        self, request: HttpRequest, obj: Calendar, form, change: bool
    ) -> None:
        """Валидация перед сохранением.

        Args:
            request: Текущий запрос.
            obj: Объект календаря.
            form: Форма админки.
            change: True, если редактирование.
        """
        # Проставляем created_by при создании
        if not change and obj.created_by_id is None:
            obj.created_by = request.user
        
        super().save_model(request, obj, form, change)


# backend/requests_app/admin.py
from django import forms
from django.contrib import admin, messages
from django.db import models
from django.utils.translation import gettext_lazy as _

from .enums import RequestStatus
from .models import Request


# Админ-форма: без принуждения вводить approver (мы выставим его автоматически)
class RequestAdminForm(forms.ModelForm):
    class Meta:
        model = Request
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get("status")
        approver = cleaned.get("approver")

        # Если статус "Отменено" — согласующий должен быть пустым
        if status == RequestStatus.CANCELLED and approver:
            cleaned["approver"] = None

        # Для approved/rejected НЕ требуем approver — его поставим в save_model.
        return cleaned


@admin.register(Request)
class RequestAdmin(admin.ModelAdmin):
    form = RequestAdminForm

    list_display = (
        "id",
        "display_title",
        "type",
        "status",
        "employee",
        "department",
        "date_from",
        "date_to",
        "decided_at",
        "created_at",
    )
    list_filter = (
        "type",
        "status",
        "department",
        ("created_at", admin.DateFieldListFilter),
        ("decided_at", admin.DateFieldListFilter),
    )
    search_fields = (
        "title",
        "comment",
        "employee__last_name",
        "employee__first_name",
        "employee__email",
    )
    autocomplete_fields = ("employee", "department")
    # approver только для просмотра (покажем, кто согласовал)
    readonly_fields = ("approver", "created_at", "updated_at", "decided_at")

    fieldsets = (
        (
            _("Основное"),
            {
                "fields": (
                    "employee",
                    "department",
                    "type",
                    "title",
                    ("date_from", "date_to"),
                    "comment",
                    "attachment",
                )
            },
        ),
        (
            _("Статус"),
            {
                "fields": (
                    "status",
                    # показываем, но не редактируем
                    "approver",
                    "decided_at",
                )
            },
        ),
        (
            _("Служебное"),
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at"),
            },
        ),
    )

    # HTML5-пикеры дат/времени в админке
    formfield_overrides = {
        models.DateField: {"widget": forms.DateInput(attrs={"type": "date"})},
        models.DateTimeField: {
            "widget": forms.DateTimeInput(attrs={"type": "datetime-local"})
        },
    }

    def save_model(self, request, obj: Request, form, change):
        """
        Приводим пару статус/согласующий к валидному виду ДО сохранения:
        - approved/rejected -> approver = текущий пользователь, если не задан
        - cancelled -> approver = None
        Это гарантирует отсутствие конфликтов с БД-constraint.
        """
        if obj.status in {RequestStatus.APPROVED, RequestStatus.REJECTED}:
            if obj.approver_id is None:
                obj.approver = request.user
        elif obj.status == RequestStatus.CANCELLED:
            if obj.approver_id is not None:
                obj.approver = None

        super().save_model(request, obj, form, change)

    # Массовые действия работают через методы модели (ставят approver и
    # decided_at)
    @admin.action(description=_("Одобрить выбранные"))
    def action_approve(self, request, queryset):
        updated = 0
        for obj in queryset:
            if obj.status != RequestStatus.APPROVED:
                obj.approve(request.user)
                updated += 1
        self.message_user(
            request, _(f"Одобрено заявок: {updated}"), level=messages.SUCCESS
        )

    @admin.action(description=_("Отклонить выбранные"))
    def action_reject(self, request, queryset):
        updated = 0
        for obj in queryset:
            if obj.status != RequestStatus.REJECTED:
                obj.reject(request.user)
                updated += 1
        self.message_user(
            request, _(f"Отклонено заявок: {updated}"), level=messages.SUCCESS
        )

    @admin.action(description=_("Отменить выбранные"))
    def action_cancel(self, request, queryset):
        updated = 0
        for obj in queryset:
            if obj.status != RequestStatus.CANCELLED:
                obj.cancel()
                updated += 1
        self.message_user(
            request, _(f"Отменено заявок: {updated}"), level=messages.SUCCESS
        )

    actions = ("action_approve", "action_reject", "action_cancel")

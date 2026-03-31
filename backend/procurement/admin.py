from decimal import Decimal

from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Approval,
    ApprovalRoute,
    Budget,
    Equipment,
    EquipmentCategory,
    MaintenanceRecord,
    ProcurementItem,
    ProcurementRequest,
    Supplier,
)


class ProcurementItemInline(admin.TabularInline):
    """Инлайн для позиций заявки."""

    model = ProcurementItem
    extra = 1
    fields = [
        "name",
        "quantity",
        "unit",
        "estimated_unit_price",
        "supplier_info",
    ]


class ApprovalInline(admin.TabularInline):
    """Инлайн для согласований."""

    model = Approval
    extra = 0
    fields = ["approver", "role", "status", "comment", "created_at"]
    readonly_fields = ["created_at"]
    can_delete = False


@admin.register(ProcurementRequest)
class ProcurementRequestAdmin(admin.ModelAdmin):
    """Админка для заявок на закупку."""

    list_display = [
        "id",
        "title",
        "department",
        "requestor",
        "status_badge",
        "urgency_badge",
        "get_total_cost",
        "created_at",
    ]
    list_filter = ["status", "urgency", "department", "created_at"]
    search_fields = ["title", "description", "requestor__username"]
    readonly_fields = [
        "created_at",
        "updated_at",
        "submitted_at",
        "completed_at",
        "get_total_cost",
    ]
    date_hierarchy = "created_at"
    inlines = [ProcurementItemInline, ApprovalInline]

    fieldsets = (
        (
            "Основная информация",
            {"fields": ("title", "description", "department", "requestor")},
        ),
        (
            "Параметры",
            {
                "fields": (
                    "status",
                    "urgency",
                    "get_total_cost",
                    "actual_cost",
                )
            },
        ),
        (
            "Временные метки",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                    "submitted_at",
                    "completed_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def status_badge(self, obj):
        """Цветной бадж статуса."""
        colors = {
            "draft": "#6c757d",
            "pending": "#0dcaf0",
            "approved": "#198754",
            "rejected": "#dc3545",
            "in_progress": "#0d6efd",
            "completed": "#198754",
            "cancelled": "#6c757d",
        }
        color = colors.get(obj.status, "#6c757d")
        return format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Статус"

    def urgency_badge(self, obj):
        """Цветной бадж срочности."""
        colors = {
            "low": "#198754",
            "medium": "#ffc107",
            "high": "#fd7e14",
            "critical": "#dc3545",
        }
        color = colors.get(obj.urgency, "#6c757d")
        return format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_urgency_display(),
        )

    urgency_badge.short_description = "Срочность"

    def get_total_cost(self, obj):
        """Сумма заявки из позиций."""
        return f"{obj.total_cost:,.2f} ₽"

    get_total_cost.short_description = "Сумма"


@admin.register(ProcurementItem)
class ProcurementItemAdmin(admin.ModelAdmin):
    """Админка для позиций заявок."""

    list_display = [
        "id",
        "request",
        "name",
        "quantity",
        "unit",
        "estimated_unit_price",
        "total_price",
    ]
    list_filter = ["unit", "created_at"]
    search_fields = ["name", "description", "request__title"]
    readonly_fields = ["created_at", "total_price"]


@admin.register(ApprovalRoute)
class ApprovalRouteAdmin(admin.ModelAdmin):
    """Маршруты согласования закупок."""

    list_display = ["priority", "min_amount", "name", "resolver_type", "employee"]
    ordering = ["priority"]
    autocomplete_fields = ["employee"]


@admin.register(Approval)
class ApprovalAdmin(admin.ModelAdmin):
    """Админка для согласований."""

    list_display = [
        "id",
        "request",
        "approver",
        "priority",
        "step_name",
        "status_badge",
        "created_at",
    ]
    list_filter = ["status", "priority", "created_at"]
    search_fields = [
        "request__title",
        "approver__username",
        "approver__email",
    ]
    readonly_fields = ["created_at", "updated_at"]

    def status_badge(self, obj):
        """Цветной бадж статуса."""
        colors = {
            "pending": "#ffc107",
            "approved": "#198754",
            "rejected": "#dc3545",
        }
        color = colors.get(obj.status, "#6c757d")
        return format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Статус"


@admin.register(EquipmentCategory)
class EquipmentCategoryAdmin(admin.ModelAdmin):
    """Админка для категорий оборудования."""

    list_display = ["id", "name", "parent", "icon", "created_at"]
    list_filter = ["parent"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at", "full_path"]


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    """Админка для оборудования."""

    list_display = [
        "inventory_number",
        "name",
        "category",
        "status_badge",
        "department",
        "responsible_person",
        "warranty_status",
    ]
    list_filter = ["status", "category", "department", "purchase_date"]
    search_fields = [
        "name",
        "inventory_number",
        "serial_number",
        "responsible_person__username",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
        "is_under_warranty",
    ]
    date_hierarchy = "purchase_date"

    fieldsets = (
        (
            "Основная информация",
            {
                "fields": (
                    "name",
                    "inventory_number",
                    "serial_number",
                    "category",
                )
            },
        ),
        (
            "Статус и расположение",
            {
                "fields": (
                    "status",
                    "department",
                    "responsible_person",
                    "location",
                )
            },
        ),
        (
            "Финансовая информация",
            {
                "fields": (
                    "purchase_date",
                    "warranty_until",
                    "purchase_cost",
                    "is_under_warranty",
                )
            },
        ),
        (
            "Дополнительно",
            {
                "fields": ("notes", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def status_badge(self, obj):
        """Цветной бадж статуса."""
        colors = {
            "available": "#198754",
            "in_use": "#0d6efd",
            "maintenance": "#ffc107",
            "repair": "#fd7e14",
            "retired": "#6c757d",
            "lost": "#dc3545",
        }
        color = colors.get(obj.status, "#6c757d")
        return format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Статус"

    def warranty_status(self, obj):
        """Статус гарантии."""
        if obj.is_under_warranty:
            return format_html(
                '<span style="color: #198754;">✓ На гарантии</span>'
            )
        return format_html(
            '<span style="color: #6c757d;">— Гарантия истекла</span>'
        )

    warranty_status.short_description = "Гарантия"


@admin.register(MaintenanceRecord)
class MaintenanceRecordAdmin(admin.ModelAdmin):
    """Админка для записей обслуживания."""

    list_display = [
        "id",
        "equipment",
        "date",
        "type",
        "cost",
        "performed_by",
        "next_maintenance_date",
    ]
    list_filter = ["type", "date", "performed_by"]
    search_fields = [
        "equipment__name",
        "equipment__inventory_number",
        "description",
    ]
    readonly_fields = ["created_at"]
    date_hierarchy = "date"


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    """Админка для бюджетов."""

    list_display = [
        "id",
        "department",
        "year",
        "quarter",
        "allocated_amount",
        "spent_amount",
        "get_remaining_amount",
        "utilization_badge",
    ]
    list_filter = ["year", "quarter", "department"]
    search_fields = ["department__name"]
    readonly_fields = [
        "created_at",
        "updated_at",
        "get_remaining_amount",
        "get_utilization_percentage",
    ]
    actions = ["create_next_quarter_budgets", "copy_selected_budgets"]

    def create_next_quarter_budgets(self, request, queryset):
        """Создать бюджеты на следующий квартал для всех отделов."""
        from django.utils import timezone
        from employees.models import Department

        now = timezone.now()
        current_quarter = (now.month - 1) // 3 + 1

        # Определяем следующий квартал
        if current_quarter == 4:
            next_quarter = 1
            next_year = now.year + 1
        else:
            next_quarter = current_quarter + 1
            next_year = now.year

        # Получаем все активные отделы
        departments = Department.objects.all()
        created_count = 0
        skipped_count = 0

        for dept in departments:
            # Проверяем существует ли уже бюджет
            exists = Budget.objects.filter(
                department=dept,
                year=next_year,
                quarter=next_quarter
            ).exists()

            if exists:
                skipped_count += 1
                continue

            # Пытаемся скопировать бюджет из текущего квартала
            try:
                current_budget = Budget.objects.get(
                    department=dept,
                    year=now.year,
                    quarter=current_quarter
                )
                allocated = current_budget.allocated_amount
            except Budget.DoesNotExist:
                # Если нет текущего бюджета - ставим 0
                allocated = Decimal('0.00')

            Budget.objects.create(
                department=dept,
                year=next_year,
                quarter=next_quarter,
                allocated_amount=allocated,
                spent_amount=Decimal('0.00')
            )
            created_count += 1

        self.message_user(
            request,
            f"Создано {created_count} бюджетов на "
            f"{next_year} Q{next_quarter}. "
            f"Пропущено (уже существуют): {skipped_count}."
        )

    create_next_quarter_budgets.short_description = (
        "🔄 Создать бюджеты на следующий квартал для всех отделов"
    )

    def copy_selected_budgets(self, request, queryset):
        """Копировать выбранные бюджеты в следующий квартал."""
        from django.utils import timezone

        now = timezone.now()
        current_quarter = (now.month - 1) // 3 + 1

        # Определяем следующий квартал
        if current_quarter == 4:
            next_quarter = 1
            next_year = now.year + 1
        else:
            next_quarter = current_quarter + 1
            next_year = now.year

        created_count = 0
        skipped_count = 0

        for budget in queryset:
            # Проверяем существует ли уже бюджет
            exists = Budget.objects.filter(
                department=budget.department,
                year=next_year,
                quarter=next_quarter
            ).exists()

            if exists:
                skipped_count += 1
                continue

            Budget.objects.create(
                department=budget.department,
                year=next_year,
                quarter=next_quarter,
                allocated_amount=budget.allocated_amount,
                spent_amount=Decimal('0.00')
            )
            created_count += 1

        self.message_user(
            request,
            f"Скопировано {created_count} бюджетов в "
            f"{next_year} Q{next_quarter}. "
            f"Пропущено (уже существуют): {skipped_count}."
        )

    copy_selected_budgets.short_description = (
        "📋 Скопировать выбранные бюджеты в следующий квартал"
    )

    def get_remaining_amount(self, obj):
        """Остаток бюджета (для отображения в админке)."""
        return obj.remaining_amount
    get_remaining_amount.short_description = "Остаток"

    def get_utilization_percentage(self, obj):
        """Процент использования (для отображения в админке)."""
        return f"{obj.utilization_percentage}%"
    get_utilization_percentage.short_description = "Использовано"

    def utilization_badge(self, obj):
        """Цветной бадж использования бюджета."""
        percentage = obj.utilization_percentage
        if percentage < 50:
            color = "#198754"
        elif percentage < 75:
            color = "#ffc107"
        elif percentage < 90:
            color = "#fd7e14"
        else:
            color = "#dc3545"

        percentage_str = f"{float(percentage):.1f}"
        return format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 3px 10px; border-radius: 3px;">{}%</span>',
            color,
            percentage_str,
        )

    utilization_badge.short_description = "Использовано"


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    """Админка для поставщиков."""

    list_display = [
        "id",
        "name",
        "contact_person",
        "phone",
        "email",
        "rating",
        "is_active",
    ]
    list_filter = ["is_active", "rating"]
    search_fields = ["name", "contact_person", "email", "inn"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("Основная информация", {"fields": ("name", "is_active", "rating")}),
        (
            "Контактная информация",
            {
                "fields": (
                    "contact_person",
                    "phone",
                    "email",
                    "website",
                    "address",
                )
            },
        ),
        ("Юридическая информация", {"fields": ("inn",)}),
        (
            "Дополнительно",
            {
                "fields": ("notes", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

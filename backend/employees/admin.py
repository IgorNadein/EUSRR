# backend/employees/admin.py
from django.contrib import admin
from django.db.models import Count, OuterRef, Subquery
from .models import (
    Employee,
    EmployeeAction,
    Department,
    EmployeeDepartment,
    EmployeePosition,
    Absence,
    Skill,
    Education,
)
from .constants import ACTION_DISMISSED


# =========================
#  Инлайны
# =========================
class EmployeeDepartmentInline(admin.TabularInline):
    """Принадлежности сотрудника к отделам (в карточке сотрудника)"""

    model = EmployeeDepartment
    fk_name = "employee"
    extra = 0
    autocomplete_fields = ("department",)
    fields = ("department", "role", "is_active", "date_from", "date_to")
    show_change_link = True


class EmployeeActionInline(admin.TabularInline):
    model = EmployeeAction
    extra = 0
    fields = ("action", "date", "comment")
    readonly_fields = ()
    ordering = ("-date",)


class EmployeePositionInline(admin.TabularInline):
    model = EmployeePosition
    fk_name = "employee"
    extra = 0
    autocomplete_fields = ("department",)
    fields = ("department", "title", "date_from", "date_to")


class AbsenceInline(admin.TabularInline):
    model = Absence
    fk_name = "employee"
    extra = 0
    fields = ("type", "date_from", "date_to", "status", "comment")
    readonly_fields = ()
    ordering = ("-date_from",)


class EducationInline(admin.TabularInline):
    model = Education
    fk_name = "employee"
    extra = 0
    fields = ("institution", "degree", "graduation_year")
    ordering = ("-graduation_year",)


class DepartmentMembershipInline(admin.TabularInline):
    """Состав отдела (в карточке отдела)"""

    model = EmployeeDepartment
    fk_name = "department"
    extra = 0
    autocomplete_fields = ("employee",)
    fields = ("employee", "role", "is_active", "date_from", "date_to")
    show_change_link = True


class DepartmentPositionInline(admin.TabularInline):
    """Должности в отделе (в карточке отдела)"""

    model = EmployeePosition
    fk_name = "department"
    extra = 0
    autocomplete_fields = ("employee",)
    fields = ("employee", "title", "date_from", "date_to")


# =========================
#  Фильтры
# =========================
class ActuallyActiveFilter(admin.SimpleListFilter):
    title = "Фактически активен"
    parameter_name = "actually_active"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Да"),
            ("no", "Нет"),
        )

    def queryset(self, request, queryset):
        # Берём последнюю кадровую операцию и фильтруем по её типу
        latest_action_subq = (
            EmployeeAction.objects.filter(employee=OuterRef("pk"))
            .order_by("-date")
            .values("action")[:1]
        )
        queryset = queryset.annotate(latest_action=Subquery(latest_action_subq))
        val = self.value()
        if val == "yes":
            return queryset.filter(latest_action__isnull=False).exclude(
                latest_action=ACTION_DISMISSED
            )
        if val == "no":
            return queryset.filter(latest_action__in=[ACTION_DISMISSED, None])
        return queryset


# =========================
#  Employee
# =========================
@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = (
        "last_name",
        "first_name",
        "phone_number",
        "email",
        "is_active",
        "actually_active",
        "departments_list",
        "created_at",
    )
    list_filter = ("is_active", ActuallyActiveFilter)
    search_fields = (
        "last_name",
        "first_name",
        "patronymic",
        "email",
        "phone_number",
        "telegram",
        "wechat",
    )
    readonly_fields = ("created_at", "updated_at")
    ordering = ("last_name", "first_name")
    filter_horizontal = ("skills",)
    inlines = [
        EmployeeDepartmentInline,
        EmployeePositionInline,
        EmployeeActionInline,
        AbsenceInline,
        EducationInline,
    ]
    list_select_related = ()

    fieldsets = (
        (
            "Общая информация",
            {
                "fields": (
                    ("last_name", "first_name", "patronymic"),
                    ("gender", "birth_date"),
                    ("avatar",),
                )
            },
        ),
        (
            "Контакты",
            {
                "fields": (
                    ("phone_number", "email"),
                    ("telegram", "whatsapp", "wechat"),
                )
            },
        ),
        (
            "Служебное",
            {
                "fields": (("is_active",), ("created_at", "updated_at")),
            },
        ),
        (
            "Навыки",
            {
                "fields": ("skills",),
                "classes": ("collapse",),
            },
        ),
    )

    def departments_list(self, obj):
        # Корректно отобразим отделы (учитывая property obj.departments)
        deps = (
            obj.departments.all()
            if hasattr(obj.departments, "all")
            else obj.departments
        )
        names = [d.name for d in deps] if deps else []
        return ", ".join(names) or "—"

    departments_list.short_description = "Отделы"

    def actually_active(self, obj):
        return obj.is_actually_active

    actually_active.boolean = True
    actually_active.short_description = "Фактически активен"


# =========================
#  EmployeeAction
# =========================
@admin.register(EmployeeAction)
class EmployeeActionAdmin(admin.ModelAdmin):
    list_display = ("employee", "action", "date", "comment_short")
    list_filter = ("action",)
    search_fields = ("employee__last_name", "employee__first_name", "comment")
    ordering = ("-date",)
    date_hierarchy = "date"

    def comment_short(self, obj):
        return (
            (obj.comment[:80] + "…")
            if obj.comment and len(obj.comment) > 80
            else obj.comment
        )

    comment_short.short_description = "Комментарий"


# =========================
#  Department
# =========================
@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = ("name", "head", "employees_count", "created_at")
    search_fields = ("name", "head__last_name", "head__first_name")
    ordering = ("name",)
    autocomplete_fields = ("head",)
    inlines = [DepartmentMembershipInline, DepartmentPositionInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(emp_cnt=Count("employeedepartment", filter=None))

    def employees_count(self, obj):
        return getattr(obj, "emp_cnt", 0)

    employees_count.short_description = "Сотрудников"


# =========================
#  EmployeeDepartment
# =========================
@admin.register(EmployeeDepartment)
class EmployeeDepartmentAdmin(admin.ModelAdmin):
    list_display = (
        "employee",
        "department",
        "role",
        "is_active",
        "date_from",
        "date_to",
    )
    list_filter = ("is_active", "department")
    search_fields = (
        "employee__last_name",
        "employee__first_name",
        "department__name",
        "role",
    )
    autocomplete_fields = ("employee", "department")
    ordering = ("department", "employee")
    actions = ("mark_active", "mark_inactive", "make_head")

    @admin.action(description="Отметить активными")
    def mark_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Обновлено записей: {updated}")

    @admin.action(description="Отметить неактивными")
    def mark_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Обновлено записей: {updated}")

    @admin.action(description="Сделать выбранного сотрудника руководителем отдела")
    def make_head(self, request, queryset):
        # Разрешим только если выбрана ровно 1 запись
        if queryset.count() != 1:
            self.message_user(
                request,
                "Выберите ровно одну запись для назначения руководителя.",
                level="warning",
            )
            return
        link = queryset.first()
        dept = link.department
        dept.head = link.employee
        dept.save(update_fields=["head"])
        self.message_user(
            request, f"{link.employee} назначен руководителем отдела «{dept.name}»."
        )


# =========================
#  EmployeePosition
# =========================
@admin.register(EmployeePosition)
class EmployeePositionAdmin(admin.ModelAdmin):
    list_display = ("employee", "department", "title", "date_from", "date_to")
    list_filter = ("department",)
    search_fields = (
        "employee__last_name",
        "employee__first_name",
        "title",
        "department__name",
    )
    autocomplete_fields = ("employee", "department")
    ordering = ("-date_from",)


# =========================
#  Absence
# =========================
@admin.register(Absence)
class AbsenceAdmin(admin.ModelAdmin):
    list_display = ("employee", "type", "date_from", "date_to", "status")
    list_filter = ("type", "status", "date_from")
    search_fields = ("employee__last_name", "employee__first_name", "comment")
    autocomplete_fields = ("employee",)
    ordering = ("-date_from",)
    date_hierarchy = "date_from"


# =========================
#  Skill
# =========================
@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("name", "employees_count")
    search_fields = ("name",)
    ordering = ("name",)

    def employees_count(self, obj):
        return obj.employees.count()

    employees_count.short_description = "Кол-во сотрудников"


# =========================
#  Education
# =========================
@admin.register(Education)
class EducationAdmin(admin.ModelAdmin):
    list_display = ("employee", "institution", "degree", "graduation_year")
    list_filter = ("graduation_year",)
    search_fields = (
        "employee__last_name",
        "employee__first_name",
        "institution",
        "degree",
    )
    autocomplete_fields = ("employee",)
    ordering = ("-graduation_year",)

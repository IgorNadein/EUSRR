# backend/employees/admin.py

from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField, AdminPasswordChangeForm
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from simple_history.admin import SimpleHistoryAdmin

from .models import (
    Employee,
    EmployeeAction,
    Department,
    DepartmentRole,
    EmployeeDepartment,
    Position,
    Skill,
)

# =========================
#   Формы для кастомного User (Employee)
# =========================

class EmployeeCreationForm(forms.ModelForm):
    """
    Создание сотрудника в админке: логин — email, без username.
    """
    password1 = forms.CharField(label="Пароль", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Подтверждение пароля", widget=forms.PasswordInput)

    class Meta:
        model = Employee
        fields = ("email", "first_name", "last_name", "phone_number")

    def clean_password2(self):
        p1 = self.cleaned_data.get("password1") or ""
        p2 = self.cleaned_data.get("password2") or ""
        if not p1:
            raise forms.ValidationError("Пароль обязателен")
        if p1 != p2:
            raise forms.ValidationError("Пароли не совпадают")
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        # При создании через админку обычно активируем и помечаем e-mail подтверждённым
        if not user.is_active:
            user.is_active = True
        if not user.email_verified:
            user.email_verified = True
        if commit:
            user.save()
        return user


class EmployeeChangeForm(forms.ModelForm):
    """
    Редактирование сотрудника: пароль только для чтения (смена пароля — отдельной кнопкой).
    """
    password = ReadOnlyPasswordHashField(
        label="Хэш пароля",
        help_text=(
            "Пароль хранится в виде хэша — посмотреть его невозможно. "
            "Используйте кнопку «Изменить пароль» выше."
        ),
        required=False,
    )

    class Meta:
        model = Employee
        fields = (
            "email",
            "password",
            "first_name",
            "last_name",
            "patronymic",
            "gender",
            "birth_date",
            "avatar",
            "phone_number",
            "telegram",
            "whatsapp",
            "wechat",
            "position",
            "skills",
            "is_active",
            "email_verified",
            "is_staff",
            "is_superuser",
            "groups",
            "user_permissions",
            "last_login",
        )

    def clean_password(self):
        # Возвращаем исходное значение (хэш), даже если пользователь ничего не ввёл
        return self.initial.get("password")


# =========================
#   Инлайны
# =========================

class EmployeeDepartmentInline(admin.TabularInline):
    """
    Принадлежности сотрудника к отделам (видно из карточки сотрудника).
    """
    model = EmployeeDepartment
    fk_name = "employee"
    extra = 0
    autocomplete_fields = ("department", "role")
    fields = ("department", "role", "is_active", "date_from", "date_to")
    show_change_link = True



class DepartmentMembershipInline(admin.TabularInline):
    """
    Состав отдела — список участников прямо в карточке отдела.
    """
    model = EmployeeDepartment
    fk_name = "department"
    extra = 0
    autocomplete_fields = ("employee", "role")
    fields = ("employee", "role", "is_active", "date_from", "date_to")
    show_change_link = True


# =========================
#   Админки моделей
# =========================

@admin.register(Employee)
class EmployeeAdmin(DjangoUserAdmin):
    """
    Кастомный UserAdmin для модели Employee.
    Включает стандартную кнопку «Изменить пароль».
    """
    add_form = EmployeeCreationForm
    form = EmployeeChangeForm
    model = Employee

    # Включаем стандартную форму смены пароля и шаблон,
    # который показывает ссылку «Изменить пароль» на форме изменения пользователя.
    change_password_form = AdminPasswordChangeForm
    change_form_template = "admin/employees/employee/change_form.html"

    list_display = (
        "email",
        "last_name",
        "first_name",
        "phone_number",
        "position",
        "is_active",
        "email_verified",
        "is_staff",
    )
    list_filter = ("is_active", "email_verified", "is_staff", "is_superuser", "position", "groups")
    search_fields = ("email", "first_name", "last_name", "phone_number")
    ordering = ("last_name", "first_name")
    list_select_related = ("position",)

    filter_horizontal = ("groups", "user_permissions", "skills")

    readonly_fields = ("last_login", "created_at", "updated_at")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Личная информация", {
            "fields": (
                "first_name",
                "last_name",
                "patronymic",
                "gender",
                "birth_date",
                "avatar",
            )
        }),
        ("Контакты", {
            "fields": ("phone_number", "telegram", "whatsapp", "wechat")
        }),
        ("Работа", {
            "fields": ("position", "skills")
        }),
        ("Права и статусы", {
            "fields": (
                "is_active",
                "email_verified",
                "is_staff",
                "is_superuser",
                "groups",
                "user_permissions",
            )
        }),
        ("Служебное", {"fields": ("last_login", "created_at", "updated_at")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "email",
                "first_name",
                "last_name",
                "phone_number",
                "whatsapp",
                "position",
                "password1",
                "password2",
                "is_active",
                "email_verified",
                "is_staff",
                "is_superuser",
                "groups",
                "user_permissions",
            ),
        }),
    )

    inlines = [EmployeeDepartmentInline,]


@admin.register(Position)
class PositionAdmin(SimpleHistoryAdmin):
    list_display = ("name", "description")
    search_fields = ("name", "description")
    filter_horizontal = ("groups",)


@admin.register(EmployeeAction)
class EmployeeActionAdmin(SimpleHistoryAdmin):
    list_display = ("employee", "action", "date")
    list_filter = ("action",)
    search_fields = ("employee__first_name", "employee__last_name", "comment")
    autocomplete_fields = ("employee",)
    date_hierarchy = "date"


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "head", "created_at")
    list_filter = ("head",)
    search_fields = ("name",)
    autocomplete_fields = ("head",)
    readonly_fields = ("created_at", "head_appointed_at")
    inlines = [DepartmentMembershipInline]


@admin.register(DepartmentRole)
class DepartmentRoleAdmin(admin.ModelAdmin):
    list_display = ("name", "department")
    list_filter = ("department",)
    search_fields = ("name", "department__name")
    autocomplete_fields = ("department",)
    filter_horizontal = ("scoped_permissions",)

@admin.register(EmployeeDepartment)
class EmployeeDepartmentAdmin(admin.ModelAdmin):
    list_display = ("employee", "department", "role", "is_active", "date_from", "date_to")
    list_filter = ("is_active", "department", "role")
    search_fields = ("employee__first_name", "employee__last_name", "department__name")
    autocomplete_fields = ("employee", "department", "role")
    date_hierarchy = "date_from"


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


# Полезно иметь Permission в админке
@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("name", "codename", "content_type")
    list_filter = ("content_type",)
    search_fields = ("name", "codename")

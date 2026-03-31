"""
django-rules: декларативные правила доступа для employees

Правила используются для проверки permissions на уровне объектов.
https://github.com/dfunckt/django-rules
"""

import rules


# -----------------------------------------------------------------------------
# ПРЕДИКАТЫ (predicates)
# -----------------------------------------------------------------------------


@rules.predicate
def is_superuser(user):
    """Суперпользователь имеет все права"""
    return user.is_superuser


@rules.predicate
def is_staff(user):
    """Сотрудник (is_staff) имеет базовые права"""
    return user.is_staff


@rules.predicate
def is_hr_staff(user):
    """
    HR сотрудник - определяется по должности или группе.
    Адаптируйте под вашу логику: по position, department, группе и т.д.
    """
    if not hasattr(user, "position"):
        return False
    position_name = getattr(user.position, "name", "").lower()
    return "hr" in position_name or "кадр" in position_name


@rules.predicate
def is_department_head(user):
    """
    Руководитель отдела - определяется по должности.
    Адаптируйте под вашу логику.
    """
    if not hasattr(user, "position"):
        return False
    position_name = getattr(user.position, "name", "").lower()
    return any(
        keyword in position_name
        for keyword in [
            "руководитель",
            "начальник",
            "директор",
            "заведующий",
            "глава",
        ]
    )


@rules.predicate
def is_own_profile(user, employee):
    """Пользователь просматривает свой собственный профиль"""
    if employee is None:
        return False
    return user.pk == employee.pk


@rules.predicate
def is_same_department(user, employee):
    """Пользователь и сотрудник в одном отделе"""
    if (
        employee is None
        or not hasattr(user, "department")
        or not hasattr(employee, "department")
    ):
        return False
    return user.department == employee.department


# -----------------------------------------------------------------------------
# ПРАВИЛА (rules)
# -----------------------------------------------------------------------------

# Просмотр профиля сотрудника
rules.add_rule(
    "employees.view_employee",
    is_superuser | is_staff | is_hr_staff | is_own_profile,
)

# Изменение профиля сотрудника
rules.add_rule(
    "employees.change_employee",
    is_superuser | is_hr_staff | (is_own_profile & ~rules.always_deny),
)

# Удаление сотрудника (только HR и superuser)
rules.add_rule("employees.delete_employee", is_superuser | is_hr_staff)

# Просмотр списка всех сотрудников
rules.add_rule(
    "employees.view_all_employees", is_superuser | is_staff | is_hr_staff
)

# Просмотр отчётов по персоналу (только HR и руководители)
rules.add_rule(
    "employees.view_reports", is_superuser | is_hr_staff | is_department_head
)

# Изменение должности сотрудника (только HR)
rules.add_rule("employees.change_position", is_superuser | is_hr_staff)

# Изменение отдела сотрудника (только HR)
rules.add_rule("employees.change_department", is_superuser | is_hr_staff)

# Просмотр контактной информации сотрудника
rules.add_rule(
    "employees.view_contact_info",
    is_superuser | is_staff | is_own_profile | is_same_department,
)

# -----------------------------------------------------------------------------
# PERMISSIONS ДЛЯ МОДЕЛЕЙ
# -----------------------------------------------------------------------------

# Если вы хотите переопределить стандартные Django permissions для модели:
# rules.add_perm('employees.view_employee', is_superuser | is_staff)
# rules.add_perm('employees.change_employee', is_superuser | is_hr_staff)
# rules.add_perm('employees.delete_employee', is_superuser | is_hr_staff)
# rules.add_perm('employees.add_employee', is_superuser | is_hr_staff)


# -----------------------------------------------------------------------------
# ИСПОЛЬЗОВАНИЕ В КОДЕ
# -----------------------------------------------------------------------------

"""
# В views:
from django.core.exceptions import PermissionDenied

def employee_detail(request, pk):
    employee = get_object_or_404(Employee, pk=pk)

    # Проверка через has_perm (если правило зарегистрировано через add_perm)
    if not request.user.has_perm('employees.view_employee', employee):
        raise PermissionDenied

    # Или напрямую через rules.test_rule
    if not rules.test_rule('employees.view_employee', request.user, employee):
        raise PermissionDenied

    return render(request, 'employees/detail.html', {'employee': employee})


# В templates:
{% load rules %}

{% has_perm 'employees.change_employee' user employee as can_change %}
{% if can_change %}
    <a href="{% url 'employees:edit' employee.pk %}">Редактировать</a>
{% endif %}


# В DRF permissions:
from rest_framework import permissions
import rules

class EmployeePermission(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return rules.test_rule(
                'employees.view_employee', request.user, obj
            )
        elif request.method in ['PUT', 'PATCH']:
            return rules.test_rule(
                'employees.change_employee', request.user, obj
            )
        elif request.method == 'DELETE':
            return rules.test_rule(
                'employees.delete_employee', request.user, obj
            )
        return False


# В admin.py для object-level permissions:
from django.contrib import admin

class EmployeeAdmin(admin.ModelAdmin):
    def has_change_permission(self, request, obj=None):
        if obj is None:
            return super().has_change_permission(request, obj)
        return rules.test_rule('employees.change_employee', request.user, obj)
"""

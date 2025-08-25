# employees/permissions.py
from __future__ import annotations

from django.contrib.auth.models import Permission
from django.db.models import Prefetch
from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import Department, EmployeeDepartment

MANAGE_PERM = "manage_department"
CHANGE_HEAD_PERM = "change_department_head"
ASSIGN_ROLE_PERM = "assign_department_role"


def user_is_dept_head(user, dept: Department) -> bool:
    return bool(
        user and user.is_authenticated and dept.head_id == getattr(user, "id", None)
    )


def user_is_staffish(user) -> bool:
    return bool(user and user.is_authenticated and (user.is_superuser or user.is_staff))


def get_user_dept_link(user, dept: Department) -> EmployeeDepartment | None:
    if not user or not user.is_authenticated:
        return None
    # можно закешировать на user, если часто вызывается:
    cache_key = f"_dept_link_{dept.id}"
    cached = getattr(user, cache_key, None)
    if cached is not None:
        return cached

    link = (
        EmployeeDepartment.objects.select_related("role")
        .prefetch_related(
            Prefetch(
                "role__permissions", queryset=Permission.objects.only("id", "codename")
            )
        )
        .filter(employee_id=user.id, department_id=dept.id, is_active=True)
        .first()
    )
    setattr(user, cache_key, link)
    return link


def user_has_dept_perm(user, dept: Department, perm_code: str) -> bool:
    if not (user and user.is_authenticated):
        return False
    # staff/superuser — сразу ок (оставим как было)
    if user_is_staffish(user):
        return True
    # руководитель — сразу ок
    if user_is_dept_head(user, dept):
        return True
    # основная проверка: активная связь + у роли есть нужный Permission
    return EmployeeDepartment.objects.filter(
        employee_id=user.id,
        department_id=dept.id,
        is_active=True,
        role__permissions__codename=perm_code,
    ).exists()


class IsDeptManagerForWrite(BasePermission):
    """
    Для DepartmentViewSet.
    View может указать:
        self.required_perm_code in {"change_department_head", "assign_department_role", "manage_department"}
    По умолчанию — "manage_department".
    """

    message = "Недостаточно прав для управления отделом."

    def has_object_permission(self, request, view, obj):
        dept = getattr(obj, "department", obj)
        if request.method in SAFE_METHODS:
            return True

        user = request.user
        if not user or not user.is_authenticated:
            return False

        if user_is_staffish(user) or user_is_dept_head(user, dept):
            return True

        perm_code = getattr(view, "required_perm_code", MANAGE_PERM)

        # NEW: если у пользователя есть глобальный модельный пермишен (employees.<perm_code>) — пускаем
        # (сбросим кэш прав — в тестах перм выдают после первого запроса)
        for attr in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            if hasattr(user, attr):
                try:
                    delattr(user, attr)
                except Exception:
                    pass
        app_label = Department._meta.app_label  # "employees"
        if user.has_perm(f"{app_label}.{perm_code}"):
            return True

        # иначе — проверяем наличие нужного права через роль в данном отделе
        return user_has_dept_perm(user, dept, perm_code)


class IsSelfOrStaff(BasePermission):
    """
    Доступ к объекту Employee:
      - staff/superuser — всегда
      - сам сотрудник к своему объекту
    """

    message = "Недостаточно прав."

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or user.is_staff:
            return True
        return getattr(obj, "id", None) == getattr(user, "id", None)


class IsStaffOrHasModelPerm(BasePermission):
    """
    Read: любой аутентифицированный
    Write: staff ИЛИ пользователь с правом, указанным во view.required_perm_code
    """

    def has_permission(self, request, view):
        user = request.user
        if request.method in SAFE_METHODS:
            return bool(user and user.is_authenticated)
        if not (user and user.is_authenticated):
            return False
        if user.is_staff or user.is_superuser:
            return True
        code = getattr(view, "required_perm_code", None)
        # NOTE: в тестах права выдают уже после первого запроса; кэш прав у user остаётся.
        # Сбросим кэш, чтобы has_perm перечитал права из БД в рамках текущего запроса.
        for attr in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            if hasattr(user, attr):
                try:
                    delattr(user, attr)
                except Exception:
                    pass
        return bool(code and user.has_perm(code))


__all__ = [
    "MANAGE_PERM",
    "CHANGE_HEAD_PERM",
    "ASSIGN_ROLE_PERM",
    "IsDeptManagerForWrite",
    "IsSelfOrStaff",
    "IsStaffOrHasModelPerm",
    "user_is_dept_head",
    "user_has_dept_perm",
]

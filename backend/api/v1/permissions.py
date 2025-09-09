# backend\api\v1\permissions.py
from __future__ import annotations

from typing import Any, Dict, Optional

from django.contrib.auth.models import AbstractBaseUser
from employees.constants import DeptPerm
from employees.models import Department, EmployeeDepartment
from rest_framework.permissions import (SAFE_METHODS, BasePermission,
                                        DjangoModelPermissions)

MANAGE_PERM = "manage_department"
CHANGE_HEAD_PERM = "change_department_head"
ASSIGN_ROLE_PERM = "assign_department_role"


def user_is_dept_head(user, dept: Department) -> bool:
    return bool(
        user and user.is_authenticated and dept.head_id == getattr(user, "id", None)
    )


def user_is_staffish(user) -> bool:
    return bool(user and user.is_authenticated and (user.is_superuser or user.is_staff))


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
        role__scoped_permissions__codename=perm_code,
    ).exists()


def has_dept_perm(user: AbstractBaseUser, department_id: int, code: str) -> bool:
    """
    Возвращает True, если пользователь имеет право `code` в рамках отдела `department_id`.

    Логика:
      1) staff/superuser → всегда True
      2) пользователь является текущим руководителем отдела → True для любых «управленческих» кодов
      3) пользователь состоит в отделе и его роль содержит `code` в scoped_permissions → True
      4) иначе False
    """
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True

    # 2) Руководитель отдела имеет все управленческие права в своём отделе
    if Department.objects.filter(id=department_id, head_id=user.id).exists():
        return True

    # 3) Проверка роли в отделе
    link = (
        EmployeeDepartment.objects.select_related("role")
        .filter(employee_id=user.id, department_id=department_id, is_active=True)
        .first()
    )
    if not link or not link.role_id:
        return False

    # роль хранит «скоуп-права» только для этого отдела
    return link.role.scoped_permissions.filter(code=code).exists()


class AdminOrDeptAllowed(BasePermission):
    """Комбинированный пермишен: админский доступ ИЛИ доступ по праву на конкретный отдел.

    Поведение:
        1. Если пользователь superuser/staff — доступ всегда разрешён.
        2. Если для текущего экшена требуется код права (например, DeptPerm.MANAGE_CALENDAR),
           то доступ разрешается только при наличии у пользователя этого права на указанный отдел.
        3. Идентификатор отдела извлекается из:
             - URL kwargs: 'department_pk' → 'department_id';
             - request.data: 'department' → 'department_id';
             - query params: 'department' → 'department_id'.
           На уровне has_object_permission отдел берётся из самого объекта:
             - Department.id;
             - obj.department_id / obj.dept_id;
             - obj.department.id.
        4. Если код права не задан (required_code/required_code_map пусты), то
           для SAFE-методов (GET/HEAD/OPTIONS) доступ разрешён, если allow_safe_without_code=True (по умолчанию).
           Для небезопасных методов в этом случае доступ запрещён.

    Атрибуты класса:
        required_code (str|None): Единый код права для всех экшенов. Если None, используется required_code_map.
        required_code_map (dict[str,str]): Коды прав по имени action (create/update/partial_update/destroy/...).
        allow_safe_without_code (bool): Разрешать ли SAFE-методы, когда код не задан. По умолчанию True.

    Примеры:
        class ManageCalendarPerm(AdminOrDeptAllowed):
            required_code = DeptPerm.MANAGE_CALENDAR

        class DeptEventsPerm(AdminOrDeptAllowed):
            required_code_map = {
                "create": DeptPerm.MANAGE_CALENDAR,
                "update": DeptPerm.MANAGE_CALENDAR,
                "partial_update": DeptPerm.MANAGE_CALENDAR,
                "destroy": DeptPerm.MANAGE_CALENDAR,
            }
    """

    required_code: Optional[str] = None
    required_code_map: Dict[str, str] = {}
    allow_safe_without_code: bool = True

    # -------- helpers --------

    def get_required_code(self, request, view) -> Optional[str]:
        """Определяет требуемый код права для текущего экшена.

        Сначала берёт из required_code_map по имени action (DRF: view.action),
        затем fallback на required_code.

        Args:
            request: DRF Request (не используется в текущей логике).
            view: DRF View/ViewSet; важно наличие атрибута 'action' для ViewSet.

        Returns:
            Optional[str]: Код права или None, если право для экшена не требуется.
        """
        return (
            self.required_code_map.get(getattr(view, "action", None))
            or self.required_code
        )

    def _extract_dept_id_from_request(self, request, view) -> Optional[int]:
        """Пытается извлечь department_id из kwargs, body или query-параметров.

        Порядок:
            1) view.kwargs: department_pk, department_id
            2) request.data: department, department_id
            3) request.query_params: department, department_id

        Args:
            request: DRF Request
            view: DRF View

        Returns:
            Optional[int]: Значение dept_id, если найдено и приведено к int, иначе None.
        """
        for k in ("department_pk", "department_id"):
            v = view.kwargs.get(k)
            if v is not None:
                return v
        for k in ("department", "department_id"):
            v = request.data.get(k)
            if v is not None:
                return v
        for k in ("department", "department_id"):
            v = request.query_params.get(k)
            if v is not None:
                return v
        return None

    def _extract_dept_id_from_obj(self, obj: Any) -> Optional[int]:
        """Извлекает department_id из объекта.

        Порядок:
            - Если obj — модель Department с полем id → вернуть id.
            - Если у obj есть атрибуты department_id или dept_id → вернуть его.
            - Если у obj есть атрибут department (FK) → взять department.id.

        Args:
            obj: Модель/объект detail-view.

        Returns:
            Optional[int]: department_id или None.
        """
        if obj is None:
            return None
        if obj.__class__.__name__ == "Department" and hasattr(obj, "id"):
            return obj.id
        for attr in ("department_id", "dept_id"):
            if hasattr(obj, attr):
                return getattr(obj, attr)
        dep = getattr(obj, "department", None)
        if dep is not None:
            return getattr(dep, "id", None)
        return None

    def _to_int_or_none(self, v) -> Optional[int]:
        """Аккуратное приведение к int.

        Args:
            v: Любое значение с возможностью строкового преобразования.

        Returns:
            Optional[int]: int или None при ошибке.
        """
        try:
            return int(str(v))
        except Exception:
            return None

    # -------- main checks --------

    def has_permission(self, request, view) -> bool:
        """Проверка доступа на уровне запроса (до доступа к объекту).

        Правила:
            - Неаутентифицированные → False.
            - superuser/staff → True.
            - Если код не требуется:
                - SAFE-методы → allow_safe_without_code ? True : False
                - небезопасные → False
            - Если код требуется:
                - Пытаемся найти department_id в запросе;
                - Если нашли → проверяем has_dept_perm(user, dept_id, code);
                - Если не нашли:
                    * если detail-вью → отложить проверку до has_object_permission (вернуть True);
                    * иначе → False.

        Returns:
            bool: Разрешить/запретить доступ.
        """
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
            return True

        code = self.get_required_code(request, view)
        if not code:
            return (
                request.method in SAFE_METHODS
                if self.allow_safe_without_code
                else False
            )

        dept_id = self._to_int_or_none(
            self._extract_dept_id_from_request(request, view)
        )
        if dept_id is None:
            # detail-экшены проверим на объекте
            return True if getattr(view, "detail", False) else False

        return has_dept_perm(user, dept_id, code)

    def has_object_permission(self, request, view, obj) -> bool:
        """Проверка доступа к конкретному объекту (detail).

        Правила:
            - superuser/staff → True.
            - Если код не требуется → SAFE-методы допускаются (если allow_safe_without_code=True).
            - Иначе:
                - Пытаемся извлечь department_id из объекта;
                - если не удалось — пробуем извлечь из запроса (kwargs/data/query);
                - если не нашли вообще → False;
                - иначе → has_dept_perm(user, dept_id, code).

        Returns:
            bool: Разрешить/запретить доступ к объекту.
        """
        user = getattr(request, "user", None)
        if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
            return True

        code = self.get_required_code(request, view)
        if not code:
            return (
                request.method in SAFE_METHODS
                if self.allow_safe_without_code
                else False
            )

        dept_id = self._to_int_or_none(self._extract_dept_id_from_obj(obj))
        if dept_id is None:
            dept_id = self._to_int_or_none(
                self._extract_dept_id_from_request(request, view)
            )
        if dept_id is None:
            return False

        return has_dept_perm(request.user, dept_id, code)


class IsSelfOrStaff(BasePermission):
    # На class-level пускаем любого аутентифицированного.
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    # На object-level: сам объект, либо staff/superuser.
    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
            return True

        # Основной случай — объект сотрудника.
        try:
            from employees.models import \
                Employee  # локальный импорт, чтобы избежать циклов
        except Exception:
            Employee = None

        if Employee is not None and isinstance(obj, Employee):
            return obj.pk == user.pk

        # Fallback: сравнить id из URL, если obj не Employee (на всякий случай)
        lookup = getattr(view, "lookup_field", "pk")
        return str(view.kwargs.get(lookup)) == str(user.pk)


class IsAuthorOrStaffForComments(BasePermission):
    """
    Создание/чтение — любой аутентифицированный (проверяет IsAuthenticated во view).
    Изменение/удаление — автор комментария или staff/superuser.
    """

    message = "Можно редактировать/удалять только свои комментарии."

    def has_permission(self, request, view):
        # IsAuthenticated уже стоит во вьюхе; дублируем True для небезопасных методов,
        # чтобы проверка прошла до object-level.
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user_is_staffish(user):
            return True
        return getattr(obj, "author_id", None) == getattr(user, "id", None)


class AdminOrActionOrModelPerms(DjangoModelPermissions):
    """
    Админ/суперпользователь → всегда True.
    Если задан код права (view.required_perm_code или required_perms_by_action[action]),
    проверяем его через user.has_perm(...). Иначе — стандартные DjangoModelPermissions.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or user.is_staff:
            return True

        mapping = getattr(view, "required_perms_by_action", {}) or {}
        action = getattr(view, "action", None)
        code = getattr(view, "required_perm_code", None) or mapping.get(action)
        if code:
            return user.has_perm(code)

        return super().has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser or user.is_staff:
            return True

        mapping = getattr(view, "required_perms_by_action", {}) or {}
        action = getattr(view, "action", None)
        code = getattr(view, "required_perm_code", None) or mapping.get(action)
        if code:
            return user.has_perm(code)

        return super().has_object_permission(request, view, obj)


__all__ = [
    "MANAGE_PERM",
    "CHANGE_HEAD_PERM",
    "ASSIGN_ROLE_PERM",
    "IsSelfOrStaff",
    "IsAuthorOrStaffForComments",
    "AdminOrActionOrModelPerms",
    "user_is_dept_head",
    "user_has_dept_perm",
]

# backend\api\v1\permissions.py
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Tuple, Type

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.db.models import Model
from employees.constants import DeptPerm
from employees.models import Department, EmployeeDepartment
<<<<<<< HEAD
from rest_framework.permissions import (SAFE_METHODS, BasePermission,
                                        DjangoModelPermissions)
=======
from rest_framework.permissions import (
    SAFE_METHODS,
    BasePermission,
    DjangoModelPermissions,
)
>>>>>>> origin/feat/ldap-writeback
from rest_framework.request import Request

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
    """Проверяет, есть ли у пользователя право `perm_code` в указанном отделе.

    Правила:
        - Неаутентифицированным → False.
        - staff/superuser → True.
        - Руководитель отдела → True.
        - Иначе: существует активная связь EmployeeDepartment, и у роли есть
          DepartmentPermission с нужным code.

    Args:
        user (User): Текущий пользователь.
        dept (Department): Отдел.
        perm_code (str): Код департаментного права (см. DeptPerm.CHOICES).

    Returns:
        bool: True, если доступ разрешён.

    Raises:
        ValueError: Если `dept` не задан или не имеет id.
    """
    if not (user and user.is_authenticated):
        return False

    # staff/superuser — сразу ок
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return True

    if not isinstance(dept, Department) or getattr(dept, "id", None) is None:
        raise ValueError("Argument `dept` must be Department instance with a valid id.")

    # руководитель — сразу ок
    if getattr(dept, "head_id", None) == user.id:
        return True

    # основная проверка: активная связь + у роли есть нужный DepartmentPermission.code
    return EmployeeDepartment.objects.filter(
        employee_id=user.id,
        department_id=dept.id,
        is_active=True,
        role__scoped_permissions__code=perm_code,  # <-- ВАЖНО: `code`, не `codename`
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
        """См. докстринг класса. Если dept_id не найден, но это detail-запрос,
        откладываем проверку до object-level (вернём True)."""

        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
            return True

        code = self.get_required_code(request, view)
        if not code:
            return (
                (request.method in SAFE_METHODS)
                if self.allow_safe_without_code
                else False
            )

        dept_id = self._to_int_or_none(
            self._extract_dept_id_from_request(request, view)
        )

        if dept_id is None:
            # robust: считаем detail, если есть lookup в kwargs
            lookup_kw = getattr(view, "lookup_url_kwarg", None) or getattr(
                view, "lookup_field", "pk"
            )
            is_detail = getattr(view, "detail", None)
            if is_detail is None:
                is_detail = lookup_kw in getattr(view, "kwargs", {})
            if is_detail:
                # отложим проверку до has_object_permission
                return True
            return False

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

        return has_dept_perm(request.user, dept_id, code)


class IsSelfOrStaff(BasePermission):
    """Доступ для staff/superuser или владельца объекта.

    ВАЖНО:
        • SAFE-методы НЕ дают автоматического допуска.
        • Добавлена поддержка кейса "объект = сам пользователь" (self-update).
    """

<<<<<<< HEAD
    DEFAULT_OWNER_ID_ATTRS: Tuple[str, ...] = (
        "employee_id",
        "author_id",
        "user_id",
        "owner_id",
    )
=======
    DEFAULT_OWNER_ID_ATTRS: Tuple[str, ...] = ("employee_id", "author_id", "user_id", "owner_id")
>>>>>>> origin/feat/ldap-writeback
    DEFAULT_OWNER_OBJ_ATTRS: Tuple[str, ...] = ("employee", "author", "user", "owner")

    def has_permission(self, request: Request, view) -> bool:
        """Пускаем только аутентифицированных.

        Args:
            request (Request): DRF-запрос.
            view: DRF ViewSet.

        Returns:
            bool: True если пользователь аутентифицирован.
        """
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated)

    def has_object_permission(self, request: Request, view, obj) -> bool:
        """Разрешает доступ staff/superuser или владельцу объекта.

        Логика владельца:
            1) Совпадение *_id полей (employee_id/user_id/…)
            2) Совпадение связанных owner-объектов (employee/user/…)
            3) Фоллбек "self-object": obj.__class__ == user.__class__ и obj.pk == user.pk

        Args:
            request (Request): DRF-запрос.
            view: DRF ViewSet.
            obj: Проверяемый объект.

        Returns:
            bool: True если доступ разрешён.

        Raises:
            Ничего не выбрасывает.
        """
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False

        # Админский доступ
        if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
            return True

        # 1) *_id поля владельца
<<<<<<< HEAD
        owner_id_attrs: Iterable[str] = getattr(
            view, "owner_id_attrs", self.DEFAULT_OWNER_ID_ATTRS
        )
=======
        owner_id_attrs: Iterable[str] = getattr(view, "owner_id_attrs", self.DEFAULT_OWNER_ID_ATTRS)
>>>>>>> origin/feat/ldap-writeback
        for attr in owner_id_attrs:
            if getattr(obj, attr, None) == user.id:
                return True

        # 2) связанные owner-объекты
<<<<<<< HEAD
        owner_obj_attrs: Iterable[str] = getattr(
            view, "owner_obj_attrs", self.DEFAULT_OWNER_OBJ_ATTRS
        )
=======
        owner_obj_attrs: Iterable[str] = getattr(view, "owner_obj_attrs", self.DEFAULT_OWNER_OBJ_ATTRS)
>>>>>>> origin/feat/ldap-writeback
        for attr in owner_obj_attrs:
            owner = getattr(obj, attr, None)
            if owner is not None and getattr(owner, "id", None) == user.id:
                return True

        # 3) self-object: редактирование собственной учётки (Employee ↔ Employee)
        try:
<<<<<<< HEAD
            if obj.__class__ is user.__class__ and getattr(obj, "pk", None) == getattr(
                user, "pk", None
            ):
=======
            if obj.__class__ is user.__class__ and getattr(obj, "pk", None) == getattr(user, "pk", None):
>>>>>>> origin/feat/ldap-writeback
                return True
        except Exception:
            # максимально безопасно: не пускаем, если что-то пошло не так
            pass

        return False


class AdminOrActionOrModelPerms(DjangoModelPermissions):
    """staff/superuser ИЛИ явные пермы экшена ИЛИ стандартные DjangoModelPermissions.

    Логика:
      1) staff/superuser → True
      2) Если на вью заданы «явные» коды прав для текущего action (метод `_explicit_perm_codes`),
         достаточно ЛЮБОГО из них → True/False
      3) Иначе — делегируем в DjangoModelPermissions.has_permission():
         - для SAFE_METHODS потребует `view_<model>`
         - для небезопасных — коды из perms_map (add/change/delete)
    """

    perms_map = {
        "GET": ["%(app_label)s.view_%(model_name)s"],
        "OPTIONS": [],
        "HEAD": [],
        "POST": ["%(app_label)s.add_%(model_name)s"],
        "PUT": ["%(app_label)s.change_%(model_name)s"],
        "PATCH": ["%(app_label)s.change_%(model_name)s"],
        "DELETE": ["%(app_label)s.delete_%(model_name)s"],
    }

    @staticmethod
    def _normalize_codes(value: Any) -> Optional[list[str]]:
        """Приводит конфигурацию кодов прав к списку строк.

        Args:
            value (Any): Значение из конфигурации прав:
                - str — один код,
                - Iterable[str] — несколько кодов,
                - None — отсутствует.

        Returns:
            Optional[list[str]]: Список кодов или None.

        Raises:
            TypeError: Если найден нестроковый элемент в Iterable.
        """
        if value is None:
            return None
        if isinstance(value, str):
            v = value.strip()
            return [v] if v else None
        if isinstance(value, Iterable):
            out: list[str] = []
            for v in value:
                if not isinstance(v, str):
                    raise TypeError("Коды прав должны быть строками.")
                v = v.strip()
                if v:
                    out.append(v)
            return out or None
        return None

    @staticmethod
    def _explicit_perm_codes(view) -> Optional[list[str]]:
        """Достаёт из вью «явные» коды прав (ИЛИ между кодами).

        Поддерживаемые формы на ViewSet:
          - required_perm_code: str | Iterable[str]
          - required_perms_by_action[action]: str | Iterable[str]
          - required_perms_by_action[action]: {method: str|Iterable[str]}
            где method сравнивается без учёта регистра, возможны '*', 'ANY',
            а HEAD трактуется как GET.

        Args:
            view: DRF ViewSet с полями `action`, `request` (опционально).

        Returns:
            Optional[list[str]]: Список кодов прав или None.
        """
        # 1) Единый код(ы) на всю вью
        codes = AdminOrActionOrModelPerms._normalize_codes(
            getattr(view, "required_perm_code", None)
        )
        if codes:
            return codes

        # 2) Карта по экшенам (+ по методам)
        mapping = getattr(view, "required_perms_by_action", None) or {}
        if not isinstance(mapping, dict):
            return None

        action = getattr(view, "action", None)
        if not action or action not in mapping:
            return None

        value = mapping[action]

        # 2.1) Прямо строка/итерируемое — сразу нормализуем
        codes = AdminOrActionOrModelPerms._normalize_codes(value)
        if codes is not None:
            return codes

        # 2.2) Вложенная карта по методам
        if isinstance(value, dict):
            method = getattr(getattr(view, "request", None), "method", None)
            if not method:
                return None
            m = method.upper()
            keys = (m, m.lower())
            if m == "HEAD":
                keys += ("GET", "get")
            keys += ("*", "ANY")
            for k in keys:
                if k in value:
                    return AdminOrActionOrModelPerms._normalize_codes(value[k])
            return None

        # Иное — игнорируем
        return None

    def has_permission(self, request: Request, view) -> bool:
        """Проверяет доступ на уровне запроса.

        Args:
            request (Request): DRF-запрос.
            view: DRF View/ViewSet.

        Returns:
            bool: Разрешён ли доступ.

        Raises:
            PermissionDenied: не выбрасывается здесь; при False DRF отдаст 403.
        """
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            return False
        if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
            return True

        # 1) Явные пермы, привязанные к action (если у тебя есть такой механизм)
        explicit: Optional[Iterable[str]] = getattr(
            self, "_explicit_perm_codes", lambda _v: None
        )(view)
        if explicit:
            return any(user.has_perm(code) for code in explicit)

        # 2) Всё остальное — родителю (в т.ч. SAFE_METHODS → view_<model>)
        return super().has_permission(request, view)


__all__ = [
    "MANAGE_PERM",
    "CHANGE_HEAD_PERM",
    "ASSIGN_ROLE_PERM",
    "IsSelfOrStaff",
    "AdminOrActionOrModelPerms",
    "user_is_dept_head",
    "user_has_dept_perm",
]

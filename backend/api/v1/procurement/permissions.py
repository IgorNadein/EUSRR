"""
Права доступа для модуля закупок.
"""

from rest_framework import permissions

from api.v1.permissions import has_dept_perm
from employees.constants import DeptPerm
from employees.models import Department, EmployeeDepartment
from procurement.services import ProcurementApprovalResolver


class IsDepartmentHead(permissions.BasePermission):
    """Проверка, что пользователь - руководитель отдела."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser or request.user.is_staff:
            return True

        # Проверяем, является ли пользователь руководителем
        # какого-либо отдела
        return request.user.led_departments.exists()


class IsDirector(permissions.BasePermission):
    """Проверка, что пользователь - директор."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Директор = суперпользователь или есть специальное право
        return request.user.is_superuser or request.user.has_perm(
            "procurement.approve_procurementrequest"
        )


class CanCreateProcurementRequest(permissions.BasePermission):
    """Проверка права на создание заявки на закупку."""

    def has_permission(self, request, view):
        from employees.models import Employee

        if not request.user or not request.user.is_authenticated:
            return False

        if request.method in permissions.SAFE_METHODS:
            return True

        if request.method == "POST":
            # Любой авторизованный сотрудник может создать заявку
            return isinstance(request.user, Employee)

        return True


class CanEditOwnProcurementRequest(permissions.BasePermission):
    """Проверка права на редактирование своей заявки."""

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        # Чтение доступно всем
        if request.method in permissions.SAFE_METHODS:
            return True

        # Суперпользователь может все
        if request.user.is_superuser:
            return True

        # Редактировать можно только свою заявку в статусе DRAFT
        if request.method in ["PUT", "PATCH", "DELETE"]:
            return obj.requestor == request.user and obj.is_editable

        return False


class CanApproveProcurementRequest(permissions.BasePermission):
    """Проверка права на согласование заявки."""

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        return ProcurementApprovalResolver.user_can_approve(request.user, obj)


class CanManageProcurementRequest(permissions.BasePermission):
    """Комплексная проверка прав на заявки закупок.

    Логика доступа:
    - Просмотр (SAFE_METHODS): любой аутентифицированный (фильтрация в queryset)

    - Создание:
        - admin/staff/superuser → любой отдел
        - модельные права (add_procurementrequest) → любой отдел
        - сотрудник отдела → только свой отдел
        - без отдела → запрещено

    - Изменение:
        - admin/staff/superuser → любая заявка в DRAFT
        - модельные права (change_procurementrequest) → любая заявка в DRAFT
        - автор заявки → своя заявка в DRAFT
        - начальник отдела → заявки своего отдела в DRAFT

    - Удаление:
        - admin/staff/superuser → любая заявка
        - модельные права (delete_procurementrequest) → любая заявка
        - автор заявки → своя заявка в DRAFT
        - начальник отдела → заявки своего отдела в DRAFT
    """

    def _is_admin(self, user) -> bool:
        """Проверяет, является ли пользователь админом."""
        return getattr(user, "is_superuser", False) or getattr(
            user, "is_staff", False
        )

    def _has_model_perm(self, user, action: str) -> bool:
        """Проверяет модельные права на заявки."""
        perm_map = {
            "create": "procurement.add_procurementrequest",
            "update": "procurement.change_procurementrequest",
            "partial_update": "procurement.change_procurementrequest",
            "destroy": "procurement.delete_procurementrequest",
        }
        perm = perm_map.get(action)
        return perm and user.has_perm(perm)

    def _get_user_departments(self, user) -> list[int]:
        """Возвращает список ID отделов, где пользователь состоит."""
        return list(
            EmployeeDepartment.objects.filter(
                employee_id=user.id, is_active=True
            ).values_list("department_id", flat=True)
        )

    def _get_dept_id_from_request(self, request) -> int | None:
        """Извлекает ID отдела из данных запроса."""
        dept_id = request.data.get("department")
        if dept_id is not None:
            try:
                return int(dept_id)
            except (ValueError, TypeError):
                pass
        return None

    def _is_dept_head(self, user, dept_id: int) -> bool:
        """Проверяет, является ли пользователь начальником отдела."""
        return Department.objects.filter(id=dept_id, head_id=user.id).exists()

    def has_permission(self, request, view) -> bool:
        """Проверка доступа на уровне запроса."""
        user = request.user
        if not user or not user.is_authenticated:
            return False

        # Чтение доступно всем аутентифицированным
        if request.method in permissions.SAFE_METHODS:
            return True

        # Админы могут всё
        if self._is_admin(user):
            return True

        action = getattr(view, "action", None)

        # Модельные права дают полный доступ
        if self._has_model_perm(user, action):
            return True

        # Для создания проверяем отдел
        if action == "create":
            dept_id = self._get_dept_id_from_request(request)
            if dept_id is None:
                return False

            # Пользователь должен состоять в указанном отделе
            user_depts = self._get_user_departments(user)
            if not user_depts:
                # Пользователь без отдела не может создавать
                return False

            if dept_id not in user_depts:
                # Нельзя создавать заявку в чужом отделе
                return False

            return True

        # Для update/delete проверка на уровне объекта
        if action in ("update", "partial_update", "destroy"):
            return True

        return True

    def has_object_permission(self, request, view, obj) -> bool:
        """Проверка доступа к конкретному объекту."""
        user = request.user
        if not user or not user.is_authenticated:
            return False

        # Чтение доступно всем
        if request.method in permissions.SAFE_METHODS:
            return True

        # Админы могут всё
        if self._is_admin(user):
            return True

        action = getattr(view, "action", None)

        # Модельные права
        if self._has_model_perm(user, action):
            return True

        dept_id = obj.department_id

        # Submit (отправка на согласование) - только владелец
        if action == "submit":
            return obj.requestor == user

        # Cancel (отмена заявки) - только владелец
        if action == "cancel":
            return obj.requestor == user

        # Комментарии доступны тем, кто видит заявку
        if action == "comments":
            return True

        # Удаление комментария дополнительно валидируется во view по автору/админу
        if action == "delete_comment":
            return True

        # Start_work (взять в работу) - любой авторизованный
        if action == "start_work":
            return True

        # Complete (завершить) - только исполнитель
        if action == "complete":
            return obj.executor == user

        # Удаление
        if action == "destroy":
            # Автор может удалить свою заявку в DRAFT
            if obj.requestor == user and obj.is_editable:
                return True
            # Начальник отдела может удалить заявку отдела в DRAFT
            if self._is_dept_head(user, dept_id) and obj.is_editable:
                return True
            return False

        # Изменение
        if action in ("update", "partial_update"):
            # Заявка должна быть редактируемой (DRAFT)
            if not obj.is_editable:
                return False

            # Автор может редактировать свою заявку
            if obj.requestor == user:
                return True

            # Начальник отдела может редактировать заявки отдела
            if self._is_dept_head(user, dept_id):
                return True

            return False

        return False


class CanManageEquipment(permissions.BasePermission):
    """Проверка права на управление оборудованием.

    Логика доступа:
    - Просмотр (SAFE_METHODS): любой аутентифицированный
    - Создание:
        - admin/staff/superuser → ✅
        - модельные права (add_equipment) → ✅
        - начальник отдела (department из request.data) → ✅
        - скоуп-право MANAGE_EQUIPMENT в отделе → ✅
    - Изменение:
        - admin/staff/superuser → ✅
        - модельные права (change_equipment) → ✅
        - начальник отдела оборудования → ✅
        - скоуп-право MANAGE_EQUIPMENT в отделе → ✅
        - ответственный за оборудование → ✅
    - Удаление:
        - admin/staff/superuser → ✅
        - модельные права (delete_equipment) → ✅
        - начальник отдела оборудования → ✅
        - НЕ уполномоченный, НЕ ответственный
    """

    def _is_admin(self, user) -> bool:
        """Проверяет, является ли пользователь админом."""
        return getattr(user, "is_superuser", False) or getattr(
            user, "is_staff", False
        )

    def _has_model_perm(self, user, action: str) -> bool:
        """Проверяет модельные права на оборудование."""
        perm_map = {
            "create": "procurement.add_equipment",
            "update": "procurement.change_equipment",
            "partial_update": "procurement.change_equipment",
            "destroy": "procurement.delete_equipment",
        }
        perm = perm_map.get(action)
        return perm and user.has_perm(perm)

    def _get_dept_id_from_request(self, request) -> int | None:
        """Извлекает ID отдела из данных запроса."""
        dept_id = request.data.get("department")
        if dept_id is not None:
            try:
                return int(dept_id)
            except (ValueError, TypeError):
                pass
        return None

    def _is_dept_head(self, user, dept_id: int) -> bool:
        """Проверяет, является ли пользователь начальником отдела."""
        return Department.objects.filter(id=dept_id, head_id=user.id).exists()

    def _has_scoped_perm(self, user, dept_id: int) -> bool:
        """Проверяет наличие скоуп-права MANAGE_EQUIPMENT в отделе."""
        return has_dept_perm(user, dept_id, DeptPerm.MANAGE_EQUIPMENT)

    def _get_user_departments(self, user) -> list[int]:
        """Возвращает список ID отделов, где пользователь состоит."""
        return list(
            EmployeeDepartment.objects.filter(
                employee_id=user.id, is_active=True
            ).values_list("department_id", flat=True)
        )

    def has_permission(self, request, view) -> bool:
        """Проверка доступа на уровне запроса."""
        user = request.user
        if not user or not user.is_authenticated:
            return False

        # Чтение доступно всем аутентифицированным
        if request.method in permissions.SAFE_METHODS:
            return True

        # Админы могут всё
        if self._is_admin(user):
            return True

        action = getattr(view, "action", None)

        # Модельные права дают полный доступ
        if self._has_model_perm(user, action):
            return True

        # Для создания нужен отдел из запроса
        if action == "create":
            dept_id = self._get_dept_id_from_request(request)
            if dept_id is None:
                return False

            # Начальник отдела может создавать
            if self._is_dept_head(user, dept_id):
                return True

            # Проверяем скоуп-право в отделе
            if self._has_scoped_perm(user, dept_id):
                return True

            return False

        # Для update/delete проверка будет на уровне объекта
        if action in ("update", "partial_update", "destroy"):
            # Пропускаем на has_object_permission
            return True

        return False

    def has_object_permission(self, request, view, obj) -> bool:
        """Проверка доступа к конкретному объекту."""
        user = request.user
        if not user or not user.is_authenticated:
            return False

        # Чтение доступно всем
        if request.method in permissions.SAFE_METHODS:
            return True

        # Админы могут всё
        if self._is_admin(user):
            return True

        action = getattr(view, "action", None)

        # Модельные права
        if self._has_model_perm(user, action):
            return True

        dept_id = obj.department_id

        # Начальник отдела оборудования
        if self._is_dept_head(user, dept_id):
            return True

        # Удаление — только админ, модельные права или начальник
        if action == "destroy":
            return False

        # Изменение: скоуп-право или ответственный
        if action in ("update", "partial_update"):
            # Скоуп-право в отделе
            if self._has_scoped_perm(user, dept_id):
                return True

            # Ответственный за оборудование
            if obj.responsible_person_id == user.id:
                return True

        return False


class CanManageEquipmentCategory(permissions.BasePermission):
    """Права на справочник категорий оборудования.

    Категории являются глобальным справочником, поэтому для чтения
    достаточно аутентификации, а изменение доступно только staff/
    superuser или пользователям с модельными правами.
    """

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if request.method in permissions.SAFE_METHODS:
            return True

        if getattr(user, "is_superuser", False) or getattr(
            user, "is_staff", False
        ):
            return True

        perm_map = {
            "create": "procurement.add_equipmentcategory",
            "update": "procurement.change_equipmentcategory",
            "partial_update": "procurement.change_equipmentcategory",
            "destroy": "procurement.delete_equipmentcategory",
        }
        permission = perm_map.get(getattr(view, "action", None))
        return bool(permission and user.has_perm(permission))


class CanManageSupplier(permissions.BasePermission):
    """Проверка права на управление поставщиками."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Чтение доступно всем сотрудникам
        if request.method in permissions.SAFE_METHODS:
            return True

        # Создание/изменение - только для staff
        return request.user.is_staff or request.user.has_perm(
            "procurement.add_supplier"
        )


class IsResponsibleForEquipment(permissions.BasePermission):
    """Проверка, что пользователь - ответственный за оборудование."""

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        return request.user.is_staff or obj.responsible_person == request.user

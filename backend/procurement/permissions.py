"""
Права доступа для модуля закупок.
"""

from rest_framework import permissions

from employees.models import Employee


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


class IsFinanceManager(permissions.BasePermission):
    """Проверка, что пользователь - финансовый менеджер."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser or request.user.is_staff:
            return True

        # Проверяем наличие права на управление бюджетами
        return request.user.has_perm('procurement.change_budget')


class IsDirector(permissions.BasePermission):
    """Проверка, что пользователь - директор."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Директор = суперпользователь или есть специальное право
        return (
            request.user.is_superuser or
            request.user.has_perm('procurement.approve_procurementrequest')
        )


class CanCreateProcurementRequest(permissions.BasePermission):
    """Проверка права на создание заявки на закупку."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.method in permissions.SAFE_METHODS:
            return True

        if request.method == 'POST':
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
        if request.method in ['PUT', 'PATCH', 'DELETE']:
            return (
                obj.requestor == request.user and
                obj.is_editable
            )

        return False


class CanApproveProcurementRequest(permissions.BasePermission):
    """Проверка права на согласование заявки."""

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        # Получаем требуемые роли для согласования
        required_roles = obj.get_required_approvals()

        # Проверяем, имеет ли пользователь одну из требуемых ролей
        from procurement.constants import ApprovalRole

        if ApprovalRole.DEPARTMENT_HEAD in required_roles:
            # Руководитель отдела заявителя
            if obj.department.head == request.user:
                return True

        if ApprovalRole.FINANCE_MANAGER in required_roles:
            # Финансовый менеджер
            if request.user.has_perm('procurement.change_budget'):
                return True

        if ApprovalRole.DIRECTOR in required_roles:
            # Директор
            if request.user.has_perm(
                'procurement.approve_procurementrequest'
            ):
                return True

        return False


class CanManageEquipment(permissions.BasePermission):
    """Проверка права на управление оборудованием."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Чтение доступно всем сотрудникам
        if request.method in permissions.SAFE_METHODS:
            return True

        # Создание/изменение - только для staff или с правами
        return (
            request.user.is_staff or
            request.user.has_perm('procurement.add_equipment')
        )

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        # Чтение доступно всем
        if request.method in permissions.SAFE_METHODS:
            return True

        # Изменение - только staff или ответственный
        return (
            request.user.is_staff or
            obj.responsible_person == request.user or
            request.user.has_perm('procurement.change_equipment')
        )


class CanManageBudget(permissions.BasePermission):
    """Проверка права на управление бюджетами."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Чтение доступно руководителям отделов
        if request.method in permissions.SAFE_METHODS:
            return (
                request.user.is_staff or
                request.user.led_departments.exists()
            )

        # Создание/изменение - только финансовые менеджеры
        return (
            request.user.is_staff or
            request.user.has_perm('procurement.change_budget')
        )


class CanManageSupplier(permissions.BasePermission):
    """Проверка права на управление поставщиками."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Чтение доступно всем сотрудникам
        if request.method in permissions.SAFE_METHODS:
            return True

        # Создание/изменение - только для staff
        return (
            request.user.is_staff or
            request.user.has_perm('procurement.add_supplier')
        )


class IsResponsibleForEquipment(permissions.BasePermission):
    """Проверка, что пользователь - ответственный за оборудование."""

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        return (
            request.user.is_staff or
            obj.responsible_person == request.user
        )

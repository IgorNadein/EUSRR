from rest_framework import permissions
from employees.models import Department


class IsDepartmentHeadOrAdmin(permissions.BasePermission):
    """
    Доступ разрешён только админам или руководителю отдела.
    """

    def has_permission(self, request, view):
        # Для списков — только админы видят все отделы
        return request.user and (
            request.user.is_staff or request.user.is_superuser
        )

    def has_object_permission(self, request, view, obj):
        # obj — это объект Department
        return (
            request.user and (
                request.user.is_staff or
                request.user.is_superuser or
                (isinstance(obj, Department) and obj.head == request.user)
            )
        )


class IsSelfOrAdmin(permissions.BasePermission):
    """
    Разрешает изменение только самому сотруднику или администратору.
    """

    def has_object_permission(self, request, view, obj):
        # obj — это объект Employee
        return (
            request.user and request.user.is_authenticated and (
                request.user == obj or
                request.user.is_staff or
                request.user.is_superuser
            )
        )


class IsHR(permissions.BasePermission):
    """
    Только HR (или админ/суперпользователь).
    """
    def has_permission(self, request, view):
        user = request.user
        return (
            user.is_authenticated and (
                getattr(user, 'is_hr', False) or user.is_staff or user.is_superuser
            )
        )
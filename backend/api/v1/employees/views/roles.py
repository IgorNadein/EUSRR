"""DepartmentRoleViewSet — CRUD ролей отделов."""

from __future__ import annotations

from employees.models import (
    DepartmentPermission,
    DepartmentRole,
    DeptPerm,
    RoleAssignment,
)
from employees.utils import _ensure_department_permissions
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ...permissions import AdminOrDeptAllowed
from ..serializers import DepartmentRoleSerializer
from ._helpers import Employee


class DepartmentRoleViewSet(viewsets.ModelViewSet):
    """
    Роли отдела:
      - list/retrieve с фильтром ?department=<id>
      - create/update/destroy → требуется право DeptPerm.ASSIGN_ROLE
      - GET  /department-roles/perm_choices/
      - GET  /department-roles/{id}/perms/
      - POST /department-roles/{id}/set_perms
    """

    queryset = (
        DepartmentRole.objects.select_related("department")
        .prefetch_related("scoped_permissions")
        .all()
    )
    serializer_class = DepartmentRoleSerializer

    class AssignRolePerm(AdminOrDeptAllowed):
        """Право на назначение ролей участникам отдела."""

        required_code = DeptPerm.ASSIGN_ROLE

        def has_permission(self, request, view) -> bool:
            if getattr(view, "action", None) in {
                "update",
                "partial_update",
                "destroy",
                "set_perms",
                "assign",
                "revoke",
            }:
                user = getattr(request, "user", None)
                return bool(user and user.is_authenticated)
            return super().has_permission(request, view)

    ordering_fields = ("name", "id")
    ordering = ("name", "id")

    def _active_assignments_count(self, role: DepartmentRole) -> int:
        employee_ids = set(
            role.assignments.filter(is_active=True).values_list(
                "employee_id", flat=True
            )
        )
        employee_ids.update(
            role.members.filter(is_active=True).values_list(
                "employee_id", flat=True
            )
        )
        return len(employee_ids)

    def get_permissions(self):
        if self.action in {
            "create",
            "update",
            "partial_update",
            "destroy",
            "set_perms",
            "assign",
            "revoke",
        }:
            return [self.AssignRolePerm()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        dept = self.request.query_params.get("department")
        if dept:
            qs = qs.filter(department_id=dept)

        ord_param = self.request.query_params.get("ordering")
        if ord_param in {"name", "-name", "id", "-id"}:
            qs = qs.order_by(
                ord_param, "id" if not ord_param.startswith("-") else "-id"
            )
        else:
            qs = qs.order_by(*self.ordering)
        return qs

    def create(self, request, *args, **kwargs):
        """Создание роли."""
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        self.perform_create(ser)
        role = ser.instance
        return Response(
            self.get_serializer(role).data, status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        """Обновление роли."""
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        raw_department = request.data.get("department")
        if raw_department is not None and str(raw_department) != str(instance.department_id):
            return Response(
                {"department": ["Роль нельзя перенести в другой отдел."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ser = self.get_serializer(instance, data=request.data, partial=partial)
        ser.is_valid(raise_exception=True)
        self.perform_update(ser)
        return Response(ser.data)

    def partial_update(self, request, *args, **kwargs):
        """Частичное обновление роли."""
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Удаление роли."""
        instance = self.get_object()
        active_assignments_count = self._active_assignments_count(instance)
        force = str(request.query_params.get("force", "")).lower() in {
            "1",
            "true",
            "yes",
        }
        if active_assignments_count and not force:
            return Response(
                {
                    "detail": "У роли есть активные назначения.",
                    "active_assignments_count": active_assignments_count,
                    "force_required": True,
                },
                status=status.HTTP_409_CONFLICT,
            )
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"])
    def perm_choices(self, request):
        """Справочник скоуп-прав для ролей отдела из DeptPerm.CHOICES."""
        data = _ensure_department_permissions()
        return Response({"count": len(data), "results": data}, status=200)

    @action(detail=True, methods=["get"])
    def perms(self, request, pk=None):
        """Список прав, назначенных данной роли."""
        role = self.get_object()
        data = [
            {"id": p.id, "code": p.code, "name": p.name}
            for p in role.scoped_permissions.order_by("code")
        ]
        return Response({"count": len(data), "results": data}, status=200)

    @action(detail=True, methods=["post"])
    def set_perms(self, request, pk=None):
        """Полностью заменяет набор прав у роли."""
        role = self.get_object()

        ids = request.data.get("permission_ids") or []
        codes = request.data.get("permission_codes") or []

        if isinstance(ids, list) and ids:
            ids_int = {int(i) for i in ids if str(i).isdigit()}
            qs = DepartmentPermission.objects.filter(id__in=ids_int)
            if qs.count() != len(ids_int):
                return Response(
                    {"detail": "Некоторые permission_ids не найдены."},
                    status=400,
                )
        elif isinstance(codes, list) and codes:
            codes_set = set(codes)
            qs = DepartmentPermission.objects.filter(code__in=codes_set)
            if qs.count() != len(codes_set):
                return Response(
                    {"detail": "Некоторые permission_codes не найдены."},
                    status=400,
                )
        else:
            qs = DepartmentPermission.objects.none()

        role.scoped_permissions.set(list(qs))
        ser = self.get_serializer(role)
        return Response(ser.data, status=200)

    @action(detail=True, methods=["get"])
    def assignments(self, request, pk=None):
        """Список назначений роли (RoleAssignment)."""
        role = self.get_object()
        qs = RoleAssignment.objects.filter(role=role).select_related(
            "employee", "assigned_by"
        )

        active = request.query_params.get("active", "true").lower()
        if active == "true":
            qs = qs.filter(is_active=True)
        elif active == "false":
            qs = qs.filter(is_active=False)

        data = [
            {
                "id": a.id,
                "employee_id": a.employee_id,
                "employee_name": str(a.employee) if a.employee else None,
                "assigned_at": a.assigned_at.isoformat()
                if a.assigned_at
                else None,
                "assigned_by_id": a.assigned_by_id,
                "assigned_by_name": str(a.assigned_by)
                if a.assigned_by
                else None,
                "is_active": a.is_active,
            }
            for a in qs.order_by("-assigned_at")
        ]
        return Response({"count": len(data), "results": data}, status=200)

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        """Назначает роль сотруднику."""
        role = self.get_object()
        employee_id = request.data.get("employee_id")

        if not employee_id:
            return Response({"detail": "employee_id is required."}, status=400)

        try:
            employee = Employee.objects.get(id=employee_id)
        except Employee.DoesNotExist:
            return Response({"detail": "Сотрудник не найден."}, status=404)

        assigned_by = request.user if request.user.is_authenticated else None

        assignment, created = RoleAssignment.objects.update_or_create(
            employee=employee,
            role=role,
            defaults={
                "is_active": True,
                "assigned_by": assigned_by,
            },
        )
        return Response(
            {
                "id": assignment.id,
                "employee_id": assignment.employee_id,
                "role_id": assignment.role_id,
                "assigned_at": assignment.assigned_at.isoformat()
                if assignment.assigned_at
                else None,
                "is_active": assignment.is_active,
            },
            status=201,
        )

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        """Отзывает роль у сотрудника."""
        role = self.get_object()
        employee_id = request.data.get("employee_id")

        if not employee_id:
            return Response({"detail": "employee_id is required."}, status=400)

        try:
            employee = Employee.objects.get(id=employee_id)
        except Employee.DoesNotExist:
            return Response({"detail": "Сотрудник не найден."}, status=404)

        for assignment in RoleAssignment.objects.filter(
            employee=employee,
            role=role,
            is_active=True,
        ):
            assignment.is_active = False
            assignment.save(update_fields=["is_active"])
        return Response(status=204)

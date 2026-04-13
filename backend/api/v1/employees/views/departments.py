"""DepartmentViewSet — CRUD отделов + действия (set_head, add_member и т.д.)."""

from __future__ import annotations

import logging
from typing import Any, Dict

from django.db.models import (
    Case,
    Count,
    Exists,
    F,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from employees.models import (
    Department,
    DepartmentRole,
    DeptPerm,
    EmployeeDepartment,
    RoleAssignment,
)
from employees.utils import (
    _build_links_for_dept,
    _other_active_department_link,
    _validate_head_active,
)
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ...permissions import (
    AdminOrActionOrModelPerms,
    AdminOrDeptAllowed,
    has_dept_perm,
)
from ..serializers import (
    AddMemberInput,
    DepartmentBriefSerializer,
    DepartmentSerializer,
    EmployeeBriefSerializer,
    RemoveMemberInput,
    SetHeadInput,
    SetMemberRoleInput,
)

logger = logging.getLogger(__name__)


class DepartmentViewSet(viewsets.ModelViewSet):
    """
    CRUD отделов + действия:
      - POST /departments/{id}/set_head
      - POST /departments/{id}/set_member_role
      - POST /departments/{id}/add_member
      - POST /departments/{id}/remove_member
    Права:
      - update/partial_update/destroy → manage_department
      - set_head                   → change_department_head
            - set_member_role           → assign_department_role
                (назначение/снятие роли)
            - add_member/remove_member  → manage_department
                (управление участниками)
      - create                    → staff/superuser
      - чтение                    → аутентифицированным
    """

    queryset = (
        Department.objects.select_related("head")
        .prefetch_related("roles")
        .all()
    )
    serializer_class = DepartmentSerializer

    # пермишены (скоуп-право по отделу)
    class ManagePerm(AdminOrDeptAllowed):
        """Право на общее управление отделом."""

        required_code = DeptPerm.MANAGE

    class ChangeHeadPerm(AdminOrDeptAllowed):
        """Право на смену руководителя отдела."""

        required_code = DeptPerm.CHANGE_HEAD

    class AssignRolePerm(AdminOrDeptAllowed):
        """Право на назначение ролей участникам отдела."""

        required_code = DeptPerm.ASSIGN_ROLE

    def get_permissions(self):
        if self.action in {"update", "partial_update", "destroy"}:
            return [self.ManagePerm()]
        if self.action == "set_head":
            return [self.ChangeHeadPerm()]
        if self.action in {"set_member_role"}:
            return [self.AssignRolePerm()]
        if self.action in {"add_member", "remove_member"}:
            return [self.ManagePerm()]
        if self.action == "create":
            return [AdminOrActionOrModelPerms()]
        if self.action in {
            "members",
            "user_perms",
            "list",
            "retrieve",
            "my_departments",
        }:
            return [IsAuthenticated()]
        return [AdminOrActionOrModelPerms()]

    # --- поиск и сортировка ---
    ordering = ["name"]
    ordering_fields = ["name", "id"]

    def get_queryset(self):
        qs = super().get_queryset()

        # ---------- аннотации для employees_count ----------
        active_links = EmployeeDepartment.objects.filter(
            department_id=OuterRef("pk"), is_active=True
        )

        active_count_subq = (
            active_links.values("department_id")
            .annotate(c=Count("employee_id", distinct=True))
            .values("c")[:1]
        )

        qs = qs.annotate(
            active_count=Coalesce(
                Subquery(active_count_subq, output_field=IntegerField()),
                Value(0),
            ),
            head_in_active=Exists(
                active_links.filter(employee_id=OuterRef("head_id"))
            ),
        ).annotate(
            employees_count=F("active_count")
            + Case(
                When(
                    Q(head_id__isnull=False) & Q(head_in_active=False),
                    then=Value(1),
                ),
                default=Value(0),
                output_field=IntegerField(),
            )
        )

        search = (
            self.request.query_params.get("search")
            or self.request.query_params.get("q")
            or ""
        ).strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(description__icontains=search)
                | Q(head__first_name__icontains=search)
                | Q(head__last_name__icontains=search)
                | Q(head__patronymic__icontains=search)
            ).distinct()

        ordering = self.request.query_params.get("ordering")
        if ordering in {"name", "-name", "id", "-id"}:
            qs = qs.order_by(ordering)
        else:
            qs = qs.order_by("name")
        return qs

    def _extract_department_ldap_changes(
        self, instance: Department, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Собирает diff значимых LDAP-полей до сохранения."""
        changes: Dict[str, Any] = {}
        for field in ("name", "description"):
            if field not in data:
                continue
            new_value = data.get(field)
            if new_value != getattr(instance, field):
                changes[field] = new_value
        return changes

    def _mark_department_sync_attrs(
        self,
        instance: Department,
        *,
        changes: Dict[str, Any] | None = None,
        sync_head: bool = False,
    ) -> None:
        """Передаёт post_save сигналу точный diff отдела."""
        if changes:
            existing = getattr(instance, "_ldap_changes", {}) or {}
            if not isinstance(existing, dict):
                existing = {}
            existing.update(changes)
            instance._ldap_changes = existing
        if sync_head:
            instance._ldap_sync_head = True

    # --- частичное изменение ---

    def _perform_set_head(
        self, instance: Department, desired_head_id: int | None, request
    ) -> Response | Department:
        """Общая логика назначения руководителя.

        Используется для set_head action и partial_update.

        Возвращает Response при ошибке или обновлённый Department при успехе.
        """
        # Проверка прав
        perm = self.ChangeHeadPerm()
        has_perm = perm.has_permission(
            request, self
        ) and perm.has_object_permission(request, self, instance)
        if not has_perm:
            return Response(
                {"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN
            )

        # Если тот же руководитель — пропустим
        if (desired_head_id or None) == (instance.head_id or None):
            return instance

        # Валидация кандидата
        new_head = None
        if desired_head_id is not None:
            employee_model = Department._meta.get_field(
                "head"
            ).remote_field.model
            new_head = get_object_or_404(employee_model, id=desired_head_id)

            require_verified = not (
                instance.head_id
                and instance.head_id == getattr(request.user, "id", None)
            )
            ok, errs = _validate_head_active(
                instance,
                desired_head_id,
                require_email_verified=require_verified,
            )
            if not ok:
                return Response(errs, status=status.HTTP_400_BAD_REQUEST)

        # Обновляем руководителя (сигналы синхронизируют с LDAP)
        instance.head = new_head
        if new_head:
            instance.head_appointed_at = timezone.now()
        else:
            instance.head_appointed_at = None
        self._mark_department_sync_attrs(instance, sync_head=True)
        instance.save(update_fields=["head", "head_appointed_at"])

        return instance

    def perform_update(self, serializer):
        """Обновление отдела с фиксацией LDAP diff до save()."""
        instance = serializer.instance
        validated_data = serializer.validated_data
        self._mark_department_sync_attrs(
            instance,
            changes=self._extract_department_ldap_changes(
                instance, validated_data
            ),
            sync_head=(
                "head" in validated_data
                and validated_data.get("head") != instance.head
            ),
        )
        serializer.save()

    def partial_update(self, request, *args, **kwargs) -> Response:
        """Частичный апдейт отдела."""
        instance = self.get_object()
        data: Dict[str, Any] = request.data

        # --- HEAD ---
        if any(k in data for k in ("head", "head_id")):
            raw_desired = data.get("head_id", data.get("head", None))

            try:
                if isinstance(
                    raw_desired, str
                ) and raw_desired.strip().lower() in {
                    "",
                    "null",
                    "none",
                }:
                    desired_head_id = None
                else:
                    try:
                        desired_head_id = (
                            int(raw_desired)
                            if raw_desired is not None
                            else None
                        )
                    except (TypeError, ValueError):
                        raise ValueError(
                            "head_id должен быть целым числом или null"
                        )
            except ValueError as e:
                return Response(
                    {"head_id": [str(e)]}, status=status.HTTP_400_BAD_REQUEST
                )

            # Используем общий метод
            result = self._perform_set_head(instance, desired_head_id, request)
            if isinstance(result, Response):
                return result
            instance = result

        # --- NAME / DESCRIPTION ---
        changes = self._extract_department_ldap_changes(instance, data)

        if changes:
            for k, v in changes.items():
                setattr(instance, k, v)
            self._mark_department_sync_attrs(instance, changes=changes)
            instance.save(update_fields=list(changes.keys()))

        return Response(
            self.get_serializer(instance).data, status=status.HTTP_200_OK
        )

    # -------- actions --------

    @action(detail=True, methods=["post"])
    def set_head(self, request, pk: str | None = None) -> Response:
        """Назначение/снятие руководителя отдела."""
        dept = self.get_object()

        payload = SetHeadInput(data=request.data)
        payload.is_valid(raise_exception=True)
        head_id = payload.validated_data.get("head_id")

        # Используем общий метод
        result = self._perform_set_head(dept, head_id, request)
        if isinstance(result, Response):
            return result

        return Response(
            self.get_serializer(result).data, status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["post"])
    def set_member_role(self, request, pk=None):
        """
        Назначает/снимает РОЛЬ сотруднику в контексте отдела.

        Если сотрудник — член отдела, обновляет EmployeeDepartment.role.
        Если нет — создаёт/обновляет RoleAssignment.
        """
        dept = self.get_object()
        payload = SetMemberRoleInput(data=request.data)
        if not payload.is_valid():
            return Response(payload.errors, status=400)

        emp_id = payload.validated_data["employee_id"]
        role_id = payload.validated_data.get("role_id")

        employee_model = Department._meta.get_field("head").remote_field.model
        employee = get_object_or_404(employee_model, id=emp_id)
        role = None
        if role_id is not None:
            role = get_object_or_404(DepartmentRole, id=role_id)
            if role.department_id != dept.id:
                return Response(
                    {"role_id": ["Role does not belong to this department."]},
                    status=400,
                )

        # Проверяем, является ли сотрудник членом отдела
        link = EmployeeDepartment.objects.filter(
            employee_id=emp_id,
            department_id=dept.id,
            is_active=True,
        ).first()

        via_assignment = False

        active_assignments = list(
            RoleAssignment.objects.filter(
                employee_id=emp_id,
                role__department=dept,
                is_active=True,
            ).select_related("role")
        )

        def deactivate_assignment(assignment: RoleAssignment) -> None:
            assignment.is_active = False
            assignment.save(update_fields=["is_active"])

        if link:
            # Сотрудник — член отдела: сперва приводим RoleAssignment
            # к единственному актуальному значению, затем обновляем link.role.
            for assignment in active_assignments:
                if role is None or assignment.role_id != role.id:
                    deactivate_assignment(assignment)

            if role:
                RoleAssignment.objects.update_or_create(
                    employee_id=emp_id,
                    role=role,
                    defaults={"is_active": True, "assigned_by": request.user},
                )

            link.role = role
            link.save(update_fields=["role"])
        else:
            # Сотрудник НЕ член отдела: используем только RoleAssignment
            via_assignment = True

            if role:
                for assignment in active_assignments:
                    if assignment.role_id != role.id:
                        deactivate_assignment(assignment)
                RoleAssignment.objects.update_or_create(
                    employee=employee,
                    role=role,
                    defaults={"is_active": True, "assigned_by": request.user},
                )
            else:
                for assignment in active_assignments:
                    deactivate_assignment(assignment)

        return Response(
            {
                "employee_id": emp_id,
                "role_id": (role.id if role else None),
                "is_active": link.is_active if link else True,
                "via_assignment": via_assignment,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], url_path="members")
    def members(self, request, pk=None):
        """GET /api/v1/departments/{id}/members/ — список участников отдела."""
        dept = self.get_object()
        links = _build_links_for_dept(dept, EmployeeBriefSerializer)
        return Response({"count": len(links), "results": links}, status=200)

    @action(detail=True, methods=["get"], url_path="user-perms")
    def user_perms(self, request, pk=None):
        """GET /api/v1/departments/{id}/user-perms/.

        Возвращает флаги прав текущего пользователя.
        """
        dept = self.get_object()
        uid = getattr(request.user, "id", None)
        data = {
            "is_head": bool(uid and uid == dept.head_id),
            "can_manage": has_dept_perm(request.user, dept.id, DeptPerm.MANAGE),
            "can_change_head": has_dept_perm(
                request.user, dept.id, DeptPerm.CHANGE_HEAD
            ),
            "can_assign_roles": has_dept_perm(
                request.user, dept.id, DeptPerm.ASSIGN_ROLE
            ),
        }
        return Response(data, status=200)

    @action(detail=True, methods=["post"], url_path="add_member")
    def add_member(self, request, pk: int | None = None):
        """Добавляет сотрудника в отдел."""
        dept = self.get_object()
        payload = AddMemberInput(data=request.data)
        payload.is_valid(raise_exception=True)

        emp_id = payload.validated_data["employee_id"]

        employee_model = Department._meta.get_field("head").remote_field.model
        employee = get_object_or_404(employee_model, id=emp_id)

        if getattr(employee, "is_active", True) is False:
            return Response(
                {"employee_id": ["Employee is inactive."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        other_active_link = _other_active_department_link(
            emp_id,
            exclude_department_id=dept.id,
        )
        if other_active_link is not None:
            return Response(
                {
                    "employee_id": [
                        (
                            "Employee already belongs to another active "
                            f"department: {other_active_link.department.name}."
                        )
                    ]
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        link, created = EmployeeDepartment.objects.get_or_create(
            employee_id=emp_id,
            department_id=dept.id,
            defaults={"is_active": True},
        )
        if not created and not link.is_active:
            link.is_active = True
            link.save(update_fields=["is_active"])

        return Response(
            {
                "employee_id": emp_id,
                "is_active": True,
                "role_id": link.role_id,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="remove_member")
    def remove_member(self, request, pk: int | None = None):
        """Удаляет члена отдела."""
        dept = self.get_object()

        payload = RemoveMemberInput(data=request.data)
        payload.is_valid(raise_exception=True)
        emp_id: int = payload.validated_data["employee_id"]

        employee_model = Department._meta.get_field("head").remote_field.model
        get_object_or_404(employee_model, id=emp_id)
        if dept.head_id == emp_id:
            return Response(
                {"detail": "Нельзя удалить руководителя отдела."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            link = EmployeeDepartment.objects.get(
                employee_id=emp_id, department_id=dept.id
            )
            link.is_active = False
            link.save(update_fields=["is_active"])
            return Response(
                {"employee_id": emp_id, "removed": True},
                status=status.HTTP_200_OK,
            )
        except EmployeeDepartment.DoesNotExist:
            return Response(
                {"detail": "Employee is not a member of this department."},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=False, methods=["get"], url_path="my-departments")
    def my_departments(self, request) -> Response:
        """Вернёт список отделов, доступных текущему пользователю."""
        user = request.user
        qs = self.get_queryset()

        active_link_exists = EmployeeDepartment.objects.filter(
            department_id=OuterRef("pk"),
            employee_id=user.id,
            is_active=True,
        )
        user_qs = qs.filter(
            Q(head_id=user.id) | Exists(active_link_exists)
        ).distinct()

        user_qs = user_qs.order_by("name", "id")
        data = DepartmentBriefSerializer(user_qs, many=True).data
        return Response(data)

"""DepartmentViewSet — CRUD отделов + действия (set_head, add_member и т.д.)."""

from __future__ import annotations

import logging
import traceback
from typing import Any, Dict

from django.db import transaction
from django.db.models import (Case, Count, Exists, F, IntegerField, OuterRef,
                              Q, Subquery, Value, When)
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from employees.ldap.directory_service import (DirectoryDepartmentDTO,
                                              DirectoryService)
from employees.ldap.errors import (DirectoryDbError, DirectoryLdapError,
                                   DirectoryServiceError)
from employees.models import (Department, DepartmentRole, DeptPerm,
                              EmployeeDepartment, RoleAssignment)
from employees.utils import (_build_links_for_dept, _head_choices_for_dept,
                             _perm_choices_synced, _validate_head_active)
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ...permissions import (AdminOrActionOrModelPerms, AdminOrDeptAllowed,
                            has_dept_perm)
from ..serializers import (AddMemberInput, DepartmentBriefSerializer,
                           DepartmentRoleSerializer, DepartmentSerializer,
                           EmployeeBriefSerializer, RemoveMemberInput,
                           SetHeadInput, SetMemberRoleInput)
from ._helpers import _is_ldap_enabled

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
      - set_member_role           → assign_department_role     (назначение/снятие роли)
      - add_member/remove_member  → manage_department          (управление участниками)
      - create                    → staff/superuser
      - чтение                    → аутентифицированным
    """

    queryset = Department.objects.select_related(
        "head").prefetch_related("roles").all()
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
            "ui_context",
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
            head_in_active=Exists(active_links.filter(
                employee_id=OuterRef("head_id"))),
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

    # --- частичное изменение ---

    def _perform_set_head(self, instance: Department, desired_head_id: int | None, request) -> Response | Department:
        """Общая логика назначения руководителя для set_head action и partial_update.

        Возвращает Response при ошибке или обновлённый Department при успехе.
        """
        # Проверка прав
        perm = self.ChangeHeadPerm()
        has_perm = perm.has_permission(request, self) and perm.has_object_permission(
            request, self, instance
        )
        if not has_perm:
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        # Если тот же руководитель — пропустим
        if (desired_head_id or None) == (instance.head_id or None):
            return instance

        # Валидация кандидата
        new_head = None
        if desired_head_id is not None:
            employee_model = Department._meta.get_field(
                "head").remote_field.model
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

        # LDAP → DB
        ldap_enabled = _is_ldap_enabled()
        if ldap_enabled:
            svc = DirectoryService()
            try:
                instance = svc.set_head(instance, new_head)
            except (
                DirectoryLdapError,
                DirectoryDbError,
                DirectoryServiceError,
            ) as e:
                code = (
                    status.HTTP_502_BAD_GATEWAY
                    if isinstance(e, DirectoryLdapError)
                    else (
                        status.HTTP_400_BAD_REQUEST
                        if isinstance(e, DirectoryServiceError)
                        else status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
                )
                return Response({"detail": str(e)}, status=code)
        else:
            instance.head = new_head
            if new_head:
                instance.head_appointed_at = timezone.now()
            else:
                instance.head_appointed_at = None
            instance.save(update_fields=["head", "head_appointed_at"])

        return instance

    def partial_update(self, request, *args, **kwargs) -> Response:
        """Частичный апдейт отдела через сервисный слой (LDAP → DB)."""
        instance = self.get_object()
        data: Dict[str, Any] = request.data
        ldap_enabled = _is_ldap_enabled()
        svc = DirectoryService() if ldap_enabled else None

        # --- HEAD ---
        if any(k in data for k in ("head", "head_id")):
            raw_desired = data.get("head_id", data.get("head", None))

            try:
                if isinstance(raw_desired, str) and raw_desired.strip().lower() in {
                    "",
                    "null",
                    "none",
                }:
                    desired_head_id = None
                else:
                    try:
                        desired_head_id = int(
                            raw_desired) if raw_desired is not None else None
                    except (TypeError, ValueError):
                        raise ValueError(
                            "head_id должен быть целым числом или null")
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
        changes: Dict[str, Any] = {}
        for k in ("name", "description"):
            if k in data:
                changes[k] = data.get(k)

        if changes:
            if ldap_enabled:
                try:
                    instance = svc.update_department(instance, changes)
                except DirectoryLdapError as e:
                    return Response(
                        {"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY
                    )
                except DirectoryDbError as e:
                    return Response(
                        {"detail": str(e)},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )
            else:
                for k, v in changes.items():
                    setattr(instance, k, v)
                instance.save(update_fields=list(changes.keys()))

        return Response(self.get_serializer(instance).data, status=status.HTTP_200_OK)

    # -------- actions --------

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def set_head(self, request, pk: str | None = None) -> Response:
        """Назначение/снятие руководителя отдела через сервисный слой (LDAP → DB)."""
        dept = self.get_object()

        payload = SetHeadInput(data=request.data)
        payload.is_valid(raise_exception=True)
        head_id = payload.validated_data.get("head_id")

        # Используем общий метод
        result = self._perform_set_head(dept, head_id, request)
        if isinstance(result, Response):
            return result

        return Response(self.get_serializer(result).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    @transaction.atomic
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
            employee_id=emp_id, department_id=dept.id
        ).first()

        via_assignment = False

        if link:
            # Сотрудник — член отдела: обновляем роль в линке
            svc = DirectoryService() if _is_ldap_enabled() else None

            if svc:
                try:
                    svc.set_member_role(dept, employee, role)
                except (
                    DirectoryLdapError,
                    DirectoryDbError,
                    DirectoryServiceError,
                ) as e:
                    return Response(
                        {"detail": str(e)},
                        status=(
                            502
                            if isinstance(e, DirectoryLdapError)
                            else 400
                            if isinstance(e, DirectoryServiceError)
                            else 500
                        ),
                    )
            else:
                link.role = role
                link.save(update_fields=["role"])

            # Также создаём/обновляем RoleAssignment для консистентности
            if role:
                RoleAssignment.objects.update_or_create(
                    employee_id=emp_id,
                    role=role,
                    defaults={"is_active": True, "assigned_by": request.user},
                )
            else:
                RoleAssignment.objects.filter(
                    employee_id=emp_id, role__department=dept, is_active=True
                ).update(is_active=False)
        else:
            # Сотрудник НЕ член отдела: используем только RoleAssignment
            via_assignment = True

            if role:
                from employees.ldap.services.department_service import \
                    DepartmentService
                from employees.ldap.services.group_service import GroupService
                from employees.ldap.services.user_service import UserService

                if _is_ldap_enabled():
                    try:
                        group_service = GroupService()
                        user_service = UserService(group_service)
                        dept_service = DepartmentService(
                            group_service, user_service)
                        dept_service.assign_role(employee, role, request.user)
                    except Exception as e:
                        return Response({"detail": str(e)}, status=400)
                else:
                    RoleAssignment.objects.update_or_create(
                        employee=employee,
                        role=role,
                        defaults={"is_active": True,
                                  "assigned_by": request.user},
                    )
            else:
                from employees.ldap.services.department_service import \
                    DepartmentService
                from employees.ldap.services.group_service import GroupService
                from employees.ldap.services.user_service import UserService

                active_assignments = RoleAssignment.objects.filter(
                    employee_id=emp_id, role__department=dept, is_active=True
                ).select_related("role")

                if _is_ldap_enabled():
                    try:
                        group_service = GroupService()
                        user_service = UserService(group_service)
                        dept_service = DepartmentService(
                            group_service, user_service)
                        for assignment in active_assignments:
                            dept_service.revoke_role(employee, assignment.role)
                    except Exception as e:
                        return Response({"detail": str(e)}, status=400)
                else:
                    active_assignments.update(is_active=False)

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
        """GET /api/v1/departments/{id}/user-perms/ — флаги прав текущего пользователя."""
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

    @action(detail=True, methods=["get"], url_path="ui-context")
    def ui_context(self, request, pk=None):
        """GET /api/v1/departments/{id}/ui-context/ — BFF-агрегатор для страницы отдела."""
        dept = self.get_object()
        dept_data = self.get_serializer(dept).data

        roles_qs = (
            DepartmentRole.objects.filter(department_id=dept.id)
            .prefetch_related("scoped_permissions")
            .order_by("name", "id")
        )
        roles_data = DepartmentRoleSerializer(roles_qs, many=True).data

        links = _build_links_for_dept(dept, EmployeeBriefSerializer)
        perm_choices = _perm_choices_synced()
        head_choices = _head_choices_for_dept(dept, EmployeeBriefSerializer)
        user_perms = {
            "is_head": (
                request.user.id == dept.head_id
                if getattr(request.user, "id", None)
                else False
            ),
            "can_manage": has_dept_perm(request.user, dept.id, DeptPerm.MANAGE),
            "can_change_head": has_dept_perm(
                request.user, dept.id, DeptPerm.CHANGE_HEAD
            ),
            "can_assign_roles": has_dept_perm(
                request.user, dept.id, DeptPerm.ASSIGN_ROLE
            ),
        }

        payload = {
            "dept": dept_data,
            "roles": roles_data,
            "links": links,
            "head_choices": head_choices,
            "dept_perm_choices": perm_choices,
            "user_perms": user_perms,
        }
        return Response(payload, status=200)

    @action(detail=True, methods=["post"], url_path="add_member")
    @transaction.atomic
    def add_member(self, request, pk: int | None = None):
        """Добавляет сотрудника в отдел: MOVE в OU → активирует линк (LDAP → DB)."""
        dept = self.get_object()
        payload = AddMemberInput(data=request.data)
        payload.is_valid(raise_exception=True)

        emp_id = payload.validated_data["employee_id"]

        employee_model = Department._meta.get_field("head").remote_field.model
        employee = get_object_or_404(employee_model, id=emp_id)

        ldap_enabled = _is_ldap_enabled()

        if ldap_enabled:
            svc = DirectoryService()
            try:
                svc.add_member(dept, employee)
                link = (
                    EmployeeDepartment.objects.filter(
                        employee_id=emp_id, department_id=dept.id
                    )
                    .only("role_id", "is_active")
                    .first()
                )

                return Response(
                    {
                        "employee_id": emp_id,
                        "is_active": True,
                        "role_id": getattr(link, "role_id", None) if link else None,
                    },
                    status=status.HTTP_200_OK,
                )
            except (DirectoryLdapError, DirectoryDbError, DirectoryServiceError) as e:
                return Response(
                    {"detail": str(e)},
                    status=(
                        status.HTTP_502_BAD_GATEWAY
                        if isinstance(e, DirectoryLdapError)
                        else (
                            status.HTTP_400_BAD_REQUEST
                            if isinstance(e, DirectoryServiceError)
                            else status.HTTP_500_INTERNAL_SERVER_ERROR
                        )
                    ),
                )
        else:
            link, created = EmployeeDepartment.objects.get_or_create(
                employee_id=emp_id, department_id=dept.id, defaults={
                    "is_active": True}
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
    @transaction.atomic
    def remove_member(self, request, pk: int | None = None):
        """Удаляет члена отдела: MOVE в Users OU → удаляет линк (LDAP → DB)."""
        dept = self.get_object()

        payload = RemoveMemberInput(data=request.data)
        payload.is_valid(raise_exception=True)
        emp_id: int = payload.validated_data["employee_id"]

        employee_model = Department._meta.get_field("head").remote_field.model
        employee = get_object_or_404(employee_model, id=emp_id)
        if dept.head_id == emp_id:
            return Response(
                {"detail": "Нельзя удалить руководителя отдела."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ldap_enabled = _is_ldap_enabled()

        if ldap_enabled:
            svc = DirectoryService()
            try:
                svc.remove_member(dept, employee)
                return Response(
                    {"employee_id": emp_id, "removed": True},
                    status=status.HTTP_200_OK,
                )
            except (DirectoryLdapError, DirectoryDbError, DirectoryServiceError) as e:
                return Response(
                    {"detail": str(e)},
                    status=(
                        502
                        if isinstance(e, DirectoryLdapError)
                        else 400
                        if isinstance(e, DirectoryServiceError)
                        else 500
                    ),
                )
        else:
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
        user_qs = qs.filter(Q(head_id=user.id) | Exists(
            active_link_exists)).distinct()

        user_qs = user_qs.order_by("name", "id")
        data = DepartmentBriefSerializer(user_qs, many=True).data
        return Response(data)

    def create(self, request, *args, **kwargs):
        """Создание отдела: сначала LDAP OU → затем запись Department."""
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        head = None
        head_id = ser.validated_data.get(
            "head") or ser.validated_data.get("head_id")
        if head_id:
            employee_model = Department._meta.get_field(
                "head").remote_field.model
            head = get_object_or_404(employee_model, id=head_id)

        ldap_enabled = _is_ldap_enabled()

        if ldap_enabled:
            dto = DirectoryDepartmentDTO(
                name=ser.validated_data["name"],
                description=ser.validated_data.get("description", ""),
                head=head,
            )
            svc = DirectoryService()
            try:
                dept = svc.create_department(dto)
                return Response(
                    self.get_serializer(
                        dept).data, status=status.HTTP_201_CREATED
                )
            except DirectoryLdapError as e:
                return Response({"detail": str(e)}, status=502)
            except DirectoryDbError as e:
                return Response({"detail": str(e)}, status=500)
        else:
            dept = Department.objects.create(
                name=ser.validated_data["name"],
                description=ser.validated_data.get("description", ""),
                head=head,
            )
            return Response(
                self.get_serializer(dept).data, status=status.HTTP_201_CREATED
            )

    def destroy(self, request, *args, **kwargs):
        """Удаляет отдел: сначала в LDAP → затем из БД."""
        dept = self.get_object()

        ldap_enabled = _is_ldap_enabled()

        if ldap_enabled:
            svc = DirectoryService()
            try:
                svc.delete_department(dept)
                return Response(status=204)
            except DirectoryLdapError as e:
                return Response({"detail": str(e)}, status=502)
            except DirectoryDbError as e:
                return Response({"detail": str(e)}, status=500)
        else:
            dept.delete()
            return Response(status=204)

"""EmployeeViewSet.

CRUD сотрудников, профиль, навыки, LDAP-info и Excel-экспорт.
"""

from __future__ import annotations

import logging

from common.emails import send_templated_mail
from django.contrib.contenttypes.models import ContentType
from django.db.models import Exists, Max, OuterRef, Prefetch, Q, Subquery
from django.utils.crypto import get_random_string
from employees.constants import (
    ACTION_DISMISSED,
    ACTIVATING_MARKER_ACTIONS,
    PERMANENT_ACTIONS,
)
from employees.models import (
    Department,
    EmployeeAction,
    EmployeeDepartment,
    RoleAssignment,
    Skill,
)
from employees.utils import _to_bool
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ...permissions import AdminOrActionOrModelPerms, IsSelfOrStaff
from ..serializers import EmployeeListSerializer, EmployeeSerializer
from ._helpers import Employee

logger = logging.getLogger(__name__)


class EmployeeViewSet(viewsets.ModelViewSet):
    """
    /api/v1/employees/

    CRUD для сотрудников + профиль текущего пользователя.

    Доступ:
      - GET list/retrieve          — только аутентифицированные пользователи.
      - POST (create)              — только staff/superuser.
            - PATCH/PUT/DELETE {id}      — staff/superuser ИЛИ пользователи
                с модельными правами.
            - GET/PATCH /employees/me/   — только аутентифицированные;
                PATCH правит профиль текущего пользователя.

    Поиск: last_name, first_name, patronymic, email, phone_number

    LDAP синхронизация происходит через Django сигналы (signals_ldap.py).
    """

    serializer_class = EmployeeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "last_name",
        "first_name",
        "patronymic",
        "email",
        "phone_number",
    ]
    ordering_fields = ["last_name", "first_name", "created_at", "id"]
    ordering = ["last_name", "first_name"]

    @staticmethod
    def _with_last_activity(queryset):
        return queryset.annotate(
            last_activity_at=Max(
                "auth_sessions__last_seen_at",
                filter=Q(auth_sessions__revoked_at__isnull=True),
            )
        )

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated(), AdminOrActionOrModelPerms()]
        if self.action == "destroy":
            return [IsAuthenticated(), AdminOrActionOrModelPerms()]
        if self.action in {"update", "partial_update"}:
            return [
                IsAuthenticated(),
                (IsSelfOrStaff | AdminOrActionOrModelPerms)(),
            ]
        return [IsAuthenticated()]

    def get_queryset(self):
        status_action_codes = PERMANENT_ACTIONS | ACTIVATING_MARKER_ACTIONS
        last_action_code_sq = Subquery(
            EmployeeAction.objects.filter(employee_id=OuterRef("pk"))
            .filter(action__in=status_action_codes)
            .order_by("-date")
            .values("action")[:1]
        )
        dep_links_prefetch = Prefetch(
            "departments_links",
            queryset=EmployeeDepartment.objects.filter(
                is_active=True
            ).select_related("department", "role"),
            to_attr="dept_links",
        )

        prefetches = [
            "skills",
            dep_links_prefetch,
            Prefetch(
                "actions", queryset=EmployeeAction.objects.order_by("-date")
            ),
        ]

        qs = self._with_last_activity(
            Employee.objects.select_related("position")
            .prefetch_related(*prefetches)
            .annotate(last_action_code=last_action_code_sq)
            .order_by(*self.ordering)
        )

        qp = self.request.query_params

        # по отделу
        dep = qp.get("department")
        if dep:
            try:
                dep_id = int(dep)
            except (TypeError, ValueError):
                dep_id = None
            if dep_id:
                member_ids = EmployeeDepartment.objects.filter(
                    department_id=dep_id
                ).values("employee_id")
                head_ids = Department.objects.filter(id=dep_id).values(
                    "head_id"
                )
                role_assignment_ids = RoleAssignment.objects.filter(
                    role__department_id=dep_id, is_active=True
                ).values("employee_id")

                qs = qs.filter(
                    Q(id__in=member_ids)
                    | Q(id__in=head_ids)
                    | Q(id__in=role_assignment_ids)
                ).distinct()

                qs = qs.annotate(
                    _is_dept_member=Exists(
                        EmployeeDepartment.objects.filter(
                            employee_id=OuterRef("pk"),
                            department_id=dep_id,
                            is_active=True,
                        )
                    ),
                    _is_dept_head=Exists(
                        Department.objects.filter(
                            id=dep_id, head_id=OuterRef("pk")
                        )
                    ),
                    _has_role_assignment=Exists(
                        RoleAssignment.objects.filter(
                            employee_id=OuterRef("pk"),
                            role__department_id=dep_id,
                            is_active=True,
                        )
                    ),
                )

                self.request._department_filter_id = dep_id

        # по должности
        position = qp.get("position")
        if position:
            qs = qs.filter(position_id=position)

        # по навыкам (any-of)
        skill_ids = qp.getlist("skill")
        if skill_ids:
            qs = qs.filter(skills__in=skill_ids).distinct()

        # статусы
        email_verified = _to_bool(qp.get("email_verified"))
        if email_verified is not None:
            qs = qs.filter(email_verified=email_verified)

        active = _to_bool(qp.get("active"))
        if active is not None:
            qs = qs.filter(is_active=active)

        actually = _to_bool(qp.get("actually_active"))
        if actually is True:
            qs = qs.filter(
                Q(email_verified=True)
                & (
                    Q(last_action_code__isnull=True, is_active=True)
                    | ~Q(last_action_code=ACTION_DISMISSED)
                )
            )
        elif actually is False:
            qs = qs.exclude(
                Q(email_verified=True)
                & (
                    Q(last_action_code__isnull=True, is_active=True)
                    | ~Q(last_action_code=ACTION_DISMISSED)
                )
            )

        created_at_gte = qp.get("created_at__gte")
        if created_at_gte:
            qs = qs.filter(created_at__gte=created_at_gte)

        return qs

    def _attach_linked_task_payloads(self, employees: list[Employee]) -> None:
        """Предзагрузить компактные бейджи задач для списка сотрудников."""
        if not employees:
            return

        user = getattr(self.request, "user", None)
        employee_ids = [employee.id for employee in employees]
        mapping = {employee_id: [] for employee_id in employee_ids}

        if user and user.is_authenticated:
            from tasks.access import task_board_access_q
            from tasks.models import (
                TaskBoard,
                TaskLinkedObject,
                TaskLinkedObjectKind,
            )

            employee_ct = ContentType.objects.get_for_model(Employee)
            accessible_boards = TaskBoard.objects.filter(
                is_archived=False,
            ).filter(task_board_access_q(user))

            links = (
                TaskLinkedObject.objects.filter(
                    kind=TaskLinkedObjectKind.EMPLOYEE,
                    content_type=employee_ct,
                    object_id__in=employee_ids,
                    task__board__in=accessible_boards,
                )
                .select_related("task", "task__board", "task__column")
                .order_by("object_id", "task__title", "task_id")
            )

            for link in links:
                mapping.setdefault(link.object_id, []).append(
                    {
                        "link_id": link.id,
                        "id": link.task_id,
                        "title": link.task.title,
                        "board_id": link.task.board_id,
                        "board_name": link.task.board.name,
                        "column_id": link.task.column_id,
                        "column_name": link.task.column.name,
                        "column_color": link.task.column.color,
                        "priority": link.task.priority,
                        "priority_display": link.task.get_priority_display(),
                    }
                )

        for employee in employees:
            employee._linked_task_payloads = mapping.get(employee.id, [])

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            self._attach_linked_task_payloads(list(page))
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        employees = list(queryset)
        self._attach_linked_task_payloads(employees)
        serializer = self.get_serializer(employees, many=True)
        return Response(serializer.data)

    def get_serializer_class(self):
        if self.action == "list":
            return EmployeeListSerializer
        return EmployeeSerializer

    def perform_create(self, serializer):
        """Создание сотрудника (административное, без пароля).

        Создание LDAP пользователей с паролем - через RegisterAPIView.
        """
        instance = serializer.save()
        instance.set_unusable_password()
        instance.save(update_fields=["password"])

        # Навыки
        skills_ids = self.request.data.get("skills_ids", [])
        if skills_ids:
            instance.skills.set(skills_ids)

    def perform_update(self, serializer):
        """Обновление сотрудника."""
        instance = serializer.instance
        old_email = instance.email
        avatar_payload = serializer.validated_data.get("avatar")

        # Передаем данные для синхронизации с LDAP (через сигналы)
        # DRF request.data может быть dict (JSON) или QueryDict (form data)
        data = self.request.data
        instance._ldap_changes = (
            data.dict() if hasattr(data, "dict") else dict(data)
        )
        if "avatar" in self.request.FILES:
            instance._ldap_avatar = self.request.FILES["avatar"]
        elif avatar_payload is not None:
            instance._ldap_avatar = avatar_payload

        serializer.save()

        # Если email изменился - сбрасываем верификацию
        new_email = instance.email
        if new_email and new_email.lower() != old_email.lower():
            instance.email_verified = False
            instance.email_activation_code = get_random_string(6, "0123456789")
            instance.save(
                update_fields=["email_verified", "email_activation_code"]
            )

            try:
                send_templated_mail(
                    subject="Подтверждение нового email",
                    to=[instance.email],
                    template_base="emails/registration_verify_code",
                    context={
                        "code": instance.email_activation_code,
                        "user": instance,
                    },
                )
            except Exception:
                pass

    @action(detail=False, methods=["get", "patch"])
    def me(self, request):
        """GET — профиль текущего пользователя; PATCH — частичное обновление."""
        instance: Employee = request.user  # type: ignore

        if request.method == "GET":
            instance = (
                self._with_last_activity(Employee.objects.select_related("position"))
                .prefetch_related(
                    "skills",
                    Prefetch(
                        "departments_links",
                        queryset=EmployeeDepartment.objects.filter(
                            is_active=True
                        ).select_related("department", "role"),
                        to_attr="dept_links",
                    ),
                    Prefetch(
                        "actions",
                        queryset=EmployeeAction.objects.order_by("-date"),
                    ),
                )
                .get(pk=request.user.pk)
            )
            ctx = self.get_serializer_context()
            ctx["include_actions"] = True
            ctx["include_action_history"] = True
            data = self.get_serializer(instance, context=ctx).data
            return Response(data, status=200)

        # PATCH — используем стандартный механизм
        serializer = self.get_serializer(
            instance, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data, status=200)

    @action(detail=True, methods=["post"])
    def add_skill(self, request, pk=None):
        """Добавить навык сотруднику.

        Доступно любому аутентифицированному пользователю.
        Можно передать либо skill_id, либо name.
        """
        instance = self.get_object()
        skill_id = request.data.get("skill_id")
        skill_name = (request.data.get("name") or "").strip()

        if not skill_id and not skill_name:
            return Response(
                {"detail": "Нужно передать skill_id или name"},
                status=400,
            )

        if skill_id:
            try:
                skill = Skill.objects.get(pk=int(skill_id))
            except (TypeError, ValueError, Skill.DoesNotExist):
                return Response({"detail": "Skill не найден"}, status=404)
        else:
            skill, _ = Skill.objects.get_or_create(name=skill_name)

        instance.skills.add(skill)
        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=200)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        if getattr(self, "action", None) in {"retrieve", "me"}:
            ctx["include_actions"] = True
            ctx["include_action_history"] = True
        return ctx

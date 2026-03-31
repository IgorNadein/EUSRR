"""GroupViewSet — CRUD и операции с группами."""

from __future__ import annotations

from typing import List, Optional

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import FieldError
from django.db.models import Q
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ...permissions import AdminOrActionOrModelPerms
from ..serializers import GroupSerializer
from ._helpers import Employee


class GroupViewSet(viewsets.ModelViewSet):
    """CRUD и LDAP-операции с группами.

    Базовые маршруты:
        GET/POST   /api/v1/groups/
        GET/PATCH/DELETE /api/v1/groups/{id}/

        Экшены: permissions, set-permissions, add-permissions,
            remove-permissions, rename, set-description, members,
            add-members, remove-members, replace-members
    """

    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    pagination_class = None

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name", "id"]
    ordering = ["name"]

    permission_classes = [IsAuthenticated, AdminOrActionOrModelPerms]
    required_perms_by_action = {
        "set_permissions": "employees.assign_group_permissions",
        "add_permissions": "employees.assign_group_permissions",
        "remove_permissions": "employees.assign_group_permissions",
        "rename": "employees.assign_group_permissions",
        "set_description": "employees.assign_group_permissions",
        "add_members": "employees.assign_group_permissions",
        "remove_members": "employees.assign_group_permissions",
        "replace_members": "employees.assign_group_permissions",
    }

    # ---------- queryset ----------

    def get_queryset(self):
        qs = super().get_queryset()

        member_raw = self.request.query_params.get(
            "member"
        ) or self.request.query_params.get("member_id")
        if member_raw is None:
            return qs

        try:
            member_id = int(str(member_raw).strip())
        except (TypeError, ValueError):
            return qs.none()

        try:
            return qs.filter(
                Q(user__id=member_id) | Q(user_set__id=member_id)
            ).distinct()
        except FieldError:
            try:
                return qs.filter(user__id=member_id).distinct()
            except FieldError:
                try:
                    return qs.filter(user_set__id=member_id).distinct()
                except FieldError:
                    return qs.none()

    # ---------- helpers ----------

    def _validate_permissions_payload(
        self, request
    ) -> tuple[Optional[List[Permission]], Optional[Response]]:
        """Валидирует payload с ID permissions."""
        ids = request.data.get("permissions")
        if not isinstance(ids, list):
            return None, Response(
                {"detail": "Поле 'permissions' должно быть списком id"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            pid_list = [int(x) for x in ids]
        except (TypeError, ValueError):
            return None, Response(
                {"detail": "Список 'permissions' должен содержать целые числа"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        qs = Permission.objects.filter(id__in=pid_list)
        if qs.count() != len(set(pid_list)):
            return None, Response(
                {"detail": "Некоторые permissions не найдены"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return list(qs), None

    # ---------- override CRUD ----------

    def create(self, request, *args, **kwargs) -> Response:
        """Создаёт Group в БД. Синхронизация в LDAP через сигналы."""
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)

        grp = Group.objects.create(name=ser.validated_data["name"])

        # Устанавливаем LDAP-специфичные атрибуты для сигнала
        grp._ldap_parent_dn = request.data.get("ldap_parent_dn")
        grp._ldap_description = request.data.get("ldap_description")
        grp._ldap_scope = request.data.get("ldap_scope", "global")
        grp._ldap_security_enabled = bool(
            request.data.get("ldap_security", True)
        )

        perms = ser.validated_data.get("permissions")
        if perms:
            grp.permissions.set(perms)

        # Сохраняем для триггера сигнала создания
        grp.save()

        out = self.get_serializer(grp)
        return Response(
            out.data,
            status=status.HTTP_201_CREATED,
            headers=self.get_success_headers(out.data),
        )

    def partial_update(self, request, *args, **kwargs) -> Response:
        """Частичное обновление Group. Синхронизация в LDAP через сигналы."""
        grp = self.get_object()
        new_name = request.data.get("name")
        new_desc = request.data.get("ldap_description", "__NO_CHANGE__")

        # Устанавливаем LDAP-специфичные атрибуты для сигнала
        if new_name and new_name != grp.name:
            grp._ldap_old_name = grp.name
        if new_desc != "__NO_CHANGE__":
            grp._ldap_description = new_desc

        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs) -> Response:
        """Удаляет Group из БД. Синхронизация в LDAP через сигналы."""
        return super().destroy(request, *args, **kwargs)

    def list(self, request, *args, **kwargs) -> Response:
        """Список групп."""
        return super().list(request, *args, **kwargs)

    # ---------- Actions: Django permissions ----------

    @action(detail=True, methods=["get"])
    def permissions(self, request, pk=None) -> Response:
        """Permissions, привязанные к группе."""
        grp = self.get_object()
        perms = grp.permissions.select_related("content_type").distinct()
        data = [
            {
                "id": p.id,
                "codename": f"{p.content_type.app_label}.{p.codename}",
                "name": p.name,
                "app": p.content_type.app_label,
                "model": p.content_type.model,
            }
            for p in perms
        ]
        return Response(
            {"count": len(data), "results": data}, status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["post"], url_path="set-permissions")
    def set_permissions(self, request, pk=None) -> Response:
        """Полностью заменяет набор permissions у группы."""
        grp = self.get_object()
        qs, error = self._validate_permissions_payload(request)
        if error:
            return error
        grp.permissions.set(qs)
        return Response(
            {
                "ok": True,
                "permission_ids": list(
                    grp.permissions.values_list("id", flat=True)
                ),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="add-permissions")
    def add_permissions(self, request, pk=None) -> Response:
        """Добавляет permissions к группе."""
        grp = self.get_object()
        qs, error = self._validate_permissions_payload(request)
        if error:
            return error
        grp.permissions.add(*qs)
        return Response(
            {
                "ok": True,
                "permission_ids": list(
                    grp.permissions.values_list("id", flat=True)
                ),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="remove-permissions")
    def remove_permissions(self, request, pk=None) -> Response:
        """Удаляет указанные permissions у группы."""
        grp = self.get_object()
        qs, error = self._validate_permissions_payload(request)
        if error:
            return error
        grp.permissions.remove(*qs)
        return Response(
            {
                "ok": True,
                "permission_ids": list(
                    grp.permissions.values_list("id", flat=True)
                ),
            },
            status=status.HTTP_200_OK,
        )

    # ---------- Actions: LDAP ----------

    @action(detail=True, methods=["post"])
    def rename(self, request, pk=None) -> Response:
        """Переименовывает группу. Синхронизация в LDAP через сигналы."""
        grp = self.get_object()
        new_name = (request.data.get("new_name") or "").strip()
        if not new_name:
            return Response(
                {"detail": "new_name обязателен"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        grp._ldap_old_name = grp.name
        grp.name = new_name
        grp.save(update_fields=["name"])
        return Response(
            {"ok": True, "name": grp.name}, status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["post"], url_path="set-description")
    def set_description(self, request, pk=None) -> Response:
        """Устанавливает описание группы. Синхронизация в LDAP через сигналы."""
        grp = self.get_object()
        grp._ldap_description = request.data.get("description")
        grp.save()
        return Response({"ok": True}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def members(self, request, pk=None) -> Response:
        """Состав группы."""
        grp = self.get_object()
        users = grp.user_set.all()
        employees = [
            {
                "id": u.id,
                "email": u.email,
                "first_name": u.first_name,
                "last_name": u.last_name,
            }
            for u in users
        ]
        return Response({"employees": employees}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="add-members")
    def add_members(self, request, pk=None) -> Response:
        """Добавляет участников в группу. Синхронизация в LDAP через сигналы."""
        grp = self.get_object()
        member_ids = request.data.get("member_ids") or []
        if not isinstance(member_ids, list):
            return Response(
                {"detail": "member_ids must be a list"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        users = Employee.objects.filter(id__in=member_ids)
        grp.user_set.add(*users)

        ok_user_ids = [u.id for u in users]
        return Response(
            {
                "ok": True,
                "db_added": len(users),
                "ok_user_ids": ok_user_ids,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="remove-members")
    def remove_members(self, request, pk=None) -> Response:
        """Удаляет участников из группы. Синхронизация в LDAP через сигналы."""
        grp = self.get_object()
        member_ids = request.data.get("member_ids") or []
        if not isinstance(member_ids, list):
            return Response(
                {"detail": "member_ids must be a list"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        users = Employee.objects.filter(id__in=member_ids)
        grp.user_set.remove(*users)

        ok_user_ids = [u.id for u in users]
        return Response(
            {
                "ok": True,
                "db_removed": len(users),
                "ok_user_ids": ok_user_ids,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="replace-members")
    def replace_members(self, request, pk=None) -> Response:
        """Полностью заменяет состав группы.

        Синхронизация в LDAP выполняется через сигналы.
        """
        grp = self.get_object()
        member_ids = request.data.get("member_ids") or []
        if not isinstance(member_ids, list):
            return Response(
                {"detail": "member_ids must be a list"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        users = Employee.objects.filter(id__in=member_ids)
        grp.user_set.set(users)

        ok_user_ids = [u.id for u in users]
        return Response(
            {
                "ok": True,
                "db_total": len(users),
                "ok_user_ids": ok_user_ids,
            },
            status=status.HTTP_200_OK,
        )

"""PositionViewSet — CRUD должностей с LDAP-синхронизацией групп."""

from __future__ import annotations

from django.contrib.auth.models import Group, Permission
from employees.ldap.directory_service import DirectoryService
from employees.models import Position
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ...permissions import AdminOrActionOrModelPerms
from ..serializers import PositionSerializer
from ._helpers import HistoryActionMixin, _is_ldap_enabled, _ldap_try


class PositionViewSet(HistoryActionMixin, viewsets.ModelViewSet):
    """
    /api/v1/positions/
      GET list/retrieve   — аутентифицированные
      POST/PUT/PATCH/DEL  — staff/superuser ИЛИ пользователь с model perms
      Экшены:
        POST /{id}/set-groups
        POST /{id}/add-groups
        POST /{id}/remove-groups
        GET  /{id}/permissions
    """

    queryset = Position.objects.all().prefetch_related("groups")
    serializer_class = PositionSerializer
    pagination_class = None
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "id"]
    ordering = ["name"]
    history_diff_fields = ["name", "description"]
    permission_classes = [AdminOrActionOrModelPerms]
    required_perms_by_action = {
        "set_groups": "employees.assign_position_groups",
        "add_groups": "employees.assign_position_groups",
        "remove_groups": "employees.assign_position_groups",
    }

    def _validate_groups_payload(self, request):
        ids = request.data.get("groups")
        if not isinstance(ids, list):
            return None, Response(
                {"detail": "Поле 'groups' должно быть списком id"}, status=400
            )
        qs = Group.objects.filter(id__in=ids)
        if qs.count() != len(set(ids)):
            return None, Response({"detail": "Некоторые группы не найдены"}, status=400)
        return qs, None

    def get_permissions(self):
        if self.action in {"list", "retrieve", "permissions"}:
            return [IsAuthenticated()]
        if self.action == "create":
            return [AdminOrActionOrModelPerms()]
        return [AdminOrActionOrModelPerms()]

    @action(detail=True, methods=["post"])
    def set_groups(self, request, pk=None):
        pos = self.get_object()
        qs, err = self._validate_groups_payload(request)
        if err:
            return err
        pos.groups.set(qs)
        err2 = _ldap_try(lambda: DirectoryService().reconcile_position(pos))
        if err2:
            return err2
        return Response(
            {
                "ok": True,
                "group_ids": list(pos.groups.values_list("id", flat=True)),
            }
        )

    @action(detail=True, methods=["post"])
    def add_groups(self, request, pk=None):
        pos = self.get_object()
        qs, err = self._validate_groups_payload(request)
        if err:
            return err
        pos.groups.add(*qs)
        err2 = _ldap_try(lambda: DirectoryService().reconcile_position(pos))
        if err2:
            return err2
        return Response(
            {
                "ok": True,
                "group_ids": list(pos.groups.values_list("id", flat=True)),
            }
        )

    @action(detail=True, methods=["post"])
    def remove_groups(self, request, pk=None):
        pos = self.get_object()
        qs, err = self._validate_groups_payload(request)
        if err:
            return err
        pos.groups.remove(*qs)
        err2 = _ldap_try(lambda: DirectoryService().reconcile_position(pos))
        if err2:
            return err2
        return Response(
            {
                "ok": True,
                "group_ids": list(pos.groups.values_list("id", flat=True)),
            }
        )

    @action(detail=True, methods=["get"])
    def permissions(self, request, pk=None):
        pos = self.get_object()
        perms = (
            Permission.objects.filter(group__positions=pos)
            .select_related("content_type")
            .distinct()
        )
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
        return Response({"count": len(data), "results": data}, status=200)

    def perform_create(self, serializer):
        pos = serializer.save()
        err = _ldap_try(lambda: DirectoryService().reconcile_position(pos))
        if err:
            raise Exception(err.data["detail"])

    def perform_update(self, serializer):
        pos = serializer.save()
        _ldap_try(lambda: DirectoryService().reconcile_position(pos))

    def perform_destroy(self, instance):
        _ldap_try(lambda: DirectoryService().delete_position_group(instance))
        return super().perform_destroy(instance)

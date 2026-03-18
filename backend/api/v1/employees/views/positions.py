"""PositionViewSet — CRUD должностей."""

from __future__ import annotations

from django.contrib.auth.models import Group, Permission
from django.db import transaction
from employees.models import Position
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ...permissions import AdminOrActionOrModelPerms
from ..serializers import PositionSerializer
from ._helpers import HistoryActionMixin


class PositionViewSet(HistoryActionMixin, viewsets.ModelViewSet):
    """
    /api/v1/positions/
      GET list/retrieve   — аутентифицированные
      POST/PUT/PATCH/DEL  — staff/superuser ИЛИ пользователь с model perms
      Экшены:
        POST /{id}/set-groups      — заменить все группы
        POST /{id}/add-groups      — добавить группы
        POST /{id}/remove-groups   — удалить группы
        GET  /{id}/permissions     — получить права должности
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
        """Валидация payload с группами.
        
        Returns:
            tuple: (QuerySet групп, Response с ошибкой или None)
        """
        ids = request.data.get("groups")
        if not isinstance(ids, list):
            return None, Response(
                {"detail": "Поле 'groups' должно быть списком id"}, status=400
            )
        
        unique_ids = list(set(ids))
        qs = Group.objects.filter(id__in=unique_ids)
        
        if qs.count() != len(unique_ids):
            found_ids = set(qs.values_list('id', flat=True))
            missing_ids = set(unique_ids) - found_ids
            return None, Response(
                {
                    "detail": "Некоторые группы не найдены",
                    "missing_ids": list(missing_ids)
                },
                status=400
            )
        return qs, None

    def get_permissions(self):
        """Права доступа: чтение для всех аутентифицированных, изменения для админов."""
        if self.action in {"list", "retrieve", "permissions"}:
            return [IsAuthenticated()]
        return [AdminOrActionOrModelPerms()]

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def set_groups(self, request, pk=None):
        """Заменяет все группы должности на указанные.
        
        POS-группа должности автоматически вкладывается в соответствующие AD-группы
        через сигнал m2m_changed для Position.groups (см. signals/ldap/position.py).
        """
        pos = self.get_object()
        qs, err = self._validate_groups_payload(request)
        if err:
            return err
        
        old_groups = set(pos.groups.values_list('id', flat=True))
        pos.groups.set(qs)
        new_groups = set(pos.groups.values_list('id', flat=True))
        
        return Response({
            "ok": True,
            "position_id": pos.id,
            "position_name": pos.name,
            "group_ids": list(new_groups),
            "added": list(new_groups - old_groups),
            "removed": list(old_groups - new_groups),
        })

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def add_groups(self, request, pk=None):
        """Добавляет группы к должности.
        
        POS-группа должности автоматически вкладывается в соответствующие AD-группы
        через сигнал m2m_changed для Position.groups (см. signals/ldap/position.py).
        """
        pos = self.get_object()
        qs, err = self._validate_groups_payload(request)
        if err:
            return err
        
        old_groups = set(pos.groups.values_list('id', flat=True))
        pos.groups.add(*qs)
        new_groups = set(pos.groups.values_list('id', flat=True))
        
        return Response({
            "ok": True,
            "position_id": pos.id,
            "position_name": pos.name,
            "group_ids": list(new_groups),
            "added": list(new_groups - old_groups),
        })

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def remove_groups(self, request, pk=None):
        """Удаляет группы у должности.
        
        POS-группа должности автоматически удаляется из соответствующих AD-групп
        через сигнал m2m_changed для Position.groups (см. signals/ldap/position.py).
        """
        pos = self.get_object()
        qs, err = self._validate_groups_payload(request)
        if err:
            return err
        
        old_groups = set(pos.groups.values_list('id', flat=True))
        pos.groups.remove(*qs)
        new_groups = set(pos.groups.values_list('id', flat=True))
        
        return Response({
            "ok": True,
            "position_id": pos.id,
            "position_name": pos.name,
            "group_ids": list(new_groups),
            "removed": list(old_groups - new_groups),
        })

    @action(detail=True, methods=["get"])
    def permissions(self, request, pk=None):
        """Возвращает все права (permissions), которые получает должность через свои группы."""
        pos = self.get_object()
        perms = (
            Permission.objects.filter(group__positions=pos)
            .select_related("content_type")
            .distinct()
            .order_by('content_type__app_label', 'codename')
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
        return Response({
            "position_id": pos.id,
            "position_name": pos.name,
            "count": len(data),
            "results": data
        })

    def perform_create(self, serializer):
        """Создание должности."""
        serializer.save()

    def perform_update(self, serializer):
        """Обновление должности."""
        serializer.save()

    def perform_destroy(self, instance):
        """Удаление должности."""
        super().perform_destroy(instance)

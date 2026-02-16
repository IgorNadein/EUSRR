"""SkillViewSet — CRUD навыков сотрудников."""

from __future__ import annotations

from django.db import transaction
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..permissions import AdminOrActionOrModelPerms
from ..serializers import SkillSerializer
from ._helpers import Employee

from employees.models import Skill


class SkillViewSet(viewsets.ModelViewSet):
    """
    /api/v1/skills/
      - GET list/retrieve      — IsAuthenticated
      - POST (create)          — IsAuthenticated
      - PATCH/PUT              — staff/superuser ИЛИ perm employees.change_skill
      - DELETE                 — staff/superuser ИЛИ perm employees.delete_skill
    Экшены:
      - POST /skills/bulk_create
      - POST /skills/merge
    """

    queryset = Skill.objects.all().order_by("name")
    serializer_class = SkillSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name", "id"]
    ordering = ["name"]
    pagination_class = None
    required_perms_by_action = {
        "merge": "employees.change_skill",
    }

    def get_permissions(self):
        if self.action in ("create", "bulk_create", "list", "retrieve"):
            return [IsAuthenticated()]
        return [IsAuthenticated(), AdminOrActionOrModelPerms()]

    @action(detail=False, methods=["post"])
    def bulk_create(self, request):
        names = request.data.get("names")
        if not isinstance(names, list) or not names:
            return Response(
                {"detail": "Поле 'names' должно быть непустым списком строк"},
                status=400,
            )

        cleaned = []
        seen = set()
        for n in names:
            if not isinstance(n, str):
                continue
            s = n.strip()
            if not s:
                continue
            key = s.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(s)

        existing = set(
            Skill.objects.filter(name__in=cleaned).values_list("name", flat=True)
        )
        to_create = [Skill(name=n) for n in cleaned if n not in existing]
        Skill.objects.bulk_create(to_create, ignore_conflicts=True)

        created = Skill.objects.filter(
            name__in=[n for n in cleaned if n not in existing]
        ).order_by("name")
        return Response(
            {
                "created_count": created.count(),
                "created": SkillSerializer(created, many=True).data,
            },
            status=201,
        )

    @action(detail=False, methods=["post"])
    @transaction.atomic
    def merge(self, request):
        """Заменяет навык source на target, опционально переносит всех сотрудников."""
        sid = request.data.get("source_id")
        tid = request.data.get("target_id")
        reassign = bool(request.data.get("reassign", True))
        delete_source = bool(request.data.get("delete_source", True))

        if not sid or not tid:
            return Response({"detail": "source_id и target_id обязательны"}, status=400)
        try:
            sid = int(sid)
            tid = int(tid)
        except (TypeError, ValueError):
            return Response(
                {"detail": "source_id и target_id должны быть числами"}, status=400
            )
        if sid == tid:
            return Response(
                {"detail": "source_id и target_id не должны совпадать"}, status=400
            )

        try:
            source = Skill.objects.get(pk=sid)
            target = Skill.objects.get(pk=tid)
        except Skill.DoesNotExist:
            return Response({"detail": "Skill не найден"}, status=404)

        moved_count = 0
        if reassign:
            qs = Employee.objects.filter(skills=source).only("id").distinct()
            for emp in qs:
                emp.skills.add(target)
                emp.skills.remove(source)
                moved_count += 1

        if delete_source:
            source.delete()

        return Response(
            {
                "ok": True,
                "source_id": sid,
                "target_id": tid,
                "reassigned_employees": moved_count,
                "source_deleted": bool(delete_source),
            },
            status=200,
        )

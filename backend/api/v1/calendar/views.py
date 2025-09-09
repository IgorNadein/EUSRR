from __future__ import annotations

from datetime import date
from typing import Optional, Type, List, Dict, Any

from django.core.cache import cache
from django.http import Http404
from django.utils.dateparse import parse_date
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from calendar_app.models import CalendarEvent
from .serializers import (
    CalendarEventSerializer,
    CalendarEventWriteSerializer,
)
from calendar_app.services.recurrence import expand_event_occurrences

from ..permissions import AdminOrActionOrModelPerms, AdminOrDeptAllowed     # пермишены для "компании"
from employees.constants import DeptPerm                    # коды прав отделов
import logging
logger = logging.getLogger(__name__)


class CalendarEventsViewSet(ModelViewSet):
    """Единый CRUD по событиям календаря (компания/отдел) с развёрткой повторяемости.

    list:
        Возвращает МАТЕРИАЛИЗОВАННЫЕ вхождения в окне [start, end).
        Если указан department_id — события отдела, иначе — компании.

    retrieve/create/update/partial_update/destroy:
        Работают с объектом CalendarEvent.
    """

    queryset = CalendarEvent.objects.select_related("department").order_by(
        "start_date", "start_time"
    )
    renderer_classes = [JSONRenderer]

    # ---------- Внутренний пермишен для отделов ----------

    class ManageCalendarPerm(AdminOrDeptAllowed):
        """Право на управление календарём отдела (для компании молчит)."""

        required_code = DeptPerm.MANAGE_CALENDAR

    # ---------- Подключение пермишенов ----------

    def get_permissions(self):
        """Для компании — AdminOrActionOrModelPerms, для отдела — ManageCalendarPerm.

        ВАЖНО: прокидываем найденный department_id в kwargs, чтобы пермишен
        гарантированно его увидел на этапе has_permission().
        """
        dep = self._dept_id(required=False)
        print(f"Request user: {self.request.user}, Auth: {self.request.auth}")
        if dep is None:
            
            return [AdminOrActionOrModelPerms()]

        # События отдела: подложим dep в kwargs (если его не было)
        # чтобы AdminOrDeptAllowed нашёл department_id без чтения request.data
        self.kwargs = dict(self.kwargs)  # скопировать, т.к. может быть MappingProxy
        self.kwargs.setdefault("department_id", dep)

        return [self.ManageCalendarPerm()]
    
    # ---------- Сериализаторы ----------

    def get_serializer_class(self) -> Type[serializers.Serializer]:
        """Выбор сериализатора по действию.

        Returns:
            Type[serializers.Serializer]: Класс сериализатора.
        """
        if self.action in {"create", "update", "partial_update"}:
            return CalendarEventWriteSerializer
        return CalendarEventSerializer

    # ---------- Утилиты ----------

    def _dept_id(self, *, required: bool = False) -> Optional[int]:
        """Читает department_id из kwargs/query/body.

        ВАЖНО: *не* путать pk события с department_id.

        Args:
            required (bool): Если True — бросить 404 при отсутствии/ошибке.

        Raises:
            Http404: При некорректном или отсутствующем department_id (когда required=True).

        Returns:
            Optional[int]: PK отдела или None (компания).
        """
        # nested-url вида: /departments/{department_id}/events/
        for key in ("department_pk", "department_id"):
            if key in self.kwargs:
                try:
                    return int(self.kwargs[key])
                except Exception:
                    raise Http404("Некорректный department_id в URL.")

        req = getattr(self, "request", None)
        if req is not None:
            for key in ("department_id", "department"):
                val = req.query_params.get(key)
                if val is not None:
                    try:
                        return int(val)
                    except Exception:
                        raise Http404("Некорректный department_id в query.")

        data = getattr(req, "data", {}) if req is not None else {}
        if isinstance(data, dict):
            for key in ("department_id", "department"):
                if key in data and data[key] is not None:
                    try:
                        return int(data[key])
                    except Exception:
                        raise Http404("Некорректный department_id в теле запроса.")

        if required:
            raise Http404("Не указан department_id.")
        return None

    # ---------- QuerySet ----------

    def get_queryset(self):
        """QS для list фильтруем по компании/отделу, для detail — не фильтруем.

        Returns:
            QuerySet: Набор для текущего действия.
        """
        qs = super().get_queryset()
        if getattr(self, "action", None) != "list":
            # detail — нужен полный QS, чтобы по pk находить любой объект
            return qs

        dep = self._dept_id(required=False)
        return qs.filter(department__isnull=True) if dep is None else qs.filter(department_id=dep)

    # ---------- LIST: материализация повторов ----------

    def list(self, request, *args, **kwargs):
        """Возвращает материализованные вхождения в окне [start, end).

        Query params:
            start (YYYY-MM-DD) — левая граница (включительно).
            end   (YYYY-MM-DD) — правая граница (исключительно).

        Returns:
            Response: Массив объектов для FullCalendar.
        """
        start_str = request.query_params.get("start")
        end_str = request.query_params.get("end")
        if not start_str or not end_str:
            return Response([], status=status.HTTP_200_OK)

        r_start: Optional[date] = parse_date(start_str[:10])
        r_end: Optional[date] = parse_date(end_str[:10])
        if not r_start or not r_end:
            return Response(
                {"detail": "Некорректные параметры start/end."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if r_start >= r_end:
            return Response([], status=status.HTTP_200_OK)

        items: List[Dict[str, Any]] = []
        for ev in self.get_queryset():
            for oc in expand_event_occurrences(
                ev, range_start=r_start, range_end=r_end, max_instances=1000
            ):
                items.append(
                    {
                        "id": ev.id,  # идентификатор «родителя»; можно заменить на oc.id, если нужен уникальный на каждое вхождение
                        "title": ev.title,
                        "start": oc.start.isoformat(),
                        "end": oc.end.isoformat(),
                        "allDay": oc.all_day,
                        "color": ev.color or None,
                        "recurrence": ev.recurrence,
                        "department_id": ev.department_id,
                    }
                )
        return Response(items, status=status.HTTP_200_OK)

    # ---------- Создание/изменение/удаление ----------

    def perform_create(self, serializer: CalendarEventWriteSerializer) -> None:
        """Сохраняет объект, подставляя department_id из контекста (если есть) и автора.

        Raises:
            ValidationError: Если сериализатор невалиден (поднимет сам DRF).
        """
        dep = self._dept_id(required=False)
        serializer.save(
            department_id=dep if dep is not None else serializer.validated_data.get("department_id"),
            created_by=self.request.user,
        )
        cache.clear()

    def perform_update(self, serializer: CalendarEventWriteSerializer) -> None:
        """Обновляет событие и чистит кеш."""
        serializer.save()
        cache.clear()

    def perform_destroy(self, instance: CalendarEvent) -> None:
        """Удаляет событие и чистит кеш."""
        instance.delete()
        cache.clear()
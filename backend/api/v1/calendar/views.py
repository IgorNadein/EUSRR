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
from rest_framework.decorators import action as rest_action

from calendar_app.models import CalendarEvent
from .serializers import (
    CalendarEventSerializer,
    CalendarEventWriteSerializer,
)
from calendar_app.services.recurrence import expand_event_occurrences

from ..permissions import AdminOrDeptAllowed
from employees.constants import DeptPerm
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
    # ВАЖНО: Переопределяем глобальные DEFAULT_PERMISSION_CLASSES
    # Используем только get_permissions() для динамического определения прав
    permission_classes = []

    # ---------- Внутренний пермишен для отделов ----------

    class ManageCalendarPerm(AdminOrDeptAllowed):
        """Право на управление календарём отдела (для компании молчит)."""

        required_code = DeptPerm.MANAGE_CALENDAR

    # ---------- Подключение пермишенов ----------

    def get_permissions(self):
        """Настройка прав доступа в зависимости от действия.
        
        - list, retrieve: доступно всем авторизованным пользователям
        - create, update, partial_update, destroy для компании: требуется staff/superuser
        - create, update, partial_update, destroy для отдела: требуется MANAGE_CALENDAR
        - create, update, partial_update, destroy для личного календаря: только владелец
        """
        action = getattr(self, "action", None)
        method = self.request.method if hasattr(self, 'request') else None
        
        # Если action ещё не установлен, определяем по методу
        if action is None:
            if method in ['GET', 'HEAD', 'OPTIONS']:
                return [IsAuthenticated()]
            elif method == 'POST':
                action = 'create'
            elif method in ['PUT', 'PATCH']:
                action = 'update'
            elif method == 'DELETE':
                action = 'destroy'
        
        # Просмотр событий доступен всем авторизованным пользователям
        if action in ["list", "retrieve"]:
            return [IsAuthenticated()]
        
        # Для изменений требуются права управления календарём
        emp = self._employee_id(required=False)
        dep = self._dept_id(required=False)
        
        # Личный календарь — полный контроль только у владельца
        if emp is not None:
            # Проверка, что текущий пользователь = владелец календаря
            if self.request.user.id == emp:
                return [IsAuthenticated()]
            else:
                # Другой пользователь не может изменять чужой личный календарь
                from rest_framework.permissions import BasePermission
                class DenyAll(BasePermission):
                    def has_permission(self, request, view):
                        return False
                return [DenyAll()]
        
        # Календарь компании — только администраторы
        if dep is None:
            from rest_framework.permissions import IsAdminUser
            return [IsAdminUser()]
        
        # Календарь отдела — требуется право MANAGE_CALENDAR
        self.kwargs = dict(self.kwargs)
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
            Optional[int]: PK отдела или None (компания или личный календарь).
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
    
    def _employee_id(self, *, required: bool = False) -> Optional[int]:
        """Читает employee_id из kwargs/query/body для личного календаря.

        Args:
            required (bool): Если True — бросить 404 при отсутствии/ошибке.

        Raises:
            Http404: При некорректном или отсутствующем employee_id (когда required=True).

        Returns:
            Optional[int]: PK сотрудника или None (компания/отдел).
        """
        # nested-url вида: /employees/{employee_id}/events/
        for key in ("employee_pk", "employee_id"):
            if key in self.kwargs:
                try:
                    return int(self.kwargs[key])
                except Exception:
                    raise Http404("Некорректный employee_id в URL.")

        req = getattr(self, "request", None)
        if req is not None:
            for key in ("employee_id", "employee"):
                val = req.query_params.get(key)
                if val is not None:
                    try:
                        return int(val)
                    except Exception:
                        raise Http404("Некорректный employee_id в query.")

        data = getattr(req, "data", {}) if req is not None else {}
        if isinstance(data, dict):
            for key in ("employee_id", "employee"):
                if key in data and data[key] is not None:
                    try:
                        return int(data[key])
                    except Exception:
                        raise Http404("Некорректный employee_id в теле запроса.")

        if required:
            raise Http404("Не указан employee_id.")
        return None

    # ---------- QuerySet ----------

    def get_queryset(self):
        """QS для list фильтруем по компании/отделу/сотруднику, для detail — не фильтруем.

        Returns:
            QuerySet: Набор для текущего действия.
        """
        qs = super().get_queryset()
        if getattr(self, "action", None) != "list":
            # detail — нужен полный QS, чтобы по pk находить любой объект
            return qs

        dep = self._dept_id(required=False)
        emp = self._employee_id(required=False)
        
        # Приоритет: employee_id > department_id > company
        if emp is not None:
            # Личный календарь сотрудника
            return qs.filter(employee_id=emp, department__isnull=True)
        elif dep is not None:
            # Календарь отдела
            return qs.filter(department_id=dep, employee__isnull=True)
        else:
            # Календарь компании
            return qs.filter(department__isnull=True, employee__isnull=True)

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
        """Сохраняет объект, подставляя department_id/employee_id из контекста и автора.

        Raises:
            ValidationError: Если сериализатор невалиден (поднимет сам DRF).
        """
        dep = self._dept_id(required=False)
        emp = self._employee_id(required=False)
        
        # Приоритет: employee_id > department_id
        if emp is not None:
            serializer.save(
                employee_id=emp,
                department_id=None,
                created_by=self.request.user,
            )
        else:
            serializer.save(
                department_id=dep if dep is not None else serializer.validated_data.get("department_id"),
                employee_id=None,
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

    # ---------- Проверка прав ----------

    @rest_action(
        detail=True,
        methods=["get"],
        permission_classes=[IsAuthenticated],
        url_path="permissions",
    )
    def permissions(self, request, pk=None):
        """Проверяет права пользователя на редактирование/удаление события.

        Returns:
            Response: {
                "can_edit": bool,
                "can_delete": bool,
                "can_view": bool (всегда True для авторизованных)
            }
        """
        event = self.get_object()
        user = request.user

        # Просмотр доступен всем авторизованным
        can_view = True

        # Права на редактирование и удаление
        can_edit = False
        can_delete = False

        # Проверка прав
        if user.is_superuser or user.is_staff:
            # Админы могут всё
            can_edit = True
            can_delete = True
        elif event.employee_id is not None:
            # Личное событие — редактировать может только владелец
            if event.employee_id == user.id:
                can_edit = True
                can_delete = True
        elif event.department_id is None:
            # Событие компании — только админы (уже проверено выше)
            pass
        else:
            # Событие отдела — проверяем право MANAGE_CALENDAR
            try:
                from employees.models import EmployeeDepartment

                # Проверяем, является ли пользователь руководителем отдела
                if hasattr(event.department, "head_id"):
                    if event.department.head_id == user.id:
                        can_edit = True
                        can_delete = True

                # Проверяем наличие права MANAGE_CALENDAR
                if not can_edit:
                    has_perm = EmployeeDepartment.objects.filter(
                        employee_id=user.id,
                        department_id=event.department_id,
                        is_active=True,
                        role__scoped_permissions__code=DeptPerm.MANAGE_CALENDAR,
                    ).exists()

                    if has_perm:
                        can_edit = True
                        can_delete = True
            except Exception as e:
                logger.error(f"Error checking permissions: {e}")

        return Response(
            {"can_view": can_view, "can_edit": can_edit, "can_delete": can_delete}
        )

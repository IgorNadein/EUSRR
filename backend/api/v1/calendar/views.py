from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional, Type

from calendar_app.cache import (
    invalidate_calendar_cache,
    invalidate_event_cache,
    invalidate_subscription_cache,
)
from calendar_app.models import CalendarEvent
from calendar_app.services.recurrence import expand_event_occurrences
from django.http import Http404
from django.utils.dateparse import parse_date
from employees.constants import DeptPerm
from rest_framework import serializers, status
from rest_framework.decorators import action as rest_action
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from ..permissions import AdminOrDeptAllowed
from .serializers import (
    CalendarEventSerializer,
    CalendarEventWriteSerializer,
    CalendarInviteBulkSerializer,
    CalendarInviteSerializer,
    CalendarSerializer,
    CalendarSubscriptionSerializer,
    CalendarSubscriptionWriteSerializer,
    CalendarWriteSerializer,
)

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
        - create, update, partial_update, destroy для новой архитектуры:
          проверка через calendar.can_user_edit()
        - create, update, partial_update, destroy для компании (legacy):
          требуется staff/superuser
        - create, update, partial_update, destroy для отдела (legacy):
          требуется MANAGE_CALENDAR
        - create, update, partial_update, destroy для личного календаря
          (legacy): только владелец
        """
        action = getattr(self, "action", None)
        method = self.request.method if hasattr(self, "request") else None

        # Если action ещё не установлен, определяем по методу
        if action is None:
            if method in ["GET", "HEAD", "OPTIONS"]:
                return [IsAuthenticated()]
            elif method == "POST":
                action = "create"
            elif method in ["PUT", "PATCH"]:
                action = "update"
            elif method == "DELETE":
                action = "destroy"

        # Просмотр событий доступен всем авторизованным пользователям
        if action in ["list", "retrieve"]:
            return [IsAuthenticated()]

        # Для изменений проверяем новую архитектуру (calendar_id)
        from rest_framework.permissions import BasePermission

        class CalendarEditPermission(BasePermission):
            """Проверка прав редактирования через календари."""

            def has_permission(self, request, view):
                from calendar_app.models import Calendar

                # Пытаемся получить calendar_id из разных источников
                calendar_id = None

                # 1. Из тела запроса (create)
                if hasattr(request, "data") and isinstance(request.data, dict):
                    calendar_id = request.data.get("calendar_id")

                # 2. Из query параметров
                if calendar_id is None:
                    calendar_id = request.query_params.get("calendar_id")

                # 3. Для update/delete из объекта события
                if calendar_id is None and hasattr(view, "get_object"):
                    try:
                        event = view.get_object()
                        calendar_id = event.calendar_id
                    except Exception:
                        pass

                # Если calendar_id указан — используем новую логику
                if calendar_id is not None:
                    try:
                        calendar = Calendar.objects.get(id=int(calendar_id))
                        return calendar.can_user_edit(request.user)
                    except (Calendar.DoesNotExist, ValueError):
                        return False

                # Если calendar_id не указан — используем legacy логику
                return None  # Пропускаем дальше к legacy проверкам

        # Проверяем через новую архитектуру
        calendar_perm = CalendarEditPermission()
        has_perm = calendar_perm.has_permission(self.request, self)

        # Если новая архитектура вернула результат — используем его
        if has_perm is not None:
            if has_perm:
                return [IsAuthenticated()]
            else:
                # Нет прав на редактирование календаря
                class DenyAll(BasePermission):
                    def has_permission(self, request, view):
                        return False

                return [DenyAll()]

        # LEGACY ЛОГИКА: calendar_id не указан, используем старую логику
        emp = self._employee_id(required=False)
        dep = self._dept_id(required=False)

        # Личный календарь — полный контроль только у владельца
        if emp is not None:
            # Проверка, что текущий пользователь = владелец календаря
            if self.request.user.id == emp:
                return [IsAuthenticated()]
            else:
                # Другой пользователь не может изменять чужой личный календарь
                class DenyAll(BasePermission):
                    def has_permission(self, request, view):
                        return False

                return [DenyAll()]

        # Календарь компании (legacy) — только администраторы
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
        """QS для list/list_raw фильтруем по компании/отделу/сотруднику/календарю, для detail — не фильтруем.

        Returns:
            QuerySet: Набор для текущего действия.
        """
        qs = super().get_queryset()
        action = getattr(self, "action", None)

        # Фильтруем для list и list_raw, для остальных (detail и т.д.) — полный QS
        if action not in ("list", "list_raw"):
            # detail — нужен полный QS, чтобы по pk находить любой объект
            return qs

        # Новая архитектура: calendar_id имеет приоритет
        calendar_id = self.request.query_params.get("calendar_id")
        if calendar_id is not None:
            try:
                return qs.filter(calendar_id=int(calendar_id))
            except ValueError:
                raise Http404("Некорректный calendar_id.")

        # Legacy логика: department_id / employee_id / company
        dep = self._dept_id(required=False)
        emp = self._employee_id(required=False)

        # Приоритет: employee_id > department_id > company
        if emp is not None:
            # Личный календарь сотрудника (legacy)
            return qs.filter(
                employee_id=emp, department__isnull=True, calendar__isnull=True
            )
        elif dep is not None:
            # Календарь отдела (legacy)
            return qs.filter(
                department_id=dep, employee__isnull=True, calendar__isnull=True
            )
        else:
            # Календарь компании (legacy)
            return qs.filter(
                department__isnull=True, employee__isnull=True, calendar__isnull=True
            )

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
                # 🔧 FIX: Автоматически конвертируем многодневные события в allDay
                # для корректного отображения в FullCalendar dayGridMonth
                all_day = oc.all_day
                start = oc.start
                end = oc.end

                if not all_day and start and end:
                    # Проверяем длительность
                    duration = end - start
                    if duration.days > 1:
                        # Многодневное событие -> делаем allDay и убираем время
                        all_day = True
                        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
                        end = end.replace(hour=0, minute=0, second=0, microsecond=0)

                items.append(
                    {
                        "id": ev.id,
                        "title": ev.title,
                        "start": start.isoformat() if start else None,
                        "end": end.isoformat() if end else None,
                        "allDay": all_day,
                        "color": ev.color or None,
                        "recurrence": ev.recurrence,
                        "department_id": ev.department_id,
                    }
                )
        return Response(items, status=status.HTTP_200_OK)

    @rest_action(detail=False, methods=["GET"])
    def list_raw(self, request, *args, **kwargs):
        """Возвращает список событий БЕЗ материализации вхождений.

        Используется для выбора события при перемещении между календарями.
        Поддерживает те же параметры фильтрации, что и get_queryset():
        - calendar_id (новая архитектура)
        - department_id (legacy)
        - employee_id (legacy)
        - без параметров = события компании (legacy)

        Returns:
            Response: Массив объектов CalendarEvent (сериализованных).
        """
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

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
                department_id=dep
                if dep is not None
                else serializer.validated_data.get("department_id"),
                employee_id=None,
                created_by=self.request.user,
            )
        invalidate_event_cache()

    def perform_update(self, serializer: CalendarEventWriteSerializer) -> None:
        """Обновляет событие и чистит кеш."""
        serializer.save()
        invalidate_event_cache()

    def perform_destroy(self, instance: CalendarEvent) -> None:
        """Удаляет событие и чистит кеш."""
        instance.delete()
        invalidate_event_cache()

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


class CalendarViewSet(ModelViewSet):
    """CRUD операции для календарей.

    Доступные действия:
    - list: список календарей (доступные текущему пользователю)
    - create: создание нового календаря (только владельцы/админы)
    - retrieve: просмотр календаря
    - update/partial_update: обновление календаря (только владелец)
    - destroy: удаление календаря (только владелец)
    - subscribe: подписка на календарь
    - unsubscribe: отписка от календаря
    """

    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer]

    def get_queryset(self):
        """Возвращает календари, доступные текущему пользователю."""
        from calendar_app.models import Calendar

        user = self.request.user

        if self.action == "list":
            # Для списка показываем только доступные календари
            # Сначала получаем доступные, потом оптимизируем
            qs = Calendar.objects.get_available_for_user(user)
        else:
            # Для остальных действий возвращаем все календари
            # (права проверяются в permissions)
            qs = Calendar.objects.all()

        # Оптимизация N+1 запросов для всех случаев
        return qs.select_related(
            "owner_user", "owner_department", "created_by"
        ).prefetch_related("subscriptions", "subscriptions__user")

    def get_serializer_class(self):
        """Выбор сериализатора по действию."""
        if self.action in {"create", "update", "partial_update"}:
            return CalendarWriteSerializer
        return CalendarSerializer

    def get_permissions(self):
        """Настройка прав доступа."""
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]
        elif self.action in ["create"]:
            # Создавать календари могут все авторизованные пользователи
            return [IsAuthenticated()]
        elif self.action in ["update", "partial_update", "destroy"]:
            # Изменять/удалять могут только владельцы
            return [IsAuthenticated()]
        else:
            return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        """Создание календаря с корректным сериализатором для ответа."""
        write_serializer = self.get_serializer(data=request.data)
        write_serializer.is_valid(raise_exception=True)
        self.perform_create(write_serializer)

        # Для ответа используем CalendarSerializer
        instance = write_serializer.instance
        read_serializer = CalendarSerializer(instance, context={"request": request})

        from rest_framework import status
        from rest_framework.response import Response

        headers = self.get_success_headers(read_serializer.data)
        return Response(
            read_serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    def perform_create(self, serializer):
        """Создание календаря."""
        # Владелец определяется в serializer.save()
        serializer.save()
        invalidate_calendar_cache()

    def perform_update(self, serializer):
        """Обновление календаря."""
        # Проверяем права владельца
        calendar = self.get_object()
        user = self.request.user

        if not (user.is_superuser or user.is_staff or calendar.is_owner(user)):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Только владелец может изменять календарь.")

        instance = serializer.save()
        invalidate_calendar_cache(calendar_id=instance.id)

    def perform_destroy(self, instance):
        """Удаление календаря."""
        user = self.request.user

        if not (user.is_superuser or user.is_staff or instance.is_owner(user)):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Только владелец может удалять календарь.")

        calendar_id = instance.id
        instance.delete()
        invalidate_calendar_cache(calendar_id=calendar_id)

    @rest_action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated],
        url_path="subscribe",
    )
    def subscribe(self, request, pk=None):
        """Подписка на календарь.

        Body params:
            can_edit (bool, optional): Право на редактирование событий
            can_manage (bool, optional): Право на управление календарем
        """
        from calendar_app.models import Calendar, CalendarSubscription

        calendar = self.get_object()
        user = request.user

        # Проверяем, доступен ли календарь для подписки
        if not calendar.can_user_view(user):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Календарь недоступен для подписки.")

        # Проверяем, не подписан ли уже пользователь
        existing = CalendarSubscription.objects.filter(
            calendar=calendar, user=user
        ).first()

        if existing:
            return Response(
                {"detail": "Вы уже подписаны на этот календарь."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Создаем подписку
        can_edit = request.data.get("can_edit", False)
        can_manage = request.data.get("can_manage", False)

        # Только владелец может выдавать права can_edit и can_manage
        if (can_edit or can_manage) and not calendar.is_owner(user):
            can_edit = False
            can_manage = False

        subscription = CalendarSubscription.objects.create(
            calendar=calendar,
            user=user,
            can_edit=can_edit,
            can_manage=can_manage,
        )

        serializer = CalendarSubscriptionSerializer(
            subscription, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @rest_action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated],
        url_path="unsubscribe",
    )
    def unsubscribe(self, request, pk=None):
        """Отписка от календаря."""
        from calendar_app.models import CalendarSubscription

        calendar = self.get_object()
        user = request.user

        subscription = CalendarSubscription.objects.filter(
            calendar=calendar, user=user
        ).first()

        if not subscription:
            return Response(
                {"detail": "Вы не подписаны на этот календарь."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subscription.delete()
        return Response(
            {"detail": "Подписка успешно отменена."},
            status=status.HTTP_200_OK,
        )

    @rest_action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated],
        url_path="my-calendars",
    )
    def my_calendars(self, request):
        """Список всех календарей, доступных текущему пользователю."""
        from calendar_app.models import Calendar

        user = request.user
        calendars = Calendar.objects.get_available_for_user(user)

        serializer = CalendarSerializer(
            calendars, many=True, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @rest_action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated],
        url_path="invite",
    )
    def invite(self, request, pk=None):
        """Приглашение пользователя в календарь.

        Только владелец календаря может приглашать пользователей.

        Body params:
            user_id (int, optional): ID пользователя для приглашения
            username (str, optional): Username пользователя
            can_edit (bool, optional): Право редактирования событий
            can_manage (bool, optional): Право управления календарем
            notify (bool, optional): Отправить уведомление (default: True)
        """
        from calendar_app.models import CalendarSubscription
        from django.contrib.auth import get_user_model

        User = get_user_model()
        calendar = self.get_object()
        owner = request.user

        # Проверяем, что пользователь - владелец календаря
        if not calendar.is_owner(owner):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                "Только владелец календаря может приглашать пользователей."
            )

        # Валидация данных
        serializer = CalendarInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Получаем пользователя по user_id или username
        user_id = serializer.validated_data.get("user_id")
        username = serializer.validated_data.get("username")

        try:
            if user_id:
                invited_user = User.objects.get(id=user_id)
            else:
                invited_user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                {"detail": "Пользователь не найден."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Проверяем, не приглашает ли владелец сам себя
        if invited_user.id == owner.id:
            return Response(
                {"detail": "Вы не можете пригласить самого себя."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Проверяем, не подписан ли уже пользователь
        existing = CalendarSubscription.objects.filter(
            calendar=calendar, user=invited_user
        ).first()

        if existing:
            return Response(
                {
                    "detail": "Пользователь уже подписан на этот календарь.",
                    "subscription_id": existing.id,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Создаем подписку с правами
        can_edit = serializer.validated_data.get("can_edit", False)
        can_manage = serializer.validated_data.get("can_manage", False)
        notify = serializer.validated_data.get("notify", True)

        subscription = CalendarSubscription.objects.create(
            calendar=calendar,
            user=invited_user,
            can_edit=can_edit,
            can_manage=can_manage,
            is_visible=True,
        )

        # Отправляем уведомление
        if notify:
            self._send_invitation_notification(
                calendar=calendar,
                invited_user=invited_user,
                owner=owner,
                can_edit=can_edit,
                can_manage=can_manage,
            )

        invalidate_subscription_cache(user_id=invited_user.id)

        response_serializer = CalendarSubscriptionSerializer(
            subscription, context={"request": request}
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @rest_action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated],
        url_path="invite-bulk",
    )
    def invite_bulk(self, request, pk=None):
        """Массовое приглашение пользователей в календарь.

        Body params:
            user_ids (list[int], optional): Список ID пользователей
            usernames (list[str], optional): Список username
            can_edit (bool, optional): Право редактирования событий
            can_manage (bool, optional): Право управления календарем
            notify (bool, optional): Отправить уведомления (default: True)
        """
        from calendar_app.models import CalendarSubscription
        from django.contrib.auth import get_user_model

        User = get_user_model()
        calendar = self.get_object()
        owner = request.user

        # Проверяем, что пользователь - владелец календаря
        if not calendar.is_owner(owner):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                "Только владелец календаря может приглашать пользователей."
            )

        # Валидация данных
        serializer = CalendarInviteBulkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Получаем список пользователей
        user_ids = serializer.validated_data.get("user_ids")
        usernames = serializer.validated_data.get("usernames")
        can_edit = serializer.validated_data.get("can_edit", False)
        can_manage = serializer.validated_data.get("can_manage", False)
        notify = serializer.validated_data.get("notify", True)

        # Находим пользователей
        if user_ids:
            users = User.objects.filter(id__in=user_ids)
        else:
            users = User.objects.filter(username__in=usernames)

        if not users.exists():
            return Response(
                {"detail": "Ни один пользователь не найден."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Исключаем владельца из списка
        users = users.exclude(id=owner.id)

        # Создаем подписки
        created_subscriptions = []
        already_subscribed = []
        errors = []

        for user in users:
            # Проверяем, не подписан ли уже
            existing = CalendarSubscription.objects.filter(
                calendar=calendar, user=user
            ).first()

            if existing:
                already_subscribed.append(
                    {
                        "user_id": user.id,
                        "username": user.username,
                        "subscription_id": existing.id,
                    }
                )
                continue

            try:
                subscription = CalendarSubscription.objects.create(
                    calendar=calendar,
                    user=user,
                    can_edit=can_edit,
                    can_manage=can_manage,
                    is_visible=True,
                )

                # Отправляем уведомление
                if notify:
                    self._send_invitation_notification(
                        calendar=calendar,
                        invited_user=user,
                        owner=owner,
                        can_edit=can_edit,
                        can_manage=can_manage,
                    )

                invalidate_subscription_cache(user_id=user.id)

                created_subscriptions.append(
                    CalendarSubscriptionSerializer(
                        subscription, context={"request": request}
                    ).data
                )
            except Exception as e:
                logger.error(f"Error creating subscription for user {user.id}: {e}")
                errors.append(
                    {"user_id": user.id, "username": user.username, "error": str(e)}
                )

        return Response(
            {
                "created": created_subscriptions,
                "already_subscribed": already_subscribed,
                "errors": errors,
                "total_created": len(created_subscriptions),
                "total_already_subscribed": len(already_subscribed),
                "total_errors": len(errors),
            },
            status=status.HTTP_201_CREATED
            if created_subscriptions
            else status.HTTP_200_OK,
        )

    def _send_invitation_notification(
        self, calendar, invited_user, owner, can_edit, can_manage
    ):
        """Отправляет уведомление о приглашении в календарь."""
        try:
            from notifications.signals import notify

            # Формируем текст о правах
            permissions_text = []
            if can_edit:
                permissions_text.append("редактирование событий")
            if can_manage:
                permissions_text.append("управление календарем")

            permissions_str = (
                f" с правами: {', '.join(permissions_text)}" if permissions_text else ""
            )

            owner_name = owner.get_full_name() or owner.username

            notify.send(
                sender=owner,
                recipient=invited_user,
                verb='calendar_invitation',
                action_object=calendar,
                description=(
                    f'{owner_name} пригласил вас в календарь '
                    f'"{calendar.title}"{permissions_str}.'
                ),
                action_url='/calendar',
                data={
                    'title': f'Приглашение в календарь: {calendar.title}',
                    'calendar_id': calendar.id,
                    'can_edit': can_edit,
                    'can_manage': can_manage,
                },
            )
            logger.info(
                f"Sent invitation notification to user {invited_user.id} "
                f"for calendar {calendar.id}"
            )
        except Exception as e:
            logger.error(f"Error sending invitation notification: {e}")


class CalendarSubscriptionViewSet(ModelViewSet):
    """CRUD операции для подписок на календари.

    Доступные действия:
    - list: список подписок текущего пользователя
    - create: создание новой подписки
    - retrieve: просмотр подписки
    - update/partial_update: обновление подписки (права доступа)
    - destroy: удаление подписки
    """

    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer]

    def get_queryset(self):
        """Подписки пользователя + подписки на его календари."""
        from calendar_app.models import CalendarSubscription
        from django.db.models import Q

        user = self.request.user

        if user.is_superuser or user.is_staff:
            # Админы видят все подписки
            return CalendarSubscription.objects.all()

        # Обычные пользователи видят:
        # 1. Свои подписки (user=user)
        # 2. Подписки на календари, где они владельцы
        return CalendarSubscription.objects.filter(
            Q(user=user)  # Свои подписки
            | Q(calendar__owner_user=user)  # Владелец календаря
        ).distinct()

    def get_serializer_class(self):
        """Выбор сериализатора по действию."""
        if self.action in {"create", "update", "partial_update"}:
            return CalendarSubscriptionWriteSerializer
        return CalendarSubscriptionSerializer

    def perform_create(self, serializer):
        """Создание подписки."""
        # Пользователь устанавливается автоматически в сериализаторе
        subscription = serializer.save(user=self.request.user)
        invalidate_subscription_cache(user_id=subscription.user_id)

    def perform_update(self, serializer):
        """Обновление подписки."""
        subscription = self.get_object()
        user = self.request.user

        # Получаем изменяемые поля
        validated_data = serializer.validated_data

        # Проверяем, какие поля пытаются изменить
        permission_fields = {"can_edit", "can_manage"}
        personal_fields = {"is_visible", "color_override"}

        changing_permissions = any(
            field in validated_data for field in permission_fields
        )
        changing_personal = any(field in validated_data for field in personal_fields)

        # Права (can_edit, can_manage) - только владелец календаря
        if changing_permissions and not subscription.calendar.is_owner(user):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                "Только владелец календаря может изменять права подписки."
            )

        # Личные настройки (is_visible, color_override) - владелец подписки
        is_subscription_owner = subscription.user == user
        is_calendar_owner = subscription.calendar.is_owner(user)

        if changing_personal and not is_subscription_owner:
            if not is_calendar_owner:
                from rest_framework.exceptions import PermissionDenied

                raise PermissionDenied(
                    "Вы можете изменять только свои личные настройки."
                )

        updated = serializer.save()
        invalidate_subscription_cache(user_id=updated.user_id)

    def perform_destroy(self, instance):
        """Удаление подписки."""
        user = self.request.user

        # Удалять подписку может владелец подписки или календаря
        if not (instance.user == user or instance.calendar.is_owner(user)):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Вы не можете удалить эту подписку.")

        user_id = instance.user_id
        instance.delete()
        invalidate_subscription_cache(user_id=user_id)

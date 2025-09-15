from __future__ import annotations

from typing import Any, List  # было: Any, Dict, List, Type

from django.db.models import QuerySet
# from django.shortcuts import get_object_or_404  # <- не используется
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request as DRFRequest
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer  # <- для типизации get_serializer_class

from requests_app.models import Request as EmployeeRequest, RequestComment

from ..permissions import AdminOrActionOrModelPerms
from .serializers import (
    RequestCommentSerializer,
    RequestReadSerializer,
    RequestWriteSerializer,
)


class RequestViewSet(viewsets.ModelViewSet):
    """ViewSet для заявок сотрудников.

    Админы могут всё. Пользователи с модельными правами действуют по правам.
    Без прав аутентифицированные пользователи работают только со своими заявками.

    Поддерживает экшены:
      - POST /requests/{id}/approve/
      - POST /requests/{id}/reject/
      - POST /requests/{id}/cancel/
      - GET/POST /requests/{id}/comments/

    Raises:
        PermissionDenied: При нарушении правил доступа.
    """

    queryset = EmployeeRequest.objects.select_related(
        "employee", "approver", "department"
    ).all()
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    

    def get_permissions(self) -> list[Any]:
        """Подбирает пермишены под текущий action."""
        return [IsAuthenticated(), AdminOrActionOrModelPerms()]

    def get_serializer_class(self) -> type[BaseSerializer]:
        """Возвращает сериализатор в зависимости от action."""
        if self.action in {"list", "retrieve"}:
            return RequestReadSerializer
        return RequestWriteSerializer

    # ---------- Queryset с учётом прав ----------

    def _can_view_all(self, user) -> bool:
        """Проверяет, может ли пользователь видеть все заявки."""
        return bool(
            user.is_staff
            or user.has_perm("requests_app.can_view_all_requests")
            or user.has_perm("requests_app.view_request")
        )

    def get_queryset(self) -> QuerySet[EmployeeRequest]:
        """Ограничивает список заявок с учётом прав и запроса.

        Поведение:
            - Администратор (is_staff=True):
                * по умолчанию видит все заявки;
                * если передать `?view=mine` ИЛИ `?mine=1`, видит только свои.
            - Пользователь с модельными правами просмотра (`view_request` или
              `requests_app.can_view_all_requests`): видит все.
            - Прочие аутентифицированные пользователи: только свои (параметры
              `view`/`mine` игнорируются).

        Поддерживаются простые фильтры `?type=...&status=...`.
        """
        qs = super().get_queryset()
        user = self.request.user
        params = self.request.query_params

        # Явный запрос "только свои" для админов
        mine_raw = (params.get("mine") or "").lower()
        want_mine = (params.get("view") == "mine") or (mine_raw in {"1", "true", "yes", "on"})

        if user.is_staff:
            if want_mine:
                qs = qs.filter(employee_id=user.id)
        else:
            # Если нет прав на просмотр всех — урезаем до своих
            if not self._can_view_all(user):
                qs = qs.filter(employee_id=user.id)

        # Доп. фильтры
        t = (params.get("type") or "").strip()
        s = (params.get("status") or "").strip()
        if t:
            qs = qs.filter(type=t)
        if s:
            qs = qs.filter(status=s)

        return qs

    # ---------- CRUD ----------

    def perform_create(self, serializer: RequestWriteSerializer) -> None:
        """Создание: сотруднику принудительно ставим себя как автора (если не админ)."""
        user = self.request.user
        is_power = user.is_staff or user.has_perm("requests_app.add_request")
        data: dict[str, Any] = {}
        if not is_power:
            data["employee"] = user
        serializer.save(**data)

    def perform_update(self, serializer: RequestWriteSerializer) -> None:
        """Обновление: владельцу разрешаем до финального статуса.

        Raises:
            PermissionDenied: Если заявка финальная и нет прав, либо правка чужой заявки без прав.
        """
        obj = self.get_object()
        user = self.request.user
        if obj.is_final and not (
            user.is_staff or user.has_perm("requests_app.change_request")
        ):
            raise PermissionDenied("Финальная заявка недоступна для правок.")
        if (obj.employee_id != user.id) and not (
            user.is_staff or user.has_perm("requests_app.change_request")
        ):
            raise PermissionDenied("Нельзя редактировать чужую заявку.")
        serializer.save()

    # ---------- Комментарии ----------

    @action(detail=True, methods=["get", "post"])
    def comments(self, request: DRFRequest, pk: int | str | None = None) -> Response:
        """Список/создание комментариев для заявки.

        GET: список комментариев
        POST: создать комментарий { "text": "..." }
        """
        req_obj = self.get_object()
        if request.method == "GET":
            qs = RequestComment.objects.filter(request=req_obj).select_related("author")
            ser = RequestCommentSerializer(qs, many=True, context=self.get_serializer_context())
            return Response(ser.data)

        # POST
        ser = RequestCommentSerializer(data=request.data, context=self.get_serializer_context())
        ser.is_valid(raise_exception=True)
        ser.save(request=req_obj, author=request.user)
        return Response(ser.data, status=status.HTTP_201_CREATED)

    # ---------- Экшены статусов ----------

    @action(detail=True, methods=["post"])
    def approve(self, request: DRFRequest, pk: int | str | None = None) -> Response:
        """Одобряет заявку. Требует прав can_process_requests/change_request.

        Raises:
            PermissionDenied: Если у пользователя нет достаточных прав.
        """
        obj = self.get_object()
        user = request.user
        if not (
            user.is_staff
            or user.has_perm("requests_app.can_process_requests")
            or user.has_perm("requests_app.change_request")
        ):
            raise PermissionDenied("Недостаточно прав для одобрения заявки.")
        obj.approve(by_user=user)
        return Response(RequestReadSerializer(obj, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def reject(self, request: DRFRequest, pk: int | str | None = None) -> Response:
        """Отклоняет заявку. Требует прав can_process_requests/change_request.

        Raises:
            PermissionDenied: Если у пользователя нет достаточных прав.
        """
        obj = self.get_object()
        user = request.user
        if not (
            user.is_staff
            or user.has_perm("requests_app.can_process_requests")
            or user.has_perm("requests_app.change_request")
        ):
            raise PermissionDenied("Недостаточно прав для отклонения заявки.")
        obj.reject(by_user=user)
        return Response(RequestReadSerializer(obj, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request: DRFRequest, pk: int | str | None = None) -> Response:
        """Отменяет заявку.

        Владельцу разрешено, если заявка ещё не финальна.
        Администратору — всегда.

        Raises:
            PermissionDenied: Если пользователь не владелец/не админ, или заявка финальная для не-админа.
        """
        obj = self.get_object()
        user = request.user
        if not (user.is_staff or obj.employee_id == user.id):
            raise PermissionDenied("Нельзя отменять чужую заявку.")
        if obj.is_final and not user.is_staff:
            raise PermissionDenied("Финальная заявка уже не может быть отменена.")
        obj.cancel()
        return Response(RequestReadSerializer(obj, context=self.get_serializer_context()).data)

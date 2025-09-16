from __future__ import annotations

from typing import Any, List, Optional  # было: Any, Dict, List, Type

from django.db.models import Q, QuerySet
from django.shortcuts import get_object_or_404  # раскомментируйте импорт
from employees.models import EmployeeDepartment
from requests_app.models import Request as EmployeeRequest
from requests_app.models import RequestComment
# from django.shortcuts import get_object_or_404  # <- не используется
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import (SAFE_METHODS, BasePermission,
                                        IsAuthenticated)
from rest_framework.request import Request as DRFRequest
from rest_framework.response import Response
from rest_framework.serializers import \
    BaseSerializer  # <- для типизации get_serializer_class

from ..permissions import (AdminOrActionOrModelPerms, AdminOrDeptAllowed,
                           IsSelfOrStaff)
from .permissions import (CommentsPermission, DeptCanProcess,
                          DeptChangeRequest, DeptComments, DeptViewRequest,
                          NotFinalOrStaff)
from .serializers import (RequestCommentSerializer, RequestReadSerializer,
                          RequestWriteSerializer)


class RequestViewSet(viewsets.ModelViewSet):
    """ViewSet для заявок сотрудников.

    Админы могут всё. Пользователи с модельными правами действуют по правам.
    Без прав аутентифицированные пользователи работают только со своими заявками.

    Поддерживаемые экшены:
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
    pagination_class = None

    # Декларативная карта прав. Поддерживаются:
    # - строка ("approve": "app.perm")
    # - список (ИЛИ прав)
    # - карта по методам для action ("comments": {"GET": "...", "POST": "..."}).
    required_perms_by_action = {
        "comments": {
            "GET": "requests_app.view_requestcomment",
            "HEAD": "requests_app.view_requestcomment",  # на всякий случай
            "POST": "requests_app.add_requestcomment",
        },
        "reject": ["requests_app.can_process_requests", "requests_app.change_request"],
        "approve": ["requests_app.can_process_requests", "requests_app.change_request"],
        # cancel — проверяется владением/админством, отдельный код не нужен
    }

    def get_permissions(self) -> list[BasePermission]:
        """Подбирает пермишены под текущий action.

        - comments: владелец ИЛИ staff ИЛИ явные модельные права из required_perms_by_action.
        - approve/reject: аутентификация + явные права из required_perms_by_action.
        - cancel: владелец ИЛИ staff.
        - остальное (CRUD): владелец ИЛИ staff ИЛИ модельные права.
        """
        if self.action == "comments":
            return [CommentsPermission()]
        if self.action in {"approve", "reject"}:
            return [IsAuthenticated(), (AdminOrActionOrModelPerms)()]
        if self.action == "cancel":
            return [IsAuthenticated(), IsSelfOrStaff()]
        if self.action == "destroy":
            return [IsAuthenticated(), IsSelfOrStaff(), NotFinalOrStaff()]
        return [(IsSelfOrStaff | AdminOrActionOrModelPerms)()]

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
        """Список заявок с учётом прав:
        - staff/глобальные видят всё (или только свои при ?view=mine),
        - остальные: свои + по отделам, где есть право 'view_request'.
        """
        qs = super().get_queryset()
        user = self.request.user
        params = self.request.query_params

        mine_raw = (params.get("mine") or "").lower()
        want_mine = (params.get("view") == "mine") or (mine_raw in {"1", "true", "yes", "on"})

        if user.is_staff or self._can_view_all(user):
            if want_mine:
                qs = qs.filter(employee_id=user.id)
        else:
            # отделы, где у пользователя есть dept-право 'view_request'
            dept_ids_qs = (
                EmployeeDepartment.objects
                .filter(employee_id=user.id, is_active=True, role__scoped_permissions__code="view_request")
                .values_list("department_id", flat=True)
                .distinct()
            )
            scope = Q(employee_id=user.id) | Q(department_id__in=dept_ids_qs)
            qs = qs.filter(scope)

        t = (params.get("type") or "").strip()
        s = (params.get("status") or "").strip()
        if t:
            qs = qs.filter(type=t)
        if s:
            qs = qs.filter(status=s)

        return qs

    # --- ВАЖНО: не ловить 404 на detail-экшенах из-за урезанного get_queryset() ---

    def get_object(self):
        """Возвращает объект для detail-экшенов.

        Для 'approve', 'reject', 'comments', 'cancel' берём объект из полного
        набора записей по первичному ключу (в обход get_queryset()), затем
        вызываем check_object_permissions() — чтобы объектные пермишены отработали.
        Для остальных действий — стандартное поведение базового класса.

        Returns:
            EmployeeRequest: Объект заявки.

        Raises:
            Http404: Если объект не найден.
            PermissionDenied: Если объектные права не пройдены.
        """
        if getattr(self, "action", None) in {"approve", "reject", "comments", "cancel"}:
            lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
            lookup_val = self.kwargs[lookup_url_kwarg]
            obj = get_object_or_404(EmployeeRequest, **{self.lookup_field: lookup_val})
            self.check_object_permissions(self.request, obj)
            return obj
        return super().get_object()

    # ---------- CRUD ----------

    def perform_create(self, serializer: RequestWriteSerializer) -> None:
        """Создание: для не-админа принудительно ставим себя как автора."""
        user = self.request.user
        is_power = user.is_staff or user.has_perm("requests_app.add_request")
        extra = {"employee": user} if not is_power else {}
        serializer.save(**extra)

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

        GET: список комментариев (staff, владелец или право view_requestcomment).
        POST: создание {"text": "..."} (staff, владелец или право add_requestcomment).
        """
        req_obj = self.get_object()  # проходит через check_object_permissions()

        if request.method in {"GET", "HEAD"}:
            qs = RequestComment.objects.filter(request=req_obj).select_related("author")
            ser = RequestCommentSerializer(
                qs, many=True, context=self.get_serializer_context()
            )
            return Response(ser.data)

        ser = RequestCommentSerializer(
            data=request.data, context=self.get_serializer_context()
        )
        ser.is_valid(raise_exception=True)
        ser.save(request=req_obj, author=request.user)
        return Response(ser.data, status=status.HTTP_201_CREATED)

    # ---------- Экшены статусов (только бизнес-валидация) ----------

    @action(detail=True, methods=["post"])
    def approve(self, request: DRFRequest, pk: int | str | None = None) -> Response:
        """Одобряет заявку.

        Raises:
            ValidationError: Если заявка уже финальная.
        """
        obj = self.get_object()  # права проверит AdminOrActionOrModelPerms
        if getattr(obj, "is_final", False):
            raise ValidationError("Заявка уже в финальном статусе.")
        obj.approve(by_user=request.user)
        return Response(
            RequestReadSerializer(obj, context=self.get_serializer_context()).data
        )

    @action(detail=True, methods=["post"])
    def reject(self, request: DRFRequest, pk: int | str | None = None) -> Response:
        """Отклоняет заявку.

        Raises:
            ValidationError: Если заявка уже финальная.
        """
        obj = self.get_object()  # права проверит AdminOrActionOrModelPerms
        if getattr(obj, "is_final", False):
            raise ValidationError("Заявка уже в финальном статусе.")
        obj.reject(by_user=request.user)
        return Response(
            RequestReadSerializer(obj, context=self.get_serializer_context()).data
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request: DRFRequest, pk: int | str | None = None) -> Response:
        """Отменяет заявку (владелец или админ).

        Raises:
            PermissionDenied: Если заявка финальная (для не admin).
        """
        obj = self.get_object()  # владение/admin проверит IsSelfOrStaff
        if getattr(obj, "is_final", False) and not request.user.is_staff:
            raise PermissionDenied("Финальная заявка уже не может быть отменена.")
        obj.cancel()
        return Response(
            RequestReadSerializer(obj, context=self.get_serializer_context()).data
        )

    def create(self, request, *args, **kwargs):
        """Создание заявки: валидируем write-сериализатором, отвечаем read-сериализатором."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        read = RequestReadSerializer(instance, context=self.get_serializer_context())
        headers = self.get_success_headers(read.data)
        return Response(read.data, status=status.HTTP_201_CREATED, headers=headers)

from __future__ import annotations

from typing import Any, List, Optional  # было: Any, Dict, List, Type

from django.db.models import Q, QuerySet
from django.shortcuts import get_object_or_404  # раскомментируйте импорт
from employees.models import EmployeeDepartment, Department  # добавлен Department
from requests_app.models import Request as EmployeeRequest
from requests_app.models import RequestComment
from requests_app.enums import RequestStatus

# from django.shortcuts import get_object_or_404  # <- не используется
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import (
    NotAuthenticated,
    PermissionDenied,
    ValidationError,
)
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import SAFE_METHODS, BasePermission, IsAuthenticated
from rest_framework.request import Request as DRFRequest
from rest_framework.response import Response
from rest_framework.serializers import (
    BaseSerializer,
)  # <- для типизации get_serializer_class

from ..permissions import AdminOrActionOrModelPerms, AdminOrDeptAllowed, IsSelfOrStaff
from .permissions import (
    CommentsPermission,
    DeptCanProcess,
    DeptChangeRequest,
    DeptComments,
    DeptViewRequest,
    NotFinalOrStaff,
)
from .serializers import (
    RequestCommentSerializer,
    RequestReadSerializer,
    RequestWriteSerializer,
)


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
    # Используем глобальную пагинацию из settings (PageNumberPagination, PAGE_SIZE=20)

    required_perms_by_action = {
        "comments": {
            "GET": "requests_app.view_requestcomment",
            "HEAD": "requests_app.view_requestcomment",
            "POST": "requests_app.add_requestcomment",
        },
        "reject": ["requests_app.can_process_requests", "requests_app.change_request"],
        "approve": ["requests_app.can_process_requests", "requests_app.change_request"],
    }

    def get_permissions(self) -> list[BasePermission]:
        """Подбирает пермишены под текущий action.

        - comments: владелец ИЛИ staff ИЛИ явные модельные права из required_perms_by_action.
        - approve/reject: аутентификация + явные права из required_perms_by_action.
        - cancel: владелец ИЛИ staff.
        - остальное (CRUD): владелец ИЛИ staff ИЛИ модельные права.
        """
        if self.action == "comments":
            return [(CommentsPermission | DeptComments)()]
        if self.action in {"approve", "reject"}:
            return [(AdminOrActionOrModelPerms | DeptCanProcess)()]
        if self.action == "cancel":
            return [IsSelfOrStaff()]
        if self.action == "retrieve":
            return [(IsSelfOrStaff | DeptViewRequest | AdminOrActionOrModelPerms)()]
        if self.action == "destroy":
            return [
                (IsSelfOrStaff | AdminOrActionOrModelPerms | DeptChangeRequest)(),
                NotFinalOrStaff(),
            ]
        return [(IsSelfOrStaff | AdminOrActionOrModelPerms | DeptChangeRequest)()]

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
        """Список заявок с учётом прав и получателей:
        - staff/глобальные видят всё (или только свои при ?view=mine),
        - автор видит свои заявки,
        - получатели (recipients/cc_users) видят адресованные им,
        - сотрудники отделов видят заявки отделов (с правами),
        - при sent_to_all_department видят все из отделов.
        """
        qs = super().get_queryset()
        user = self.request.user
        params = self.request.query_params

        mine_raw = (params.get("mine") or "").lower()
        want_mine = (params.get("view") == "mine") or (
            mine_raw in {"1", "true", "yes", "on"}
        )
        
        # Новый параметр для фильтрации "мне адресовано"
        addressed_to_me = params.get("addressed_to_me") == "true"

        if user.is_staff or self._can_view_all(user):
            if want_mine:
                qs = qs.filter(employee_id=user.id)
            elif addressed_to_me:
                # Заявки, где я получатель
                my_dept_ids = EmployeeDepartment.objects.filter(
                    employee=user,
                    is_active=True
                ).values_list('department_id', flat=True)
                
                scope = (
                    Q(recipients=user) | 
                    Q(cc_users=user) |
                    Q(
                        sent_to_all_department=True,
                        departments__in=my_dept_ids
                    )
                )
                qs = qs.filter(scope).distinct()
        else:
            # Обычный пользователь
            scope = Q(employee_id=user.id)  # Свои заявки
            
            # Заявки, где я получатель (основной или CC)
            scope |= Q(recipients=user) | Q(cc_users=user)
            
            # Заявки отделов с sent_to_all_department
            my_dept_ids = EmployeeDepartment.objects.filter(
                employee=user,
                is_active=True
            ).values_list('department_id', flat=True)
            
            if my_dept_ids:
                scope |= Q(
                    sent_to_all_department=True,
                    departments__in=my_dept_ids
                )
            
            # Департаментные права (как было)
            view_dept_ids = (
                EmployeeDepartment.objects.filter(
                    employee_id=user.id,
                    is_active=True,
                    role__scoped_permissions__code="view_request",
                )
                .values_list("department_id", flat=True)
                .distinct()
            )
            proc_dept_ids = (
                EmployeeDepartment.objects.filter(
                    employee_id=user.id,
                    is_active=True,
                    role__scoped_permissions__code="can_process_requests",
                )
                .values_list("department_id", flat=True)
                .distinct()
            )
            head_dept_ids = Department.objects.filter(
                head_id=user.id
            ).values_list("id", flat=True)
            
            combined_ids = (
                set(view_dept_ids) | set(proc_dept_ids) | set(head_dept_ids)
            )

            if combined_ids:
                # Заявки этих отделов (новое поле departments)
                scope |= Q(departments__in=combined_ids)
                
                # Заявки сотрудников этих отделов
                dept_emp_ids = (
                    EmployeeDepartment.objects.filter(
                        department_id__in=list(combined_ids),
                        is_active=True,
                    )
                    .values_list("employee_id", flat=True)
                    .distinct()
                )
                if dept_emp_ids:
                    scope |= Q(employee_id__in=list(dept_emp_ids))
            
            # Фильтр "только адресованные мне"
            if addressed_to_me:
                scope = (
                    Q(recipients=user) | Q(cc_users=user) |
                    Q(
                        sent_to_all_department=True, 
                        departments__in=my_dept_ids
                    )
                )
            elif want_mine:
                scope = Q(employee_id=user.id)
            
            qs = qs.filter(scope).distinct()

        # Применяем фильтры type/status для всех пользователей
        t = (params.get("type") or "").strip()
        s = (params.get("status") or "").strip()
        if t:
            qs = qs.filter(type=t)
        if s:
            qs = qs.filter(status=s)

        return qs

    # --- ВАЖНО: не ловить 404 на detail-экшенах из-за урезанного get_queryset() ---

    def get_object(self) -> EmployeeRequest:
        """Возвращает объект заявки для detail-экшенов.

        Для экшенов {'approve', 'reject', 'comments', 'cancel', 'retrieve'}:
        - достаём объект **в обход** урезанного get_queryset() по PK,
        - прогоняем через object-level пермишены (check_object_permissions),
          чтобы при отсутствии прав получить **403 Forbidden**, а не 404.

        Returns:
            EmployeeRequest: Объект заявки.

        Raises:
            Http404: Если объект с таким PK не существует вообще.
            PermissionDenied: Если object-level пермишены не пройдены.
        """
        if getattr(self, "action", None) in {
            "approve",
            "reject",
            "comments",
            "cancel",
            "retrieve",
        }:
            lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
            lookup_value = self.kwargs[lookup_url_kwarg]
            base = EmployeeRequest.objects.select_related("employee", "approver", "department")
            obj = get_object_or_404(base, **{self.lookup_field: lookup_value})
            self.check_object_permissions(self.request, obj)
            return obj

        return super().get_object()

    # ---------- CRUD ----------

    def perform_create(self, serializer: RequestWriteSerializer) -> None:
        """Создание: для не-админа принудительно ставим себя как автора."""
        user = self.request.user
        if not user or not user.is_authenticated:
            raise NotAuthenticated("Authentication required")
        is_power = user.is_staff or user.has_perm("requests_app.add_request")
        extra = {"employee": user} if not is_power else {}
        save_as = (self.request.query_params.get("save_as") or "").strip().lower()
        if save_as == "draft":
            extra["status"] = RequestStatus.DRAFT  # ✅ обычному пользователю поле в payload всё равно бы «очистили»

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
        extra: dict[str, Any] = {}
        save_as = (self.request.query_params.get("save_as") or "").strip().lower()

        if save_as == "draft":
            extra["status"] = RequestStatus.DRAFT
        elif save_as == "submit" and obj.status == RequestStatus.DRAFT:
            # ⬅️ явная подача «на рассмотрение» из черновика
            extra["status"] = RequestStatus.PENDING

        serializer.save(**extra)

    # ---------- Комментарии ----------

    @action(detail=True, methods=["get", "post"])
    def comments(self, request: DRFRequest, pk: int | str | None = None) -> Response:
        """Список/создание комментариев для заявки.

        GET: список комментариев (staff, владелец или право view_requestcomment).
        POST: создание {"text": "..."} (staff, владелец или право add_requestcomment).
        """
        req_obj = self.get_object()

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
        obj = self.get_object()
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
        obj = self.get_object()
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

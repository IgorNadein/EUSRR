from __future__ import annotations

import calendar
from datetime import date
from typing import Any  # было: Any, Dict, List, Type

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, IntegerField, OuterRef, Q, QuerySet, Subquery, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404  # раскомментируйте импорт
from django.utils import timezone
from requests_app.enums import RequestStatus, RequestType
from requests_app.models import Request as EmployeeRequest
from communications import comments_helpers
from drf_spectacular.utils import OpenApiParameter, extend_schema

# from django.shortcuts import get_object_or_404  # <- не используется
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import (
    NotAuthenticated,
    PermissionDenied,
    ValidationError,
)
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import BasePermission
from rest_framework.request import Request as DRFRequest
from rest_framework.response import Response
from rest_framework.serializers import (
    BaseSerializer,
)  # <- для типизации get_serializer_class

from .permissions import (
    CanViewRequest,
    CommentsPermission,
    IsRecipientOfRequest,
    IsRequestAuthor,
    NotFinalOrStaff,
)
from .serializers import (
    RequestReadSerializer,
    RequestWriteSerializer,
)


UNPAID_VACATION_MARKERS = (
    "за свой счет",
    "за свой счёт",
    "без сохранения заработной платы",
    "без сохранения зарплаты",
    "без сохранения зп",
    "неоплачиваем",
)


def _request_duration_days(req: EmployeeRequest) -> int:
    """Возвращает длительность заявки в днях, включая обе даты."""
    if req.date_from and req.date_to:
        return max((req.date_to - req.date_from).days + 1, 0)
    if req.date_from:
        return 1
    return 0


def _is_unpaid_vacation(req: EmployeeRequest) -> bool:
    """Определяет отпуск за свой счёт по текстовым маркерам.

    Явного поля в модели пока нет, поэтому используем временную эвристику
    по title/comment.
    """
    haystack = " ".join(
        [
            str(getattr(req, "title", "") or ""),
            str(getattr(req, "comment", "") or ""),
        ]
    ).lower()
    return any(marker in haystack for marker in UNPAID_VACATION_MARKERS)


def _resolve_stats_window(period: str) -> tuple[timezone.datetime.date, timezone.datetime.date] | tuple[None, None]:
    """Возвращает границы окна статистики для month/year/all."""
    today = timezone.localdate()
    if period == "month":
        _, last_day = calendar.monthrange(today.year, today.month)
        return today.replace(day=1), today.replace(day=last_day)
    if period == "year":
        return today.replace(month=1, day=1), today.replace(month=12, day=31)
    return None, None


def _parse_iso_date(raw_value: str, field_name: str) -> date:
    """Парсит ISO-даты для custom period."""
    try:
        return date.fromisoformat(raw_value)
    except ValueError as exc:
        raise ValidationError(
            {field_name: ["Ожидается дата в формате YYYY-MM-DD."]}
        ) from exc


def _resolve_stats_window_from_query(
    period: str, request: DRFRequest
) -> tuple[date | None, date | None]:
    """Возвращает окно статистики, включая custom range."""
    if period != "custom":
        return _resolve_stats_window(period)

    date_from_raw = (request.query_params.get("date_from") or "").strip()
    date_to_raw = (request.query_params.get("date_to") or "").strip()
    if not date_from_raw or not date_to_raw:
        raise ValidationError(
            {
                "date_from": ["Обязательное поле для custom периода."],
                "date_to": ["Обязательное поле для custom периода."],
            }
        )

    start_date = _parse_iso_date(date_from_raw, "date_from")
    end_date = _parse_iso_date(date_to_raw, "date_to")
    if start_date > end_date:
        raise ValidationError(
            {"date_to": ["Дата окончания не может быть раньше даты начала."]}
        )
    return start_date, end_date


def _request_duration_days_in_window(
    req: EmployeeRequest,
    start_date,
    end_date,
) -> int:
    """Возвращает число дней заявки внутри заданного окна."""
    if start_date is None or end_date is None:
        return _request_duration_days(req)

    if req.date_from and req.date_to:
        overlap_start = max(req.date_from, start_date)
        overlap_end = min(req.date_to, end_date)
        if overlap_start > overlap_end:
            return 0
        return (overlap_end - overlap_start).days + 1

    if req.date_from and start_date <= req.date_from <= end_date:
        return 1

    return 0


def _can_view_request_statistics(user) -> bool:
    return bool(
        getattr(user, "is_staff", False)
        or getattr(user, "is_superuser", False)
        or user.has_perm("requests_app.view_statistics")
        or user.has_perm("requests_app.can_view_all_requests")
    )


def _build_employee_statistics(
    employee_id: int,
    employee_name: str,
    period: str,
    start_date: date | None = None,
    end_date: date | None = None,
):
    if period != "custom":
        start_date, end_date = _resolve_stats_window(period)

    base_qs = EmployeeRequest.objects.filter(employee_id=employee_id).exclude(
        status=RequestStatus.DRAFT
    )
    if start_date and end_date:
        base_qs = base_qs.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
        )

    approved_qs = EmployeeRequest.objects.filter(
        employee_id=employee_id,
        status=RequestStatus.APPROVED,
    )

    sick_leave_days = 0
    day_off_days = 0
    maternity_days = 0
    paid_vacation_days = 0
    unpaid_vacation_days = 0

    for req in approved_qs.only(
        "type", "date_from", "date_to", "title", "comment"
    ):
        duration = _request_duration_days_in_window(
            req,
            start_date,
            end_date,
        )
        if req.type == RequestType.SICK_LEAVE:
            sick_leave_days += duration
        elif req.type == RequestType.DAY_OFF:
            day_off_days += duration
        elif req.type == RequestType.MATERNITY:
            maternity_days += duration
        elif req.type == RequestType.VACATION:
            if _is_unpaid_vacation(req):
                unpaid_vacation_days += duration
            else:
                paid_vacation_days += duration

    return {
        "employee_id": employee_id,
        "employee_name": employee_name,
        "period": period,
        "date_from": start_date.isoformat() if start_date else None,
        "date_to": end_date.isoformat() if end_date else None,
        "total_submitted_requests": base_qs.count(),
        "sick_leave_requests_count": base_qs.filter(
            type=RequestType.SICK_LEAVE
        ).count(),
        "day_off_requests_count": base_qs.filter(
            type=RequestType.DAY_OFF
        ).count(),
        "maternity_requests_count": base_qs.filter(
            type=RequestType.MATERNITY
        ).count(),
        "sick_leave_days": sick_leave_days,
        "day_off_days": day_off_days,
        "maternity_days": maternity_days,
        "paid_vacation_days": paid_vacation_days,
        "unpaid_vacation_days": unpaid_vacation_days,
    }


class RequestViewSet(viewsets.ModelViewSet):
    """ViewSet для заявок сотрудников.

    Обычный UI/API работает по строгим правилам участников:
    автор, прямые получатели и пользователи в копии.

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
    ).order_by("-created_at")
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    # Используем глобальную пагинацию из settings (PageNumberPagination,
    # PAGE_SIZE=20)

    def get_permissions(self) -> list[BasePermission]:
        """Подбирает пермишены под текущий action.

                - comments/retrieve/delete_comment: только участники заявки.
                - approve/reject: только прямой получатель заявки.
        - cancel: только автор заявки.
        - остальное (CRUD): только автор заявки.
        """
        if self.action == "comments":
            return [CommentsPermission()]
        if self.action == "delete_comment":
            return [CommentsPermission()]
        if self.action in {"approve", "reject"}:
            return [IsRecipientOfRequest()]
        if self.action == "cancel":
            return [IsRequestAuthor()]
        if self.action == "statistics":
            from rest_framework.permissions import IsAuthenticated

            return [IsAuthenticated()]
        if self.action in {"retrieve", "employee_statistics"}:
            return [CanViewRequest()]
        if self.action == "destroy":
            return [IsRequestAuthor(), NotFinalOrStaff()]
        return [IsRequestAuthor()]

    def get_serializer_class(self) -> type[BaseSerializer]:
        """Возвращает сериализатор в зависимости от action."""
        if self.action in {"list", "retrieve"}:
            return RequestReadSerializer
        return RequestWriteSerializer

    # ---------- Queryset с учётом прав ----------

    def get_queryset(self) -> QuerySet[EmployeeRequest]:
        """Список заявок с учётом строгих правил участия.

        TODO: Отдельно переопределить семантику sent_to_all_department
        для обычного UI/API. В этом проходе фиксируем только пользовательскую
        адресацию: автор, recipients и cc_users.
        """
        qs = super().get_queryset()
        user = self.request.user
        params = self.request.query_params

        mine_raw = (params.get("mine") or "").lower()
        want_mine = (params.get("view") == "mine") or (
            mine_raw in {"1", "true", "yes", "on"}
        )

        incoming_scope = (
            Q(recipients=user) | Q(cc_users=user)
        ) & ~Q(status=RequestStatus.DRAFT)

        addressed_to_me = params.get("addressed_to_me") == "true"
        if addressed_to_me:
            scope = incoming_scope
        elif want_mine:
            scope = Q(employee_id=user.id)
        else:
            scope = Q(employee_id=user.id) | incoming_scope

        qs = qs.filter(scope).distinct()

        # Применяем фильтры
        # type/status/employee_id/created_from/created_to/date_from/date_to для
        # всех пользователей
        t = (params.get("type") or "").strip()
        s = (params.get("status") or "").strip()
        employee_id = (params.get("employee_id") or "").strip()
        created_from = (params.get("created_from") or "").strip()
        created_to = (params.get("created_to") or "").strip()
        date_from = (params.get("date_from") or "").strip()
        date_to = (params.get("date_to") or "").strip()

        if t:
            qs = qs.filter(type=t)
        if s:
            qs = qs.filter(status=s)
        if employee_id and employee_id.isdigit():
            qs = qs.filter(employee_id=int(employee_id))

        # Фильтры по дате создания заявления
        if created_from:
            qs = qs.filter(created_at__date__gte=created_from)
        if created_to:
            qs = qs.filter(created_at__date__lte=created_to)

        # Фильтры по периоду заявления (date_from/date_to в самой заявке)
        if date_from:
            # Заявки, у которых период не закончился до указанной даты
            qs = qs.filter(Q(date_to__isnull=True) | Q(date_to__gte=date_from))
        if date_to:
            # Заявки, у которых период не начался после указанной даты
            qs = qs.filter(
                Q(date_from__isnull=True) | Q(date_from__lte=date_to)
            )

        # Аннотируем счётчик комментариев через communications.Chat
        from communications.models import Message

        # ContentType для EmployeeRequest
        request_ct = ContentType.objects.get_for_model(EmployeeRequest)

        # Подсчёт сообщений в чате комментариев для каждой заявки
        comments_subquery = (
            Message.objects.filter(
                chat__type="comments",
                chat__context_content_type=request_ct,
                chat__context_object_id=OuterRef("pk"),
                is_deleted=False,
            )
            .values("chat")
            .annotate(count=Count("id"))
            .values("count")
        )

        qs = qs.annotate(
            comments_count=Coalesce(
                Subquery(comments_subquery, output_field=IntegerField()),
                Value(0),
            )
        )

        return qs

    def _attach_linked_task_payloads(
        self,
        requests: list[EmployeeRequest],
    ) -> None:
        """Предзагрузить компактные бейджи задач для списка заявлений."""
        if not requests:
            return

        user = getattr(self.request, "user", None)
        request_ids = [request_obj.id for request_obj in requests]
        mapping = {request_id: [] for request_id in request_ids}

        if user and user.is_authenticated:
            from tasks.access import task_board_access_q
            from tasks.models import (
                TaskBoard,
                TaskLinkedObject,
                TaskLinkedObjectKind,
            )

            request_ct = ContentType.objects.get_for_model(EmployeeRequest)
            accessible_boards = TaskBoard.objects.filter(
                is_archived=False,
            ).filter(task_board_access_q(user))

            links = (
                TaskLinkedObject.objects.filter(
                    kind=TaskLinkedObjectKind.REQUEST,
                    content_type=request_ct,
                    object_id__in=request_ids,
                    task__board__in=accessible_boards,
                )
                .select_related("task", "task__board", "task__column")
                .order_by("object_id", "task__title", "task_id")
            )

            for link in links:
                mapping.setdefault(link.object_id, []).append(
                    {
                        "link_id": link.id,
                        "id": link.task_id,
                        "title": link.task.title,
                        "board_id": link.task.board_id,
                        "board_name": link.task.board.name,
                        "column_id": link.task.column_id,
                        "column_name": link.task.column.name,
                        "column_color": link.task.column.color,
                        "priority": link.task.priority,
                        "priority_display": link.task.get_priority_display(),
                    }
                )

        for request_obj in requests:
            request_obj._linked_task_payloads = mapping.get(request_obj.id, [])

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            self._attach_linked_task_payloads(list(page))
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        requests = list(queryset)
        self._attach_linked_task_payloads(requests)
        serializer = self.get_serializer(requests, many=True)
        return Response(serializer.data)

    # --- ВАЖНО: не ловить 404 на detail-экшенах
    # из-за урезанного get_queryset() ---

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
            "employee_statistics",
        }:
            lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
            lookup_value = self.kwargs[lookup_url_kwarg]
            base = EmployeeRequest.objects.select_related(
                "employee", "approver", "department"
            )
            obj = get_object_or_404(base, **{self.lookup_field: lookup_value})
            self.check_object_permissions(self.request, obj)
            return obj

        return super().get_object()

    # ---------- CRUD ----------

    def perform_create(self, serializer: RequestWriteSerializer) -> None:
        """Создание: автором всегда становится текущий пользователь."""
        user = self.request.user
        if not user or not user.is_authenticated:
            raise NotAuthenticated("Authentication required")
        extra = {"employee": user}
        save_as = (
            (self.request.query_params.get("save_as") or "").strip().lower()
        )
        if save_as == "draft":
            extra["status"] = (
                RequestStatus.DRAFT
            )  # ✅ обычному пользователю поле в payload всё равно бы «очистили»

        serializer.save(**extra)

    def perform_update(self, serializer: RequestWriteSerializer) -> None:
        """Обновление: владельцу разрешаем до финального статуса.

        Raises:
            PermissionDenied: Если заявка финальная или чужая.
        """
        obj = self.get_object()
        if obj.is_final:
            raise PermissionDenied("Финальная заявка недоступна для правок.")
        extra: dict[str, Any] = {}
        save_as = (
            (self.request.query_params.get("save_as") or "").strip().lower()
        )

        if save_as == "draft":
            extra["status"] = RequestStatus.DRAFT
        elif save_as == "submit" and obj.status == RequestStatus.DRAFT:
            # ⬅️ явная подача «на рассмотрение» из черновика
            extra["status"] = RequestStatus.PENDING

        serializer.save(**extra)

    # ---------- Комментарии ----------

    @action(detail=True, methods=["get", "post"])
    def comments(
        self, request: DRFRequest, pk: int | str | None = None
    ) -> Response:
        """Список/создание комментариев для заявки.

        GET: список комментариев участникам заявки.
        POST: создание {"text": "..."} участниками заявки.
        """
        import logging
        from .serializers import EmployeeBriefSerializer

        logger = logging.getLogger(__name__)

        req_obj = self.get_object()
        logger.info(
            f"[RequestViewSet.comments] user={request.user.id}, request_id={
                req_obj.id
            }, "
            f"method={request.method}"
        )

        if request.method in {"GET", "HEAD"}:
            # Используем unified comments system
            messages = comments_helpers.get_comments(req_obj)

            # Форматируем в старый формат API для совместимости
            comments_data = []
            for msg in messages:
                author_ser = EmployeeBriefSerializer(msg.author)
                comments_data.append(
                    {
                        "id": msg.id,
                        "request": req_obj.id,
                        "author": author_ser.data,
                        # content -> text для совместимости
                        "text": msg.content,
                        "created_at": msg.created_at,
                    }
                )

            logger.info(
                f"[RequestViewSet.comments] GET: returning {
                    len(comments_data)
                } comments"
            )
            return Response(comments_data)

        # POST - создание комментария
        text = request.data.get("text", "").strip()
        if not text:
            return Response(
                {"text": ["Это поле не может быть пустым."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        logger.info(
            "[RequestViewSet.comments] POST: creating comment "
            f"with text length={len(text)}"
        )

        # Используем unified comments system
        message = comments_helpers.create_comment(
            obj=req_obj, author=request.user, content=text
        )

        # Форматируем ответ
        author_ser = EmployeeBriefSerializer(message.author)
        response_data = {
            "id": message.id,
            "request": req_obj.id,
            "author": author_ser.data,
            "text": message.content,
            "created_at": message.created_at,
        }

        logger.info(
            f"[RequestViewSet.comments] POST: comment created id={message.id}"
        )
        return Response(response_data, status=status.HTTP_201_CREATED)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="comment_id",
                type=int,
                location=OpenApiParameter.PATH,
                description="ID комментария в треде заявки.",
            )
        ]
    )
    @action(
        detail=True,
        methods=["delete"],
        url_path="comments/(?P<comment_id>[^/.]+)",
    )
    def delete_comment(
        self,
        request: DRFRequest,
        pk: int | str | None = None,
        comment_id: int | str | None = None,
    ) -> Response:
        """Удаление комментария.

        DELETE /api/v1/requests/{pk}/comments/{comment_id}/

        Права: только автор комментария.
        """
        import logging
        from communications.models import Message

        logger = logging.getLogger(__name__)

        req_obj = self.get_object()

        # Получаем чат для этой заявки
        chat = comments_helpers.get_or_create_comments_chat(req_obj)

        # Находим комментарий
        try:
            message = Message.objects.get(id=comment_id, chat=chat)
        except Message.DoesNotExist:
            return Response(
                {"detail": "Comment not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if message.author != request.user:
            return Response(
                {"detail": "You don't have permission to delete this comment"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Используем unified comment system (мягкое удаление)
        comments_helpers.delete_comment(
            message=message, deleted_by=request.user, soft_delete=True
        )

        logger.info(
            f"[RequestViewSet.delete_comment] user={
                request.user.id
            } deleted comment_id={comment_id}"
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ---------- Экшены статусов (только бизнес-валидация) ----------

    @action(detail=True, methods=["post"])
    def approve(
        self, request: DRFRequest, pk: int | str | None = None
    ) -> Response:
        """Одобряет заявку.

        Raises:
            ValidationError: Если заявка уже финальная.
        """
        obj = self.get_object()
        if obj.status != RequestStatus.PENDING:
            raise ValidationError(
                "Решение можно принять только по заявке в статусе "
                "'На рассмотрении'."
            )
        if getattr(obj, "is_final", False):
            raise ValidationError("Заявка уже в финальном статусе.")
        obj.approve(by_user=request.user)
        return Response(
            RequestReadSerializer(
                obj, context=self.get_serializer_context()
            ).data
        )

    @action(detail=True, methods=["post"])
    def reject(
        self, request: DRFRequest, pk: int | str | None = None
    ) -> Response:
        """Отклоняет заявку.

        Raises:
            ValidationError: Если заявка уже финальная.
        """
        obj = self.get_object()
        if obj.status != RequestStatus.PENDING:
            raise ValidationError(
                "Решение можно принять только по заявке в статусе "
                "'На рассмотрении'."
            )
        if getattr(obj, "is_final", False):
            raise ValidationError("Заявка уже в финальном статусе.")
        obj.reject(by_user=request.user)
        return Response(
            RequestReadSerializer(
                obj, context=self.get_serializer_context()
            ).data
        )

    @action(detail=True, methods=["post"])
    def cancel(
        self, request: DRFRequest, pk: int | str | None = None
    ) -> Response:
        """Отменяет заявку.

        Raises:
            PermissionDenied: Если заявка финальная.
        """
        obj = self.get_object()
        if getattr(obj, "is_final", False):
            raise PermissionDenied(
                "Финальная заявка уже не может быть отменена."
            )
        obj.cancel()
        return Response(
            RequestReadSerializer(
                obj, context=self.get_serializer_context()
            ).data
        )

    @action(detail=True, methods=["get"], url_path="employee-statistics")
    def employee_statistics(
        self, request: DRFRequest, pk: int | str | None = None
    ) -> Response:
        """Возвращает сводную статистику по заявлениям сотрудника.

        Доступно администраторам и пользователям с явным правом
        ``requests_app.view_statistics`` или ``requests_app.can_view_all_requests``.
        """
        obj = self.get_object()
        user = request.user

        if not _can_view_request_statistics(user):
            raise PermissionDenied(
                "У вас нет доступа к статистике по заявлениям."
            )

        period = (request.query_params.get("period") or "all").strip().lower()
        if period not in {"all", "year", "month", "custom"}:
            raise ValidationError(
                "Параметр period должен быть one of: all, year, month, custom."
            )
        start_date, end_date = _resolve_stats_window_from_query(period, request)

        return Response(
            _build_employee_statistics(
                employee_id=obj.employee_id,
                employee_name=str(obj.employee),
                period=period,
                start_date=start_date,
                end_date=end_date,
            )
        )

    @action(detail=False, methods=["get"], url_path="statistics")
    def statistics(self, request: DRFRequest) -> Response:
        """Возвращает статистику по выбранному сотруднику для страницы."""
        if not _can_view_request_statistics(request.user):
            raise PermissionDenied(
                "У вас нет доступа к статистике по заявлениям."
            )

        employee_id_raw = (request.query_params.get("employee_id") or "").strip()
        if not employee_id_raw.isdigit():
            raise ValidationError("Параметр employee_id обязателен.")

        period = (request.query_params.get("period") or "all").strip().lower()
        if period not in {"all", "year", "month", "custom"}:
            raise ValidationError(
                "Параметр period должен быть one of: all, year, month, custom."
            )
        start_date, end_date = _resolve_stats_window_from_query(period, request)

        UserModel = get_user_model()
        employee = get_object_or_404(UserModel, pk=int(employee_id_raw))
        return Response(
            _build_employee_statistics(
                employee_id=employee.id,
                employee_name=str(employee),
                period=period,
                start_date=start_date,
                end_date=end_date,
            )
        )

    def create(self, request, *args, **kwargs):
        """
        Создание заявки: валидируем write-сериализатором,
        отвечаем read-сериализатором.
        """
        import logging

        logger = logging.getLogger(__name__)

        logger.info(
            f"[RequestViewSet.create] User: {request.user.id}, "
            f"Content-Type: {request.content_type}"
        )
        logger.info(
            f"[RequestViewSet.create] POST keys: {list(request.POST.keys())}"
        )
        logger.info(
            f"[RequestViewSet.create] FILES keys: {list(request.FILES.keys())}"
        )
        logger.info(
            f"[RequestViewSet.create] Data keys: {list(request.data.keys())}"
        )

        # Логируем значения для отладки
        for key in ["type", "title", "date_from", "date_to", "comment"]:
            value = request.data.get(key)
            logger.info(
                f"[RequestViewSet.create] {key}: {value} (type: {
                    type(value).__name__
                })"
            )

        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            logger.error(
                f"[RequestViewSet.create] Validation errors: {
                    serializer.errors
                }"
            )
            logger.error(
                f"[RequestViewSet.create] Request data: {request.data}"
            )

        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        read = RequestReadSerializer(
            instance, context=self.get_serializer_context()
        )
        headers = self.get_success_headers(read.data)
        return Response(
            read.data, status=status.HTTP_201_CREATED, headers=headers
        )

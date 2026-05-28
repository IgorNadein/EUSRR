"""ViewSets для API модуля закупок."""

from drf_spectacular.utils import OpenApiParameter, extend_schema
from django.db.models import Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from employees.models import Department, EmployeeDepartment
from procurement.constants import (
    ApprovalStatus,
    ProcurementStatus,
    EquipmentStatus,
    ProcurementItemExecutionStatus,
)
from procurement.models import (
    Approval,
    Budget,
    Equipment,
    EquipmentCategory,
    EquipmentTransferLog,
    MaintenanceRecord,
    ProcurementItem,
    ProcurementRequest,
    Supplier,
)
from procurement.notifications.handlers import (
    notify_item_comment,
    notify_item_issue_reported,
    notify_item_updated,
    notify_request_comment,
)
from communications import comments_helpers
from communications.models import Message
from procurement.services import ProcurementApprovalResolver
from .permissions import (
    CanApproveProcurementRequest,
    CanManageEquipment,
    CanManageEquipmentCategory,
    CanManageProcurementRequest,
    CanManageSupplier,
)
from .serializers import (
    BudgetSerializer,
    EquipmentCategorySerializer,
    EquipmentDetailSerializer,
    EquipmentListSerializer,
    MaintenanceRecordSerializer,
    ProcurementDepartmentStatsSerializer,
    ProcurementOverviewStatsSerializer,
    ProcurementItemSerializer,
    ProcurementRequestCreateSerializer,
    ProcurementRequestDetailSerializer,
    ProcurementRequestListSerializer,
    SupplierSerializer,
)


class ProcurementRequestViewSet(viewsets.ModelViewSet):
    """ViewSet для заявок на закупку."""

    queryset = ProcurementRequest.objects.select_related(
        "department",
        "processing_department",
        "requestor",
        "executor",
    ).prefetch_related("items", "approvals__approver")
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = {
        "status": ["exact", "in"],
        "urgency": ["exact"],
        "department": ["exact"],
        "processing_department": ["exact"],
        "executor": ["exact"],
        "fulfillment_status": ["exact"],
    }
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "status"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        """Выбрать сериализатор в зависимости от действия."""
        if self.action == "create":
            return ProcurementRequestCreateSerializer
        elif self.action in [
            "retrieve",
            "submit",
            "approve",
            "reject",
            "start_work",
            "complete",
            "cancel",
            "mark_all_received",
        ]:
            return ProcurementRequestDetailSerializer
        return ProcurementRequestListSerializer

    def get_permissions(self):
        """Выбрать права доступа в зависимости от действия."""
        if self.action in ["approve", "reject"]:
            permission_classes = [CanApproveProcurementRequest]
        elif self.action == "submit":
            permission_classes = [permissions.IsAuthenticated]
        else:
            # Для create, update, delete и остальных действий
            permission_classes = [CanManageProcurementRequest]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        """Фильтровать заявки в зависимости от роли пользователя и scope."""
        from datetime import timedelta
        from django.contrib.contenttypes.models import ContentType
        from django.db.models import Count, IntegerField, OuterRef, Subquery, Value
        from django.db.models.functions import Coalesce
        from django.utils import timezone
        from communications.models import Chat

        ct = ContentType.objects.get_for_model(ProcurementRequest)
        comments_sub = (
            Chat.objects.filter(
                type="comments",
                context_content_type=ct,
                context_object_id=OuterRef("pk"),
            )
            .annotate(
                msg_count=Count(
                    "messages", filter=Q(messages__is_deleted=False)
                )
            )
            .values("msg_count")[:1]
        )

        queryset = super().get_queryset().annotate(
            comments_count=Coalesce(
                Subquery(comments_sub, output_field=IntegerField()),
                Value(0),
                output_field=IntegerField(),
            )
        )
        user = self.request.user
        scope = self.request.query_params.get("scope", None)
        period = self.request.query_params.get("period", None)
        participant_department_ids = (
            ProcurementApprovalResolver.get_user_department_participant_ids(
                user,
            )
        )

        # Обработка scope параметра
        if scope == "mine":
            # Только мои заявки (где я автор)
            queryset = queryset.filter(requestor=user)
        elif scope == "department":
            # Заявки моего отдела
            queryset = queryset.filter(department__in=user.departments.all())
        elif scope == "processing_department":
            # Заявки, направленные в отделы, где пользователь участвует.
            queryset = queryset.filter(
                processing_department_id__in=participant_department_ids,
            )
        elif scope == "my_work":
            # Заявки, которые я взял в работу (где я исполнитель)
            queryset = queryset.filter(executor=user)
        elif scope == "available":
            queryset = queryset.filter(
                status__in=[
                    ProcurementStatus.WAITING,
                    ProcurementStatus.APPROVED,
                ],
                executor__isnull=True,
            )
            if not (
                user.is_superuser
                or user.is_staff
                or user.has_perm("procurement.change_procurementrequest")
                or user.has_perm("procurement.execute_procurement")
            ):
                queryset = queryset.filter(
                    Q(
                        status=ProcurementStatus.WAITING,
                        processing_department_id__in=participant_department_ids,
                    )
                    | Q(
                        status=ProcurementStatus.APPROVED,
                        processing_department__isnull=True,
                    )
                )
        elif scope == "all":
            # Все заявки - применяем стандартную логику прав
            pass
        else:
            # Если scope не указан, применяем стандартную логику
            # Админы и пользователи с модельными правами видят все
            if user.is_superuser or user.is_staff:
                pass
            # Пользователи с любыми модельными правами на заявки видят все
            elif (
                user.has_perm("procurement.view_procurementrequest")
                or user.has_perm("procurement.change_procurementrequest")
                or user.has_perm("procurement.delete_procurementrequest")
            ):
                pass
            else:
                # Показываем: свои заявки + заявки отдела + где я approver
                queryset = queryset.filter(
                    Q(requestor=user)
                    | Q(department__in=user.departments.all())
                    | Q(
                        processing_department_id__in=participant_department_ids
                    )
                    | Q(approvals__approver=user)
                    | Q(
                        status=ProcurementStatus.APPROVED,
                        processing_department__isnull=True,
                    )
                )

        # Фильтрация по периоду
        if period:
            now = timezone.now()
            if period == "today":
                start_date = now.replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                queryset = queryset.filter(created_at__gte=start_date)
            elif period == "week":
                start_date = now - timedelta(days=7)
                queryset = queryset.filter(created_at__gte=start_date)
            elif period == "month":
                start_date = now - timedelta(days=30)
                queryset = queryset.filter(created_at__gte=start_date)
            elif period == "quarter":
                start_date = now - timedelta(days=90)
                queryset = queryset.filter(created_at__gte=start_date)

        return queryset.distinct()

    @action(detail=True, methods=["get", "post"])
    def comments(self, request, pk=None):
        """Список/создание комментариев для заявки на закупку."""
        from api.v1.employees.serializers.employee import (
            EmployeeBriefSerializer,
        )

        procurement_request = self.get_object()

        if request.method in ("GET", "HEAD"):
            messages = comments_helpers.get_comments(procurement_request)
            comments_data = []
            for msg in messages:
                author_ser = EmployeeBriefSerializer(msg.author)
                comments_data.append(
                    {
                        "id": msg.id,
                        "request": procurement_request.id,
                        "author": author_ser.data,
                        "text": msg.content,
                        "created_at": msg.created_at,
                    }
                )
            return Response(comments_data)

        text = request.data.get("text", "").strip()
        if not text:
            return Response(
                {"text": ["Это поле не может быть пустым."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        message = comments_helpers.create_comment(
            obj=procurement_request,
            author=request.user,
            content=text,
        )
        notify_request_comment(
            procurement_request,
            message,
            actor=request.user,
        )
        author_ser = EmployeeBriefSerializer(message.author)
        return Response(
            {
                "id": message.id,
                "request": procurement_request.id,
                "author": author_ser.data,
                "text": message.content,
                "created_at": message.created_at,
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="comment_id",
                type=int,
                location=OpenApiParameter.PATH,
                description="ID комментария в чате комментариев заявки.",
            )
        ]
    )
    @action(
        detail=True,
        methods=["delete"],
        url_path="comments/(?P<comment_id>[^/.]+)",
    )
    def delete_comment(self, request, pk=None, comment_id=None):
        """Удаление комментария к заявке на закупку."""
        procurement_request = self.get_object()
        chat = comments_helpers.get_or_create_comments_chat(procurement_request)
        if isinstance(chat, tuple):
            chat = chat[0]

        try:
            message = Message.objects.get(id=comment_id, chat=chat)
        except Message.DoesNotExist:
            return Response(
                {"detail": "Комментарий не найден"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not (request.user.is_staff or message.author == request.user):
            return Response(
                {"detail": "Нет прав на удаление"},
                status=status.HTTP_403_FORBIDDEN,
            )

        comments_helpers.delete_comment(
            message=message,
            deleted_by=request.user,
            soft_delete=True,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        """Отправить заявку на согласование."""
        from django.db import transaction

        procurement_request = self.get_object()

        if (
            procurement_request.status == ProcurementStatus.PENDING
            or procurement_request.approvals.filter(
                status=ApprovalStatus.PENDING,
            ).exists()
        ):
            return Response(
                {"error": "Заявка уже находится на согласовании"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not ProcurementApprovalResolver.user_can_submit_for_approval(
            request.user,
            procurement_request,
        ):
            return Response(
                {"error": "Вы не можете отправить эту заявку на согласование"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if (
            not procurement_request.processing_department_id
            and not procurement_request.is_editable
        ):
            return Response(
                {"error": "Заявка уже отправлена на согласование"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if procurement_request.items.count() == 0:
            return Response(
                {"error": "Добавьте хотя бы одну позицию в заявку"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        required_priorities = (
            procurement_request.get_required_approval_priorities()
        )
        if not required_priorities:
            return Response(
                {
                    "error": (
                        "Для этой суммы заявки не настроены "
                        "маршруты согласования"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        resolved_approvals, missing_routes = (
            ProcurementApprovalResolver.resolve_required_approvers_detailed(
                procurement_request
            )
        )
        if missing_routes:
            missing_priorities = [
                route["priority"] for route in missing_routes
            ]
            missing_department_head = next(
                (
                    route
                    for route in missing_routes
                    if route["reason"] == "department_head_missing"
                ),
                None,
            )
            if missing_department_head:
                return Response(
                    {
                        "error": (
                            "У выбранного отдела не назначен руководитель. "
                            "Заявку нельзя отправить на согласование, "
                            "пока не будет назначен начальник отдела."
                        ),
                        "code": "department_head_missing",
                        "missing_priorities": missing_priorities,
                        "missing_routes": missing_routes,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {
                    "error": "Не настроены согласующие для обязательных этапов",
                    "code": "approval_routes_incomplete",
                    "missing_priorities": missing_priorities,
                    "missing_routes": missing_routes,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            for priority, approver, step_name in resolved_approvals:
                Approval.objects.create(
                    request=procurement_request,
                    approver=approver,
                    priority=priority,
                    step_name=step_name,
                    status=ApprovalStatus.PENDING,
                )

            procurement_request.status = ProcurementStatus.PENDING
            procurement_request.submitted_at = timezone.now()
            procurement_request._notification_actor = request.user
            procurement_request.save(
                update_fields=["status", "submitted_at", "updated_at"]
            )

            procurement_request.refresh_from_db()

        serializer = self.get_serializer(procurement_request)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """Одобрить заявку."""
        procurement_request = self.get_object()

        # Проверяем права
        self.check_object_permissions(request, procurement_request)

        # Находим или создаем доступный этап текущего пользователя.
        approval = ProcurementApprovalResolver.get_or_create_available_approval(
            request.user,
            procurement_request,
        )

        if not approval:
            return Response(
                {"error": "У вас нет прав на согласование этой заявки"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Вышестоящий согласующий закрывает все предыдущие pending-этапы.
        procurement_request.approvals.filter(
            status=ApprovalStatus.PENDING,
            priority__lt=approval.priority,
        ).update(
            status=ApprovalStatus.APPROVED,
            comment="Автоматически одобрено вышестоящим согласующим",
            updated_at=timezone.now(),
        )

        # Одобряем
        approval.status = ApprovalStatus.APPROVED
        approval.comment = request.data.get("comment", "")
        approval.save()  # Сигнал post_save(Approval) отправит уведомление

        # Проверяем, все ли одобрили
        pending_approvals = procurement_request.approvals.filter(
            status=ApprovalStatus.PENDING
        ).count()

        if pending_approvals == 0:
            if procurement_request.processing_department_id:
                procurement_request.status = (
                    ProcurementStatus.IN_PROGRESS
                    if procurement_request.executor_id
                    else ProcurementStatus.WAITING
                )
            else:
                procurement_request.status = ProcurementStatus.APPROVED
            procurement_request._notification_actor = request.user
            procurement_request.save(update_fields=["status", "updated_at"])

        procurement_request.refresh_from_db()

        serializer = self.get_serializer(procurement_request)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        """Отклонить заявку."""
        procurement_request = self.get_object()

        # Проверяем права
        self.check_object_permissions(request, procurement_request)

        # Находим или создаем доступный этап текущего пользователя.
        approval = ProcurementApprovalResolver.get_or_create_available_approval(
            request.user,
            procurement_request,
        )

        if not approval:
            return Response(
                {"error": "У вас нет прав на согласование этой заявки"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Вышестоящий согласующий закрывает предыдущие pending-этапы.
        procurement_request.approvals.filter(
            status=ApprovalStatus.PENDING,
            priority__lt=approval.priority,
        ).update(
            status=ApprovalStatus.REJECTED,
            comment="Автоматически закрыто вышестоящим отклонением",
            updated_at=timezone.now(),
        )

        # Отклоняем
        approval.status = ApprovalStatus.REJECTED
        approval.comment = request.data.get("comment", "")
        approval.save()  # Сигнал post_save(Approval) отправит уведомление

        # Меняем статус заявки; сигнал post_save(ProcurementRequest) уведомит
        # requestor'а
        procurement_request.status = ProcurementStatus.REJECTED
        procurement_request._notification_actor = request.user
        procurement_request._requestor_rejected_notified = True
        procurement_request.save()

        procurement_request.refresh_from_db()

        serializer = self.get_serializer(procurement_request)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def my_requests(self, request):
        """Получить заявки текущего пользователя."""
        queryset = self.get_queryset().filter(requestor=request.user)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def pending_approvals(self, request):
        """Получить заявки, ожидающие согласования текущим польз."""
        # Находим заявки где есть pending approval для текущего юзера
        base_queryset = self.filter_queryset(
            self.queryset.filter(
                status=ProcurementStatus.PENDING,
            )
        )
        available_ids = [
            request_obj.id
            for request_obj in base_queryset
            if ProcurementApprovalResolver.user_can_approve(
                request.user, request_obj
            )
        ]
        queryset = base_queryset.filter(id__in=available_ids)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def my_work(self, request):
        """Получить заявки, взятые текущим пользователем в работу."""
        queryset = self.filter_queryset(
            self.get_queryset().filter(executor=request.user)
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ProcurementRequestListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = ProcurementRequestListSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def available(self, request):
        """Получить заявки, доступные для взятия в работу."""
        queryset = self.filter_queryset(
            self.get_queryset().filter(
                status__in=[
                    ProcurementStatus.WAITING,
                    ProcurementStatus.APPROVED,
                ],
                executor__isnull=True,
            )
        )

        if not (
            request.user.is_superuser
            or request.user.is_staff
            or request.user.has_perm("procurement.change_procurementrequest")
            or request.user.has_perm("procurement.execute_procurement")
        ):
            participant_department_ids = (
                ProcurementApprovalResolver.get_user_department_participant_ids(
                    request.user,
                )
            )
            queryset = queryset.filter(
                Q(
                    status=ProcurementStatus.WAITING,
                    processing_department_id__in=participant_department_ids,
                )
                | Q(
                    status=ProcurementStatus.APPROVED,
                    processing_department__isnull=True,
                )
            )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ProcurementRequestListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = ProcurementRequestListSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def start_work(self, request, pk=None):
        """Начать работу над заявкой (перевод в статус IN_PROGRESS).

        Общий пул может взять любой авторизованный пользователь.
        Адресную заявку может взять сотрудник отдела-исполнителя.
        """
        procurement_request = self.get_object()
        self.check_object_permissions(request, procurement_request)

        # Проверяем текущий статус
        if procurement_request.status not in [
            ProcurementStatus.APPROVED,
            ProcurementStatus.WAITING,
        ]:
            return Response(
                {
                    "error": (
                        "Только одобренные или ожидающие заявки "
                        "можно взять в работу"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Проверяем, что заявка ещё не взята кем-то
        if procurement_request.executor:
            return Response(
                {
                    "error": (
                        f"Заявка уже взята в работу пользователем "
                        f"{procurement_request.executor.get_full_name()}"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Назначаем исполнителя и меняем статус
        # Сигнал post_save(ProcurementRequest) с IN_PROGRESS отправит
        # уведомления
        procurement_request.executor = request.user
        procurement_request.started_at = timezone.now()
        procurement_request.status = ProcurementStatus.IN_PROGRESS
        procurement_request._notification_actor = request.user
        procurement_request.save()

        serializer = self.get_serializer(procurement_request)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """Завершить заявку (перевод в статус COMPLETED)."""
        procurement_request = self.get_object()

        # Только исполнитель может завершить заявку
        if procurement_request.executor != request.user:
            return Response(
                {"error": "Только исполнитель заявки может завершить её"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Проверяем текущий статус
        if procurement_request.status != ProcurementStatus.IN_PROGRESS:
            return Response(
                {"error": "Только заявки в работе можно завершить"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Меняем статус
        procurement_request.status = ProcurementStatus.COMPLETED
        procurement_request.completed_at = timezone.now()
        procurement_request._notification_actor = request.user
        procurement_request.save()
        # Сигнал post_save(ProcurementRequest) с COMPLETED уведомит автора

        serializer = self.get_serializer(procurement_request)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def mark_all_received(self, request, pk=None):
        """Отметить все позиции заявки как полученные."""
        procurement_request = self.get_object()
        self.check_object_permissions(request, procurement_request)

        if procurement_request.status not in [
            ProcurementStatus.WAITING,
            ProcurementStatus.IN_PROGRESS,
        ]:
            return Response(
                {
                    "error": (
                        "Отмечать позиции можно только в ожидающей "
                        "или взятой в работу заявке"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        items_to_update = [
            item
            for item in procurement_request.items.all()
            if (
                item.execution_status
                != ProcurementItemExecutionStatus.RECEIVED
                or item.ordered_quantity != item.quantity
                or item.received_quantity != item.quantity
            )
        ]

        for item in items_to_update:
            item.execution_status = ProcurementItemExecutionStatus.RECEIVED
            item.ordered_quantity = item.quantity
            item.received_quantity = item.quantity
        ProcurementItem.objects.bulk_update(
            items_to_update,
            ["execution_status", "ordered_quantity", "received_quantity"],
        )
        for item in items_to_update:
            notify_item_updated(
                item,
                actor=request.user,
                changed_fields=[
                    "execution_status",
                    "ordered_quantity",
                    "received_quantity",
                ],
            )
        procurement_request._notification_actor = request.user
        procurement_request.recalculate_fulfillment_status(save=True)
        procurement_request.refresh_from_db()

        serializer = self.get_serializer(procurement_request)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Отменить заявку."""
        procurement_request = self.get_object()

        # Только автор заявки может отменить её
        if procurement_request.requestor != request.user:
            return Response(
                {"error": "Только автор заявки может отменить её"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Нельзя отменить уже завершённую или отменённую заявку
        if procurement_request.status in [
            ProcurementStatus.COMPLETED,
            ProcurementStatus.CANCELLED,
        ]:
            return Response(
                {"error": "Эту заявку нельзя отменить"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reason = request.data.get("reason", "")

        # Сохраняем причину на экземпляре, чтобы сигнал мог её использовать
        procurement_request.cancellation_reason = reason or "не указана"
        procurement_request._notification_actor = request.user

        # Меняем статус; сигнал post_save(ProcurementRequest) с CANCELLED
        # уведомит согласующих с указанием причины
        procurement_request.status = ProcurementStatus.CANCELLED
        procurement_request.save()

        serializer = self.get_serializer(procurement_request)
        return Response(serializer.data)


class ProcurementItemViewSet(viewsets.ModelViewSet):
    """ViewSet для позиций заявок."""

    NOTIFICATION_TRACKED_FIELDS = [
        "name",
        "quantity",
        "unit",
        "estimated_unit_price",
        "ordered_quantity",
        "received_quantity",
        "links",
        "expected_delivery_date",
        "actual_unit_price",
        "execution_status",
        "executor_comment",
    ]

    queryset = ProcurementItem.objects.select_related(
        "request",
        "request__department",
        "request__processing_department",
    )
    serializer_class = ProcurementItemSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["request"]
    search_fields = ["name", "description"]

    def get_queryset(self):
        """Annotate item comments count."""
        from django.contrib.contenttypes.models import ContentType
        from django.db.models import Count, IntegerField, OuterRef, Subquery, Value
        from django.db.models.functions import Coalesce
        from communications.models import Chat

        ct = ContentType.objects.get_for_model(ProcurementItem)
        comments_sub = (
            Chat.objects.filter(
                type="comments",
                context_content_type=ct,
                context_object_id=OuterRef("pk"),
            )
            .annotate(
                msg_count=Count(
                    "messages", filter=Q(messages__is_deleted=False)
                )
            )
            .values("msg_count")[:1]
        )

        return super().get_queryset().annotate(
            comments_count=Coalesce(
                Subquery(comments_sub, output_field=IntegerField()),
                Value(0),
                output_field=IntegerField(),
            )
        )

    def _is_processing_department_member(self, user, procurement_request):
        return ProcurementApprovalResolver.user_is_processing_department_member(
            user,
            procurement_request,
        )

    def _can_process_request_items(self, user, procurement_request):
        if user.is_superuser or user.is_staff:
            return True
        if (
            user.has_perm("procurement.change_procurementrequest")
            or user.has_perm("procurement.execute_procurement")
        ):
            return True
        return self._is_processing_department_member(
            user,
            procurement_request,
        )

    def _can_access_item_comments(self, user, procurement_request):
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or user.is_staff:
            return True
        if (
            user.has_perm("procurement.view_procurementrequest")
            or user.has_perm("procurement.change_procurementrequest")
            or user.has_perm("procurement.execute_procurement")
        ):
            return True
        if procurement_request.requestor_id == user.id:
            return True
        if procurement_request.executor_id == user.id:
            return True
        if procurement_request.department.head_id == user.id:
            return True
        if EmployeeDepartment.objects.filter(
            employee_id=user.id,
            department_id=procurement_request.department_id,
            is_active=True,
        ).exists():
            return True
        return self._is_processing_department_member(
            user,
            procurement_request,
        )

    def get_permissions(self):
        """Только создатель заявки может редактировать позиции."""
        if self.action in [
            "create",
            "update",
            "partial_update",
            "destroy",
            "create_equipment",
            "link_equipment",
            "comments",
            "delete_comment",
            "report_issue",
            "confirm_received",
            "cancel_received",
            "cancel_issue",
        ]:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [CanManageProcurementRequest]
        return [permission() for permission in permission_classes]

    def _can_use_item_quick_action(self, user, procurement_request):
        return (
            procurement_request.requestor_id == user.id
            or self._can_process_request_items(user, procurement_request)
        )

    def _validate_item_quick_action(self, user, procurement_request):
        if not self._can_use_item_quick_action(user, procurement_request):
            return Response(
                {"detail": "Нет прав изменить эту позицию"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if procurement_request.status in [
            ProcurementStatus.PENDING,
            ProcurementStatus.CANCELLED,
            ProcurementStatus.REJECTED,
        ]:
            return Response(
                {
                    "detail": (
                        "Нельзя изменить позицию в заявке на согласовании, "
                        "в отменённой или отклонённой заявке"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return None

    def _workflow_status_from_quantities(self, item):
        received_quantity = item.received_quantity or 0
        ordered_quantity = item.ordered_quantity or 0

        if received_quantity > 0:
            return (
                ProcurementItemExecutionStatus.RECEIVED
                if received_quantity >= item.quantity
                else ProcurementItemExecutionStatus.ORDERED
            )
        if ordered_quantity > 0:
            return ProcurementItemExecutionStatus.ORDERED
        return ProcurementItemExecutionStatus.PENDING

    def _reopen_completed_request(self, procurement_request, user):
        if procurement_request.status != ProcurementStatus.COMPLETED:
            return

        procurement_request.status = (
            ProcurementStatus.IN_PROGRESS
            if procurement_request.executor_id
            else ProcurementStatus.WAITING
        )
        procurement_request.completed_at = None
        procurement_request._notification_actor = user
        procurement_request.save(
            update_fields=["status", "completed_at", "updated_at"]
        )

    def perform_create(self, serializer):
        """Проверяем права при создании позиции.

        Логика соответствует CanManageProcurementRequest:
        - Админы/Staff могут добавлять в любые заявки в DRAFT
        - Модельные права (change_procurementrequest) → любые заявки в DRAFT
        - Автор заявки → свои заявки в DRAFT
        - Начальник отдела → заявки своего отдела в DRAFT
        """
        from rest_framework.exceptions import PermissionDenied

        procurement_request = serializer.validated_data.get("request")
        user = self.request.user

        if procurement_request.status in [
            ProcurementStatus.PENDING,
            ProcurementStatus.CANCELLED,
            ProcurementStatus.REJECTED,
        ]:
            raise PermissionDenied(
                "Нельзя добавлять позиции в заявку со статусом '{}'".format(
                    procurement_request.get_status_display()
                )
            )

        if self._can_process_request_items(user, procurement_request):
            serializer.save()
            return

        # Автор заявки
        if procurement_request.requestor == user and procurement_request.is_editable:
            serializer.save()
            return

        # Начальник отдела
        if (
            procurement_request.department.head == user
            and procurement_request.is_editable
        ):
            serializer.save()
            return

        # Нет прав
        raise PermissionDenied("Вы не можете добавлять позиции в эту заявку")

    def _check_item_edit_permission(self, item):
        """Проверка прав на редактирование позиции.

        Вынесена в отдельный метод для переиспользования.
        """
        from rest_framework.exceptions import PermissionDenied

        user = self.request.user
        procurement_request = item.request

        if procurement_request.status in [
            ProcurementStatus.PENDING,
            ProcurementStatus.CANCELLED,
            ProcurementStatus.REJECTED,
        ]:
            raise PermissionDenied(
                "Нельзя изменять позиции в заявке со статусом '{}'".format(
                    procurement_request.get_status_display()
                )
            )

        if self._can_process_request_items(user, procurement_request):
            return True

        # Автор заявки
        if procurement_request.requestor == user and procurement_request.is_editable:
            return True

        # Начальник отдела
        if (
            procurement_request.department.head == user
            and procurement_request.is_editable
        ):
            return True

        # Нет прав
        raise PermissionDenied("Вы не можете изменять позиции в этой заявке")

    def perform_update(self, serializer):
        """Проверяем права при обновлении позиции."""
        item = self.get_object()
        self._check_item_edit_permission(item)
        procurement_request = item.request
        before = {
            field: getattr(item, field)
            for field in self.NOTIFICATION_TRACKED_FIELDS
        }
        procurement_request._notification_actor = self.request.user
        updated_item = serializer.save()
        after = {
            field: getattr(updated_item, field)
            for field in self.NOTIFICATION_TRACKED_FIELDS
        }
        changed_fields = [
            field
            for field in self.NOTIFICATION_TRACKED_FIELDS
            if before[field] != after[field]
        ]
        if changed_fields:
            notify_item_updated(
                updated_item,
                actor=self.request.user,
                changed_fields=changed_fields,
            )

    @action(detail=True, methods=["post"])
    def report_issue(self, request, pk=None):
        """Отметить позицию как проблемную/бракованную."""
        item = self.get_object()
        procurement_request = item.request
        user = request.user

        error_response = self._validate_item_quick_action(
            user,
            procurement_request,
        )
        if error_response is not None:
            return error_response

        item.execution_status = ProcurementItemExecutionStatus.DEFECTIVE
        item.save(update_fields=["execution_status"])

        self._reopen_completed_request(procurement_request, user)

        text = request.data.get("text", "")
        if isinstance(text, str):
            text = text.strip()
        else:
            text = ""

        message = None
        if text:
            message = comments_helpers.create_comment(
                obj=item,
                author=user,
                content=text,
            )
            notify_item_comment(item, message, actor=user)

        notify_item_updated(
            item,
            actor=user,
            changed_fields=["execution_status"],
        )
        if procurement_request.requestor_id == user.id:
            notify_item_issue_reported(item, actor=user)

        item.refresh_from_db()
        serializer = self.get_serializer(item)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def cancel_received(self, request, pk=None):
        """Отменить подтверждение получения позиции."""
        item = self.get_object()
        procurement_request = item.request
        user = request.user

        error_response = self._validate_item_quick_action(
            user,
            procurement_request,
        )
        if error_response is not None:
            return error_response

        if (item.received_quantity or 0) <= 0:
            return Response(
                {"detail": "По позиции нет подтверждённого получения"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        item.received_quantity = 0
        item.execution_status = self._workflow_status_from_quantities(item)
        item.save(update_fields=["execution_status", "received_quantity"])
        self._reopen_completed_request(procurement_request, user)
        notify_item_updated(
            item,
            actor=user,
            changed_fields=["execution_status", "received_quantity"],
        )

        item.refresh_from_db()
        serializer = self.get_serializer(item)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def cancel_issue(self, request, pk=None):
        """Снять отметку брака/перезаказа с позиции."""
        item = self.get_object()
        procurement_request = item.request
        user = request.user

        error_response = self._validate_item_quick_action(
            user,
            procurement_request,
        )
        if error_response is not None:
            return error_response

        if item.execution_status != ProcurementItemExecutionStatus.DEFECTIVE:
            return Response(
                {"detail": "Позиция не отмечена как брак"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        item.execution_status = self._workflow_status_from_quantities(item)
        item.save(update_fields=["execution_status"])
        notify_item_updated(
            item,
            actor=user,
            changed_fields=["execution_status"],
        )

        item.refresh_from_db()
        serializer = self.get_serializer(item)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def confirm_received(self, request, pk=None):
        """Подтвердить получение позиции."""
        item = self.get_object()
        procurement_request = item.request
        user = request.user

        error_response = self._validate_item_quick_action(
            user,
            procurement_request,
        )
        if error_response is not None:
            return error_response

        item.execution_status = ProcurementItemExecutionStatus.RECEIVED
        item.ordered_quantity = item.quantity
        item.received_quantity = item.quantity
        item.save(
            update_fields=[
                "execution_status",
                "ordered_quantity",
                "received_quantity",
            ]
        )
        notify_item_updated(
            item,
            actor=user,
            changed_fields=[
                "execution_status",
                "ordered_quantity",
                "received_quantity",
            ],
        )

        item.refresh_from_db()
        serializer = self.get_serializer(item)
        return Response(serializer.data)

    def perform_destroy(self, instance):
        """Проверяем права при удалении позиции."""
        self._check_item_edit_permission(instance)
        instance.delete()

    @action(detail=True, methods=["get", "post"])
    def comments(self, request, pk=None):
        """Список/создание комментариев для позиции заявки."""
        from api.v1.employees.serializers.employee import (
            EmployeeBriefSerializer,
        )

        item = self.get_object()
        if not self._can_access_item_comments(request.user, item.request):
            return Response(
                {"detail": "Нет прав на комментарии этой позиции"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if request.method in ("GET", "HEAD"):
            messages = comments_helpers.get_comments(item)
            comments_data = []
            for msg in messages:
                author_ser = EmployeeBriefSerializer(msg.author)
                comments_data.append(
                    {
                        "id": msg.id,
                        "item": item.id,
                        "request": item.request_id,
                        "author": author_ser.data,
                        "text": msg.content,
                        "created_at": msg.created_at,
                    }
                )
            return Response(comments_data)

        text = request.data.get("text", "").strip()
        if not text:
            return Response(
                {"text": ["Это поле не может быть пустым."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        message = comments_helpers.create_comment(
            obj=item,
            author=request.user,
            content=text,
        )
        notify_item_comment(
            item,
            message,
            actor=request.user,
        )
        author_ser = EmployeeBriefSerializer(message.author)
        return Response(
            {
                "id": message.id,
                "item": item.id,
                "request": item.request_id,
                "author": author_ser.data,
                "text": message.content,
                "created_at": message.created_at,
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="comment_id",
                type=int,
                location=OpenApiParameter.PATH,
                description="ID комментария в чате комментариев позиции.",
            )
        ]
    )
    @action(
        detail=True,
        methods=["delete"],
        url_path="comments/(?P<comment_id>[^/.]+)",
    )
    def delete_comment(self, request, pk=None, comment_id=None):
        """Удаление комментария к позиции заявки."""
        item = self.get_object()
        if not self._can_access_item_comments(request.user, item.request):
            return Response(
                {"detail": "Нет прав на комментарии этой позиции"},
                status=status.HTTP_403_FORBIDDEN,
            )

        chat = comments_helpers.get_or_create_comments_chat(item)
        if isinstance(chat, tuple):
            chat = chat[0]

        try:
            message = Message.objects.get(id=comment_id, chat=chat)
        except Message.DoesNotExist:
            return Response(
                {"detail": "Комментарий не найден"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not (request.user.is_staff or message.author == request.user):
            return Response(
                {"detail": "Нет прав на удаление"},
                status=status.HTTP_403_FORBIDDEN,
            )

        comments_helpers.delete_comment(
            message=message,
            deleted_by=request.user,
            soft_delete=True,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def create_equipment(self, request, pk=None):
        """Создать оборудование из позиции закупки.

        Эндпоинт для ручного создания оборудования после получения товара.
        Требуется: inventory_number, category, department.
        Опционально: serial_number, location, warranty_until, responsible.
        """
        item = self.get_object()

        # Проверяем, что заявка завершена
        if item.request.status != ProcurementStatus.COMPLETED:
            return Response(
                {
                    "error": "Оборудование можно создать только из "
                    "завершённой заявки"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Проверяем, что оборудование еще не создано
        if item.equipment is not None:
            return Response(
                {"error": "Оборудование для этой позиции уже создано"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Получаем данные из запроса
        inventory_number = request.data.get("inventory_number")
        category_id = request.data.get("category")
        department_id = request.data.get("department")
        serial_number = request.data.get("serial_number", "")
        location = request.data.get("location", "")
        warranty_until = request.data.get("warranty_until")
        responsible_person_id = request.data.get("responsible_person")

        # Валидация обязательных полей
        if not inventory_number:
            return Response(
                {"error": "Укажите инвентарный номер"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not category_id:
            return Response(
                {"error": "Укажите категорию оборудования"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not department_id:
            return Response(
                {"error": "Укажите отдел"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Проверяем уникальность инвентарного номера
        exists = Equipment.objects.filter(
            inventory_number=inventory_number
        ).exists()
        if exists:
            return Response(
                {
                    "error": f'Инвентарный номер "{inventory_number}" '
                    "уже используется"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Создаем оборудование
        from django.utils import timezone

        purchase_cost = item.actual_unit_price or item.estimated_unit_price
        if purchase_cost is None:
            return Response(
                {
                    "error": (
                        "Для создания оборудования укажите фактическую "
                        "или ориентировочную цену позиции"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            equipment = Equipment.objects.create(
                name=item.name,
                inventory_number=inventory_number,
                serial_number=serial_number,
                category_id=category_id,
                department_id=department_id,
                status=EquipmentStatus.AVAILABLE,
                responsible_person_id=responsible_person_id,
                location=location,
                purchase_date=timezone.now().date(),
                warranty_until=warranty_until,
                purchase_cost=purchase_cost,
                notes=item.description,  # description -> notes
            )
        except Exception as e:
            return Response(
                {"error": f"Ошибка создания оборудования: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Связываем оборудование с позицией закупки
        item.equipment = equipment
        item.save()

        return Response(
            {
                "message": "Оборудование успешно создано",
                "equipment": {
                    "id": equipment.id,
                    "name": equipment.name,
                    "inventory_number": equipment.inventory_number,
                },
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def link_equipment(self, request, pk=None):
        """Связать существующее оборудование с позицией закупки.

        Используется после создания оборудования через основной API.
        Требуется: equipment_id.
        """
        item = self.get_object()

        # Проверяем, что заявка завершена
        if item.request.status != ProcurementStatus.COMPLETED:
            return Response(
                {
                    "error": "Связывать оборудование можно только "
                    "с позициями завершённых заявок"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Проверяем, что оборудование ещё не связано
        if item.equipment is not None:
            return Response(
                {"error": "Оборудование для этой позиции уже связано"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        equipment_id = request.data.get("equipment_id")
        if not equipment_id:
            return Response(
                {"error": "Укажите ID оборудования"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Находим оборудование
        try:
            equipment = Equipment.objects.get(pk=equipment_id)
        except Equipment.DoesNotExist:
            return Response(
                {"error": "Оборудование не найдено"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Проверяем, что оборудование ещё не привязано к другой позиции
        if (
            hasattr(equipment, "procurement_item")
            and equipment.procurement_item
        ):
            return Response(
                {"error": "Это оборудование уже связано с другой позицией"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Связываем
        item.equipment = equipment
        item.save()

        return Response(
            {
                "message": "Оборудование успешно связано с позицией",
                "equipment": {
                    "id": equipment.id,
                    "name": equipment.name,
                    "inventory_number": equipment.inventory_number,
                },
            },
            status=status.HTTP_200_OK,
        )


class EquipmentCategoryViewSet(viewsets.ModelViewSet):
    """ViewSet для категорий оборудования."""

    queryset = EquipmentCategory.objects.prefetch_related("children")
    serializer_class = EquipmentCategorySerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description"]
    ordering = ["name"]

    def get_permissions(self):
        """Чтение доступно всем сотрудникам, изменение только уполномоченным."""
        return [CanManageEquipmentCategory()]

    @action(detail=True, methods=["get"])
    def children(self, request, pk=None):
        """Получить подкатегории."""
        category = self.get_object()
        serializer = self.get_serializer(category.children.all(), many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def tree(self, request):
        """Получить дерево категорий."""
        # Получаем только корневые категории
        root_categories = self.get_queryset().filter(parent=None)
        serializer = self.get_serializer(root_categories, many=True)
        return Response(serializer.data)


class EquipmentViewSet(viewsets.ModelViewSet):
    """ViewSet для оборудования."""

    queryset = Equipment.objects.select_related(
        "category", "department", "responsible_person"
    )
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = {
        "status": ["exact"],
        "category": ["exact"],
        "department": ["exact"],
        "responsible_person": ["exact"],
        "purchase_date": ["gte", "lte"],
    }
    search_fields = [
        "name",
        "inventory_number",
        "serial_number",
        "location",
    ]
    ordering_fields = ["purchase_date", "name", "created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Annotate comments_count."""
        from django.contrib.contenttypes.models import ContentType
        from django.db.models import Count, Subquery, OuterRef, IntegerField
        from communications.models import Chat

        ct = ContentType.objects.get_for_model(Equipment)
        qs = super().get_queryset()

        comments_sub = (
            Chat.objects.filter(
                type="comments",
                context_content_type=ct,
                context_object_id=OuterRef("pk"),
            )
            .annotate(
                msg_count=Count(
                    "messages", filter=Q(messages__is_deleted=False)
                )
            )
            .values("msg_count")[:1]
        )
        return qs.annotate(
            comments_count=Subquery(
                comments_sub, output_field=IntegerField(default=0)
            )
        )

    def get_serializer_class(self):
        """Выбрать сериализатор."""
        if self.action == "retrieve":
            return EquipmentDetailSerializer
        return EquipmentListSerializer

    def get_permissions(self):
        """Права доступа."""
        permission_classes = [CanManageEquipment]
        return [permission() for permission in permission_classes]

    def create(self, request, *args, **kwargs):
        """Создание оборудования с поддержкой массового создания.

        Если передан параметр quantity > 1, создаётся несколько единиц
        с автоматически сгенерированными инвентарными номерами.
        """
        try:
            quantity = int(request.data.get("quantity", 1))
        except (ValueError, TypeError):
            quantity = 1
        quantity = max(1, min(quantity, 100))  # Ограничение от 1 до 100

        if quantity == 1:
            # Стандартное создание одной единицы
            return super().create(request, *args, **kwargs)

        # Массовое создание
        created_equipment = []
        errors = []

        for i in range(quantity):
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                self.perform_create(serializer)
                created_equipment.append(serializer.data)
            else:
                errors.append({"index": i, "errors": serializer.errors})

        if errors and not created_equipment:
            return Response(
                {"detail": "Не удалось создать оборудование", "errors": errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "created_count": len(created_equipment),
                "equipment": created_equipment,
                "errors": errors if errors else None,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"])
    def my_equipment(self, request):
        """Оборудование, за которое отвечает текущий пользователь."""
        queryset = self.get_queryset().filter(responsible_person=request.user)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def warranty_expiring(self, request):
        """Оборудование с истекающей гарантией (< 30 дней)."""
        from datetime import date, timedelta

        threshold = date.today() + timedelta(days=30)

        queryset = self.get_queryset().filter(
            warranty_until__lte=threshold, warranty_until__gte=date.today()
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="generate-inventory-number")
    def generate_inventory_number(self, request):
        """Генерация уникального инвентарного номера."""
        from procurement.services import InventoryNumberGenerator

        inventory_number = InventoryNumberGenerator.generate()
        return Response({"inventory_number": inventory_number})

    @action(detail=False, methods=["get"], url_path="create-options")
    def create_options(self, request):
        """Возвращает доступные опции для создания оборудования.

        Определяет уровень прав пользователя и возвращает:
        - allowed_departments: список отделов для выбора
        - can_choose_department: может ли пользователь выбирать отдел
        - can_choose_responsible: может ли выбирать ответственного
        - default_responsible: ответственный по умолчанию (если нет выбора)
        """
        from api.v1.permissions import has_dept_perm
        from employees.constants import DeptPerm
        from employees.models import EmployeeDepartment

        user = request.user

        # Определяем уровень прав
        if user.is_staff or user.is_superuser:
            perm_level = "full"
        elif user.has_perm("procurement.add_equipment"):
            perm_level = "full"
        elif Department.objects.filter(head_id=user.id).exists():
            perm_level = "dept_head"
        else:
            # Проверяем скоуп-право
            user_dept_links = EmployeeDepartment.objects.filter(
                employee_id=user.id, is_active=True
            ).select_related("department")

            has_scoped = False
            for link in user_dept_links:
                if has_dept_perm(
                    user, link.department_id, DeptPerm.MANAGE_EQUIPMENT
                ):
                    has_scoped = True
                    break

            perm_level = "scoped" if has_scoped else None

        # Формируем ответ в зависимости от уровня прав
        if perm_level == "full":
            # Полный доступ — все отделы
            departments = Department.objects.all().values("id", "name")
            return Response(
                {
                    "allowed_departments": list(departments),
                    "can_choose_department": True,
                    "can_choose_responsible": True,
                    "default_responsible": None,
                    "permission_level": "full",
                }
            )

        elif perm_level == "dept_head":
            # Начальник — только свои отделы
            departments = Department.objects.filter(head_id=user.id).values(
                "id", "name"
            )
            return Response(
                {
                    "allowed_departments": list(departments),
                    "can_choose_department": False,
                    "can_choose_responsible": True,
                    "default_responsible": {
                        "id": user.id,
                        "name": user.get_full_name(),
                    },
                    "permission_level": "dept_head",
                }
            )

        elif perm_level == "scoped":
            # Скоуп-право — отделы с правом, ответственный = начальник
            allowed_depts = []
            default_responsible = None

            user_dept_links = EmployeeDepartment.objects.filter(
                employee_id=user.id, is_active=True
            ).select_related("department", "department__head")

            for link in user_dept_links:
                if has_dept_perm(
                    user, link.department_id, DeptPerm.MANAGE_EQUIPMENT
                ):
                    dept = link.department
                    allowed_depts.append({"id": dept.id, "name": dept.name})
                    if default_responsible is None and dept.head:
                        default_responsible = {
                            "id": dept.head.id,
                            "name": dept.head.get_full_name(),
                        }

            return Response(
                {
                    "allowed_departments": allowed_depts,
                    "can_choose_department": False,
                    "can_choose_responsible": False,
                    "default_responsible": default_responsible,
                    "permission_level": "scoped",
                }
            )

        else:
            # Нет прав
            return Response(
                {
                    "allowed_departments": [],
                    "can_choose_department": False,
                    "can_choose_responsible": False,
                    "default_responsible": None,
                    "permission_level": None,
                }
            )

    @action(detail=True, methods=["post"])
    def transfer(self, request, pk=None):
        """Перевод оборудования в другой отдел или другому пользователю."""
        equipment = self.get_object()

        to_department_id = request.data.get("to_department")
        to_person_id = request.data.get("to_person")
        to_location = request.data.get("to_location")
        reason = request.data.get("reason", "")

        if not to_department_id and not to_person_id:
            return Response(
                {"error": "Укажите отдел или ответственного"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Сохраняем старые значения
        from_department = equipment.department
        from_person = equipment.responsible_person

        # Обновляем оборудование
        if to_department_id:
            try:
                to_department = Department.objects.get(pk=to_department_id)
                equipment.department = to_department
            except Department.DoesNotExist:
                return Response(
                    {"error": "Отдел не найден"},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            to_department = from_department

        if to_person_id:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            try:
                to_person = User.objects.get(pk=to_person_id)
                equipment.responsible_person = to_person
            except User.DoesNotExist:
                return Response(
                    {"error": "Пользователь не найден"},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            to_person = from_person

        if to_location:
            equipment.location = to_location

        equipment.save()

        # Создаём лог перевода
        EquipmentTransferLog.objects.create(
            equipment=equipment,
            from_department=from_department,
            to_department=to_department,
            from_person=from_person,
            to_person=to_person,
            to_location=to_location or "",
            reason=reason,
            created_by=request.user,
        )

        return Response(
            {
                "status": "transferred",
                "equipment_id": equipment.id,
                "from_department": str(from_department),
                "to_department": str(to_department),
            }
        )

    @action(detail=True, methods=["post"])
    def write_off(self, request, pk=None):
        """Списание оборудования."""
        equipment = self.get_object()
        reason = request.data.get("reason", "")

        if equipment.status == EquipmentStatus.RETIRED:
            return Response(
                {"error": "Оборудование уже списано"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        equipment.status = EquipmentStatus.RETIRED
        equipment.notes = (equipment.notes or "") + f"\n\nСписано: {reason}"
        equipment.save()

        return Response({"status": "written_off", "equipment_id": equipment.id})

    @action(detail=True, methods=["post"])
    def add_maintenance(self, request, pk=None):
        """Добавить запись об обслуживании."""
        from datetime import date

        equipment = self.get_object()

        maintenance_type = request.data.get("type", "repair")
        description = request.data.get("description", "")
        cost = request.data.get("cost")
        maintenance_date = request.data.get("date", date.today())

        record = MaintenanceRecord.objects.create(
            equipment=equipment,
            type=maintenance_type,
            description=description,
            cost=cost,
            date=maintenance_date,
            performed_by=request.user,
        )

        return Response(
            {
                "status": "created",
                "maintenance_id": record.id,
                "equipment_id": equipment.id,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"])
    def transfer_history(self, request, pk=None):
        """История переводов оборудования."""
        equipment = self.get_object()

        logs = EquipmentTransferLog.objects.filter(
            equipment=equipment
        ).order_by("-created_at")

        data = [
            {
                "id": log.id,
                "from_department": str(log.from_department),
                "to_department": str(log.to_department),
                "from_person": (
                    str(log.from_person) if log.from_person else None
                ),
                "to_person": (str(log.to_person) if log.to_person else None),
                "reason": log.reason,
                "created_by": str(log.created_by) if log.created_by else None,
                "date": log.created_at.isoformat(),
            }
            for log in logs
        ]

        return Response(data)

    @action(detail=True, methods=["get", "post"])
    def comments(self, request, pk=None):
        """Список/создание комментариев для оборудования."""
        from api.v1.employees.serializers.employee import (
            EmployeeBriefSerializer,
        )

        equipment = self.get_object()

        if request.method in ("GET", "HEAD"):
            messages = comments_helpers.get_comments(equipment)
            comments_data = []
            for msg in messages:
                author_ser = EmployeeBriefSerializer(msg.author)
                comments_data.append(
                    {
                        "id": msg.id,
                        "equipment": equipment.id,
                        "author": author_ser.data,
                        "text": msg.content,
                        "created_at": msg.created_at,
                    }
                )
            return Response(comments_data)

        text = request.data.get("text", "").strip()
        if not text:
            return Response(
                {"text": ["Это поле не может быть пустым."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        message = comments_helpers.create_comment(
            obj=equipment,
            author=request.user,
            content=text,
        )
        author_ser = EmployeeBriefSerializer(message.author)
        return Response(
            {
                "id": message.id,
                "equipment": equipment.id,
                "author": author_ser.data,
                "text": message.content,
                "created_at": message.created_at,
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="comment_id",
                type=int,
                location=OpenApiParameter.PATH,
                description="ID комментария в чате комментариев оборудования.",
            )
        ]
    )
    @action(
        detail=True,
        methods=["delete"],
        url_path="comments/(?P<comment_id>[^/.]+)",
    )
    def delete_comment(self, request, pk=None, comment_id=None):
        """Удаление комментария к оборудованию."""
        equipment = self.get_object()
        chat = comments_helpers.get_or_create_comments_chat(equipment)
        if isinstance(chat, tuple):
            chat = chat[0]

        try:
            message = Message.objects.get(id=comment_id, chat=chat)
        except Message.DoesNotExist:
            return Response(
                {"detail": "Комментарий не найден"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not (request.user.is_staff or message.author == request.user):
            return Response(
                {"detail": "Нет прав на удаление"},
                status=status.HTTP_403_FORBIDDEN,
            )

        comments_helpers.delete_comment(
            message=message,
            deleted_by=request.user,
            soft_delete=True,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class MaintenanceRecordViewSet(viewsets.ModelViewSet):
    """ViewSet для записей обслуживания."""

    queryset = MaintenanceRecord.objects.select_related(
        "equipment", "performed_by"
    )
    serializer_class = MaintenanceRecordSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.OrderingFilter,
    ]
    filterset_fields = ["equipment", "type", "performed_by"]
    ordering_fields = ["date"]
    ordering = ["-date"]

    def perform_create(self, serializer):
        """При создании записи устанавливаем performed_by."""
        serializer.save(performed_by=self.request.user)


class SupplierViewSet(viewsets.ModelViewSet):
    """ViewSet для поставщиков."""

    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["is_active"]
    search_fields = ["name", "contact_person", "inn"]
    ordering_fields = ["name", "rating"]
    ordering = ["name"]

    def get_permissions(self):
        """Права доступа."""
        permission_classes = [CanManageSupplier]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=["get"])
    def top_rated(self, request):
        """Получить поставщиков с лучшим рейтингом."""
        queryset = (
            self.get_queryset()
            .filter(is_active=True, rating__gte=4.0)
            .order_by("-rating")[:10]
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class ProcurementStatsViewSet(viewsets.ViewSet):
    """ViewSet для статистики закупок."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Procurement"],
        summary="Получить общую статистику закупок",
        responses=ProcurementOverviewStatsSerializer,
    )
    @action(detail=False, methods=["get"])
    def overview(self, request):
        """Общая статистика закупок."""
        from django.db.models import Sum, Count
        from django.utils import timezone

        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0)
        year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0)

        user = request.user

        # Базовый queryset зависит от прав пользователя
        if user.is_superuser or user.is_staff:
            base_qs = ProcurementRequest.objects.all()
        else:
            base_qs = ProcurementRequest.objects.filter(
                Q(requestor=user) | Q(department__in=user.departments.all())
            )

        # Подсчёт по статусам
        by_status = dict(
            base_qs.values("status")
            .annotate(count=Count("id"))
            .values_list("status", "count")
        )

        # Подсчёт по срочности
        by_urgency = dict(
            base_qs.values("urgency")
            .annotate(count=Count("id"))
            .values_list("urgency", "count")
        )

        # Общие метрики
        total = base_qs.count()
        pending = base_qs.filter(status=ProcurementStatus.PENDING).count()
        approved_month = base_qs.filter(
            status=ProcurementStatus.APPROVED, updated_at__gte=month_start
        ).count()
        completed_month = base_qs.filter(
            status=ProcurementStatus.COMPLETED, completed_at__gte=month_start
        ).count()

        # Сумма потраченного за год
        spent_year = (
            base_qs.filter(
                status=ProcurementStatus.COMPLETED, completed_at__gte=year_start
            ).aggregate(total=Sum("actual_cost"))["total"]
            or 0
        )

        return Response(
            {
                "total_requests": total,
                "pending_requests": pending,
                "approved_this_month": approved_month,
                "completed_this_month": completed_month,
                "total_spent_this_year": str(spent_year),
                "by_status": by_status,
                "by_urgency": by_urgency,
            }
        )

    @extend_schema(
        tags=["Procurement"],
        summary="Получить статистику закупок по отделам",
        responses=ProcurementDepartmentStatsSerializer(many=True),
    )
    @action(detail=False, methods=["get"], url_path="by-department")
    def by_department(self, request):
        """Статистика по отделам."""
        from django.db.models import Sum

        user = request.user

        # Только для staff/superuser или руководителей
        if not (user.is_superuser or user.is_staff):
            if not user.headed_departments.exists():
                return Response(
                    {"detail": "Нет доступа к статистике по отделам."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            departments = user.headed_departments.all()
        else:
            departments = Department.objects.all()

        result = []
        for dept in departments:
            requests = ProcurementRequest.objects.filter(department=dept)
            total = requests.count()
            spent = (
                requests.filter(status=ProcurementStatus.COMPLETED).aggregate(
                    total=Sum("actual_cost")
                )["total"]
                or 0
            )

            result.append(
                {
                    "department": {"id": dept.id, "name": dept.name},
                    "total_requests": total,
                    "total_spent": str(spent),
                }
            )

        return Response(result)


class BudgetViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet для просмотра бюджетов отдела."""

    queryset = Budget.objects.select_related("department")
    serializer_class = BudgetSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["department", "year", "quarter"]
    ordering = ["-year", "-quarter", "department__name"]

    def get_permissions(self):
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.is_superuser or user.is_staff:
            return queryset

        headed_departments = user.headed_departments.all()
        if headed_departments.exists():
            return queryset.filter(department__in=headed_departments)

        if self.action == "my_department":
            return queryset

        return queryset.none()

    def list(self, request, *args, **kwargs):
        user = request.user
        if not (
            user.is_superuser
            or user.is_staff
            or user.headed_departments.exists()
        ):
            return Response(
                {"detail": "Нет доступа к бюджетам отделов."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().list(request, *args, **kwargs)

    @action(detail=False, methods=["get"], url_path="my-department")
    def my_department(self, request):
        """Бюджет текущего отдела пользователя на текущий квартал."""
        user_departments = request.user.departments.all()
        department = user_departments.first()
        if department is None:
            return Response(
                {"detail": "Пользователь не состоит ни в одном отделе."},
                status=status.HTTP_404_NOT_FOUND,
            )

        now = timezone.now()
        quarter = (now.month - 1) // 3 + 1
        budget = (
            self.get_queryset()
            .filter(
                department=department,
                year=now.year,
                quarter=quarter,
            )
            .first()
        )
        if budget is None:
            return Response(
                {"detail": "Бюджет на текущий квартал не найден."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = self.get_serializer(budget)
        return Response(serializer.data)

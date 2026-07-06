from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from django.db.models import (
    Count,
    IntegerField,
    Max,
    OuterRef,
    Q,
    Subquery,
    Value,
)
from django.db.models.functions import Coalesce
from attendance.models import AttendanceRecord
from communications import comments_helpers
from communications.models import Message
from communications.utils import user_can_access_chat
from documents.models import Document
from guests.models import Guest, GuestVisit
from procurement.models import ProcurementRequest
from requests_app.models import Request as EmployeeRequest
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from schedule.models import Event

from tasks.access import (
    task_board_access_q,
    user_can_access_calendar_event,
    user_can_access_document,
    user_can_access_employee,
    user_can_access_employee_request,
    user_can_access_guest,
    user_can_access_guest_visit,
    user_can_access_attendance_record,
    user_can_access_procurement_request,
)
from tasks.models import (
    Task,
    TaskActivity,
    TaskActivityAction,
    TaskBoard,
    TaskColumn,
    TaskLabel,
    TaskLinkedObject,
    TaskLinkedObjectKind,
)
from tasks.realtime import (
    get_task_board_recipient_ids,
    send_task_board_update,
)

from .serializers import (
    EmployeeBriefSerializer,
    TaskActivitySerializer,
    TaskBoardSerializer,
    TaskColumnSerializer,
    TaskLabelSerializer,
    TaskLinkedCalendarEventSerializer,
    TaskLinkedAttendanceRecordSerializer,
    TaskLinkedDocumentSerializer,
    TaskLinkedEmployeeSerializer,
    TaskLinkedGuestSerializer,
    TaskLinkedGuestVisitSerializer,
    TaskLinkedMessageSerializer,
    TaskLinkedProcurementRequestSerializer,
    TaskLinkedRequestSerializer,
    TaskSerializer,
    create_default_columns,
    get_attendance_record_content_type,
    get_calendar_event_content_type,
    get_document_content_type,
    get_employee_content_type,
    get_guest_content_type,
    get_guest_visit_content_type,
    get_message_content_type,
    get_procurement_request_content_type,
    get_request_content_type,
)

Employee = get_user_model()


def create_task_activity(
    task,
    actor,
    action,
    *,
    object_kind="",
    object_id=None,
    metadata=None,
):
    TaskActivity.objects.create(
        task=task,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        object_kind=object_kind or "",
        object_id=object_id,
        metadata=metadata or {},
    )


def normalize_column_positions(column):
    task_ids = list(
        column.tasks.order_by("position", "-created_at", "id").values_list(
            "id",
            flat=True,
        )
    )
    for index, task_id in enumerate(task_ids):
        Task.objects.filter(id=task_id).update(position=(index + 1) * 1000)


class TaskBoardViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = TaskBoardSerializer

    def get_queryset(self):
        return (
            TaskBoard.objects.filter(is_archived=False)
            .filter(task_board_access_q(self.request.user))
            .select_related("created_by")
            .prefetch_related(
                "members",
                "departments",
                "columns",
                "labels",
                "tasks__created_by",
                "tasks__assignee",
                "tasks__labels",
                "tasks__linked_objects",
            )
            .annotate(tasks_count=Count("tasks", distinct=True))
            .distinct()
            .order_by("name", "id")
        )

    def perform_create(self, serializer):
        board = serializer.save(created_by=self.request.user)
        create_default_columns(board)
        send_task_board_update(board, "created", "board", board.id)

    def perform_update(self, serializer):
        board = self.get_object()
        previous_recipient_ids = get_task_board_recipient_ids(board)
        board = serializer.save()
        recipient_ids = previous_recipient_ids | get_task_board_recipient_ids(board)
        send_task_board_update(
            board,
            "updated",
            "board",
            board.id,
            recipient_ids=recipient_ids,
        )

    def perform_destroy(self, instance):
        recipient_ids = get_task_board_recipient_ids(instance)
        board_id = instance.id
        instance.delete()
        send_task_board_update(
            None,
            "deleted",
            "board",
            board_id,
            recipient_ids=recipient_ids,
            board_id=board_id,
        )

    @action(detail=False, methods=["get"], url_path="default")
    def default(self, request):
        board = self.get_queryset().order_by("id").first()
        if not board:
            board = TaskBoard.objects.create(
                name="Рабочая доска",
                description="",
                created_by=request.user,
            )
            create_default_columns(board)
        serializer = self.get_serializer(self.get_queryset().get(id=board.id))
        return Response(serializer.data)


class TaskColumnViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = TaskColumnSerializer

    def get_queryset(self):
        queryset = (
            TaskColumn.objects.filter(board__is_archived=False)
            .filter(
                board__in=TaskBoard.objects.filter(
                    task_board_access_q(self.request.user)
                )
            )
            .select_related("board")
            .annotate(tasks_count=Count("tasks", distinct=True))
            .order_by("board_id", "position", "id")
        )
        board = self.request.query_params.get("board")
        if board:
            queryset = queryset.filter(board_id=board)
        return queryset

    def perform_create(self, serializer):
        column = serializer.save()
        send_task_board_update(column.board, "created", "column", column.id)

    def perform_update(self, serializer):
        column = serializer.save()
        send_task_board_update(column.board, "updated", "column", column.id)

    def perform_destroy(self, instance):
        board = instance.board
        column_id = instance.id
        instance.delete()
        send_task_board_update(board, "deleted", "column", column_id)


class TaskLabelViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = TaskLabelSerializer

    def get_queryset(self):
        queryset = (
            TaskLabel.objects.filter(board__is_archived=False)
            .filter(
                board__in=TaskBoard.objects.filter(
                    task_board_access_q(self.request.user)
                )
            )
            .select_related("board")
        )
        board = self.request.query_params.get("board")
        if board:
            queryset = queryset.filter(board_id=board)
        return queryset.order_by("name", "id")

    def perform_create(self, serializer):
        label = serializer.save()
        send_task_board_update(label.board, "created", "label", label.id)

    def perform_update(self, serializer):
        label = serializer.save()
        send_task_board_update(label.board, "updated", "label", label.id)

    def perform_destroy(self, instance):
        board = instance.board
        label_id = instance.id
        instance.delete()
        send_task_board_update(board, "deleted", "label", label_id)


class TaskViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = TaskSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "description"]
    ordering_fields = ["position", "created_at", "updated_at", "due_date"]
    ordering = ["position", "-created_at"]

    def get_queryset(self):
        task_content_type = ContentType.objects.get_for_model(Task)
        comments_subquery = (
            Message.objects.filter(
                chat__type="comments",
                chat__context_content_type=task_content_type,
                chat__context_object_id=OuterRef("pk"),
                is_deleted=False,
            )
            .values("chat")
            .annotate(count=Count("id"))
            .values("count")
        )
        queryset = (
            Task.objects.filter(board__is_archived=False)
            .filter(
                board__in=TaskBoard.objects.filter(
                    task_board_access_q(self.request.user)
                )
            )
            .select_related("board", "column", "created_by", "assignee")
            .prefetch_related("labels")
            .annotate(
                linked_messages_count=Count(
                    "linked_objects",
                    filter=Q(linked_objects__kind=TaskLinkedObjectKind.MESSAGE),
                    distinct=True,
                ),
                linked_events_count=Count(
                    "linked_objects",
                    filter=Q(
                        linked_objects__kind=TaskLinkedObjectKind.CALENDAR_EVENT
                    ),
                    distinct=True,
                ),
                linked_documents_count=Count(
                    "linked_objects",
                    filter=Q(
                        linked_objects__kind=TaskLinkedObjectKind.DOCUMENT,
                    ),
                    distinct=True,
                ),
                linked_requests_count=Count(
                    "linked_objects",
                    filter=Q(
                        linked_objects__kind=TaskLinkedObjectKind.REQUEST,
                    ),
                    distinct=True,
                ),
                linked_procurement_requests_count=Count(
                    "linked_objects",
                    filter=Q(
                        linked_objects__kind=(
                            TaskLinkedObjectKind.PROCUREMENT_REQUEST
                        ),
                    ),
                    distinct=True,
                ),
                linked_employees_count=Count(
                    "linked_objects",
                    filter=Q(
                        linked_objects__kind=TaskLinkedObjectKind.EMPLOYEE,
                    ),
                    distinct=True,
                ),
                linked_guests_count=Count(
                    "linked_objects",
                    filter=Q(
                        linked_objects__kind=TaskLinkedObjectKind.GUEST,
                    ),
                    distinct=True,
                ),
                linked_guest_visits_count=Count(
                    "linked_objects",
                    filter=Q(
                        linked_objects__kind=TaskLinkedObjectKind.GUEST_VISIT,
                    ),
                    distinct=True,
                ),
                linked_attendance_records_count=Count(
                    "linked_objects",
                    filter=Q(
                        linked_objects__kind=(
                            TaskLinkedObjectKind.ATTENDANCE_RECORD
                        ),
                    ),
                    distinct=True,
                ),
                linked_objects_count=Count("linked_objects", distinct=True),
                comments_count=Coalesce(
                    Subquery(comments_subquery, output_field=IntegerField()),
                    Value(0),
                ),
            )
        )
        params = self.request.query_params
        if board := params.get("board"):
            queryset = queryset.filter(board_id=board)
        if column := params.get("column"):
            queryset = queryset.filter(column_id=column)
        if assignee := params.get("assignee"):
            queryset = queryset.filter(assignee_id=assignee)
        if priority := params.get("priority"):
            queryset = queryset.filter(priority=priority)
        if params.get("unassigned") == "true":
            queryset = queryset.filter(assignee__isnull=True)
        return queryset

    def perform_create(self, serializer):
        task = serializer.save(created_by=self.request.user)
        create_task_activity(
            task,
            self.request.user,
            TaskActivityAction.CREATED,
            metadata={"column": task.column.name},
        )
        send_task_board_update(task.board, "created", "task", task.id)

    def perform_update(self, serializer):
        instance = serializer.instance
        previous = {
            "title": instance.title,
            "description": instance.description,
            "assignee_id": instance.assignee_id,
            "priority": instance.priority,
            "due_date": instance.due_date.isoformat() if instance.due_date else None,
            "label_ids": sorted(instance.labels.values_list("id", flat=True)),
        }
        task = serializer.save()
        current = {
            "title": task.title,
            "description": task.description,
            "assignee_id": task.assignee_id,
            "priority": task.priority,
            "due_date": task.due_date.isoformat() if task.due_date else None,
            "label_ids": sorted(task.labels.values_list("id", flat=True)),
        }
        changed_fields = [
            field for field, value in current.items() if previous[field] != value
        ]
        if changed_fields:
            create_task_activity(
                task,
                self.request.user,
                TaskActivityAction.UPDATED,
                metadata={"fields": changed_fields},
            )
        send_task_board_update(task.board, "updated", "task", task.id)

    def perform_destroy(self, instance):
        board = instance.board
        task_id = instance.id
        instance.delete()
        send_task_board_update(board, "deleted", "task", task_id)

    @action(detail=True, methods=["post"])
    def move(self, request, pk=None):
        task = self.get_object()
        column_id = request.data.get("column")
        position = request.data.get("position")
        if not column_id:
            return Response(
                {"column": ["Это поле обязательно."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            column = TaskColumn.objects.get(
                id=column_id,
                board_id=task.board_id,
                is_archived=False,
            )
        except TaskColumn.DoesNotExist:
            return Response(
                {"column": ["Колонка не найдена на этой доске."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        old_column = task.column
        if position in (None, ""):
            max_position = (
                Task.objects.filter(column=column).exclude(id=task.id).aggregate(
                    Max("position")
                )["position__max"]
                or 0
            )
            position = max_position + 1000
        else:
            try:
                position = int(position)
            except (TypeError, ValueError):
                return Response(
                    {"position": ["Позиция должна быть числом."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        task.column = column
        task.position = position
        task.save(update_fields=["column", "position", "completed_at", "updated_at"])

        normalize_column_positions(column)
        if old_column.id != column.id:
            normalize_column_positions(old_column)
        task.refresh_from_db()

        serializer = self.get_serializer(task)
        create_task_activity(
            task,
            request.user,
            TaskActivityAction.MOVED,
            metadata={
                "from_column_id": old_column.id,
                "from_column": old_column.name,
                "to_column_id": column.id,
                "to_column": column.name,
            },
        )
        send_task_board_update(
            task.board,
            "moved",
            "task",
            task.id,
            extra={"column_id": task.column_id},
        )
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="activity")
    def activity(self, request, pk=None):
        task = self.get_object()
        queryset = task.activities.select_related("actor").order_by(
            "-created_at",
            "-id",
        )
        serializer = TaskActivitySerializer(queryset, many=True)
        return Response(serializer.data)

    def _comment_payload(self, task, message):
        return {
            "id": message.id,
            "task": task.id,
            "author": EmployeeBriefSerializer(message.author).data,
            "text": message.content,
            "created_at": message.created_at,
        }

    @action(detail=True, methods=["get", "post"], url_path="comments")
    def comments(self, request, pk=None):
        task = self.get_object()

        if request.method in ("GET", "HEAD"):
            messages = comments_helpers.get_comments(task)
            return Response(
                [self._comment_payload(task, message) for message in messages]
            )

        text = request.data.get("text", "").strip()
        if not text:
            return Response(
                {"text": ["Это поле не может быть пустым."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        message = comments_helpers.create_comment(
            obj=task,
            author=request.user,
            content=text,
        )
        send_task_board_update(
            task.board,
            "commented",
            "task",
            task.id,
            extra={"comment_id": message.id},
        )
        return Response(
            self._comment_payload(task, message),
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"comments/(?P<comment_id>\d+)",
    )
    def delete_comment(self, request, pk=None, comment_id=None):
        task = self.get_object()
        chat = comments_helpers.get_comments_chat_if_exists(task)
        if chat is None:
            return Response(
                {"detail": "Комментарий не найден."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            message = Message.objects.get(
                id=comment_id,
                chat=chat,
                is_deleted=False,
            )
        except Message.DoesNotExist:
            return Response(
                {"detail": "Комментарий не найден."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not (
            request.user.is_staff
            or request.user.is_superuser
            or message.author_id == request.user.id
        ):
            return Response(
                {"detail": "Нет прав на удаление комментария."},
                status=status.HTTP_403_FORBIDDEN,
            )

        comments_helpers.delete_comment(
            message=message,
            deleted_by=request.user,
            soft_delete=True,
        )
        send_task_board_update(
            task.board,
            "comment_deleted",
            "task",
            task.id,
            extra={"comment_id": int(comment_id)},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="linked-event-tasks")
    def linked_event_tasks(self, request):
        event_id = request.query_params.get("event_id")
        try:
            event_id = int(event_id)
        except (TypeError, ValueError):
            return Response(
                {"event_id": ["Укажите ID события."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            event = Event.objects.select_related(
                "calendar",
                "calendar__binding",
                "calendar__binding__context_content_type",
                "rule",
                "creator",
            ).get(id=event_id)
        except Event.DoesNotExist:
            return Response(
                {"event_id": ["Событие не найдено."]},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not user_can_access_calendar_event(request.user, event):
            return Response(
                {"detail": "Нет доступа к этому событию."},
                status=status.HTTP_403_FORBIDDEN,
            )

        queryset = (
            self.get_queryset()
            .filter(
                linked_objects__kind=TaskLinkedObjectKind.CALENDAR_EVENT,
                linked_objects__content_type=get_calendar_event_content_type(),
                linked_objects__object_id=event.id,
            )
            .distinct()
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="linked-document-tasks")
    def linked_document_tasks(self, request):
        document_id = request.query_params.get("document_id")
        try:
            document_id = int(document_id)
        except (TypeError, ValueError):
            return Response(
                {"document_id": ["Укажите ID документа."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            document = (
                Document.objects.select_related("uploaded_by", "file", "folder")
                .prefetch_related("recipients", "departments", "tags")
                .get(id=document_id)
            )
        except Document.DoesNotExist:
            return Response(
                {"document_id": ["Документ не найден."]},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not user_can_access_document(request.user, document):
            return Response(
                {"detail": "Нет доступа к этому документу."},
                status=status.HTTP_403_FORBIDDEN,
            )

        queryset = (
            self.get_queryset()
            .filter(
                linked_objects__kind=TaskLinkedObjectKind.DOCUMENT,
                linked_objects__content_type=get_document_content_type(),
                linked_objects__object_id=document.id,
            )
            .distinct()
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="linked-request-tasks")
    def linked_request_tasks(self, request):
        request_id = request.query_params.get("request_id")
        try:
            request_id = int(request_id)
        except (TypeError, ValueError):
            return Response(
                {"request_id": ["Укажите ID заявления."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            employee_request = (
                EmployeeRequest.objects.select_related(
                    "employee",
                    "approver",
                    "department",
                )
                .prefetch_related("recipients", "cc_users")
                .get(id=request_id)
            )
        except EmployeeRequest.DoesNotExist:
            return Response(
                {"request_id": ["Заявление не найдено."]},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not user_can_access_employee_request(request.user, employee_request):
            return Response(
                {"detail": "Нет доступа к этому заявлению."},
                status=status.HTTP_403_FORBIDDEN,
            )

        queryset = (
            self.get_queryset()
            .filter(
                linked_objects__kind=TaskLinkedObjectKind.REQUEST,
                linked_objects__content_type=get_request_content_type(),
                linked_objects__object_id=employee_request.id,
            )
            .distinct()
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="linked-procurement-request-tasks")
    def linked_procurement_request_tasks(self, request):
        procurement_request_id = request.query_params.get("procurement_request_id")
        try:
            procurement_request_id = int(procurement_request_id)
        except (TypeError, ValueError):
            return Response(
                {"procurement_request_id": ["Укажите ID заявки на закупку."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            procurement_request = (
                ProcurementRequest.objects.select_related(
                    "department",
                    "processing_department",
                    "requestor",
                    "executor",
                )
                .prefetch_related("approvals", "items")
                .get(id=procurement_request_id)
            )
        except ProcurementRequest.DoesNotExist:
            return Response(
                {"procurement_request_id": ["Заявка на закупку не найдена."]},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not user_can_access_procurement_request(request.user, procurement_request):
            return Response(
                {"detail": "Нет доступа к этой заявке на закупку."},
                status=status.HTTP_403_FORBIDDEN,
            )

        queryset = (
            self.get_queryset()
            .filter(
                linked_objects__kind=TaskLinkedObjectKind.PROCUREMENT_REQUEST,
                linked_objects__content_type=get_procurement_request_content_type(),
                linked_objects__object_id=procurement_request.id,
            )
            .distinct()
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="linked-employee-tasks")
    def linked_employee_tasks(self, request):
        employee_id = request.query_params.get("employee_id")
        try:
            employee_id = int(employee_id)
        except (TypeError, ValueError):
            return Response(
                {"employee_id": ["Укажите ID сотрудника."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            employee = Employee.objects.select_related("position").get(id=employee_id)
        except Employee.DoesNotExist:
            return Response(
                {"employee_id": ["Сотрудник не найден."]},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not user_can_access_employee(request.user, employee):
            return Response(
                {"detail": "Нет доступа к этому сотруднику."},
                status=status.HTTP_403_FORBIDDEN,
            )

        queryset = (
            self.get_queryset()
            .filter(
                linked_objects__kind=TaskLinkedObjectKind.EMPLOYEE,
                linked_objects__content_type=get_employee_content_type(),
                linked_objects__object_id=employee.id,
            )
            .distinct()
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="linked-guest-tasks")
    def linked_guest_tasks(self, request):
        guest_id = request.query_params.get("guest_id")
        try:
            guest_id = int(guest_id)
        except (TypeError, ValueError):
            return Response(
                {"guest_id": ["Укажите ID гостя."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            guest = Guest.objects.get(id=guest_id)
        except Guest.DoesNotExist:
            return Response(
                {"guest_id": ["Гость не найден."]},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not user_can_access_guest(request.user, guest):
            return Response(
                {"detail": "Нет доступа к этому гостю."},
                status=status.HTTP_403_FORBIDDEN,
            )

        queryset = (
            self.get_queryset()
            .filter(
                linked_objects__kind=TaskLinkedObjectKind.GUEST,
                linked_objects__content_type=get_guest_content_type(),
                linked_objects__object_id=guest.id,
            )
            .distinct()
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="linked-guest-visit-tasks")
    def linked_guest_visit_tasks(self, request):
        guest_visit_id = request.query_params.get("guest_visit_id")
        try:
            guest_visit_id = int(guest_visit_id)
        except (TypeError, ValueError):
            return Response(
                {"guest_visit_id": ["Укажите ID заявки на гостевой визит."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            visit = GuestVisit.objects.select_related("guest", "inviter").get(
                id=guest_visit_id,
            )
        except GuestVisit.DoesNotExist:
            return Response(
                {"guest_visit_id": ["Заявка на гостевой визит не найдена."]},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not user_can_access_guest_visit(request.user, visit):
            return Response(
                {"detail": "Нет доступа к этой заявке на гостевой визит."},
                status=status.HTTP_403_FORBIDDEN,
            )

        queryset = (
            self.get_queryset()
            .filter(
                linked_objects__kind=TaskLinkedObjectKind.GUEST_VISIT,
                linked_objects__content_type=get_guest_visit_content_type(),
                linked_objects__object_id=visit.id,
            )
            .distinct()
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="linked-attendance-record-tasks")
    def linked_attendance_record_tasks(self, request):
        attendance_record_id = request.query_params.get("attendance_record_id")
        try:
            attendance_record_id = int(attendance_record_id)
        except (TypeError, ValueError):
            return Response(
                {"attendance_record_id": ["Укажите ID записи посещаемости."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            record = AttendanceRecord.objects.select_related("employee").get(
                id=attendance_record_id,
            )
        except AttendanceRecord.DoesNotExist:
            return Response(
                {"attendance_record_id": ["Запись посещаемости не найдена."]},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not user_can_access_attendance_record(request.user, record):
            return Response(
                {"detail": "Нет доступа к этой записи посещаемости."},
                status=status.HTTP_403_FORBIDDEN,
            )

        queryset = (
            self.get_queryset()
            .filter(
                linked_objects__kind=TaskLinkedObjectKind.ATTENDANCE_RECORD,
                linked_objects__content_type=get_attendance_record_content_type(),
                linked_objects__object_id=record.id,
            )
            .distinct()
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def _message_links_queryset(self, task):
        return (
            TaskLinkedObject.objects.filter(
                task=task,
                kind=TaskLinkedObjectKind.MESSAGE,
            )
            .select_related("created_by", "content_type")
            .order_by("-created_at", "-id")
        )

    def _event_links_queryset(self, task):
        return (
            TaskLinkedObject.objects.filter(
                task=task,
                kind=TaskLinkedObjectKind.CALENDAR_EVENT,
            )
            .select_related("created_by", "content_type")
            .order_by("-created_at", "-id")
        )

    def _document_links_queryset(self, task):
        return (
            TaskLinkedObject.objects.filter(
                task=task,
                kind=TaskLinkedObjectKind.DOCUMENT,
            )
            .select_related("created_by", "content_type")
            .order_by("-created_at", "-id")
        )

    def _request_links_queryset(self, task):
        return (
            TaskLinkedObject.objects.filter(
                task=task,
                kind=TaskLinkedObjectKind.REQUEST,
            )
            .select_related("created_by", "content_type")
            .order_by("-created_at", "-id")
        )

    def _procurement_request_links_queryset(self, task):
        return (
            TaskLinkedObject.objects.filter(
                task=task,
                kind=TaskLinkedObjectKind.PROCUREMENT_REQUEST,
            )
            .select_related("created_by", "content_type")
            .order_by("-created_at", "-id")
        )

    def _employee_links_queryset(self, task):
        return (
            TaskLinkedObject.objects.filter(
                task=task,
                kind=TaskLinkedObjectKind.EMPLOYEE,
            )
            .select_related("created_by", "content_type")
            .order_by("-created_at", "-id")
        )

    def _guest_links_queryset(self, task):
        return (
            TaskLinkedObject.objects.filter(
                task=task,
                kind=TaskLinkedObjectKind.GUEST,
            )
            .select_related("created_by", "content_type")
            .order_by("-created_at", "-id")
        )

    def _guest_visit_links_queryset(self, task):
        return (
            TaskLinkedObject.objects.filter(
                task=task,
                kind=TaskLinkedObjectKind.GUEST_VISIT,
            )
            .select_related("created_by", "content_type")
            .order_by("-created_at", "-id")
        )

    def _attendance_record_links_queryset(self, task):
        return (
            TaskLinkedObject.objects.filter(
                task=task,
                kind=TaskLinkedObjectKind.ATTENDANCE_RECORD,
            )
            .select_related("created_by", "content_type")
            .order_by("-created_at", "-id")
        )

    @action(detail=True, methods=["get", "post"], url_path="linked-messages")
    def linked_messages(self, request, pk=None):
        task = self.get_object()
        if request.method == "GET":
            serializer = TaskLinkedMessageSerializer(
                self._message_links_queryset(task),
                many=True,
                context={"request": request},
            )
            return Response(serializer.data)

        message_id = request.data.get("message_id")
        try:
            message_id = int(message_id)
        except (TypeError, ValueError):
            return Response(
                {"message_id": ["Укажите ID сообщения."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            message = (
                Message.objects.select_related(
                    "author",
                    "chat",
                    "reply_to",
                    "reply_to__author",
                    "poll",
                )
                .prefetch_related(
                    "attachments",
                    "reactions",
                    "reactions__user",
                    "poll__options",
                )
                .get(id=message_id)
            )
        except Message.DoesNotExist:
            return Response(
                {"message_id": ["Сообщение не найдено."]},
                status=status.HTTP_404_NOT_FOUND,
            )

        if message.is_deleted:
            return Response(
                {"message_id": ["Удаленное сообщение нельзя связать с задачей."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user_can_access_chat(message.chat, request.user):
            return Response(
                {"detail": "Нет доступа к этому сообщению."},
                status=status.HTTP_403_FORBIDDEN,
            )

        link, created = TaskLinkedObject.objects.get_or_create(
            task=task,
            kind=TaskLinkedObjectKind.MESSAGE,
            content_type=get_message_content_type(),
            object_id=message.id,
            defaults={"created_by": request.user},
        )
        serializer = TaskLinkedMessageSerializer(
            link,
            context={"request": request},
        )
        if created:
            create_task_activity(
                task,
                request.user,
                TaskActivityAction.LINKED,
                object_kind=TaskLinkedObjectKind.MESSAGE,
                object_id=message.id,
                metadata={
                    "object_label": message.content[:120],
                    "object_type": "Сообщение",
                },
            )
        send_task_board_update(
            task.board,
            "linked",
            "message",
            message.id,
            extra={"task_id": task.id, "link_id": link.id},
        )
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"linked-messages/(?P<link_id>\d+)",
    )
    def unlink_message(self, request, pk=None, link_id=None):
        task = self.get_object()
        try:
            link = self._message_links_queryset(task).get(id=link_id)
        except TaskLinkedObject.DoesNotExist:
            return Response(
                {"detail": "Связь не найдена."},
                status=status.HTTP_404_NOT_FOUND,
            )

        message_id = link.object_id
        link.delete()
        create_task_activity(
            task,
            request.user,
            TaskActivityAction.UNLINKED,
            object_kind=TaskLinkedObjectKind.MESSAGE,
            object_id=message_id,
            metadata={"object_type": "Сообщение"},
        )
        send_task_board_update(
            task.board,
            "unlinked",
            "message",
            message_id,
            extra={"task_id": task.id, "link_id": int(link_id)},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get", "post"], url_path="linked-documents")
    def linked_documents(self, request, pk=None):
        task = self.get_object()
        if request.method == "GET":
            serializer = TaskLinkedDocumentSerializer(
                self._document_links_queryset(task),
                many=True,
                context={"request": request},
            )
            return Response(serializer.data)

        document_id = request.data.get("document_id")
        try:
            document_id = int(document_id)
        except (TypeError, ValueError):
            return Response(
                {"document_id": ["Укажите ID документа."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            document = (
                Document.objects.select_related("uploaded_by", "file", "folder")
                .prefetch_related("recipients", "departments", "tags")
                .get(id=document_id)
            )
        except Document.DoesNotExist:
            return Response(
                {"document_id": ["Документ не найден."]},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not user_can_access_document(request.user, document):
            return Response(
                {"detail": "Нет доступа к этому документу."},
                status=status.HTTP_403_FORBIDDEN,
            )

        link, created = TaskLinkedObject.objects.get_or_create(
            task=task,
            kind=TaskLinkedObjectKind.DOCUMENT,
            content_type=get_document_content_type(),
            object_id=document.id,
            defaults={"created_by": request.user},
        )
        serializer = TaskLinkedDocumentSerializer(
            link,
            context={"request": request},
        )
        if created:
            create_task_activity(
                task,
                request.user,
                TaskActivityAction.LINKED,
                object_kind=TaskLinkedObjectKind.DOCUMENT,
                object_id=document.id,
                metadata={
                    "object_label": document.title,
                    "object_type": "Документ",
                },
            )
        send_task_board_update(
            task.board,
            "linked",
            "document",
            document.id,
            extra={"task_id": task.id, "link_id": link.id},
        )
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"linked-documents/(?P<link_id>\d+)",
    )
    def unlink_document(self, request, pk=None, link_id=None):
        task = self.get_object()
        try:
            link = self._document_links_queryset(task).get(id=link_id)
        except TaskLinkedObject.DoesNotExist:
            return Response(
                {"detail": "Связь не найдена."},
                status=status.HTTP_404_NOT_FOUND,
            )

        document_id = link.object_id
        link.delete()
        create_task_activity(
            task,
            request.user,
            TaskActivityAction.UNLINKED,
            object_kind=TaskLinkedObjectKind.DOCUMENT,
            object_id=document_id,
            metadata={"object_type": "Документ"},
        )
        send_task_board_update(
            task.board,
            "unlinked",
            "document",
            document_id,
            extra={"task_id": task.id, "link_id": int(link_id)},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get", "post"], url_path="linked-requests")
    def linked_requests(self, request, pk=None):
        task = self.get_object()
        if request.method == "GET":
            serializer = TaskLinkedRequestSerializer(
                self._request_links_queryset(task),
                many=True,
                context={"request": request},
            )
            return Response(serializer.data)

        request_id = request.data.get("request_id")
        try:
            request_id = int(request_id)
        except (TypeError, ValueError):
            return Response(
                {"request_id": ["Укажите ID заявления."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            employee_request = (
                EmployeeRequest.objects.select_related(
                    "employee",
                    "approver",
                    "department",
                )
                .prefetch_related("recipients", "cc_users")
                .get(id=request_id)
            )
        except EmployeeRequest.DoesNotExist:
            return Response(
                {"request_id": ["Заявление не найдено."]},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not user_can_access_employee_request(request.user, employee_request):
            return Response(
                {"detail": "Нет доступа к этому заявлению."},
                status=status.HTTP_403_FORBIDDEN,
            )

        link, created = TaskLinkedObject.objects.get_or_create(
            task=task,
            kind=TaskLinkedObjectKind.REQUEST,
            content_type=get_request_content_type(),
            object_id=employee_request.id,
            defaults={"created_by": request.user},
        )
        serializer = TaskLinkedRequestSerializer(
            link,
            context={"request": request},
        )
        if created:
            create_task_activity(
                task,
                request.user,
                TaskActivityAction.LINKED,
                object_kind=TaskLinkedObjectKind.REQUEST,
                object_id=employee_request.id,
                metadata={
                    "object_label": employee_request.display_title,
                    "object_type": "Заявление",
                },
            )
        send_task_board_update(
            task.board,
            "linked",
            "request",
            employee_request.id,
            extra={"task_id": task.id, "link_id": link.id},
        )
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"linked-requests/(?P<link_id>\d+)",
    )
    def unlink_request(self, request, pk=None, link_id=None):
        task = self.get_object()
        try:
            link = self._request_links_queryset(task).get(id=link_id)
        except TaskLinkedObject.DoesNotExist:
            return Response(
                {"detail": "Связь не найдена."},
                status=status.HTTP_404_NOT_FOUND,
            )

        request_id = link.object_id
        link.delete()
        create_task_activity(
            task,
            request.user,
            TaskActivityAction.UNLINKED,
            object_kind=TaskLinkedObjectKind.REQUEST,
            object_id=request_id,
            metadata={"object_type": "Заявление"},
        )
        send_task_board_update(
            task.board,
            "unlinked",
            "request",
            request_id,
            extra={"task_id": task.id, "link_id": int(link_id)},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get", "post"], url_path="linked-procurement-requests")
    def linked_procurement_requests(self, request, pk=None):
        task = self.get_object()
        if request.method == "GET":
            serializer = TaskLinkedProcurementRequestSerializer(
                self._procurement_request_links_queryset(task),
                many=True,
                context={"request": request},
            )
            return Response(serializer.data)

        procurement_request_id = request.data.get("procurement_request_id")
        try:
            procurement_request_id = int(procurement_request_id)
        except (TypeError, ValueError):
            return Response(
                {"procurement_request_id": ["Укажите ID заявки на закупку."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            procurement_request = (
                ProcurementRequest.objects.select_related(
                    "department",
                    "processing_department",
                    "requestor",
                    "executor",
                )
                .prefetch_related("approvals", "items")
                .get(id=procurement_request_id)
            )
        except ProcurementRequest.DoesNotExist:
            return Response(
                {"procurement_request_id": ["Заявка на закупку не найдена."]},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not user_can_access_procurement_request(request.user, procurement_request):
            return Response(
                {"detail": "Нет доступа к этой заявке на закупку."},
                status=status.HTTP_403_FORBIDDEN,
            )

        link, created = TaskLinkedObject.objects.get_or_create(
            task=task,
            kind=TaskLinkedObjectKind.PROCUREMENT_REQUEST,
            content_type=get_procurement_request_content_type(),
            object_id=procurement_request.id,
            defaults={"created_by": request.user},
        )
        serializer = TaskLinkedProcurementRequestSerializer(
            link,
            context={"request": request},
        )
        if created:
            create_task_activity(
                task,
                request.user,
                TaskActivityAction.LINKED,
                object_kind=TaskLinkedObjectKind.PROCUREMENT_REQUEST,
                object_id=procurement_request.id,
                metadata={
                    "object_label": procurement_request.title,
                    "object_type": "Заявка на закупку",
                },
            )
        send_task_board_update(
            task.board,
            "linked",
            "procurement_request",
            procurement_request.id,
            extra={"task_id": task.id, "link_id": link.id},
        )
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"linked-procurement-requests/(?P<link_id>\d+)",
    )
    def unlink_procurement_request(self, request, pk=None, link_id=None):
        task = self.get_object()
        try:
            link = self._procurement_request_links_queryset(task).get(id=link_id)
        except TaskLinkedObject.DoesNotExist:
            return Response(
                {"detail": "Связь не найдена."},
                status=status.HTTP_404_NOT_FOUND,
            )

        procurement_request_id = link.object_id
        link.delete()
        create_task_activity(
            task,
            request.user,
            TaskActivityAction.UNLINKED,
            object_kind=TaskLinkedObjectKind.PROCUREMENT_REQUEST,
            object_id=procurement_request_id,
            metadata={"object_type": "Заявка на закупку"},
        )
        send_task_board_update(
            task.board,
            "unlinked",
            "procurement_request",
            procurement_request_id,
            extra={"task_id": task.id, "link_id": int(link_id)},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get", "post"], url_path="linked-employees")
    def linked_employees(self, request, pk=None):
        task = self.get_object()
        if request.method == "GET":
            serializer = TaskLinkedEmployeeSerializer(
                self._employee_links_queryset(task),
                many=True,
                context={"request": request},
            )
            return Response(serializer.data)

        employee_id = request.data.get("employee_id")
        try:
            employee_id = int(employee_id)
        except (TypeError, ValueError):
            return Response(
                {"employee_id": ["Укажите ID сотрудника."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            employee = Employee.objects.select_related("position").get(id=employee_id)
        except Employee.DoesNotExist:
            return Response(
                {"employee_id": ["Сотрудник не найден."]},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not user_can_access_employee(request.user, employee):
            return Response(
                {"detail": "Нет доступа к этому сотруднику."},
                status=status.HTTP_403_FORBIDDEN,
            )

        link, created = TaskLinkedObject.objects.get_or_create(
            task=task,
            kind=TaskLinkedObjectKind.EMPLOYEE,
            content_type=get_employee_content_type(),
            object_id=employee.id,
            defaults={"created_by": request.user},
        )
        serializer = TaskLinkedEmployeeSerializer(
            link,
            context={"request": request},
        )
        if created:
            create_task_activity(
                task,
                request.user,
                TaskActivityAction.LINKED,
                object_kind=TaskLinkedObjectKind.EMPLOYEE,
                object_id=employee.id,
                metadata={
                    "object_label": employee.get_full_name() or employee.email,
                    "object_type": "Сотрудник",
                },
            )
        send_task_board_update(
            task.board,
            "linked",
            "employee",
            employee.id,
            extra={"task_id": task.id, "link_id": link.id},
        )
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"linked-employees/(?P<link_id>\d+)",
    )
    def unlink_employee(self, request, pk=None, link_id=None):
        task = self.get_object()
        try:
            link = self._employee_links_queryset(task).get(id=link_id)
        except TaskLinkedObject.DoesNotExist:
            return Response(
                {"detail": "Связь не найдена."},
                status=status.HTTP_404_NOT_FOUND,
            )

        employee_id = link.object_id
        link.delete()
        create_task_activity(
            task,
            request.user,
            TaskActivityAction.UNLINKED,
            object_kind=TaskLinkedObjectKind.EMPLOYEE,
            object_id=employee_id,
            metadata={"object_type": "Сотрудник"},
        )
        send_task_board_update(
            task.board,
            "unlinked",
            "employee",
            employee_id,
            extra={"task_id": task.id, "link_id": int(link_id)},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get", "post"], url_path="linked-guests")
    def linked_guests(self, request, pk=None):
        task = self.get_object()
        if request.method == "GET":
            serializer = TaskLinkedGuestSerializer(
                self._guest_links_queryset(task),
                many=True,
                context={"request": request},
            )
            return Response(serializer.data)

        guest_id = request.data.get("guest_id")
        try:
            guest_id = int(guest_id)
        except (TypeError, ValueError):
            return Response(
                {"guest_id": ["Укажите ID гостя."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            guest = Guest.objects.get(id=guest_id)
        except Guest.DoesNotExist:
            return Response(
                {"guest_id": ["Гость не найден."]},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not user_can_access_guest(request.user, guest):
            return Response(
                {"detail": "Нет доступа к этому гостю."},
                status=status.HTTP_403_FORBIDDEN,
            )

        link, created = TaskLinkedObject.objects.get_or_create(
            task=task,
            kind=TaskLinkedObjectKind.GUEST,
            content_type=get_guest_content_type(),
            object_id=guest.id,
            defaults={"created_by": request.user},
        )
        serializer = TaskLinkedGuestSerializer(
            link,
            context={"request": request},
        )
        if created:
            create_task_activity(
                task,
                request.user,
                TaskActivityAction.LINKED,
                object_kind=TaskLinkedObjectKind.GUEST,
                object_id=guest.id,
                metadata={
                    "object_label": guest.full_name,
                    "object_type": "Гость",
                },
            )
        send_task_board_update(
            task.board,
            "linked",
            "guest",
            guest.id,
            extra={"task_id": task.id, "link_id": link.id},
        )
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"linked-guests/(?P<link_id>\d+)",
    )
    def unlink_guest(self, request, pk=None, link_id=None):
        task = self.get_object()
        try:
            link = self._guest_links_queryset(task).get(id=link_id)
        except TaskLinkedObject.DoesNotExist:
            return Response(
                {"detail": "Связь не найдена."},
                status=status.HTTP_404_NOT_FOUND,
            )

        guest_id = link.object_id
        link.delete()
        create_task_activity(
            task,
            request.user,
            TaskActivityAction.UNLINKED,
            object_kind=TaskLinkedObjectKind.GUEST,
            object_id=guest_id,
            metadata={"object_type": "Гость"},
        )
        send_task_board_update(
            task.board,
            "unlinked",
            "guest",
            guest_id,
            extra={"task_id": task.id, "link_id": int(link_id)},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get", "post"], url_path="linked-guest-visits")
    def linked_guest_visits(self, request, pk=None):
        task = self.get_object()
        if request.method == "GET":
            serializer = TaskLinkedGuestVisitSerializer(
                self._guest_visit_links_queryset(task),
                many=True,
                context={"request": request},
            )
            return Response(serializer.data)

        guest_visit_id = request.data.get("guest_visit_id")
        try:
            guest_visit_id = int(guest_visit_id)
        except (TypeError, ValueError):
            return Response(
                {"guest_visit_id": ["Укажите ID заявки на гостевой визит."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            visit = GuestVisit.objects.select_related("guest", "inviter").get(
                id=guest_visit_id,
            )
        except GuestVisit.DoesNotExist:
            return Response(
                {"guest_visit_id": ["Заявка на гостевой визит не найдена."]},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not user_can_access_guest_visit(request.user, visit):
            return Response(
                {"detail": "Нет доступа к этой заявке на гостевой визит."},
                status=status.HTTP_403_FORBIDDEN,
            )

        link, created = TaskLinkedObject.objects.get_or_create(
            task=task,
            kind=TaskLinkedObjectKind.GUEST_VISIT,
            content_type=get_guest_visit_content_type(),
            object_id=visit.id,
            defaults={"created_by": request.user},
        )
        serializer = TaskLinkedGuestVisitSerializer(
            link,
            context={"request": request},
        )
        if created:
            create_task_activity(
                task,
                request.user,
                TaskActivityAction.LINKED,
                object_kind=TaskLinkedObjectKind.GUEST_VISIT,
                object_id=visit.id,
                metadata={
                    "object_label": visit.guest.full_name,
                    "object_type": "Заявка на гостевой визит",
                },
            )
        send_task_board_update(
            task.board,
            "linked",
            "guest_visit",
            visit.id,
            extra={"task_id": task.id, "link_id": link.id},
        )
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"linked-guest-visits/(?P<link_id>\d+)",
    )
    def unlink_guest_visit(self, request, pk=None, link_id=None):
        task = self.get_object()
        try:
            link = self._guest_visit_links_queryset(task).get(id=link_id)
        except TaskLinkedObject.DoesNotExist:
            return Response(
                {"detail": "Связь не найдена."},
                status=status.HTTP_404_NOT_FOUND,
            )

        guest_visit_id = link.object_id
        link.delete()
        create_task_activity(
            task,
            request.user,
            TaskActivityAction.UNLINKED,
            object_kind=TaskLinkedObjectKind.GUEST_VISIT,
            object_id=guest_visit_id,
            metadata={"object_type": "Заявка на гостевой визит"},
        )
        send_task_board_update(
            task.board,
            "unlinked",
            "guest_visit",
            guest_visit_id,
            extra={"task_id": task.id, "link_id": int(link_id)},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get", "post"], url_path="linked-attendance-records")
    def linked_attendance_records(self, request, pk=None):
        task = self.get_object()
        if request.method == "GET":
            serializer = TaskLinkedAttendanceRecordSerializer(
                self._attendance_record_links_queryset(task),
                many=True,
                context={"request": request},
            )
            return Response(serializer.data)

        attendance_record_id = request.data.get("attendance_record_id")
        try:
            attendance_record_id = int(attendance_record_id)
        except (TypeError, ValueError):
            return Response(
                {"attendance_record_id": ["Укажите ID записи посещаемости."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            record = AttendanceRecord.objects.select_related("employee").get(
                id=attendance_record_id,
            )
        except AttendanceRecord.DoesNotExist:
            return Response(
                {"attendance_record_id": ["Запись посещаемости не найдена."]},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not user_can_access_attendance_record(request.user, record):
            return Response(
                {"detail": "Нет доступа к этой записи посещаемости."},
                status=status.HTTP_403_FORBIDDEN,
            )

        link, created = TaskLinkedObject.objects.get_or_create(
            task=task,
            kind=TaskLinkedObjectKind.ATTENDANCE_RECORD,
            content_type=get_attendance_record_content_type(),
            object_id=record.id,
            defaults={"created_by": request.user},
        )
        serializer = TaskLinkedAttendanceRecordSerializer(
            link,
            context={"request": request},
        )
        if created:
            employee_name = str(record.employee) if record.employee_id else ""
            create_task_activity(
                task,
                request.user,
                TaskActivityAction.LINKED,
                object_kind=TaskLinkedObjectKind.ATTENDANCE_RECORD,
                object_id=record.id,
                metadata={
                    "object_label": f"{employee_name} {record.date}".strip(),
                    "object_type": "Запись посещаемости",
                },
            )
        send_task_board_update(
            task.board,
            "linked",
            "attendance_record",
            record.id,
            extra={"task_id": task.id, "link_id": link.id},
        )
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"linked-attendance-records/(?P<link_id>\d+)",
    )
    def unlink_attendance_record(self, request, pk=None, link_id=None):
        task = self.get_object()
        try:
            link = self._attendance_record_links_queryset(task).get(id=link_id)
        except TaskLinkedObject.DoesNotExist:
            return Response(
                {"detail": "Связь не найдена."},
                status=status.HTTP_404_NOT_FOUND,
            )

        attendance_record_id = link.object_id
        link.delete()
        create_task_activity(
            task,
            request.user,
            TaskActivityAction.UNLINKED,
            object_kind=TaskLinkedObjectKind.ATTENDANCE_RECORD,
            object_id=attendance_record_id,
            metadata={"object_type": "Запись посещаемости"},
        )
        send_task_board_update(
            task.board,
            "unlinked",
            "attendance_record",
            attendance_record_id,
            extra={"task_id": task.id, "link_id": int(link_id)},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get", "post"], url_path="linked-events")
    def linked_events(self, request, pk=None):
        task = self.get_object()
        if request.method == "GET":
            serializer = TaskLinkedCalendarEventSerializer(
                self._event_links_queryset(task),
                many=True,
                context={"request": request},
            )
            return Response(serializer.data)

        event_id = request.data.get("event_id")
        try:
            event_id = int(event_id)
        except (TypeError, ValueError):
            return Response(
                {"event_id": ["Укажите ID события."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            event = Event.objects.select_related(
                "calendar",
                "calendar__binding",
                "calendar__binding__context_content_type",
                "rule",
                "creator",
            ).get(id=event_id)
        except Event.DoesNotExist:
            return Response(
                {"event_id": ["Событие не найдено."]},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not user_can_access_calendar_event(request.user, event):
            return Response(
                {"detail": "Нет доступа к этому событию."},
                status=status.HTTP_403_FORBIDDEN,
            )

        link, created = TaskLinkedObject.objects.get_or_create(
            task=task,
            kind=TaskLinkedObjectKind.CALENDAR_EVENT,
            content_type=get_calendar_event_content_type(),
            object_id=event.id,
            defaults={"created_by": request.user},
        )
        serializer = TaskLinkedCalendarEventSerializer(
            link,
            context={"request": request},
        )
        if created:
            create_task_activity(
                task,
                request.user,
                TaskActivityAction.LINKED,
                object_kind=TaskLinkedObjectKind.CALENDAR_EVENT,
                object_id=event.id,
                metadata={
                    "object_label": event.title,
                    "object_type": "Календарное событие",
                },
            )
        send_task_board_update(
            task.board,
            "linked",
            "calendar_event",
            event.id,
            extra={"task_id": task.id, "link_id": link.id},
        )
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"linked-events/(?P<link_id>\d+)",
    )
    def unlink_event(self, request, pk=None, link_id=None):
        task = self.get_object()
        try:
            link = self._event_links_queryset(task).get(id=link_id)
        except TaskLinkedObject.DoesNotExist:
            return Response(
                {"detail": "Связь не найдена."},
                status=status.HTTP_404_NOT_FOUND,
            )

        event_id = link.object_id
        link.delete()
        create_task_activity(
            task,
            request.user,
            TaskActivityAction.UNLINKED,
            object_kind=TaskLinkedObjectKind.CALENDAR_EVENT,
            object_id=event_id,
            metadata={"object_type": "Календарное событие"},
        )
        send_task_board_update(
            task.board,
            "unlinked",
            "calendar_event",
            event_id,
            extra={"task_id": task.id, "link_id": int(link_id)},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

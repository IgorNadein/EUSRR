from django.db.models import Count, Max, Q
from communications.models import Message
from communications.utils import user_can_access_chat
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from schedule.models import Event

from tasks.access import task_board_access_q, user_can_access_calendar_event
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
    TaskActivitySerializer,
    TaskBoardSerializer,
    TaskColumnSerializer,
    TaskLabelSerializer,
    TaskLinkedCalendarEventSerializer,
    TaskLinkedMessageSerializer,
    TaskSerializer,
    create_default_columns,
    get_calendar_event_content_type,
    get_message_content_type,
)


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
                linked_objects_count=Count("linked_objects", distinct=True),
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
        queryset = task.activities.select_related("actor").order_by("-created_at", "-id")
        serializer = TaskActivitySerializer(queryset, many=True)
        return Response(serializer.data)

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

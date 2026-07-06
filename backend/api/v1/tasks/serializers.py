from django.db.models import Max
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from api.v1.documents.serializers import DocumentReadSerializer
from api.v1.employees.serializers import EmployeeBriefSerializer
from api.v1.employees.serializers.department import DepartmentBriefSerializer
from communications.models import Message
from communications.comments_helpers import get_comment_count
from communications.serialization import serialize_message
from communications.utils import user_can_access_chat
from documents.models import Document
from employees.models import Department
from procurement.models import ProcurementRequest
from requests_app.models import Request as EmployeeRequest
from schedule.models import Event
from api.v1.schedule.serializers import EventSerializer
from tasks.access import (
    user_can_access_calendar_event,
    user_can_access_document,
    user_can_access_employee_request,
    user_can_access_procurement_request,
    user_can_access_task_board,
)
from tasks.models import (
    Task,
    TaskActivity,
    TaskBoard,
    TaskColumn,
    TaskLabel,
    TaskLinkedObject,
    TaskLinkedObjectKind,
)

User = get_user_model()


DEFAULT_COLUMNS = [
    ("Новые", "#38bdf8", False),
    ("В работе", "#f59e0b", False),
    ("На проверке", "#8b5cf6", False),
    ("Готово", "#22c55e", True),
]


def create_default_columns(board):
    if board.columns.exists():
        return
    TaskColumn.objects.bulk_create(
        [
            TaskColumn(
                board=board,
                name=name,
                color=color,
                is_done=is_done,
                position=index * 1000,
            )
            for index, (name, color, is_done) in enumerate(DEFAULT_COLUMNS)
        ]
    )


def validate_board_access(serializer, board):
    request = serializer.context.get("request")
    user = getattr(request, "user", None)
    if not user_can_access_task_board(user, board):
        raise serializers.ValidationError("У вас нет доступа к этой доске.")
    return board


class TaskLabelSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskLabel
        fields = ["id", "board", "name", "color"]
        read_only_fields = ["id"]

    def validate_board(self, board):
        return validate_board_access(self, board)


class TaskColumnSerializer(serializers.ModelSerializer):
    tasks_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = TaskColumn
        fields = [
            "id",
            "board",
            "name",
            "position",
            "color",
            "is_done",
            "is_archived",
            "tasks_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "member_details",
            "department_details",
            "columns",
            "labels",
            "tasks",
            "tasks_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "tasks_count"]

    def validate_board(self, board):
        return validate_board_access(self, board)


class TaskSerializer(serializers.ModelSerializer):
    created_by = EmployeeBriefSerializer(read_only=True)
    assignee = EmployeeBriefSerializer(read_only=True)
    assignee_id = serializers.PrimaryKeyRelatedField(
        source="assignee",
        queryset=User.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    labels = TaskLabelSerializer(many=True, read_only=True)
    label_ids = serializers.PrimaryKeyRelatedField(
        source="labels",
        queryset=TaskLabel.objects.all(),
        many=True,
        required=False,
        write_only=True,
    )
    priority_display = serializers.CharField(
        source="get_priority_display",
        read_only=True,
    )
    board_name = serializers.CharField(source="board.name", read_only=True)
    column_name = serializers.CharField(source="column.name", read_only=True)
    column_color = serializers.CharField(source="column.color", read_only=True)
    linked_messages_count = serializers.SerializerMethodField()
    linked_events_count = serializers.SerializerMethodField()
    linked_documents_count = serializers.SerializerMethodField()
    linked_requests_count = serializers.SerializerMethodField()
    linked_procurement_requests_count = serializers.SerializerMethodField()
    linked_objects_count = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            "id",
            "board",
            "board_name",
            "column",
            "column_name",
            "column_color",
            "title",
            "description",
            "created_by",
            "assignee",
            "assignee_id",
            "labels",
            "label_ids",
            "priority",
            "priority_display",
            "due_date",
            "position",
            "completed_at",
            "linked_messages_count",
            "linked_events_count",
            "linked_documents_count",
            "linked_requests_count",
            "linked_procurement_requests_count",
            "linked_objects_count",
            "comments_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "board_name",
            "column_name",
            "column_color",
            "priority_display",
            "completed_at",
            "linked_messages_count",
            "linked_events_count",
            "linked_documents_count",
            "linked_requests_count",
            "linked_procurement_requests_count",
            "linked_objects_count",
            "comments_count",
            "created_at",
            "updated_at",
        ]

    @extend_schema_field(serializers.IntegerField())
    def get_linked_messages_count(self, obj):
        if hasattr(obj, "linked_messages_count"):
            return obj.linked_messages_count
        return obj.linked_objects.filter(
            kind=TaskLinkedObjectKind.MESSAGE,
        ).count()

    @extend_schema_field(serializers.IntegerField())
    def get_linked_events_count(self, obj):
        if hasattr(obj, "linked_events_count"):
            return obj.linked_events_count
        return obj.linked_objects.filter(
            kind=TaskLinkedObjectKind.CALENDAR_EVENT,
        ).count()

    @extend_schema_field(serializers.IntegerField())
    def get_linked_documents_count(self, obj):
        if hasattr(obj, "linked_documents_count"):
            return obj.linked_documents_count
        return obj.linked_objects.filter(
            kind=TaskLinkedObjectKind.DOCUMENT,
        ).count()

    @extend_schema_field(serializers.IntegerField())
    def get_linked_requests_count(self, obj):
        if hasattr(obj, "linked_requests_count"):
            return obj.linked_requests_count
        return obj.linked_objects.filter(
            kind=TaskLinkedObjectKind.REQUEST,
        ).count()

    @extend_schema_field(serializers.IntegerField())
    def get_linked_procurement_requests_count(self, obj):
        if hasattr(obj, "linked_procurement_requests_count"):
            return obj.linked_procurement_requests_count
        return obj.linked_objects.filter(
            kind=TaskLinkedObjectKind.PROCUREMENT_REQUEST,
        ).count()

    @extend_schema_field(serializers.IntegerField())
    def get_linked_objects_count(self, obj):
        if hasattr(obj, "linked_objects_count"):
            return obj.linked_objects_count
        return obj.linked_objects.count()

    @extend_schema_field(serializers.IntegerField())
    def get_comments_count(self, obj):
        if hasattr(obj, "comments_count"):
            return obj.comments_count
        return get_comment_count(obj)

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        board = attrs.get("board") or getattr(self.instance, "board", None)
        column = attrs.get("column") or getattr(self.instance, "column", None)
        labels = attrs.get("labels")

        if board and not user_can_access_task_board(user, board):
            raise serializers.ValidationError(
                {"board": "У вас нет доступа к этой доске."}
            )

        if column and board and column.board_id != board.id:
            raise serializers.ValidationError(
                {"column": "Колонка должна принадлежать выбранной доске."}
            )

        if labels is not None and board:
            invalid_labels = [
                label.id for label in labels if label.board_id != board.id
            ]
            if invalid_labels:
                raise serializers.ValidationError(
                    {"label_ids": "Метки должны принадлежать выбранной доске."}
                )

        return attrs

    def create(self, validated_data):
        labels = validated_data.pop("labels", [])
        if "position" not in validated_data:
            column = validated_data["column"]
            max_position = (
                Task.objects.filter(column=column).aggregate(Max("position"))[
                    "position__max"
                ]
                or 0
            )
            validated_data["position"] = max_position + 1000
        task = Task.objects.create(**validated_data)
        if labels:
            task.labels.set(labels)
        return task

    def update(self, instance, validated_data):
        labels = validated_data.pop("labels", None)
        task = super().update(instance, validated_data)
        if labels is not None:
            task.labels.set(labels)
        return task


class TaskBoardSerializer(serializers.ModelSerializer):
    created_by = EmployeeBriefSerializer(read_only=True)
    members = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        many=True,
        required=False,
    )
    member_details = EmployeeBriefSerializer(
        source="members",
        many=True,
        read_only=True,
    )
    departments = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        many=True,
        required=False,
    )
    department_details = DepartmentBriefSerializer(
        source="departments",
        many=True,
        read_only=True,
    )
    columns = TaskColumnSerializer(many=True, read_only=True)
    labels = TaskLabelSerializer(many=True, read_only=True)
    tasks = TaskSerializer(many=True, read_only=True)
    tasks_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = TaskBoard
        fields = [
            "id",
            "name",
            "description",
            "created_by",
            "members",
            "member_details",
            "departments",
            "department_details",
            "is_archived",
            "columns",
            "labels",
            "tasks",
            "tasks_count",
            "created_at",
            "updated_at",
        ]


class TaskLinkedMessageSerializer(serializers.ModelSerializer):
    created_by = EmployeeBriefSerializer(read_only=True)
    message = serializers.SerializerMethodField()
    message_id = serializers.IntegerField(source="object_id", read_only=True)
    can_open = serializers.SerializerMethodField()
    object_url = serializers.SerializerMethodField()

    class Meta:
        model = TaskLinkedObject
        fields = [
            "id",
            "kind",
            "message_id",
            "message",
            "can_open",
            "object_url",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.JSONField(allow_null=True))
    def get_message(self, obj):
        if obj.kind != TaskLinkedObjectKind.MESSAGE:
            return None

        message = getattr(obj, "content_object", None)
        if message is None:
            return None

        return serialize_message(message, include_linked_tasks=False)

    @extend_schema_field(serializers.BooleanField())
    def get_can_open(self, obj):
        message = getattr(obj, "content_object", None)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if obj.kind != TaskLinkedObjectKind.MESSAGE or message is None or not user:
            return False
        return user_can_access_chat(message.chat, user)

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_object_url(self, obj):
        message = getattr(obj, "content_object", None)
        if message is None or not self.get_can_open(obj):
            return None
        return f"/messages/{message.chat_id}?message={message.id}"


def get_message_content_type():
    return ContentType.objects.get_for_model(Message)


class TaskActivitySerializer(serializers.ModelSerializer):
    actor = EmployeeBriefSerializer(read_only=True)
    action_display = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = TaskActivity
        fields = [
            "id",
            "action",
            "action_display",
            "actor",
            "object_kind",
            "object_id",
            "metadata",
            "created_at",
        ]
        read_only_fields = fields


class TaskLinkedCalendarEventSerializer(serializers.ModelSerializer):
    created_by = EmployeeBriefSerializer(read_only=True)
    event = serializers.SerializerMethodField()
    event_id = serializers.IntegerField(source="object_id", read_only=True)
    can_open = serializers.SerializerMethodField()
    object_url = serializers.SerializerMethodField()

    class Meta:
        model = TaskLinkedObject
        fields = [
            "id",
            "kind",
            "event_id",
            "event",
            "can_open",
            "object_url",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.JSONField(allow_null=True))
    def get_event(self, obj):
        if obj.kind != TaskLinkedObjectKind.CALENDAR_EVENT:
            return None

        event = getattr(obj, "content_object", None)
        if event is None:
            return None

        return EventSerializer(event, context=self.context).data

    @extend_schema_field(serializers.BooleanField())
    def get_can_open(self, obj):
        event = getattr(obj, "content_object", None)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if (
            obj.kind != TaskLinkedObjectKind.CALENDAR_EVENT
            or event is None
            or not user
        ):
            return False
        return user_can_access_calendar_event(user, event)

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_object_url(self, obj):
        event = getattr(obj, "content_object", None)
        if event is None or not self.get_can_open(obj):
            return None
        return f"/calendar?calendar={event.calendar_id}&event={event.id}"


def get_calendar_event_content_type():
    return ContentType.objects.get_for_model(Event)


class TaskLinkedDocumentSerializer(serializers.ModelSerializer):
    created_by = EmployeeBriefSerializer(read_only=True)
    document = serializers.SerializerMethodField()
    document_id = serializers.IntegerField(source="object_id", read_only=True)
    can_open = serializers.SerializerMethodField()
    object_url = serializers.SerializerMethodField()

    class Meta:
        model = TaskLinkedObject
        fields = [
            "id",
            "kind",
            "document_id",
            "document",
            "can_open",
            "object_url",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.JSONField(allow_null=True))
    def get_document(self, obj):
        if obj.kind != TaskLinkedObjectKind.DOCUMENT:
            return None

        document = getattr(obj, "content_object", None)
        if document is None:
            return None

        if not self.get_can_open(obj):
            return {
                "id": document.id,
                "title": document.title,
                "description": document.description,
                "is_regulation": document.is_regulation,
                "folder_path": document.folder_path,
                "file_name": (
                    getattr(document.file, "name", None)
                    if document.file
                    else None
                ),
            }

        return DocumentReadSerializer(document, context=self.context).data

    @extend_schema_field(serializers.BooleanField())
    def get_can_open(self, obj):
        document = getattr(obj, "content_object", None)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if (
            obj.kind != TaskLinkedObjectKind.DOCUMENT
            or document is None
            or not user
        ):
            return False
        return user_can_access_document(user, document)

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_object_url(self, obj):
        document = getattr(obj, "content_object", None)
        if document is None or not self.get_can_open(obj):
            return None
        return f"/documents?document={document.id}"


def get_document_content_type():
    return ContentType.objects.get_for_model(Document)


class TaskLinkedRequestSerializer(serializers.ModelSerializer):
    created_by = EmployeeBriefSerializer(read_only=True)
    request = serializers.SerializerMethodField()
    request_id = serializers.IntegerField(source="object_id", read_only=True)
    can_open = serializers.SerializerMethodField()
    object_url = serializers.SerializerMethodField()

    class Meta:
        model = TaskLinkedObject
        fields = [
            "id",
            "kind",
            "request_id",
            "request",
            "can_open",
            "object_url",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.JSONField(allow_null=True))
    def get_request(self, obj):
        if obj.kind != TaskLinkedObjectKind.REQUEST:
            return None

        request_obj = getattr(obj, "content_object", None)
        if request_obj is None:
            return None

        return {
            "id": request_obj.id,
            "title": request_obj.title,
            "display_title": request_obj.display_title,
            "type": request_obj.type,
            "type_display": request_obj.get_type_display(),
            "status": request_obj.status,
            "status_display": request_obj.get_status_display(),
            "comment": request_obj.comment,
            "date_from": request_obj.date_from,
            "date_to": request_obj.date_to,
            "employee": EmployeeBriefSerializer(request_obj.employee).data,
            "created_at": request_obj.created_at,
            "updated_at": request_obj.updated_at,
        }

    @extend_schema_field(serializers.BooleanField())
    def get_can_open(self, obj):
        request_obj = getattr(obj, "content_object", None)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if (
            obj.kind != TaskLinkedObjectKind.REQUEST
            or request_obj is None
            or not user
        ):
            return False
        return user_can_access_employee_request(user, request_obj)

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_object_url(self, obj):
        request_obj = getattr(obj, "content_object", None)
        if request_obj is None or not self.get_can_open(obj):
            return None
        return f"/requests?request={request_obj.id}"


def get_request_content_type():
    return ContentType.objects.get_for_model(EmployeeRequest)


class TaskLinkedProcurementRequestSerializer(serializers.ModelSerializer):
    created_by = EmployeeBriefSerializer(read_only=True)
    procurement_request = serializers.SerializerMethodField()
    procurement_request_id = serializers.IntegerField(source="object_id", read_only=True)
    can_open = serializers.SerializerMethodField()
    object_url = serializers.SerializerMethodField()

    class Meta:
        model = TaskLinkedObject
        fields = [
            "id",
            "kind",
            "procurement_request_id",
            "procurement_request",
            "can_open",
            "object_url",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.JSONField(allow_null=True))
    def get_procurement_request(self, obj):
        if obj.kind != TaskLinkedObjectKind.PROCUREMENT_REQUEST:
            return None

        procurement_request = getattr(obj, "content_object", None)
        if procurement_request is None:
            return None

        return {
            "id": procurement_request.id,
            "title": procurement_request.title,
            "description": procurement_request.description,
            "status": procurement_request.status,
            "status_display": procurement_request.get_status_display(),
            "urgency": procurement_request.urgency,
            "urgency_display": procurement_request.get_urgency_display(),
            "fulfillment_status": procurement_request.fulfillment_status,
            "fulfillment_status_display": procurement_request.get_fulfillment_status_display(),
            "department_id": procurement_request.department_id,
            "department_name": (
                procurement_request.department.name
                if procurement_request.department_id
                else None
            ),
            "processing_department_id": procurement_request.processing_department_id,
            "processing_department_name": (
                procurement_request.processing_department.name
                if procurement_request.processing_department_id
                else None
            ),
            "requestor": EmployeeBriefSerializer(procurement_request.requestor).data,
            "executor": (
                EmployeeBriefSerializer(procurement_request.executor).data
                if procurement_request.executor_id
                else None
            ),
            "total_cost": procurement_request.total_cost,
            "items_count": procurement_request.items_count,
            "created_at": procurement_request.created_at,
            "updated_at": procurement_request.updated_at,
        }

    @extend_schema_field(serializers.BooleanField())
    def get_can_open(self, obj):
        procurement_request = getattr(obj, "content_object", None)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if (
            obj.kind != TaskLinkedObjectKind.PROCUREMENT_REQUEST
            or procurement_request is None
            or not user
        ):
            return False
        return user_can_access_procurement_request(user, procurement_request)

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_object_url(self, obj):
        procurement_request = getattr(obj, "content_object", None)
        if procurement_request is None or not self.get_can_open(obj):
            return None
        return f"/procurement?request={procurement_request.id}"


def get_procurement_request_content_type():
    return ContentType.objects.get_for_model(ProcurementRequest)

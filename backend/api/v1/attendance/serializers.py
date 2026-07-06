from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from attendance.models import (
    AttendanceAnalysisRun,
    AttendanceAutoSyncSettings,
    AttendanceRecord,
    EmployeeWorkSchedule,
    StandardWorkSchedule,
)
from attendance.services import get_standard_work_schedule_payload
from api.v1.employees.serializers import EmployeeBriefSerializer
from employees.constants import ACTION_REMOTE


def _linked_task_payloads(record: AttendanceRecord, user) -> list[dict]:
    if not user or not getattr(user, "is_authenticated", False):
        return []

    try:
        from tasks.access import task_board_access_q
        from tasks.models import (
            TaskBoard,
            TaskLinkedObject,
            TaskLinkedObjectKind,
        )
    except Exception:
        return []

    content_type = ContentType.objects.get_for_model(AttendanceRecord)
    accessible_boards = TaskBoard.objects.filter(
        is_archived=False,
    ).filter(task_board_access_q(user))

    links = (
        TaskLinkedObject.objects.filter(
            kind=TaskLinkedObjectKind.ATTENDANCE_RECORD,
            content_type=content_type,
            object_id=record.id,
            task__board__in=accessible_boards,
        )
        .select_related("task", "task__board", "task__column")
        .order_by("task__title", "task_id")
    )

    return [
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
        for link in links
    ]


class DateOverrideSerializer(serializers.Serializer):
    date = serializers.DateField()
    is_workday = serializers.BooleanField()
    reason = serializers.CharField(required=False, allow_blank=True)
    start_time = serializers.CharField(required=False, allow_blank=True)
    end_time = serializers.CharField(required=False, allow_blank=True)
    expected_hours = serializers.FloatField(required=False)


class LogStormScheduleSerializer(serializers.Serializer):
    start_time = serializers.CharField()
    end_time = serializers.CharField()
    expected_hours = serializers.FloatField()
    workdays = serializers.ListField(
        child=serializers.CharField(),
        required=False,
    )
    date_overrides = DateOverrideSerializer(many=True, required=False)


class LogStormAttendanceAnalyzeSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()
    period_start = serializers.DateField()
    period_end = serializers.DateField()
    schedule = LogStormScheduleSerializer(required=False)
    aliases = serializers.ListField(
        child=serializers.CharField(),
        required=False,
    )

    def validate(self, attrs):
        if attrs["period_start"] > attrs["period_end"]:
            raise serializers.ValidationError(
                "period_start must be less than or equal to period_end"
            )
        return attrs


class EmployeeWorkScheduleSerializer(serializers.ModelSerializer):
    employee_id = serializers.IntegerField(source="employee.id", read_only=True)
    is_default = serializers.BooleanField(read_only=True, default=False)

    class Meta:
        model = EmployeeWorkSchedule
        fields = (
            "id",
            "employee_id",
            "start_time",
            "end_time",
            "expected_hours",
            "workdays",
            "date_overrides",
            "is_active",
            "is_default",
            "updated_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "employee_id",
            "is_default",
            "updated_by",
            "created_at",
            "updated_at",
        )

    def validate_workdays(self, value):
        allowed = set(EmployeeWorkSchedule.DEFAULT_WORKDAYS) | {"Saturday", "Sunday"}
        if not isinstance(value, list):
            raise serializers.ValidationError("workdays must be a list")
        normalized = []
        for item in value:
            if item not in allowed:
                raise serializers.ValidationError(f"Unknown weekday: {item}")
            if item not in normalized:
                normalized.append(item)
        return normalized

    def validate_expected_hours(self, value):
        if value <= 0 or value > 24:
            raise serializers.ValidationError("expected_hours must be between 0 and 24")
        return value


class StandardWorkScheduleSerializer(serializers.ModelSerializer):
    is_default = serializers.BooleanField(read_only=True, default=False)

    class Meta:
        model = StandardWorkSchedule
        fields = (
            "id",
            "start_time",
            "end_time",
            "expected_hours",
            "workdays",
            "date_overrides",
            "is_default",
            "updated_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "is_default",
            "updated_by",
            "created_at",
            "updated_at",
        )

    def validate_workdays(self, value):
        allowed = set(StandardWorkSchedule.DEFAULT_WORKDAYS) | {"Saturday", "Sunday"}
        if not isinstance(value, list):
            raise serializers.ValidationError("workdays must be a list")
        normalized = []
        for item in value:
            if item not in allowed:
                raise serializers.ValidationError(f"Unknown weekday: {item}")
            if item not in normalized:
                normalized.append(item)
        return normalized

    def validate_expected_hours(self, value):
        if value <= 0 or value > 24:
            raise serializers.ValidationError("expected_hours must be between 0 and 24")
        return value


class AttendanceAutoSyncSettingsSerializer(serializers.ModelSerializer):
    last_status_label = serializers.CharField(
        source="get_last_status_display",
        read_only=True,
    )

    class Meta:
        model = AttendanceAutoSyncSettings
        fields = (
            "id",
            "enabled",
            "frequency_minutes",
            "lookback_days",
            "next_run_at",
            "last_started_at",
            "last_finished_at",
            "last_status",
            "last_status_label",
            "last_error",
            "last_success_count",
            "last_error_count",
            "updated_by",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "next_run_at",
            "last_started_at",
            "last_finished_at",
            "last_status",
            "last_status_label",
            "last_error",
            "last_success_count",
            "last_error_count",
            "updated_by",
            "updated_at",
        )

    def validate_frequency_minutes(self, value):
        allowed = {item[0] for item in AttendanceAutoSyncSettings.FREQUENCY_CHOICES}
        if value not in allowed:
            raise serializers.ValidationError("Unsupported frequency")
        return value

    def validate_lookback_days(self, value):
        allowed = {item[0] for item in AttendanceAutoSyncSettings.LOOKBACK_CHOICES}
        if value not in allowed:
            raise serializers.ValidationError("Unsupported lookback")
        return value


def default_work_schedule_response(employee_id: int) -> dict:
    payload = get_standard_work_schedule_payload()
    return {
        "id": None,
        "employee_id": employee_id,
        "start_time": payload["start_time"],
        "end_time": payload["end_time"],
        "expected_hours": payload["expected_hours"],
        "workdays": payload["workdays"],
        "date_overrides": payload["date_overrides"],
        "is_active": False,
        "is_default": True,
        "updated_by": None,
        "created_at": None,
        "updated_at": None,
    }


def default_standard_work_schedule_response() -> dict:
    payload = get_standard_work_schedule_payload()
    return {
        "id": None,
        "start_time": payload["start_time"],
        "end_time": payload["end_time"],
        "expected_hours": payload["expected_hours"],
        "workdays": payload["workdays"],
        "date_overrides": payload["date_overrides"],
        "is_default": True,
        "updated_by": None,
        "created_at": None,
        "updated_at": None,
    }


class AttendanceMonthlyMatrixQuerySerializer(serializers.Serializer):
    employee_ids = serializers.CharField()
    month = serializers.RegexField(r"^\d{4}-\d{2}$")

    def validate_employee_ids(self, value):
        employee_ids = []
        for raw_item in value.split(","):
            item = raw_item.strip()
            if not item:
                continue
            try:
                employee_id = int(item)
            except ValueError as exc:
                raise serializers.ValidationError(
                    "employee_ids must be a comma-separated list of integers"
                ) from exc
            if employee_id not in employee_ids:
                employee_ids.append(employee_id)

        if not employee_ids:
            raise serializers.ValidationError("employee_ids is required")
        return employee_ids

    def validate_month(self, value):
        year, month = [int(part) for part in value.split("-")]
        if month < 1 or month > 12:
            raise serializers.ValidationError("month must be between 01 and 12")
        return value


class AttendanceMonthlyMatrixExportQuerySerializer(serializers.Serializer):
    employee_ids = serializers.CharField()
    period_start = serializers.DateField()
    period_end = serializers.DateField()

    def validate_employee_ids(self, value):
        employee_ids = []
        for raw_item in value.split(","):
            item = raw_item.strip()
            if not item:
                continue
            try:
                employee_id = int(item)
            except ValueError as exc:
                raise serializers.ValidationError(
                    "employee_ids must be a comma-separated list of integers"
                ) from exc
            if employee_id not in employee_ids:
                employee_ids.append(employee_id)

        if not employee_ids:
            raise serializers.ValidationError("employee_ids is required")
        return employee_ids

    def validate(self, attrs):
        if attrs["period_start"] > attrs["period_end"]:
            raise serializers.ValidationError(
                "period_start must be less than or equal to period_end"
            )
        return attrs


class AttendanceAnalysisRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceAnalysisRun
        fields = (
            "id",
            "employee",
            "period_start",
            "period_end",
            "status",
            "schedule_payload",
            "request_payload",
            "response_payload",
            "error",
            "triggered_by",
            "created_at",
        )
        read_only_fields = fields


class AttendanceRecordSerializer(serializers.ModelSerializer):
    analysis_run_id = serializers.IntegerField(read_only=True)
    comments_count = serializers.IntegerField(read_only=True, default=0)
    non_working_reason = serializers.SerializerMethodField()
    linked_tasks = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceRecord
        fields = (
            "id",
            "analysis_run_id",
            "employee",
            "date",
            "display_name",
            "arrival_time",
            "departure_time",
            "work_hours",
            "expected_hours",
            "is_workday",
            "effective_is_workday",
            "non_working_reason",
            "is_late",
            "late_minutes",
            "is_early_leave",
            "early_leave_minutes",
            "is_underwork",
            "underwork_hours",
            "is_overtime",
            "overtime_hours",
            "is_absent",
            "statuses",
            "employee_issues",
            "technical_issues",
            "personnel_status",
            "personnel_status_label",
            "personnel_action",
            "is_manually_edited",
            "manual_edit_payload",
            "manual_edited_by",
            "manual_edited_at",
            "raw_data",
            "comments_count",
            "linked_tasks",
            "updated_at",
        )
        read_only_fields = fields

    def get_non_working_reason(self, obj):
        if obj.effective_is_workday:
            return ""
        if obj.personnel_status_label and obj.personnel_status != ACTION_REMOTE:
            return obj.personnel_status_label
        if not obj.is_workday:
            return "Выходной по графику/календарю"
        return "Нерабочий день"

    def get_linked_tasks(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return _linked_task_payloads(obj, user)


class AttendanceRecordUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceRecord
        fields = (
            "arrival_time",
            "departure_time",
            "work_hours",
            "expected_hours",
            "is_workday",
            "effective_is_workday",
            "is_late",
            "late_minutes",
            "is_early_leave",
            "early_leave_minutes",
            "is_underwork",
            "underwork_hours",
            "is_overtime",
            "overtime_hours",
            "is_absent",
        )
        extra_kwargs = {
            "arrival_time": {"required": False, "allow_blank": True, "allow_null": True},
            "departure_time": {"required": False, "allow_blank": True, "allow_null": True},
        }


class AttendanceRecordCommentSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    record = serializers.IntegerField(read_only=True)
    author = EmployeeBriefSerializer(read_only=True)
    text = serializers.CharField()
    created_at = serializers.DateTimeField(read_only=True)

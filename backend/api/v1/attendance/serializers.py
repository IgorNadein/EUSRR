from rest_framework import serializers

from attendance.models import AttendanceAnalysisRun, AttendanceRecord
from api.v1.employees.serializers import EmployeeBriefSerializer


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

    def validate(self, attrs):
        if attrs["period_start"] > attrs["period_end"]:
            raise serializers.ValidationError(
                "period_start must be less than or equal to period_end"
            )
        return attrs


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
            "updated_at",
        )
        read_only_fields = fields

    def get_non_working_reason(self, obj):
        if obj.effective_is_workday:
            return ""
        if obj.personnel_status_label:
            return obj.personnel_status_label
        if not obj.is_workday:
            return "Выходной по графику/календарю"
        return "Нерабочий день"


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

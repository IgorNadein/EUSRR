from rest_framework import serializers


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

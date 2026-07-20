from decimal import Decimal

from rest_framework import serializers

from finance.models import (
    PayrollStatement,
    PayrollStatementAcknowledgement,
    PayrollStatementLine,
    PayrollDailyWorkEntry,
    PayrollWorkRecord,
)


class PayrollStatementLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollStatementLine
        fields = [
            "code",
            "label",
            "kind",
            "amount",
            "source_period_from",
            "source_period_to",
            "is_retro",
            "calculated",
        ]


class PayrollStatementAcknowledgementSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollStatementAcknowledgement
        fields = ["viewed_at", "acknowledged_at", "disputed_at"]


def period_payload(statement):
    period = statement.run.period
    return {
        "code": period.code,
        "name": period.name,
        "date_from": period.date_from,
        "date_to": period.date_to,
        "pay_date": period.pay_date,
    }


def acknowledgement_payload(statement):
    try:
        acknowledgement = statement.acknowledgement
    except PayrollStatementAcknowledgement.DoesNotExist:
        return None
    return PayrollStatementAcknowledgementSerializer(acknowledgement).data


class OwnPayrollStatementSummarySerializer(serializers.ModelSerializer):
    """List metadata only; detailed amounts/lines require the audited endpoint."""

    period = serializers.SerializerMethodField()
    revision = serializers.IntegerField(source="run.revision", read_only=True)
    published_at = serializers.DateTimeField(
        source="run.published_at",
        read_only=True,
    )
    acknowledgement = serializers.SerializerMethodField()

    class Meta:
        model = PayrollStatement
        fields = [
            "public_id",
            "period",
            "revision",
            "published_at",
            "currency",
            "payable",
            "acknowledgement",
        ]
        read_only_fields = fields

    def get_period(self, obj):
        return period_payload(obj)

    def get_acknowledgement(self, obj):
        return acknowledgement_payload(obj)


class OwnPayrollStatementSerializer(serializers.ModelSerializer):
    period = serializers.SerializerMethodField()
    revision = serializers.IntegerField(source="run.revision", read_only=True)
    published_at = serializers.DateTimeField(
        source="run.published_at",
        read_only=True,
    )
    lines = PayrollStatementLineSerializer(many=True, read_only=True)
    acknowledgement = serializers.SerializerMethodField()

    class Meta:
        model = PayrollStatement
        fields = [
            "public_id",
            "period",
            "revision",
            "published_at",
            "currency",
            "point_delta",
            "gross_before_adjustments",
            "adjustment_total",
            "gross_total",
            "deduction_total",
            "net_pay",
            "payment_total",
            "payable",
            "lines",
            "acknowledgement",
        ]
        read_only_fields = fields

    def get_period(self, obj):
        return period_payload(obj)

    def get_acknowledgement(self, obj):
        return acknowledgement_payload(obj)


class OwnPayrollWorkRecordSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = PayrollWorkRecord
        fields = [
            "id",
            "period_id",
            "target_points",
            "target_points_overridden",
            "actual_points",
            "revision",
            "status",
            "status_label",
            "lock_version",
            "replaces_id",
            "reason",
            "source",
            "created_at",
            "updated_at",
            "approved_at",
        ]
        read_only_fields = fields


class OwnPayrollDailyWorkEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollDailyWorkEntry
        fields = [
            "id",
            "period_id",
            "work_date",
            "target_points",
            "actual_points",
            "note",
            "lock_version",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class OwnPayrollDailyWorkEntryWriteSerializer(serializers.Serializer):
    period_id = serializers.IntegerField(min_value=1)
    work_date = serializers.DateField()
    actual_points = serializers.DecimalField(
        max_digits=19,
        decimal_places=4,
        min_value=Decimal("0"),
    )
    note = serializers.CharField(
        allow_blank=True,
        required=False,
        trim_whitespace=True,
    )
    expected_lock_version = serializers.IntegerField(
        min_value=0,
        required=False,
    )

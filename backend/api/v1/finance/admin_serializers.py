"""Serializers for the native payroll administration workspace.

Workflow fields, hashes, source references and idempotency keys intentionally
never form part of a writable/read payload here.  State transitions are owned
by :mod:`finance.payroll.services`.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from finance.enums import ApprovalStatus, InputSource
from finance.models import (
    EmployeePayRate,
    PayrollComponent,
    PayrollInputLine,
    PayrollPeriod,
    PayrollRun,
    PayrollWorkRecord,
)
from finance.payroll.work_norm import calculate_period_target_points

Employee = get_user_model()


def _validation_detail(exc: DjangoValidationError):
    if hasattr(exc, "message_dict"):
        return exc.message_dict
    return {"non_field_errors": exc.messages}


class PayrollEmployeeMiniSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    position = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = ["id", "display_name", "position", "department"]
        read_only_fields = fields

    def get_display_name(self, obj):
        return obj.get_full_name().strip() or f"Сотрудник #{obj.pk}"

    def get_position(self, obj):
        position = getattr(obj, "position", None)
        return position.name if position is not None else None

    def get_department(self, obj):
        prefetched = getattr(obj, "_prefetched_objects_cache", {}).get(
            "departments_links"
        )
        if prefetched is None:
            link = (
                obj.departments_links.filter(is_active=True)
                .select_related("department")
                .order_by("department__name", "id")
                .first()
            )
        else:
            link = next(
                (
                    item
                    for item in sorted(
                        prefetched,
                        key=lambda item: (item.department.name, item.pk),
                    )
                    if item.is_active
                ),
                None,
            )
        return link.department.name if link is not None else None


class PayrollUserRefSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = ["id", "display_name"]
        read_only_fields = fields

    def get_display_name(self, obj):
        return obj.get_full_name().strip() or f"Сотрудник #{obj.pk}"


class PayrollComponentSerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = PayrollComponent
        fields = [
            "id",
            "code",
            "name",
            "kind",
            "kind_label",
            "requires_reason",
            "is_active",
            "display_order",
        ]
        read_only_fields = fields


class PayrollPeriodSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    current_run_id = serializers.IntegerField(read_only=True, allow_null=True)
    created_by_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = PayrollPeriod
        fields = [
            "id",
            "code",
            "name",
            "date_from",
            "date_to",
            "pay_date",
            "currency",
            "status",
            "status_label",
            "current_run_id",
            "lock_version",
            "created_by_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class PayrollPeriodWriteSerializer(serializers.ModelSerializer):
    expected_lock_version = serializers.IntegerField(
        min_value=0,
        required=False,
        write_only=True,
    )

    class Meta:
        model = PayrollPeriod
        fields = [
            "code",
            "name",
            "date_from",
            "date_to",
            "pay_date",
            "currency",
            "expected_lock_version",
        ]

    def validate(self, attrs):
        if self.instance is not None and "expected_lock_version" not in attrs:
            raise serializers.ValidationError(
                {"expected_lock_version": "Укажите открытую версию периода."}
            )
        return attrs


class DraftWriteSerializerMixin:
    """Create manual drafts and update them through model optimistic locking."""

    expected_lock_version = serializers.IntegerField(
        min_value=0,
        required=False,
        write_only=True,
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance is not None and "expected_lock_version" not in attrs:
            raise serializers.ValidationError(
                {"expected_lock_version": "Укажите открытую версию черновика."}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop("expected_lock_version", None)
        instance = self.Meta.model(
            **validated_data,
            status=ApprovalStatus.DRAFT,
            source=InputSource.MANUAL,
            created_by=self.context["actor"],
        )
        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(_validation_detail(exc)) from exc
        instance.save(force_insert=True)
        return instance

    def update(self, instance, validated_data):
        expected_lock_version = validated_data.pop("expected_lock_version")
        for field_name, value in validated_data.items():
            setattr(instance, field_name, value)
        instance._expected_lock_version = expected_lock_version
        try:
            instance.full_clean()
            instance.save()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(_validation_detail(exc)) from exc
        return instance


class EmployeePayRateSerializer(serializers.ModelSerializer):
    employee = PayrollEmployeeMiniSerializer(read_only=True)
    employee_id = serializers.IntegerField(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    created_by_id = serializers.IntegerField(read_only=True)
    approved_by_id = serializers.IntegerField(read_only=True, allow_null=True)
    voided_by_id = serializers.IntegerField(read_only=True, allow_null=True)
    replaces_id = serializers.IntegerField(read_only=True, allow_null=True)
    created_by = PayrollUserRefSerializer(read_only=True)
    approved_by = PayrollUserRefSerializer(read_only=True)

    class Meta:
        model = EmployeePayRate
        fields = [
            "id",
            "employee_id",
            "employee",
            "rate_code",
            "amount",
            "point_rate",
            "currency",
            "effective_from",
            "revision",
            "status",
            "status_label",
            "lock_version",
            "replaces_id",
            "reason",
            "source",
            "created_by_id",
            "created_by",
            "created_at",
            "approved_by_id",
            "approved_by",
            "approved_at",
            "voided_by_id",
            "voided_at",
        ]
        read_only_fields = fields


class EmployeePayRateWriteSerializer(
    DraftWriteSerializerMixin,
    serializers.ModelSerializer,
):
    expected_lock_version = DraftWriteSerializerMixin.expected_lock_version
    employee_id = serializers.PrimaryKeyRelatedField(
        source="employee",
        queryset=Employee.objects.filter(is_active=True),
    )

    class Meta:
        model = EmployeePayRate
        fields = [
            "employee_id",
            "rate_code",
            "amount",
            "point_rate",
            "currency",
            "effective_from",
            "reason",
            "expected_lock_version",
        ]


class EmployeePayRateRevisionSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=19, decimal_places=4, required=False)
    point_rate = serializers.DecimalField(
        max_digits=19,
        decimal_places=4,
        min_value=0,
        required=False,
        allow_null=True,
    )
    currency = serializers.CharField(max_length=3, required=False)
    reason = serializers.CharField(allow_blank=False, trim_whitespace=True)


class BulkPointRateCommandSerializer(serializers.Serializer):
    MODE_FIXED = "fixed"
    MODE_IN_NORM = "in_norm"

    employee_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )
    mode = serializers.ChoiceField(
        choices=(MODE_FIXED, MODE_IN_NORM),
        required=False,
    )
    point_rate = serializers.DecimalField(
        max_digits=19,
        decimal_places=4,
        min_value=0,
        required=False,
        allow_null=True,
    )
    reason = serializers.CharField(allow_blank=False, trim_whitespace=True)

    def validate_employee_ids(self, value):
        return list(dict.fromkeys(value))

    def validate(self, attrs):
        attrs = super().validate(attrs)
        mode = attrs.get("mode")
        if mode is None:
            mode = (
                self.MODE_FIXED
                if attrs.get("point_rate") is not None
                else self.MODE_IN_NORM
            )
            attrs["mode"] = mode
        if mode == self.MODE_FIXED and attrs.get("point_rate") is None:
            raise serializers.ValidationError(
                {"point_rate": "Укажите фиксированную цену или выберите автоматический расчёт."}
            )
        if mode == self.MODE_IN_NORM:
            attrs["point_rate"] = None
        return attrs


class BulkPayRateCommandSerializer(serializers.Serializer):
    employee_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )
    amount = serializers.DecimalField(
        max_digits=19,
        decimal_places=4,
        min_value=Decimal("0.0001"),
    )
    effective_from = serializers.DateField()
    reason = serializers.CharField(allow_blank=False, trim_whitespace=True)

    def validate_employee_ids(self, value):
        return list(dict.fromkeys(value))


class BulkTargetPointsCommandSerializer(serializers.Serializer):
    MODE_FIXED = "fixed"
    MODE_AUTOMATIC = "automatic"

    employee_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )
    mode = serializers.ChoiceField(choices=(MODE_FIXED, MODE_AUTOMATIC))
    target_points = serializers.DecimalField(
        max_digits=19,
        decimal_places=4,
        min_value=Decimal("0.0001"),
        required=False,
        allow_null=True,
    )
    reason = serializers.CharField(allow_blank=False, trim_whitespace=True)

    def validate_employee_ids(self, value):
        return list(dict.fromkeys(value))

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs["mode"] == self.MODE_FIXED and attrs.get("target_points") is None:
            raise serializers.ValidationError(
                {"target_points": "Укажите норму баллов."}
            )
        if attrs["mode"] == self.MODE_AUTOMATIC:
            attrs["target_points"] = None
        return attrs


class PayrollWorkRecordSerializer(serializers.ModelSerializer):
    employee = PayrollEmployeeMiniSerializer(read_only=True)
    employee_id = serializers.IntegerField(read_only=True)
    period_id = serializers.IntegerField(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    created_by_id = serializers.IntegerField(read_only=True)
    approved_by_id = serializers.IntegerField(read_only=True, allow_null=True)
    voided_by_id = serializers.IntegerField(read_only=True, allow_null=True)
    replaces_id = serializers.IntegerField(read_only=True, allow_null=True)
    created_by = PayrollUserRefSerializer(read_only=True)
    approved_by = PayrollUserRefSerializer(read_only=True)

    class Meta:
        model = PayrollWorkRecord
        fields = [
            "id",
            "period_id",
            "employee_id",
            "employee",
            "target_points",
            "target_points_overridden",
            "actual_points",
            "expected_point_amount",
            "expected_gross",
            "expected_recalculated_gross",
            "expected_payable",
            "revision",
            "status",
            "status_label",
            "lock_version",
            "replaces_id",
            "reason",
            "source",
            "created_by_id",
            "created_by",
            "created_at",
            "updated_at",
            "approved_by_id",
            "approved_by",
            "approved_at",
            "voided_by_id",
            "voided_at",
        ]
        read_only_fields = fields


class PayrollWorkRecordWriteSerializer(
    DraftWriteSerializerMixin,
    serializers.ModelSerializer,
):
    expected_lock_version = DraftWriteSerializerMixin.expected_lock_version
    period_id = serializers.PrimaryKeyRelatedField(
        source="period",
        queryset=PayrollPeriod.objects.all(),
    )
    employee_id = serializers.PrimaryKeyRelatedField(
        source="employee",
        queryset=Employee.objects.filter(is_active=True),
    )
    target_points = serializers.DecimalField(
        max_digits=19,
        decimal_places=4,
        min_value=Decimal("0.0001"),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = PayrollWorkRecord
        fields = [
            "period_id",
            "employee_id",
            "target_points",
            "actual_points",
            "expected_point_amount",
            "expected_gross",
            "expected_recalculated_gross",
            "expected_payable",
            "reason",
            "expected_lock_version",
        ]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        target_was_sent = "target_points" in attrs
        should_calculate = (
            self.instance is None and not target_was_sent
        ) or attrs.get("target_points") is None
        if should_calculate:
            period = attrs.get("period") or self.instance.period
            employee = attrs.get("employee") or self.instance.employee
            target_points, _, _ = calculate_period_target_points(
                period,
                employee=employee,
            )
            attrs["target_points"] = target_points
            attrs["target_points_overridden"] = False
        elif target_was_sent:
            attrs["target_points_overridden"] = True
        return attrs


class PayrollWorkRecordRevisionSerializer(serializers.Serializer):
    target_points = serializers.DecimalField(
        max_digits=19,
        decimal_places=4,
        min_value=0,
        required=False,
    )
    actual_points = serializers.DecimalField(
        max_digits=19,
        decimal_places=4,
        min_value=0,
        required=False,
    )
    expected_point_amount = serializers.DecimalField(
        max_digits=19,
        decimal_places=2,
        allow_null=True,
        required=False,
    )
    expected_gross = serializers.DecimalField(
        max_digits=19,
        decimal_places=2,
        allow_null=True,
        required=False,
    )
    expected_recalculated_gross = serializers.DecimalField(
        max_digits=19,
        decimal_places=2,
        allow_null=True,
        required=False,
    )
    expected_payable = serializers.DecimalField(
        max_digits=19,
        decimal_places=2,
        allow_null=True,
        required=False,
    )
    reason = serializers.CharField(allow_blank=False, trim_whitespace=True)


class PayrollInputLineSerializer(serializers.ModelSerializer):
    employee = PayrollEmployeeMiniSerializer(read_only=True)
    employee_id = serializers.IntegerField(read_only=True)
    period_id = serializers.IntegerField(read_only=True)
    component = PayrollComponentSerializer(read_only=True)
    component_id = serializers.IntegerField(read_only=True)
    relates_to_period_id = serializers.IntegerField(read_only=True, allow_null=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    created_by_id = serializers.IntegerField(read_only=True)
    approved_by_id = serializers.IntegerField(read_only=True, allow_null=True)
    voided_by_id = serializers.IntegerField(read_only=True, allow_null=True)
    created_by = PayrollUserRefSerializer(read_only=True)
    approved_by = PayrollUserRefSerializer(read_only=True)

    class Meta:
        model = PayrollInputLine
        fields = [
            "id",
            "period_id",
            "employee_id",
            "employee",
            "component_id",
            "component",
            "amount",
            "relates_to_period_id",
            "reason",
            "status",
            "status_label",
            "lock_version",
            "source",
            "created_by_id",
            "created_by",
            "created_at",
            "approved_by_id",
            "approved_by",
            "approved_at",
            "voided_by_id",
            "voided_at",
        ]
        read_only_fields = fields


class PayrollInputLineWriteSerializer(
    DraftWriteSerializerMixin,
    serializers.ModelSerializer,
):
    expected_lock_version = DraftWriteSerializerMixin.expected_lock_version
    period_id = serializers.PrimaryKeyRelatedField(
        source="period",
        queryset=PayrollPeriod.objects.all(),
    )
    employee_id = serializers.PrimaryKeyRelatedField(
        source="employee",
        queryset=Employee.objects.filter(is_active=True),
    )
    component_id = serializers.PrimaryKeyRelatedField(
        source="component",
        queryset=PayrollComponent.objects.all(),
    )
    relates_to_period_id = serializers.PrimaryKeyRelatedField(
        source="relates_to_period",
        queryset=PayrollPeriod.objects.all(),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = PayrollInputLine
        fields = [
            "period_id",
            "employee_id",
            "component_id",
            "amount",
            "relates_to_period_id",
            "reason",
            "expected_lock_version",
        ]


class ApprovalCommandSerializer(serializers.Serializer):
    expected_lock_version = serializers.IntegerField(min_value=0)


class ClearComponentCellCommandSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField(min_value=1)
    component_id = serializers.IntegerField(min_value=1)


class CalculatePayrollCommandSerializer(serializers.Serializer):
    expected_lock_version = serializers.IntegerField(min_value=0)
    recalculation_reason = serializers.CharField(
        allow_blank=True,
        required=False,
        default="",
        trim_whitespace=True,
    )
    idempotency_key = serializers.UUIDField(required=False, allow_null=True)


class AttendanceWorkImportCommandSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(
        choices=("missing_only", "replace_existing"),
    )
    preview_token = serializers.CharField(min_length=64, max_length=64)
    expected_period_lock_version = serializers.IntegerField(min_value=0)
    reason = serializers.CharField(
        allow_blank=True,
        required=False,
        default="",
        trim_whitespace=True,
    )

    def validate(self, attrs):
        if attrs["mode"] == "replace_existing" and not attrs["reason"]:
            raise serializers.ValidationError(
                {"reason": "Для пересчёта существующих записей укажите причину."}
            )
        return attrs


class ReturnPayrollCommandSerializer(serializers.Serializer):
    reason = serializers.CharField(allow_blank=False, trim_whitespace=True)


class PayrollRunSerializer(serializers.ModelSerializer):
    period_id = serializers.IntegerField(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    requested_by_id = serializers.IntegerField(read_only=True)
    approved_by_id = serializers.IntegerField(read_only=True, allow_null=True)
    published_by_id = serializers.IntegerField(read_only=True, allow_null=True)
    supersedes_id = serializers.IntegerField(read_only=True, allow_null=True)
    requested_by = PayrollUserRefSerializer(read_only=True)
    approved_by = PayrollUserRefSerializer(read_only=True)
    published_by = PayrollUserRefSerializer(read_only=True)

    class Meta:
        model = PayrollRun
        fields = [
            "id",
            "period_id",
            "revision",
            "status",
            "status_label",
            "supersedes_id",
            "recalculation_reason",
            "employee_count",
            "gross_total",
            "deduction_total",
            "payable_total",
            "requested_by_id",
            "requested_by",
            "requested_at",
            "approved_by_id",
            "approved_by",
            "approved_at",
            "published_by_id",
            "published_by",
            "published_at",
        ]
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self.context.get("include_amounts", False):
            for field_name in ("gross_total", "deduction_total", "payable_total"):
                data[field_name] = None
        return data

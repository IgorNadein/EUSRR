"""Native, permission-gated payroll administration API.

The endpoints in this module are an HTTP adapter around the existing finance
models and payroll services.  Generic Django model permissions never grant
access to payroll data.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import F, OuterRef, Q, Subquery
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from finance.enums import ApprovalStatus, PayrollPeriodStatus, PayrollRunStatus
from finance.models import (
    EmployeePayRate,
    PayrollAuditEvent,
    PayrollComponent,
    PayrollInputLine,
    PayrollPeriod,
    PayrollRun,
    PayrollWorkRecord,
)
from finance.payroll.config import (
    base_rate_code,
    build_rules,
    rules_cover_period,
    ruleset_not_effective_message,
    ruleset_period_details,
)
from finance.payroll.access import has_payroll_permission, has_simple_admin_access
from finance.payroll.exceptions import PayrollOperationError, PayrollPermissionDenied
from finance.payroll.services import (
    approve_input_line,
    approve_pay_rate,
    approve_run,
    approve_work_record,
    calculate_period,
    close_period,
    publish_run,
    return_run_for_correction,
    submit_run_for_review,
)
from finance.payroll.attendance import (
    apply_attendance_work_preview,
    build_attendance_work_preview,
)

from .admin_serializers import (
    AttendanceWorkImportCommandSerializer,
    ApprovalCommandSerializer,
    CalculatePayrollCommandSerializer,
    EmployeePayRateRevisionSerializer,
    EmployeePayRateSerializer,
    EmployeePayRateWriteSerializer,
    PayrollComponentSerializer,
    PayrollEmployeeMiniSerializer,
    PayrollInputLineSerializer,
    PayrollInputLineWriteSerializer,
    PayrollPeriodSerializer,
    PayrollPeriodWriteSerializer,
    PayrollRunSerializer,
    PayrollWorkRecordRevisionSerializer,
    PayrollWorkRecordSerializer,
    PayrollWorkRecordWriteSerializer,
    ReturnPayrollCommandSerializer,
    _validation_detail,
)
from .views import NoStorePayrollResponseMixin, PayrollConflict

Employee = get_user_model()

PAYROLL_PERMISSIONS = {
    "manage_inputs": "finance.manage_payroll_inputs",
    "approve_inputs": "finance.approve_payroll_inputs",
    "calculate": "finance.calculate_payroll",
    "approve_run": "finance.approve_payroll",
    "override_approval": "finance.override_payroll_approval",
    "publish": "finance.publish_payroll",
    "view_all": "finance.view_all_payroll",
    "audit": "finance.audit_payroll",
}
OPERATIONAL_PERMISSIONS = tuple(
    permission
    for key, permission in PAYROLL_PERMISSIONS.items()
    if key not in {"audit", "override_approval"}
)
INPUT_VIEW_PERMISSIONS = (
    PAYROLL_PERMISSIONS["manage_inputs"],
    PAYROLL_PERMISSIONS["approve_inputs"],
    PAYROLL_PERMISSIONS["view_all"],
)
RUN_VIEW_PERMISSIONS = (
    PAYROLL_PERMISSIONS["calculate"],
    PAYROLL_PERMISSIONS["approve_run"],
    PAYROLL_PERMISSIONS["publish"],
    PAYROLL_PERMISSIONS["view_all"],
)


def _permission_error(permission):
    raise PermissionDenied(
        detail={
            "code": "PERMISSION_DENIED",
            "message": "Недостаточно прав для операции с зарплатой.",
            "details": {"permission": permission},
        }
    )


def _conflict(code: str, message: str, **details):
    raise PayrollConflict(detail={"code": code, "message": message, "details": details})


def _optional_int(request, name):
    raw_value = request.query_params.get(name)
    if raw_value in (None, ""):
        return None
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValidationError({name: "Ожидается целое число."}) from exc
    if value < 1:
        raise ValidationError({name: "Значение должно быть положительным."})
    return value


def _audit_api_mutation(*, actor, action, instance, period=None, metadata=None):
    PayrollAuditEvent.objects.create(
        actor=actor,
        action=action,
        object_type=instance._meta.label_lower,
        object_id=str(instance.pk),
        period=period,
        metadata={"channel": "admin_api", **(metadata or {})},
    )


def _lock_period_accepting_draft_edits(period_id):
    period = get_object_or_404(
        PayrollPeriod.objects.select_for_update().select_related("current_run"),
        pk=period_id,
    )
    if period.status == PayrollPeriodStatus.CLOSED:
        _conflict(
            "PERIOD_INPUTS_LOCKED",
            "Данные закрытого периода заблокированы.",
        )
    if period.current_run is not None and period.current_run.status in {
        PayrollRunStatus.CALCULATED,
        PayrollRunStatus.REVIEW,
        PayrollRunStatus.APPROVED,
    }:
        _conflict(
            "PERIOD_INPUTS_LOCKED",
            "Сначала верните текущий расчёт на исправление.",
            run_id=period.current_run_id,
        )
    return period


class PayrollAdminAPIView(NoStorePayrollResponseMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]
    allowed_permissions = OPERATIONAL_PERMISSIONS

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not any(
            has_payroll_permission(request.user, code)
            for code in self.allowed_permissions
        ):
            _permission_error(self.allowed_permissions[0])

    def require_permission(self, request, code):
        if not has_payroll_permission(request.user, code):
            _permission_error(code)

    def include_amounts(self, request):
        return has_payroll_permission(
            request.user,
            PAYROLL_PERMISSIONS["view_all"],
        )

    def run_payload(self, request, run):
        return PayrollRunSerializer(
            run,
            context={"include_amounts": self.include_amounts(request)},
        ).data

    def handle_exception(self, exc):
        if isinstance(exc, PayrollPermissionDenied):
            exc = PermissionDenied(
                detail={
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            )
        elif isinstance(exc, PayrollOperationError):
            exc = PayrollConflict(
                detail={
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            )
        return super().handle_exception(exc)


class PayrollAdminWorkspaceView(PayrollAdminAPIView):
    """One bounded bootstrap response for the native payroll screen."""

    def get(self, request):
        permissions_payload = {
            key: has_payroll_permission(request.user, permission)
            for key, permission in PAYROLL_PERMISSIONS.items()
        }
        permissions_payload["full_access"] = has_simple_admin_access(request.user)
        periods = list(
            PayrollPeriod.objects.select_related("current_run").order_by(
                "-date_from", "-id"
            )
        )
        selected_period_id = _optional_int(request, "period_id")
        if selected_period_id is None:
            selected_period = periods[0] if periods else None
        else:
            selected_period = next(
                (period for period in periods if period.pk == selected_period_id),
                None,
            )
            if selected_period is None:
                raise Http404

        employees = (
            Employee.objects.filter(is_active=True)
            .select_related("position")
            .prefetch_related("departments_links__department")
            .order_by("last_name", "first_name", "id")
        )
        components = PayrollComponent.objects.order_by("display_order", "code")

        current_run = None
        runs = []
        readiness = {
            "rates": {
                "ready": False,
                "total": 0,
                "approved": 0,
                "draft": 0,
                "missing_employee_ids": [],
            },
            "work_records": {
                "ready": False,
                "total": 0,
                "approved": 0,
                "draft": 0,
            },
            "input_lines": {"approved": 0, "draft": 0},
            "calculation": {
                "ready": False,
                "blockers": [
                    {
                        "code": "PERIOD_NOT_SELECTED",
                        "message": "Создайте или выберите расчётный период.",
                    }
                ],
            },
        }
        pending_approvals = {"rates": 0, "work_records": 0, "input_lines": 0}
        summary = None
        if selected_period is not None:
            runs = list(
                PayrollRun.objects.filter(period=selected_period)
                .select_related("period", "requested_by", "approved_by", "published_by")
                .order_by("-revision")
            )
            current_run = selected_period.current_run
            approved_work = PayrollWorkRecord.objects.filter(
                period=selected_period,
                status=ApprovalStatus.APPROVED,
            )
            draft_work = PayrollWorkRecord.objects.filter(
                period=selected_period,
                status=ApprovalStatus.DRAFT,
            )
            approved_employee_ids = list(
                approved_work.values_list("employee_id", flat=True)
            )
            draft_work_employee_ids = list(
                draft_work.values_list("employee_id", flat=True)
            )
            roster_employee_ids = sorted(
                set(approved_employee_ids) | set(draft_work_employee_ids)
            )
            employees_with_rate = set(
                EmployeePayRate.objects.filter(
                    employee_id__in=roster_employee_ids,
                    rate_code=base_rate_code(),
                    status=ApprovalStatus.APPROVED,
                    effective_from__lte=selected_period.date_from,
                ).values_list("employee_id", flat=True)
            )
            missing_rate_employee_ids = [
                employee_id
                for employee_id in roster_employee_ids
                if employee_id not in employees_with_rate
            ]
            approved_input_count = PayrollInputLine.objects.filter(
                period=selected_period,
                status=ApprovalStatus.APPROVED,
            ).count()
            draft_input_count = PayrollInputLine.objects.filter(
                period=selected_period,
                status=ApprovalStatus.DRAFT,
            ).count()
            pending_rate_count = EmployeePayRate.objects.filter(
                employee_id__in=roster_employee_ids,
                rate_code=base_rate_code(),
                status=ApprovalStatus.DRAFT,
                effective_from__lte=selected_period.date_to,
            ).count()
            blockers = []
            active_rules = build_rules()
            if not rules_cover_period(
                active_rules,
                period_from=selected_period.date_from,
                period_to=selected_period.date_to,
            ):
                blockers.append(
                    {
                        "code": "RULESET_NOT_EFFECTIVE",
                        "message": ruleset_not_effective_message(active_rules),
                        "details": ruleset_period_details(
                            active_rules,
                            period_from=selected_period.date_from,
                            period_to=selected_period.date_to,
                        ),
                    }
                )
            if not approved_employee_ids:
                blockers.append(
                    {
                        "code": "NO_APPROVED_WORK_RECORDS",
                        "message": "Нет утверждённого состава сотрудников за период.",
                    }
                )
            blockers.extend(
                {
                    "code": "MISSING_APPROVED_RATE",
                    "message": "Нет утверждённой ставки на начало периода.",
                    "employee_id": employee_id,
                }
                for employee_id in missing_rate_employee_ids[:20]
            )
            if draft_work.exists():
                blockers.append(
                    {
                        "code": "DRAFT_WORK_RECORDS",
                        "message": "Остались неутверждённые показатели выработки.",
                    }
                )
            if draft_input_count:
                blockers.append(
                    {
                        "code": "DRAFT_INPUT_LINES",
                        "message": "Остались неутверждённые начисления или удержания.",
                    }
                )
            if pending_rate_count:
                blockers.append(
                    {
                        "code": "DRAFT_PAY_RATES",
                        "message": "Остались неутверждённые ставки сотрудников.",
                    }
                )
            if selected_period.status == PayrollPeriodStatus.CLOSED:
                blockers.append(
                    {
                        "code": "PERIOD_CLOSED",
                        "message": "Закрытый период нельзя рассчитать.",
                    }
                )
            readiness = {
                "rates": {
                    "ready": bool(roster_employee_ids)
                    and not missing_rate_employee_ids
                    and pending_rate_count == 0,
                    "total": len(roster_employee_ids),
                    "approved": len(roster_employee_ids)
                    - len(missing_rate_employee_ids),
                    "draft": pending_rate_count,
                    "missing_employee_ids": missing_rate_employee_ids,
                },
                "work_records": {
                    "ready": bool(approved_employee_ids)
                    and not draft_work_employee_ids,
                    "total": len(roster_employee_ids),
                    "approved": len(approved_employee_ids),
                    "draft": len(draft_work_employee_ids),
                },
                "input_lines": {
                    "approved": approved_input_count,
                    "draft": draft_input_count,
                },
                "calculation": {
                    "ready": not blockers,
                    "blockers": blockers,
                },
            }
            pending_approvals = {
                "rates": pending_rate_count,
                "work_records": len(draft_work_employee_ids),
                "input_lines": draft_input_count,
            }
            if current_run is not None and self.include_amounts(request):
                summary = {
                    "employee_count": current_run.employee_count,
                    "gross_total": str(current_run.gross_total),
                    "deduction_total": str(current_run.deduction_total),
                    "payable_total": str(current_run.payable_total),
                }

        run_context = {"include_amounts": self.include_amounts(request)}
        return Response(
            {
                "permissions": permissions_payload,
                "employees": PayrollEmployeeMiniSerializer(employees, many=True).data,
                "components": PayrollComponentSerializer(components, many=True).data,
                "periods": PayrollPeriodSerializer(periods, many=True).data,
                "selected_period": (
                    PayrollPeriodSerializer(selected_period).data
                    if selected_period is not None
                    else None
                ),
                "readiness": readiness,
                "current_run": (
                    PayrollRunSerializer(current_run, context=run_context).data
                    if current_run is not None
                    else None
                ),
                "runs": PayrollRunSerializer(
                    runs,
                    many=True,
                    context=run_context,
                ).data,
                "summary": summary,
                "pending_approvals": pending_approvals,
            }
        )


class PayrollAdminEmployeeListView(PayrollAdminAPIView):
    def get(self, request):
        employees = (
            Employee.objects.filter(is_active=True)
            .select_related("position")
            .prefetch_related("departments_links__department")
            .order_by("last_name", "first_name", "id")
        )
        return Response(PayrollEmployeeMiniSerializer(employees, many=True).data)


class PayrollAdminComponentListView(PayrollAdminAPIView):
    allowed_permissions = INPUT_VIEW_PERMISSIONS

    def get(self, request):
        components = PayrollComponent.objects.order_by("display_order", "code")
        return Response(PayrollComponentSerializer(components, many=True).data)


class PayrollAdminPeriodListCreateView(PayrollAdminAPIView):
    def get(self, request):
        periods = PayrollPeriod.objects.select_related("current_run").order_by(
            "-date_from", "-id"
        )
        return Response(PayrollPeriodSerializer(periods, many=True).data)

    @transaction.atomic
    def post(self, request):
        self.require_permission(request, PAYROLL_PERMISSIONS["manage_inputs"])
        serializer = PayrollPeriodWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        period_values = dict(serializer.validated_data)
        period_values.pop("expected_lock_version", None)
        period = PayrollPeriod(
            **period_values,
            created_by=request.user,
        )
        try:
            period.full_clean()
            period.save(force_insert=True)
        except DjangoValidationError as exc:
            raise ValidationError(_validation_detail(exc)) from exc
        except IntegrityError:
            _conflict(
                "PERIOD_CONFLICT",
                "Параллельная операция уже создала пересекающийся период.",
            )
        _audit_api_mutation(
            actor=request.user,
            action="payroll.period_created",
            instance=period,
            period=period,
        )
        return Response(
            PayrollPeriodSerializer(period).data,
            status=status.HTTP_201_CREATED,
        )


class PayrollAdminPeriodDetailView(PayrollAdminAPIView):
    def get(self, request, pk):
        period = get_object_or_404(PayrollPeriod, pk=pk)
        return Response(PayrollPeriodSerializer(period).data)

    @transaction.atomic
    def patch(self, request, pk):
        self.require_permission(request, PAYROLL_PERMISSIONS["manage_inputs"])
        period = get_object_or_404(
            PayrollPeriod.objects.select_for_update(),
            pk=pk,
        )
        serializer = PayrollPeriodWriteSerializer(
            period,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        expected_lock_version = serializer.validated_data.pop("expected_lock_version")
        if period.lock_version != expected_lock_version:
            _conflict(
                "STALE_PERIOD",
                "Период уже изменён; обновите данные.",
                expected_lock_version=expected_lock_version,
                actual_lock_version=period.lock_version,
            )
        if period.runs.exists():
            _conflict(
                "IMMUTABLE_PERIOD",
                "Реквизиты периода нельзя менять после первого расчёта.",
            )
        changed_fields = list(serializer.validated_data)
        if not changed_fields:
            raise ValidationError(
                {"non_field_errors": "Не передано ни одного изменения."}
            )
        for field_name, value in serializer.validated_data.items():
            setattr(period, field_name, value)
        period.lock_version += 1
        try:
            period.full_clean()
            period.save(update_fields=[*changed_fields, "lock_version", "updated_at"])
        except DjangoValidationError as exc:
            raise ValidationError(_validation_detail(exc)) from exc
        _audit_api_mutation(
            actor=request.user,
            action="payroll.period_updated",
            instance=period,
            period=period,
            metadata={"lock_version": period.lock_version},
        )
        return Response(PayrollPeriodSerializer(period).data)


class DraftCollectionView(PayrollAdminAPIView):
    allowed_permissions = INPUT_VIEW_PERMISSIONS
    model = None
    read_serializer_class = None
    write_serializer_class = None
    audit_label = "input"
    period_scoped = False

    def get_queryset(self):
        return self.model.objects.all()

    def filter_queryset(self, request, queryset):
        employee_id = _optional_int(request, "employee_id")
        if employee_id is not None:
            queryset = queryset.filter(employee_id=employee_id)
        status_value = request.query_params.get("status")
        if status_value:
            queryset = queryset.filter(status=status_value)
        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(employee__last_name__icontains=search)
                | Q(employee__first_name__icontains=search)
                | Q(employee__patronymic__icontains=search)
            )
        return queryset

    def get(self, request):
        queryset = self.filter_queryset(request, self.get_queryset())
        return Response(self.read_serializer_class(queryset, many=True).data)

    def validate_create(self, validated_data):
        if not self.period_scoped:
            return
        period = _lock_period_accepting_draft_edits(validated_data["period"].pk)
        validated_data["period"] = period

    @transaction.atomic
    def post(self, request):
        self.require_permission(request, PAYROLL_PERMISSIONS["manage_inputs"])
        serializer = self.write_serializer_class(
            data=request.data,
            context={"actor": request.user},
        )
        serializer.is_valid(raise_exception=True)
        self.validate_create(serializer.validated_data)
        try:
            instance = serializer.save()
        except IntegrityError:
            _conflict(
                "DRAFT_CONFLICT",
                "Параллельная операция уже создала такие входные данные.",
            )
        period = getattr(instance, "period", None)
        _audit_api_mutation(
            actor=request.user,
            action=f"payroll.{self.audit_label}_draft_created",
            instance=instance,
            period=period,
            metadata={"lock_version": instance.lock_version},
        )
        instance = self.get_queryset().get(pk=instance.pk)
        return Response(
            self.read_serializer_class(instance).data,
            status=status.HTTP_201_CREATED,
        )


class DraftDetailView(PayrollAdminAPIView):
    allowed_permissions = INPUT_VIEW_PERMISSIONS
    model = None
    read_serializer_class = None
    write_serializer_class = None
    audit_label = "input"
    period_scoped = False
    immutable_patch_fields = ()

    def get_queryset(self):
        return self.model.objects.all()

    def get(self, request, pk):
        instance = get_object_or_404(self.get_queryset(), pk=pk)
        return Response(self.read_serializer_class(instance).data)

    @transaction.atomic
    def patch(self, request, pk):
        self.require_permission(request, PAYROLL_PERMISSIONS["manage_inputs"])
        forbidden_fields = set(request.data) & set(self.immutable_patch_fields)
        if forbidden_fields:
            raise ValidationError(
                {
                    field_name: "Поле нельзя менять после создания черновика."
                    for field_name in sorted(forbidden_fields)
                }
            )
        # Do not reveal whether an out-of-scope or immutable payroll record exists.
        scoped_queryset = self.get_queryset().filter(
            pk=pk,
            status=ApprovalStatus.DRAFT,
        )
        if not has_simple_admin_access(request.user):
            scoped_queryset = scoped_queryset.filter(created_by=request.user)
        if self.period_scoped:
            reference_queryset = self.model.objects.only("period_id").filter(
                pk=pk,
                status=ApprovalStatus.DRAFT,
            )
            if not has_simple_admin_access(request.user):
                reference_queryset = reference_queryset.filter(created_by=request.user)
            reference = get_object_or_404(reference_queryset)
            period = _lock_period_accepting_draft_edits(reference.period_id)
        else:
            period = None
        instance = get_object_or_404(scoped_queryset.select_for_update())
        if period is not None:
            instance._state.fields_cache["period"] = period
            self.validate_period_update(instance, period)
        serializer = self.write_serializer_class(
            instance,
            data=request.data,
            partial=True,
            context={"actor": request.user},
        )
        serializer.is_valid(raise_exception=True)
        expected_lock_version = serializer.validated_data.get("expected_lock_version")
        if instance.lock_version != expected_lock_version:
            _conflict(
                "STALE_DRAFT",
                "Черновик уже изменён; обновите данные.",
                expected_lock_version=expected_lock_version,
                actual_lock_version=instance.lock_version,
            )
        try:
            instance = serializer.save()
        except IntegrityError:
            _conflict(
                "DRAFT_CONFLICT",
                "Изменение конфликтует с уже сохранёнными входными данными.",
            )
        _audit_api_mutation(
            actor=request.user,
            action=f"payroll.{self.audit_label}_draft_updated",
            instance=instance,
            period=getattr(instance, "period", None),
            metadata={"lock_version": instance.lock_version},
        )
        instance = self.get_queryset().get(pk=instance.pk)
        return Response(self.read_serializer_class(instance).data)

    def validate_period_update(self, instance, period):
        return None


class EmployeePayRateListCreateView(DraftCollectionView):
    model = EmployeePayRate
    read_serializer_class = EmployeePayRateSerializer
    write_serializer_class = EmployeePayRateWriteSerializer
    audit_label = "rate"

    def get_queryset(self):
        return EmployeePayRate.objects.select_related(
            "employee",
            "employee__position",
            "created_by",
            "approved_by",
        ).prefetch_related("employee__departments_links__department")

    def filter_queryset(self, request, queryset):
        queryset = super().filter_queryset(request, queryset)
        period_id = _optional_int(request, "period_id")
        if period_id is None:
            return queryset
        period = get_object_or_404(PayrollPeriod, pk=period_id)
        latest_effective_date = (
            EmployeePayRate.objects.filter(
                employee_id=OuterRef("employee_id"),
                rate_code=OuterRef("rate_code"),
                effective_from__lte=period.date_from,
            )
            .order_by("-effective_from")
            .values("effective_from")[:1]
        )
        return queryset.annotate(
            _latest_effective_date=Subquery(latest_effective_date)
        ).filter(
            Q(effective_from=F("_latest_effective_date"))
            | Q(
                effective_from__gt=period.date_from,
                effective_from__lte=period.date_to,
            )
        )


class EmployeePayRateDetailView(DraftDetailView):
    model = EmployeePayRate
    read_serializer_class = EmployeePayRateSerializer
    write_serializer_class = EmployeePayRateWriteSerializer
    audit_label = "rate"
    immutable_patch_fields = ("employee_id", "rate_code", "currency")

    def get_queryset(self):
        return EmployeePayRate.objects.select_related(
            "employee",
            "employee__position",
            "created_by",
            "approved_by",
        ).prefetch_related("employee__departments_links__department")


class PayrollWorkRecordListCreateView(DraftCollectionView):
    model = PayrollWorkRecord
    read_serializer_class = PayrollWorkRecordSerializer
    write_serializer_class = PayrollWorkRecordWriteSerializer
    audit_label = "work_record"
    period_scoped = True

    def validate_create(self, validated_data):
        super().validate_create(validated_data)
        if validated_data["period"].status == PayrollPeriodStatus.PUBLISHED:
            _conflict(
                "PUBLISHED_WORK_REPLACEMENT_REQUIRED",
                "После публикации показатели меняются только новой ревизией.",
            )

    def get_queryset(self):
        return PayrollWorkRecord.objects.select_related(
            "period",
            "employee",
            "employee__position",
            "created_by",
            "approved_by",
        ).prefetch_related("employee__departments_links__department")

    def filter_queryset(self, request, queryset):
        queryset = super().filter_queryset(request, queryset)
        period_id = _optional_int(request, "period_id")
        return queryset.filter(period_id=period_id) if period_id else queryset


class PayrollWorkRecordDetailView(DraftDetailView):
    model = PayrollWorkRecord
    read_serializer_class = PayrollWorkRecordSerializer
    write_serializer_class = PayrollWorkRecordWriteSerializer
    audit_label = "work_record"
    period_scoped = True
    immutable_patch_fields = ("period_id", "employee_id")

    def validate_period_update(self, instance, period):
        if period.status == PayrollPeriodStatus.PUBLISHED and not instance.replaces_id:
            _conflict(
                "PUBLISHED_WORK_REPLACEMENT_REQUIRED",
                "После публикации показатели меняются только новой ревизией.",
            )

    def get_queryset(self):
        return PayrollWorkRecord.objects.select_related(
            "period",
            "employee",
            "employee__position",
            "created_by",
            "approved_by",
        ).prefetch_related("employee__departments_links__department")


class PayrollInputLineListCreateView(DraftCollectionView):
    model = PayrollInputLine
    read_serializer_class = PayrollInputLineSerializer
    write_serializer_class = PayrollInputLineWriteSerializer
    audit_label = "input_line"
    period_scoped = True

    def get_queryset(self):
        return PayrollInputLine.objects.select_related(
            "period",
            "employee",
            "employee__position",
            "component",
            "relates_to_period",
            "created_by",
            "approved_by",
        ).prefetch_related("employee__departments_links__department")

    def filter_queryset(self, request, queryset):
        queryset = super().filter_queryset(request, queryset)
        period_id = _optional_int(request, "period_id")
        component_id = _optional_int(request, "component_id")
        if period_id:
            queryset = queryset.filter(period_id=period_id)
        if component_id:
            queryset = queryset.filter(component_id=component_id)
        return queryset


class PayrollInputLineDetailView(DraftDetailView):
    model = PayrollInputLine
    read_serializer_class = PayrollInputLineSerializer
    write_serializer_class = PayrollInputLineWriteSerializer
    audit_label = "input_line"
    period_scoped = True
    immutable_patch_fields = ("period_id", "employee_id", "component_id")

    def get_queryset(self):
        return PayrollInputLine.objects.select_related(
            "period",
            "employee",
            "employee__position",
            "component",
            "relates_to_period",
            "created_by",
            "approved_by",
        ).prefetch_related("employee__departments_links__department")


class DraftApprovalView(PayrollAdminAPIView):
    allowed_permissions = (PAYROLL_PERMISSIONS["approve_inputs"],)
    service = None
    queryset = None
    read_serializer_class = None

    def post(self, request, pk):
        serializer = ApprovalCommandSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not self.queryset.filter(pk=pk).exists():
            raise Http404
        instance = self.service(
            pk,
            actor=request.user,
            expected_lock_version=serializer.validated_data["expected_lock_version"],
        )
        instance = self.queryset.get(pk=instance.pk)
        return Response(self.read_serializer_class(instance).data)


class EmployeePayRateApproveView(DraftApprovalView):
    service = staticmethod(approve_pay_rate)
    queryset = EmployeePayRate.objects.select_related(
        "employee", "employee__position", "created_by", "approved_by"
    ).prefetch_related("employee__departments_links__department")
    read_serializer_class = EmployeePayRateSerializer


class PayrollWorkRecordApproveView(DraftApprovalView):
    service = staticmethod(approve_work_record)
    queryset = PayrollWorkRecord.objects.select_related(
        "period", "employee", "employee__position", "created_by", "approved_by"
    ).prefetch_related("employee__departments_links__department")
    read_serializer_class = PayrollWorkRecordSerializer


class PayrollInputLineApproveView(DraftApprovalView):
    service = staticmethod(approve_input_line)
    queryset = PayrollInputLine.objects.select_related(
        "period",
        "employee",
        "employee__position",
        "component",
        "created_by",
        "approved_by",
    ).prefetch_related("employee__departments_links__department")
    read_serializer_class = PayrollInputLineSerializer


class EmployeePayRateReviseView(PayrollAdminAPIView):
    allowed_permissions = INPUT_VIEW_PERMISSIONS

    @transaction.atomic
    def post(self, request, pk):
        self.require_permission(request, PAYROLL_PERMISSIONS["manage_inputs"])
        source = get_object_or_404(
            EmployeePayRate.objects.select_for_update().select_related("employee"),
            pk=pk,
            status=ApprovalStatus.APPROVED,
        )
        if EmployeePayRate.objects.filter(replaces=source).exists():
            _conflict(
                "REVISION_ALREADY_EXISTS",
                "Для этой ставки уже создана следующая ревизия.",
            )
        command = EmployeePayRateRevisionSerializer(data=request.data)
        command.is_valid(raise_exception=True)
        values = {
            "amount": source.amount,
            "point_rate": source.point_rate,
            "currency": source.currency,
            **command.validated_data,
        }
        revision = EmployeePayRate(
            employee=source.employee,
            rate_code=source.rate_code,
            effective_from=source.effective_from,
            revision=source.revision + 1,
            replaces=source,
            status=ApprovalStatus.DRAFT,
            source="manual",
            created_by=request.user,
            **values,
        )
        try:
            revision.full_clean()
            revision.save(force_insert=True)
        except DjangoValidationError as exc:
            raise ValidationError(_validation_detail(exc)) from exc
        except IntegrityError:
            _conflict(
                "REVISION_CONFLICT",
                "Параллельная операция уже создала ревизию ставки.",
            )
        _audit_api_mutation(
            actor=request.user,
            action="payroll.rate_revision_draft_created",
            instance=revision,
            metadata={"replaces_id": source.pk, "revision": revision.revision},
        )
        revision = (
            EmployeePayRate.objects.select_related(
                "employee", "employee__position", "created_by", "approved_by"
            )
            .prefetch_related("employee__departments_links__department")
            .get(pk=revision.pk)
        )
        return Response(
            EmployeePayRateSerializer(revision).data,
            status=status.HTTP_201_CREATED,
        )


class PayrollWorkRecordReviseView(PayrollAdminAPIView):
    allowed_permissions = INPUT_VIEW_PERMISSIONS

    @transaction.atomic
    def post(self, request, pk):
        self.require_permission(request, PAYROLL_PERMISSIONS["manage_inputs"])
        reference = get_object_or_404(
            PayrollWorkRecord.objects.only("period_id"),
            pk=pk,
            status=ApprovalStatus.APPROVED,
        )
        period = _lock_period_accepting_draft_edits(reference.period_id)
        source = get_object_or_404(
            PayrollWorkRecord.objects.select_for_update().select_related(
                "period", "employee"
            ),
            pk=pk,
            status=ApprovalStatus.APPROVED,
        )
        source._state.fields_cache["period"] = period
        if PayrollWorkRecord.objects.filter(replaces=source).exists():
            _conflict(
                "REVISION_ALREADY_EXISTS",
                "Для показателей уже создана следующая ревизия.",
            )
        command = PayrollWorkRecordRevisionSerializer(data=request.data)
        command.is_valid(raise_exception=True)
        values = {
            "target_points": source.target_points,
            "actual_points": source.actual_points,
            "expected_point_amount": source.expected_point_amount,
            "expected_gross": source.expected_gross,
            "expected_recalculated_gross": source.expected_recalculated_gross,
            "expected_payable": source.expected_payable,
            **command.validated_data,
        }
        revision = PayrollWorkRecord(
            period=source.period,
            employee=source.employee,
            revision=source.revision + 1,
            replaces=source,
            status=ApprovalStatus.DRAFT,
            source="manual",
            created_by=request.user,
            **values,
        )
        try:
            revision.full_clean()
            revision.save(force_insert=True)
        except DjangoValidationError as exc:
            raise ValidationError(_validation_detail(exc)) from exc
        except IntegrityError:
            _conflict(
                "REVISION_CONFLICT",
                "Параллельная операция уже создала ревизию показателей.",
            )
        _audit_api_mutation(
            actor=request.user,
            action="payroll.work_record_revision_draft_created",
            instance=revision,
            period=revision.period,
            metadata={"replaces_id": source.pk, "revision": revision.revision},
        )
        revision = (
            PayrollWorkRecord.objects.select_related(
                "period",
                "employee",
                "employee__position",
                "created_by",
                "approved_by",
            )
            .prefetch_related("employee__departments_links__department")
            .get(pk=revision.pk)
        )
        return Response(
            PayrollWorkRecordSerializer(revision).data,
            status=status.HTTP_201_CREATED,
        )


class PayrollAttendanceWorkRecordsView(PayrollAdminAPIView):
    """Preview and apply attendance-derived payroll work drafts."""

    allowed_permissions = (PAYROLL_PERMISSIONS["manage_inputs"],)

    def get(self, request, pk):
        period = get_object_or_404(PayrollPeriod, pk=pk)
        preview = build_attendance_work_preview(period, actor=request.user)
        preview.pop("_internal_items", None)
        return Response(preview)

    def post(self, request, pk):
        get_object_or_404(PayrollPeriod.objects.only("id"), pk=pk)
        command = AttendanceWorkImportCommandSerializer(data=request.data)
        command.is_valid(raise_exception=True)
        result = apply_attendance_work_preview(
            pk,
            actor=request.user,
            **command.validated_data,
        )
        record_ids = [record.pk for record in result["records"]]
        records = list(
            PayrollWorkRecord.objects.filter(pk__in=record_ids)
            .select_related(
                "period",
                "employee",
                "employee__position",
                "created_by",
                "approved_by",
            )
            .prefetch_related("employee__departments_links__department")
            .order_by("employee_id", "revision", "id")
        )
        return Response(
            {
                "mode": result["mode"],
                "summary": result["summary"],
                "records": PayrollWorkRecordSerializer(records, many=True).data,
            }
        )


class PayrollPeriodCalculateView(PayrollAdminAPIView):
    allowed_permissions = (PAYROLL_PERMISSIONS["calculate"],)

    @transaction.atomic
    def post(self, request, pk):
        command = CalculatePayrollCommandSerializer(data=request.data)
        command.is_valid(raise_exception=True)
        period = get_object_or_404(
            PayrollPeriod.objects.select_for_update(),
            pk=pk,
        )
        expected = command.validated_data["expected_lock_version"]
        if period.lock_version != expected:
            _conflict(
                "STALE_PERIOD",
                "Период уже изменён; обновите данные перед расчётом.",
                expected_lock_version=expected,
                actual_lock_version=period.lock_version,
            )
        run = calculate_period(
            period.pk,
            actor=request.user,
            idempotency_key=command.validated_data.get("idempotency_key"),
            recalculation_reason=command.validated_data["recalculation_reason"],
        )
        return Response(self.run_payload(request, run), status=status.HTTP_201_CREATED)


class PayrollRunDetailView(PayrollAdminAPIView):
    allowed_permissions = RUN_VIEW_PERMISSIONS

    def get(self, request, pk):
        run = get_object_or_404(
            PayrollRun.objects.select_related(
                "period", "requested_by", "approved_by", "published_by"
            ),
            pk=pk,
        )
        return Response(self.run_payload(request, run))


class PayrollRunSubmitReviewView(PayrollAdminAPIView):
    allowed_permissions = (PAYROLL_PERMISSIONS["calculate"],)

    def post(self, request, pk):
        if not PayrollRun.objects.filter(pk=pk).exists():
            raise Http404
        return Response(
            self.run_payload(request, submit_run_for_review(pk, actor=request.user))
        )


class PayrollRunReturnView(PayrollAdminAPIView):
    allowed_permissions = (
        PAYROLL_PERMISSIONS["calculate"],
        PAYROLL_PERMISSIONS["approve_run"],
    )

    def post(self, request, pk):
        command = ReturnPayrollCommandSerializer(data=request.data)
        command.is_valid(raise_exception=True)
        if not PayrollRun.objects.filter(pk=pk).exists():
            raise Http404
        run = return_run_for_correction(
            pk,
            actor=request.user,
            reason=command.validated_data["reason"],
        )
        return Response(self.run_payload(request, run))


class PayrollRunApproveView(PayrollAdminAPIView):
    allowed_permissions = (PAYROLL_PERMISSIONS["approve_run"],)

    def post(self, request, pk):
        if not PayrollRun.objects.filter(pk=pk).exists():
            raise Http404
        return Response(self.run_payload(request, approve_run(pk, actor=request.user)))


class PayrollRunPublishView(PayrollAdminAPIView):
    allowed_permissions = (PAYROLL_PERMISSIONS["publish"],)

    def post(self, request, pk):
        if not PayrollRun.objects.filter(pk=pk).exists():
            raise Http404
        return Response(self.run_payload(request, publish_run(pk, actor=request.user)))


class PayrollPeriodCloseView(PayrollAdminAPIView):
    allowed_permissions = (PAYROLL_PERMISSIONS["publish"],)

    def post(self, request, pk):
        if not PayrollPeriod.objects.filter(pk=pk).exists():
            raise Http404
        period = close_period(pk, actor=request.user)
        return Response(PayrollPeriodSerializer(period).data)

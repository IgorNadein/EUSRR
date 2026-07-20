from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.cache import patch_vary_headers
from rest_framework import generics, permissions, status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import APIView

from finance.enums import ApprovalStatus, PayrollPeriodStatus, PayrollRunStatus
from finance.models import (
    PayrollAuditEvent,
    PayrollDailyWorkEntry,
    PayrollPeriod,
    PayrollStatement,
    PayrollWorkSettings,
    PayrollWorkRecord,
)
from finance.payroll.exceptions import PayrollOperationError
from finance.payroll.services import (
    acknowledge_statement,
    save_own_daily_work_entry,
)
from finance.payroll.work_norm import (
    calculate_period_target_points,
    resolve_employee_schedule,
)

from .serializers import (
    OwnPayrollDailyWorkEntrySerializer,
    OwnPayrollDailyWorkEntryWriteSerializer,
    OwnPayrollStatementSerializer,
    OwnPayrollStatementSummarySerializer,
    OwnPayrollWorkRecordSerializer,
    PayrollStatementAcknowledgementSerializer,
)


class PayrollConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "payroll_conflict"


class NoStorePayrollResponseMixin:
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store, max-age=0"
        response["Pragma"] = "no-cache"
        patch_vary_headers(response, ("Authorization", "Cookie"))
        return response


def own_published_statements(user):
    return (
        PayrollStatement.objects.filter(
            employee=user,
            run__status=PayrollRunStatus.PUBLISHED,
        )
        .select_related("run", "run__period")
        .prefetch_related("lines", "acknowledgement")
        .order_by("-run__period__date_from", "-run__revision")
    )


def nearest_payroll_period(periods, reference_date):
    if not periods:
        return None

    def distance(period):
        if period.date_from <= reference_date <= period.date_to:
            return 0
        if reference_date < period.date_from:
            return (period.date_from - reference_date).days
        return (reference_date - period.date_to).days

    return min(
        periods,
        key=lambda period: (
            distance(period),
            0 if period.date_from <= reference_date <= period.date_to else 1,
            -period.date_from.toordinal(),
            -period.pk,
        ),
    )


class OwnPayrollStatementListView(
    NoStorePayrollResponseMixin,
    generics.ListAPIView,
):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OwnPayrollStatementSummarySerializer

    def get_queryset(self):
        return own_published_statements(self.request.user)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        statements = list(page) if page is not None else list(queryset)
        PayrollAuditEvent.objects.bulk_create(
            [
                PayrollAuditEvent(
                    actor=request.user,
                    action="payroll.statement_summary_viewed",
                    object_type=statement._meta.label_lower,
                    object_id=str(statement.pk),
                    period=statement.run.period,
                    after_hash=statement.result_hash,
                    metadata={"channel": "employee_api"},
                )
                for statement in statements
            ]
        )
        serializer = self.get_serializer(statements, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


class OwnPayrollStatementDetailView(
    NoStorePayrollResponseMixin,
    generics.RetrieveAPIView,
):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OwnPayrollStatementSerializer
    lookup_field = "public_id"
    lookup_url_kwarg = "public_id"

    def get_queryset(self):
        return own_published_statements(self.request.user)

    def retrieve(self, request, *args, **kwargs):
        statement = self.get_object()
        PayrollAuditEvent.objects.create(
            actor=request.user,
            action="payroll.statement_viewed",
            object_type=statement._meta.label_lower,
            object_id=str(statement.pk),
            period=statement.run.period,
            after_hash=statement.result_hash,
            metadata={"channel": "employee_api"},
        )
        return Response(self.get_serializer(statement).data)


class OwnPayrollStatementAcknowledgeView(
    NoStorePayrollResponseMixin,
    APIView,
):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, public_id):
        statement = (
            own_published_statements(request.user).filter(public_id=public_id).first()
        )
        if statement is None:
            raise Http404
        try:
            acknowledgement = acknowledge_statement(
                statement.pk,
                actor=request.user,
            )
        except PayrollOperationError as exc:
            if exc.code == "STATEMENT_NOT_FOUND":
                raise Http404 from exc
            raise PayrollConflict(
                detail={"code": exc.code, "message": exc.message}
            ) from exc
        return Response(
            PayrollStatementAcknowledgementSerializer(acknowledgement).data,
            status=status.HTTP_200_OK,
        )


class OwnPayrollWorkRecordView(
    NoStorePayrollResponseMixin,
    APIView,
):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        periods = list(
            PayrollPeriod.objects.select_related("current_run").order_by(
                "-date_from",
                "-id",
            )
        )
        records = (
            PayrollWorkRecord.objects.filter(employee=request.user)
            .exclude(status=ApprovalStatus.VOIDED)
            .order_by("period_id", "-revision", "-id")
        )
        current_by_period = {}
        for record in records:
            current_by_period.setdefault(record.period_id, record)
        requested_period_id = request.query_params.get("period_id")
        if requested_period_id:
            selected_period = get_object_or_404(
                PayrollPeriod,
                pk=requested_period_id,
            )
        else:
            selected_period = nearest_payroll_period(
                periods,
                timezone.localdate(),
            )
        entries = (
            PayrollDailyWorkEntry.objects.filter(
                employee=request.user,
                period=selected_period,
            ).order_by("-work_date", "-id")
            if selected_period is not None
            else PayrollDailyWorkEntry.objects.none()
        )
        daily_target_points = PayrollWorkSettings.get_daily_target_points()
        schedule, schedule_source = resolve_employee_schedule(request.user)
        period_payloads = []
        for period in periods:
            record = current_by_period.get(period.pk)
            automatic_target, workdays_count, _ = calculate_period_target_points(
                period,
                employee=request.user,
                daily_target_points=daily_target_points,
                schedule=schedule,
            )
            uses_saved_target = (
                record is not None and record.target_points_overridden
            )
            period_payloads.append(
                {
                    "id": period.pk,
                    "code": period.code,
                    "name": period.name,
                    "date_from": period.date_from,
                    "date_to": period.date_to,
                    "pay_date": period.pay_date,
                    "status": period.status,
                    "status_label": period.get_status_display(),
                    "editable": (
                        period.status == PayrollPeriodStatus.OPEN
                        and period.date_from <= timezone.localdate()
                    ),
                    "record": (
                        OwnPayrollWorkRecordSerializer(record).data
                        if record is not None
                        else None
                    ),
                    "summary": {
                        "target_points": str(
                            record.target_points
                            if uses_saved_target
                            else automatic_target
                        ),
                        "actual_points": str(
                            record.actual_points
                            if record is not None
                            else "0.0000"
                        ),
                        "target_source": (
                            "saved_record" if uses_saved_target else schedule_source
                        ),
                        "workdays_count": workdays_count,
                    },
                }
            )

        return Response(
            {
                "daily_target_points": str(daily_target_points),
                "selected_period_id": (
                    selected_period.pk if selected_period is not None else None
                ),
                "periods": period_payloads,
                "entries": OwnPayrollDailyWorkEntrySerializer(
                    entries,
                    many=True,
                ).data,
            }
        )

    def post(self, request):
        command = OwnPayrollDailyWorkEntryWriteSerializer(data=request.data)
        command.is_valid(raise_exception=True)
        get_object_or_404(
            PayrollPeriod.objects.only("id"),
            pk=command.validated_data["period_id"],
        )
        try:
            entry, record, operation = save_own_daily_work_entry(
                actor=request.user,
                **command.validated_data,
            )
        except PayrollOperationError as exc:
            raise PayrollConflict(
                detail={
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            ) from exc
        response_status = (
            status.HTTP_201_CREATED
            if operation == "created"
            else status.HTTP_200_OK
        )
        return Response(
            {
                "operation": operation,
                "entry": OwnPayrollDailyWorkEntrySerializer(entry).data,
                "record": OwnPayrollWorkRecordSerializer(record).data,
            },
            status=response_status,
        )

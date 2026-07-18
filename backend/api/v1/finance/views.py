from django.http import Http404
from django.utils.cache import patch_vary_headers
from rest_framework import generics, permissions, status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import APIView

from finance.enums import PayrollRunStatus
from finance.models import PayrollAuditEvent, PayrollStatement
from finance.payroll.exceptions import PayrollOperationError
from finance.payroll.services import acknowledge_statement

from .serializers import (
    OwnPayrollStatementSerializer,
    OwnPayrollStatementSummarySerializer,
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

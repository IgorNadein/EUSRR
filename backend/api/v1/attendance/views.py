import logging

from common.logstorm_attendance import analyze_employee_attendance
from common.logstorm_client import LogStormClientError
from employees.models import Employee
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import LogStormAttendanceAnalyzeSerializer

logger = logging.getLogger(__name__)


class LogStormAttendanceAnalyzeAPIView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = LogStormAttendanceAnalyzeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            employee = Employee.objects.get(pk=data["employee_id"])
        except Employee.DoesNotExist:
            return Response(
                {"detail": "Employee not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # TODO: когда schedule UI сможет явно хранить рабочие/выходные дни,
        # формировать schedule/date_overrides здесь из EUSRR-календаря, а не
        # полагаться на ручной payload или fallback LogStorm.
        try:
            result = analyze_employee_attendance(
                employee=employee,
                period_start=data["period_start"],
                period_end=data["period_end"],
                schedule=data.get("schedule"),
                client=None,
            )
        except LogStormClientError as exc:
            logger.warning("LogStorm attendance analysis failed: %s", exc)
            return Response(
                {"detail": str(exc), "error": "logstorm_unavailable"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(result)

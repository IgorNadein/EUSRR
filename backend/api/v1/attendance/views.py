import logging
from calendar import monthrange
from datetime import date
from urllib.parse import quote

from attendance.models import AttendanceRecord, EmployeeWorkSchedule, StandardWorkSchedule
from attendance.services import (
    build_attendance_matrix_export_workbook,
    build_monthly_attendance_matrix,
    get_employee_work_schedule_payload,
    get_standard_work_schedule_payload,
    normalize_attendance_record_manual_issues,
    save_logstorm_attendance_result,
)
from communications import comments_helpers
from communications.models import Message
from common.logstorm_attendance import (
    analyze_employee_attendance,
    build_logstorm_attendance_payload,
)
from common.logstorm_client import LogStormClient, LogStormClientError
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse
from django.db.models import Count, IntegerField, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from employees.models import Employee
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    AttendanceMonthlyMatrixExportQuerySerializer,
    AttendanceMonthlyMatrixQuerySerializer,
    AttendanceRecordCommentSerializer,
    AttendanceRecordSerializer,
    AttendanceRecordUpdateSerializer,
    EmployeeWorkScheduleSerializer,
    LogStormAttendanceAnalyzeSerializer,
    StandardWorkScheduleSerializer,
    default_work_schedule_response,
    default_standard_work_schedule_response,
)

logger = logging.getLogger(__name__)


def _can_access_employee(user, employee_id) -> bool:
    try:
        normalized_employee_id = int(employee_id)
    except (TypeError, ValueError):
        return False

    return bool(
        user
        and user.is_authenticated
        and (
            user.is_staff
            or user.is_superuser
            or normalized_employee_id == int(user.id)
        )
    )


def _check_employee_access(user, employee_id) -> None:
    if not _can_access_employee(user, employee_id):
        raise PermissionDenied(
            "You don't have permission to access this attendance data"
        )


def _records_visible_to(user):
    queryset = AttendanceRecord.objects.all()
    if user.is_staff or user.is_superuser:
        return queryset
    return queryset.filter(employee_id=user.id)


def _check_staff_access(user) -> None:
    if not (user and user.is_authenticated and (user.is_staff or user.is_superuser)):
        raise PermissionDenied("You don't have permission to manage attendance")


def _comments_count_annotation():
    record_ct = ContentType.objects.get_for_model(AttendanceRecord)
    comments_subquery = (
        Message.objects.filter(
            chat__type="comments",
            chat__context_content_type=record_ct,
            chat__context_object_id=OuterRef("pk"),
            is_deleted=False,
        )
        .values("chat")
        .annotate(count=Count("id"))
        .values("count")
    )
    return {
        "comments_count": Coalesce(
            Subquery(comments_subquery, output_field=IntegerField()),
            Value(0),
        )
    }


def _comment_author_name(author) -> str:
    if not author:
        return "Сотрудник"
    first_name = getattr(author, "first_name", "") or ""
    last_name = getattr(author, "last_name", "") or ""
    full_name = f"{last_name} {first_name}".strip()
    return full_name or getattr(author, "email", "") or "Сотрудник"


def _attendance_record_comments_map(record_ids: list[int]) -> dict[int, list[dict[str, str]]]:
    if not record_ids:
        return {}
    record_ct = ContentType.objects.get_for_model(AttendanceRecord)
    messages = (
        Message.objects.filter(
            chat__type="comments",
            chat__context_content_type=record_ct,
            chat__context_object_id__in=record_ids,
            is_deleted=False,
        )
        .select_related("author", "chat")
        .order_by("created_at", "id")
    )
    result: dict[int, list[dict[str, str]]] = {}
    for message in messages:
        record_id = int(message.chat.context_object_id)
        result.setdefault(record_id, []).append(
            {
                "author": _comment_author_name(message.author),
                "text": message.content,
                "created_at": timezone.localtime(message.created_at).strftime(
                    "%d.%m.%Y %H:%M"
                ),
            }
        )
    return result


class LogStormAttendanceAnalyzeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogStormAttendanceAnalyzeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        _check_employee_access(request.user, data["employee_id"])

        try:
            employee = Employee.objects.get(pk=data["employee_id"])
        except Employee.DoesNotExist:
            return Response(
                {"detail": "Employee not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        schedule_payload = data.get("schedule")
        if schedule_payload is None:
            schedule_payload = (
                get_employee_work_schedule_payload(employee)
                or get_standard_work_schedule_payload()
            )

        try:
            result = analyze_employee_attendance(
                employee=employee,
                period_start=data["period_start"],
                period_end=data["period_end"],
                schedule=schedule_payload,
                client=None,
            )
        except LogStormClientError as exc:
            logger.warning("LogStorm attendance analysis failed: %s", exc)
            return Response(
                {"detail": str(exc), "error": "logstorm_unavailable"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        request_payload = build_logstorm_attendance_payload(
            employee=employee,
            period_start=data["period_start"],
            period_end=data["period_end"],
            schedule=schedule_payload,
        )
        save_logstorm_attendance_result(
            employee=employee,
            period_start=data["period_start"],
            period_end=data["period_end"],
            schedule_payload=request_payload.get("schedule"),
            request_payload=request_payload,
            response_payload=result,
            triggered_by=request.user,
        )

        return Response(result)


class EmployeeWorkScheduleAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_employee(self, employee_id):
        _check_employee_access(self.request.user, employee_id)
        return get_object_or_404(Employee, pk=employee_id)

    def get(self, request, employee_id):
        employee = self.get_employee(employee_id)
        try:
            schedule = employee.work_schedule
        except EmployeeWorkSchedule.DoesNotExist:
            schedule = None
        if schedule is None:
            return Response(default_work_schedule_response(employee.id))
        return Response(EmployeeWorkScheduleSerializer(schedule).data)

    def patch(self, request, employee_id):
        if not (request.user.is_staff or request.user.is_superuser):
            raise PermissionDenied("You don't have permission to edit schedules")
        employee = get_object_or_404(Employee, pk=employee_id)
        try:
            schedule = employee.work_schedule
        except EmployeeWorkSchedule.DoesNotExist:
            schedule = None
        serializer = EmployeeWorkScheduleSerializer(
            schedule,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        instance = serializer.save(employee=employee, updated_by=request.user)
        return Response(EmployeeWorkScheduleSerializer(instance).data)


class StandardWorkScheduleAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        _check_staff_access(request.user)
        schedule = StandardWorkSchedule.objects.order_by("id").first()
        if schedule is None:
            return Response(default_standard_work_schedule_response())
        return Response(StandardWorkScheduleSerializer(schedule).data)

    def patch(self, request):
        _check_staff_access(request.user)
        schedule = StandardWorkSchedule.objects.order_by("id").first()
        serializer = StandardWorkScheduleSerializer(
            schedule,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        instance = serializer.save(updated_by=request.user)
        return Response(StandardWorkScheduleSerializer(instance).data)


class AttendanceRecordListAPIView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AttendanceRecordSerializer

    def get_queryset(self):
        queryset = (
            _records_visible_to(self.request.user)
            .select_related("employee", "analysis_run")
            .annotate(**_comments_count_annotation())
            .all()
            .order_by("-date", "-id")
        )

        employee_id = self.request.query_params.get("employee_id")
        if employee_id:
            _check_employee_access(self.request.user, employee_id)
            queryset = queryset.filter(employee_id=employee_id)

        date_from = self.request.query_params.get("date_from")
        if date_from:
            queryset = queryset.filter(date__gte=date_from)

        date_to = self.request.query_params.get("date_to")
        if date_to:
            queryset = queryset.filter(date__lte=date_to)

        return queryset


class AttendanceMonthlyMatrixAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = AttendanceMonthlyMatrixQuerySerializer(
            data=request.query_params,
        )
        serializer.is_valid(raise_exception=True)
        employee_ids = serializer.validated_data["employee_ids"]
        year, month = [
            int(part) for part in serializer.validated_data["month"].split("-")
        ]

        for employee_id in employee_ids:
            _check_employee_access(request.user, employee_id)

        employees = list(Employee.objects.filter(id__in=employee_ids))
        employees_by_id = {employee.id: employee for employee in employees}
        employees = [
            employees_by_id[employee_id]
            for employee_id in employee_ids
            if employee_id in employees_by_id
        ]

        start_date = date(year, month, 1)
        end_date = date(year, month, monthrange(year, month)[1])
        records = list(
            _records_visible_to(request.user)
            .filter(
                employee_id__in=[employee.id for employee in employees],
                date__gte=start_date,
                date__lte=end_date,
            )
            .select_related("employee")
            .annotate(**_comments_count_annotation())
            .order_by("employee_id", "date", "id")
        )

        return Response(
            build_monthly_attendance_matrix(
                employees=employees,
                records=records,
                year=year,
                month=month,
            )
        )


class AttendanceMonthlyMatrixExportAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        _check_staff_access(request.user)
        serializer = AttendanceMonthlyMatrixExportQuerySerializer(
            data=request.query_params,
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        employee_ids = data["employee_ids"]
        period_start = data["period_start"]
        period_end = data["period_end"]

        employees = list(Employee.objects.filter(id__in=employee_ids))
        employees_by_id = {employee.id: employee for employee in employees}
        employees = [
            employees_by_id[employee_id]
            for employee_id in employee_ids
            if employee_id in employees_by_id
        ]

        records = list(
            _records_visible_to(request.user)
            .filter(
                employee_id__in=[employee.id for employee in employees],
                date__gte=period_start,
                date__lte=period_end,
            )
            .select_related("employee")
            .annotate(**_comments_count_annotation())
            .order_by("employee_id", "date", "id")
        )

        content = build_attendance_matrix_export_workbook(
            employees=employees,
            records=records,
            period_start=period_start,
            period_end=period_end,
            record_comments=_attendance_record_comments_map(
                [record.id for record in records]
            ),
        )
        filename = f"attendance-{period_start.isoformat()}_{period_end.isoformat()}.xlsx"
        response = HttpResponse(
            content,
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class AttendanceRecordDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, record_id):
        record = get_object_or_404(
            _records_visible_to(request.user)
            .select_related("employee", "analysis_run")
            .annotate(**_comments_count_annotation()),
            pk=record_id,
        )
        return Response(AttendanceRecordSerializer(record).data)

    def patch(self, request, record_id):
        if not request.user.is_staff:
            raise PermissionDenied(
                "You don't have permission to edit attendance records"
            )

        record = get_object_or_404(
            _records_visible_to(request.user)
            .select_related("employee", "analysis_run")
            .annotate(**_comments_count_annotation()),
            pk=record_id,
        )
        serializer = AttendanceRecordUpdateSerializer(
            record,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        manual_payload = dict(serializer.validated_data)

        try:
            logstorm_override = LogStormClient().update_attendance_override(
                employee_id=str(record.employee_id),
                record_date=record.date,
                payload={**manual_payload, "source": "eusrr"},
            )
        except LogStormClientError as exc:
            logger.warning("LogStorm attendance override failed: %s", exc)
            return Response(
                {"detail": str(exc), "error": "logstorm_unavailable"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        record = serializer.save(
            is_manually_edited=True,
            manual_edit_payload=manual_payload,
            manual_edited_by=request.user,
            manual_edited_at=timezone.now(),
        )
        normalize_attendance_record_manual_issues(record, manual_payload)
        record.raw_data = {
            **record.raw_data,
            "manual_edited": True,
            "manual_edit_payload": manual_payload,
            "logstorm_override": logstorm_override,
        }
        record.save(
            update_fields=[
                "statuses",
                "employee_issues",
                "raw_data",
                "updated_at",
            ]
        )

        record = (
            _records_visible_to(request.user)
            .select_related("employee", "analysis_run")
            .annotate(**_comments_count_annotation())
            .get(pk=record.pk)
        )
        return Response(AttendanceRecordSerializer(record).data)


class AttendanceRecordDayEventsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_record(self, request, record_id):
        return get_object_or_404(
            _records_visible_to(request.user).select_related("employee"),
            pk=record_id,
        )

    def get(self, request, record_id):
        record = self.get_record(request, record_id)
        try:
            events = LogStormClient().get_attendance_day_events(
                employee_id=str(record.employee_id),
                record_date=record.date,
            )
        except LogStormClientError as exc:
            logger.warning("LogStorm attendance day events failed: %s", exc)
            return Response(
                {"detail": str(exc), "error": "logstorm_unavailable"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            [
                self._with_proxy_photo_url(request, record, event)
                for event in events
                if isinstance(event, dict)
            ]
        )

    @staticmethod
    def _with_proxy_photo_url(request, record, event):
        result = dict(event)
        event_key = str(result.get("event_key") or "")
        if result.get("has_photo") and event_key:
            result["photo_url"] = (
                f"/api/v1/attendance/records/{record.id}/day-events/"
                f"{quote(event_key)}/photo/"
            )
        else:
            result["photo_url"] = None
        return result


class AttendanceRecordDayEventPhotoAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_record(self, request, record_id):
        return get_object_or_404(
            _records_visible_to(request.user).select_related("employee"),
            pk=record_id,
        )

    def get(self, request, record_id, event_key):
        record = self.get_record(request, record_id)
        client = LogStormClient()
        try:
            events = client.get_attendance_day_events(
                employee_id=str(record.employee_id),
                record_date=record.date,
            )
            event = next(
                (
                    item
                    for item in events
                    if isinstance(item, dict)
                    and str(item.get("event_key")) == str(event_key)
                ),
                None,
            )
            if not event or not event.get("has_photo"):
                return Response(
                    {"detail": "Event photo not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            photo_response = client.get_attendance_event_photo(event_key)
        except LogStormClientError as exc:
            if exc.status_code == status.HTTP_404_NOT_FOUND:
                return Response(
                    {"detail": "Event photo not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            logger.warning("LogStorm attendance event photo failed: %s", exc)
            return Response(
                {"detail": str(exc), "error": "logstorm_unavailable"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return HttpResponse(
            photo_response.content,
            content_type=photo_response.headers.get("Content-Type", "image/jpeg"),
        )


class AttendanceRecordCommentsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_record(self, request, record_id):
        return get_object_or_404(_records_visible_to(request.user), pk=record_id)

    @staticmethod
    def serialize_message(record, message):
        payload = {
            "id": message.id,
            "record": record.id,
            "author": message.author,
            "text": message.content,
            "created_at": message.created_at,
        }
        return AttendanceRecordCommentSerializer(payload).data

    def get(self, request, record_id):
        record = self.get_record(request, record_id)
        messages = comments_helpers.get_comments(record)
        return Response(
            [self.serialize_message(record, message) for message in messages]
        )

    def post(self, request, record_id):
        record = self.get_record(request, record_id)
        serializer = AttendanceRecordCommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message = comments_helpers.create_comment(
            obj=record,
            author=request.user,
            content=serializer.validated_data["text"].strip(),
        )

        return Response(
            self.serialize_message(record, message),
            status=status.HTTP_201_CREATED,
        )


class AttendanceRecordCommentDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, record_id, comment_id):
        record = get_object_or_404(_records_visible_to(request.user), pk=record_id)
        chat = comments_helpers.get_comments_chat_if_exists(record)
        if chat is None:
            return Response(
                {"detail": "Comment not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            message = Message.objects.get(id=comment_id, chat=chat)
        except Message.DoesNotExist:
            return Response(
                {"detail": "Comment not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if message.author != request.user:
            return Response(
                {"detail": "You don't have permission to delete this comment"},
                status=status.HTTP_403_FORBIDDEN,
            )

        comments_helpers.delete_comment(
            message=message,
            deleted_by=request.user,
            soft_delete=True,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

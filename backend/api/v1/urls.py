from django.urls import include, path
from rest_framework.routers import DefaultRouter

# django-scheduler ViewSets (проверенная библиотека для календаря)
from .schedule.views import (
    ScheduleCalendarViewSet,
    ScheduleEventViewSet,
    ScheduleRuleViewSet,
    ScheduleOccurrenceViewSet,
    ScheduleEventRelationViewSet,
)

# Communications ViewSets (перенесены в communications.api)
from communications.api.viewsets import ChatViewSet, MessageViewSet, PollViewSet
from .documents.views import (
    DocumentViewSet,
    FolderViewSet,
    DocumentTagViewSet,
)
from .employees.views import (
    DepartmentRoleViewSet,
    DepartmentViewSet,
    EmployeeActionViewSet,
    EmployeeViewSet,
    GroupViewSet,
    PositionViewSet,
    SkillViewSet,
)
from .feed.views import PostViewSet
from .requests_app.views import RequestViewSet
from .search.views import search_api_view
from .attendance.views import (
    AttendanceMonthlyMatrixExportAPIView,
    AttendanceMonthlyMatrixAPIView,
    AttendanceRecordDayEventPhotoAPIView,
    AttendanceRecordDayEventsAPIView,
    AttendanceRecordCommentDetailAPIView,
    AttendanceRecordCommentsAPIView,
    AttendanceRecordDetailAPIView,
    AttendanceRecordListAPIView,
    EmployeeWorkScheduleAPIView,
    LogStormAttendanceAnalyzeAPIView,
    StandardWorkScheduleAPIView,
)

app_name = "v1"

router = DefaultRouter()

# django-scheduler endpoints (проверенная библиотека)
router.register(
    r"schedule/calendars",
    ScheduleCalendarViewSet,
    basename="schedule-calendars",
)
router.register(
    r"schedule/events", ScheduleEventViewSet, basename="schedule-events"
)
router.register(
    r"schedule/rules", ScheduleRuleViewSet, basename="schedule-rules"
)
router.register(
    r"schedule/occurrences",
    ScheduleOccurrenceViewSet,
    basename="schedule-occurrences",
)
router.register(
    r"schedule/relations",
    ScheduleEventRelationViewSet,
    basename="schedule-relations",
)

router.register(r"documents", DocumentViewSet, basename="documents")
router.register(r"folders", FolderViewSet, basename="folders")
router.register(r"document-tags", DocumentTagViewSet, basename="document-tags")

router.register(r"requests", RequestViewSet, basename="request")

router.register(r"departments", DepartmentViewSet, basename="departments")
router.register(r"employees", EmployeeViewSet, basename="employees")
router.register(
    r"employee-actions",
    EmployeeActionViewSet,
    basename="employee-actions",
)
router.register(r"positions", PositionViewSet, basename="positions")
router.register(
    r"department-roles",
    DepartmentRoleViewSet,
    basename="department-roles",
)
router.register(r"skills", SkillViewSet, basename="skills")
router.register(r"posts", PostViewSet, basename="posts")
router.register(r"groups", GroupViewSet, basename="groups")

# NEW: Communications ViewSets
router.register(r"communications/chats", ChatViewSet, basename="chats")
router.register(r"communications/messages", MessageViewSet, basename="messages")
router.register(r"communications/polls", PollViewSet, basename="polls")


urlpatterns = [
    path("auth/", include("api.auth.urls")),
    path(
        "attendance/logstorm/analyze/",
        LogStormAttendanceAnalyzeAPIView.as_view(),
        name="logstorm-attendance-analyze",
    ),
    path(
        "attendance/records/",
        AttendanceRecordListAPIView.as_view(),
        name="attendance-records",
    ),
    path(
        "attendance/monthly-matrix/",
        AttendanceMonthlyMatrixAPIView.as_view(),
        name="attendance-monthly-matrix",
    ),
    path(
        "attendance/monthly-matrix/export/",
        AttendanceMonthlyMatrixExportAPIView.as_view(),
        name="attendance-monthly-matrix-export",
    ),
    path(
        "attendance/work-schedules/<int:employee_id>/",
        EmployeeWorkScheduleAPIView.as_view(),
        name="attendance-work-schedule",
    ),
    path(
        "attendance/standard-work-schedule/",
        StandardWorkScheduleAPIView.as_view(),
        name="attendance-standard-work-schedule",
    ),
    path(
        "attendance/records/<int:record_id>/",
        AttendanceRecordDetailAPIView.as_view(),
        name="attendance-record-detail",
    ),
    path(
        "attendance/records/<int:record_id>/day-events/",
        AttendanceRecordDayEventsAPIView.as_view(),
        name="attendance-record-day-events",
    ),
    path(
        "attendance/records/<int:record_id>/day-events/<str:event_key>/photo/",
        AttendanceRecordDayEventPhotoAPIView.as_view(),
        name="attendance-record-day-event-photo",
    ),
    path(
        "attendance/records/<int:record_id>/comments/",
        AttendanceRecordCommentsAPIView.as_view(),
        name="attendance-record-comments",
    ),
    path(
        "attendance/records/<int:record_id>/comments/<int:comment_id>/",
        AttendanceRecordCommentDetailAPIView.as_view(),
        name="attendance-record-comment-detail",
    ),
    path("directory/", include("api.v1.directory.urls")),
    # Notifications API (из самого модуля notifications)
    path("notifications/", include("notifications.api.urls")),
    # Procurement API
    path("procurement/", include("api.v1.procurement.urls")),
    # Search API
    path("search/", search_api_view, name="search"),
    # Router URLs (включая все ViewSets)
    path("", include(router.urls)),
]

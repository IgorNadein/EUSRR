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
    RegisterAPIView,
    ResendEmailAPIView,
    SkillViewSet,
    VerifyEmailAPIView,
)
from .feed.views import PostViewSet
from .requests_app.views import RequestViewSet
from .search.views import search_api_view

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
    path("auth/register/", RegisterAPIView.as_view(), name="register"),
    path(
        "auth/resend-email/",
        ResendEmailAPIView.as_view(),
        name="resend-email",
    ),
    path(
        "auth/verify-email/",
        VerifyEmailAPIView.as_view(),
        name="verify-email",
    ),
    # Notifications API (из самого модуля notifications)
    path("notifications/", include("notifications.api.urls")),
    # Procurement API
    path("procurement/", include("api.v1.procurement.urls")),
    # Search API
    path("search/", search_api_view, name="search"),
    # Router URLs (включая все ViewSets)
    path("", include(router.urls)),
]

"""URL configuration for API v2."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .auth.views import RegisterAPIView, ResendEmailAPIView, VerifyEmailAPIView
from .calendar.views import (
    CalendarEventsViewSet,
    CalendarSubscriptionViewSet,
    CalendarViewSet,
)
from .communications.views import ChatViewSet, MessageViewSet, PollViewSet
from .documents.views import DocumentViewSet
from .employees.extended_views import (
    DepartmentRoleViewSet,
    EmployeeActionViewSet,
    GroupViewSet,
    PositionViewSet,
    SkillViewSet,
)
from .employees.views import DepartmentViewSet, EmployeeViewSet
from .feed.views import CommentViewSet, PostViewSet
from .requests.views import RequestViewSet

app_name = "v2"

router = DefaultRouter()

# Employees & Departments
router.register(r"employees", EmployeeViewSet, basename="employee")
router.register(r"departments", DepartmentViewSet, basename="department")
router.register(r"positions", PositionViewSet, basename="positions")
router.register(r"department-roles", DepartmentRoleViewSet,
                basename="department-roles")
router.register(r"skills", SkillViewSet, basename="skills")
router.register(r"employee-actions", EmployeeActionViewSet,
                basename="employee-actions")
router.register(r"groups", GroupViewSet, basename="groups")

# Documents
router.register(r"documents", DocumentViewSet, basename="documents")

# Requests (Заявки)
router.register(r"requests", RequestViewSet, basename="requests")

# Calendar
router.register(r"calendar/events", CalendarEventsViewSet, basename="events")
router.register(r"calendar/calendars", CalendarViewSet, basename="calendars")
router.register(
    r"calendar/subscriptions",
    CalendarSubscriptionViewSet,
    basename="subscriptions",
)

# Communications (Чаты)
router.register(r"chats", ChatViewSet, basename="chats")
router.register(r"messages", MessageViewSet, basename="messages")
router.register(r"polls", PollViewSet, basename="polls")

# Feed (Лента новостей)
router.register(r"posts", PostViewSet, basename="posts")
router.register(r"comments", CommentViewSet, basename="comments")

urlpatterns = [
    # Auth endpoints
    path("auth/register/", RegisterAPIView.as_view(), name="register"),
    path("auth/resend-email/", ResendEmailAPIView.as_view(), name="resend-email"),
    path("auth/verify-email/", VerifyEmailAPIView.as_view(), name="verify-email"),

    # Notifications (из самого модуля notifications)
    path("notifications/", include("notifications.api.urls")),

    # Router URLs (все ViewSets)
    path("", include(router.urls)),
]

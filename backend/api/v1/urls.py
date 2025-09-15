from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .calendar.views import CalendarEventsViewSet
from .employees.views import (DepartmentRoleViewSet, DepartmentViewSet,
                              EmployeeActionViewSet, EmployeeViewSet,
                              GroupViewSet, PositionViewSet,
                              RegisterAPIView, ResendEmailAPIView,
                              SkillViewSet, VerifyEmailAPIView)
from .feed.views import CommentViewSet, PostViewSet
from .documents.views import DocumentViewSet
from .requests_app.views import RequestViewSet

app_name = "v1"

router = DefaultRouter()

router.register(r"calendar/events", CalendarEventsViewSet, basename="events")

router.register(r"documents", DocumentViewSet, basename="documents")

router.register(r"requests", RequestViewSet, basename="request")

router.register(r"departments", DepartmentViewSet, basename="departments")
router.register(r"employees", EmployeeViewSet, basename="employees")
router.register(r"employee-actions", EmployeeActionViewSet, basename="employee-actions")
router.register(r"positions", PositionViewSet, basename="positions")
router.register(r"department-roles", DepartmentRoleViewSet, basename="department-roles")
router.register(r"skills", SkillViewSet, basename="skills")
router.register(r"posts", PostViewSet, basename="posts")
router.register(r"comments", CommentViewSet, basename="comments")
router.register(r"groups", GroupViewSet, basename="groups")


urlpatterns = [
    path("auth/register/", RegisterAPIView.as_view(), name="register"),
    path("auth/resend-email/", ResendEmailAPIView.as_view(), name="resend-email"),
    path("auth/verify-email/", VerifyEmailAPIView.as_view(), name="verify-email"),
    path("", include(router.urls)),
]

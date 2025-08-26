from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .calendar.viewsets import CompanyEventsViewSet, DepartmentEventsViewSet
from .employees.views import (DepartmentRoleViewSet, DepartmentViewSet,
                              EmployeeViewSet, PositionViewSet,
                              RegisterAPIView, ResendEmailAPIView,
                              VerifyEmailAPIView, SkillViewSet, EmployeeActionViewSet,)

app_name = "api_v1"

router = DefaultRouter()
router.register(r"calendar/company-events", CompanyEventsViewSet, basename="company-events")
router.register(r"departments", DepartmentViewSet, basename="departments")
router.register(r"employees", EmployeeViewSet, basename="employees")
router.register(r"employee-actions", EmployeeActionViewSet, basename="employee-actions")
router.register(r"positions", PositionViewSet, basename="positions")
router.register(r"department-roles", DepartmentRoleViewSet, basename="department-roles")
router.register(r"skills", SkillViewSet, basename="skills")

urlpatterns = [
    path("auth/register/", RegisterAPIView.as_view(), name="register"),
    path("auth/resend-email/", ResendEmailAPIView.as_view(), name="resend-email"),
    path("auth/verify-email/", VerifyEmailAPIView.as_view(), name="verify-email"),
    path("calendar/departments/<int:pk>/events/", DepartmentEventsViewSet.as_view({"get": "list"}), name="department-events",),
    path("", include(router.urls)),
]

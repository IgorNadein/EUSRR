from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .calendar.viewsets import CompanyEventsViewSet, DepartmentEventsViewSet
from .employees.views import (
    AbsenceViewSet,
    DepartmentViewSet,
    EducationViewSet,
    EmployeeActionViewSet,
    EmployeePositionViewSet,
    EmployeeViewSet,
    SkillViewSet,
)

router = DefaultRouter()
router.register(r"employees", EmployeeViewSet, basename="employee")
router.register(r"departments", DepartmentViewSet, basename="department")
router.register(r"actions", EmployeeActionViewSet, basename="action")
router.register(r"positions", EmployeePositionViewSet, basename="position")
router.register(r"absences", AbsenceViewSet, basename="absence")
router.register(r"skills", SkillViewSet, basename="skill")
router.register(r"educations", EducationViewSet, basename="education")
router.register(
    r"calendar/company-events", CompanyEventsViewSet, basename="company-events"
)
urlpatterns = [
    path(
        "calendar/departments/<int:pk>/events/",
        DepartmentEventsViewSet.as_view({"get": "list"}),
        name="department-events",
    ),
    path("", include(router.urls)),
]

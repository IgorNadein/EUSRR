from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .calendar.viewsets import CompanyEventsViewSet, DepartmentEventsViewSet
from .employees.views import (RegisterAPIView, ResendEmailAPIView,
                              VerifyEmailAPIView)

router = DefaultRouter()
router.register(
    r"calendar/company-events", CompanyEventsViewSet, basename="company-events"
)

app_name = "api_v1"

urlpatterns = [
    path("auth/register/", RegisterAPIView.as_view(), name="register"),
    path("auth/resend-email/", ResendEmailAPIView.as_view(), name="resend-email"),
    path("auth/verify-email/", VerifyEmailAPIView.as_view(), name="verify-email"),
    path(
        "calendar/departments/<int:pk>/events/",
        DepartmentEventsViewSet.as_view({"get": "list"}),
        name="department-events",
    ),
    path("", include(router.urls)),
]

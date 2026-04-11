from django.urls import path

from .views import (
    JWTTokenRefreshView,
    LogoutOtherSessionsAPIView,
    PhoneOrEmailTokenObtainPairView,
    RegisterAPIView,
    ResendEmailAPIView,
    SessionDetailAPIView,
    SessionListAPIView,
    VerifyEmailAPIView,
)

urlpatterns = [
    path("token/", PhoneOrEmailTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", JWTTokenRefreshView.as_view(), name="token_refresh"),
    path("register/", RegisterAPIView.as_view(), name="register"),
    path("resend-email/", ResendEmailAPIView.as_view(), name="resend-email"),
    path("verify-email/", VerifyEmailAPIView.as_view(), name="verify-email"),
    path("sessions/", SessionListAPIView.as_view(), name="sessions"),
    path(
        "sessions/logout-others/",
        LogoutOtherSessionsAPIView.as_view(),
        name="logout-others",
    ),
    path(
        "sessions/<uuid:session_id>/",
        SessionDetailAPIView.as_view(),
        name="session-detail",
    ),
]

from django.urls import path

from .views import (
    ChangePasswordAPIView,
    JWTTokenRefreshView,
    LogoutOtherSessionsAPIView,
    PasswordResetAPIView,
    PasswordResetConfirmAPIView,
    PhoneOrEmailTokenObtainPairView,
    QrLoginCreateAPIView,
    QrLoginExchangeAPIView,
    QrLoginRequestApproveAPIView,
    QrLoginRequestCancelAPIView,
    QrLoginRequestCreateAPIView,
    QrLoginRequestDenyAPIView,
    QrLoginRequestDetailAPIView,
    QrLoginRequestStatusAPIView,
    RegisterAPIView,
    ResendEmailAPIView,
    SessionDetailAPIView,
    SessionListAPIView,
    VerifyEmailAPIView,
)

urlpatterns = [
    path("token/", PhoneOrEmailTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", JWTTokenRefreshView.as_view(), name="token_refresh"),
    path("qr-login/", QrLoginCreateAPIView.as_view(), name="qr-login"),
    path(
        "qr-login/exchange/",
        QrLoginExchangeAPIView.as_view(),
        name="qr-login-exchange",
    ),
    path(
        "qr-login/requests/",
        QrLoginRequestCreateAPIView.as_view(),
        name="qr-login-request",
    ),
    path(
        "qr-login/requests/status/",
        QrLoginRequestStatusAPIView.as_view(),
        name="qr-login-request-status",
    ),
    path(
        "qr-login/requests/cancel/",
        QrLoginRequestCancelAPIView.as_view(),
        name="qr-login-request-cancel",
    ),
    path(
        "qr-login/requests/<str:scan_token>/",
        QrLoginRequestDetailAPIView.as_view(),
        name="qr-login-request-detail",
    ),
    path(
        "qr-login/requests/<str:scan_token>/approve/",
        QrLoginRequestApproveAPIView.as_view(),
        name="qr-login-request-approve",
    ),
    path(
        "qr-login/requests/<str:scan_token>/deny/",
        QrLoginRequestDenyAPIView.as_view(),
        name="qr-login-request-deny",
    ),
    path("password-reset/", PasswordResetAPIView.as_view(), name="password-reset"),
    path(
        "password-reset/confirm/",
        PasswordResetConfirmAPIView.as_view(),
        name="password-reset-confirm",
    ),
    path("change-password/", ChangePasswordAPIView.as_view(), name="change-password"),
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

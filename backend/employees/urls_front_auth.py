# backend\eusrr_backend\urls_front_auth.py
from django.urls import path

from . import views_auth

app_name = "auth_front"

urlpatterns = [
    path("login/", views_auth.EmailOrPhoneLoginView.as_view(), name="login"),
    path("logout/", views_auth.ConfirmLogoutView.as_view(), name="logout"),
    path("register/", views_auth.register_view, name="register"),
    path("verify-email/", views_auth.verify_email_view, name="verify_email"),
    path("resend-email/", views_auth.resend_email_view, name="resend_email"),
    path("password-reset/", views_auth.PasswordResetView.as_view(), name="password_reset"),
    path("password-reset/done/", views_auth.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("reset/<uidb64>/<token>/", views_auth.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("reset/done/", views_auth.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
]
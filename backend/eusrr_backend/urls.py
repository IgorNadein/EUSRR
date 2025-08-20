from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, reverse_lazy
from django.views.generic.edit import CreateView
from employees.forms import RegistrationForm
from employees.views_front import RegisterView

from . import views_auth

urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/login/", views_auth.EmailOrPhoneLoginView.as_view(), name="login"),
    path("auth/logout/", views_auth.ConfirmLogoutView.as_view(), name="logout"),
    path("auth/password-reset/", views_auth.PasswordResetView.as_view(
        template_name="registration/password_reset_form.html",
        email_template_name="registration/password_reset_email.txt",
        subject_template_name="registration/password_reset_subject.txt",
        success_url="/auth/password-reset/done/",
    ), name="password_reset"),
    path("auth/password-reset/done/", views_auth.PasswordResetDoneView.as_view(
        template_name="registration/password_reset_done.html",
    ), name="password_reset_done"),
    path("auth/reset/<uidb64>/<token>/", views_auth.PasswordResetConfirmView.as_view(
        template_name="registration/password_reset_confirm.html",
        success_url="/auth/reset/done/",
    ), name="password_reset_confirm"),
    path("auth/reset/done/", views_auth.PasswordResetCompleteView.as_view(
        template_name="registration/password_reset_complete.html",
    ), name="password_reset_complete"),
    # path("auth/", include("django.contrib.auth.urls")),
    # path("auth/register/", RegisterView.as_view(), name="register"),
    # path("sms-verify/", SMSVerifyView.as_view(), name="sms_verify"),
    # path("resend-sms/", resend_sms, name="resend_sms"),
    path("calendar/", include("calendar_app.urls", namespace="calendar")),
    path("documents/", include("documents.urls", namespace="documents")),
    path("requests/", include("requests_app.urls", namespace="requests_app")),
    path("employees/", include("employees.urls_front", namespace="employees")),
    path("communications/", include("communications.urls", namespace="communications")),
    path("search/", include("search.urls", namespace="search")),
    path("api/", include("api.urls")),
    path("", include("feed.urls", namespace="feed")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

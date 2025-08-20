from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, reverse_lazy
from django.views.generic.edit import CreateView
from employees.forms import RegistrationForm
from employees.views_front import RegisterView, SMSVerifyView, resend_sms

urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/", include("django.contrib.auth.urls")),
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("sms-verify/", SMSVerifyView.as_view(), name="sms_verify"),
    path("resend-sms/", resend_sms, name="resend_sms"),
    path("calendar/", include("calendar_app.urls", namespace="calendar")),
    path("documents/", include("documents.urls", namespace="documents")),
    path("requests/", include("requests_app.urls", namespace="requests_app")),
    path("employees/", include("employees.urls_front", namespace="employees")),
    path("communications/", include("communications.urls", namespace="communications")),
    path("search/", include("search.urls", namespace="search")),
    path("api/", include("api.urls")),
    path("", include("feed.urls", namespace="feed")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

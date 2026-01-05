from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.static import serve
import os

urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/", include("employees.urls_front_auth", namespace="auth_front")),
    path("documents/", include("documents.urls", namespace="documents")),
    path("requests/", include("requests_app.urls", namespace="requests")),
    path("employees/", include("employees.urls_front", namespace="employees")),
    path("communications/", include("communications.urls", namespace="communications")),
    path("notifications/", include("notifications.urls", namespace="notifications")),
    path("search/", include("search.urls", namespace="search")),
    path("finance/", include("finance.urls", namespace="finance")),
    path("api/", include(("api.urls", "api"), namespace="api")),
    # Service Worker должен быть в корне для правильного scope
    path("sw.js", serve, {"document_root": settings.BASE_DIR, "path": "sw.js", "content_type": "application/javascript"}, name="sw"),
    path("", include("feed.urls_front", namespace="feed")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

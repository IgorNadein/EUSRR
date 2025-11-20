from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/", include("employees.urls_front_auth", namespace="auth_front")),
    path("documents/", include("documents.urls", namespace="documents")),
    path("requests/", include("requests_app.urls_front", namespace="requests")),
    path("employees/", include("employees.urls_front", namespace="employees")),
    path("communications/", include("communications.urls", namespace="communications")),
    path("search/", include("search.urls", namespace="search")),
    path("finance/", include("finance.urls", namespace="finance")),
    path("api/", include(("api.urls", "api"), namespace="api")),
    path("", include("feed.urls_front", namespace="feed")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

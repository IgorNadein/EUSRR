from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(("api.urls", "api"), namespace="api")),
    path(
        "api/procurement/",
        include(("api.v1.procurement.urls", "procurement"), namespace="procurement"),
    ),
    # django-filer URLs для обработки приватных файлов
    # (с проверкой прав доступа)
    path("", include("filer.server.urls")),
]

# Публичные медиа файлы (без проверки прав)
# только в режиме разработки
if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    )

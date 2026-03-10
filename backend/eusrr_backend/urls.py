from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

# Импорт Service Worker view из приложения notifications
from notifications.views import serve_service_worker

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(("api.urls", "api"), namespace="api")),
    # Service Worker должен быть в корне для правильного scope
    path("sw.js", serve_service_worker, name="sw"),
    # django-filer URLs для обработки приватных файлов (с проверкой прав доступа)
    path("", include("filer.server.urls")),
]

# Публичные медиа файлы (без проверки прав) - только в режиме разработки
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

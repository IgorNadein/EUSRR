from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.http import FileResponse
import os

def serve_service_worker(request):
    """Обслуживает Service Worker с правильным content-type и заголовками"""
    sw_path = os.path.join(settings.BASE_DIR, 'sw.js')
    try:
        response = FileResponse(
            open(sw_path, 'rb'),
            content_type='application/javascript; charset=utf-8',
            status=200
        )
        # Отключаем кэширование для sw.js (всегда получаем свежую версию)
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        # Service-Worker-Allowed позволяет контролировать весь домен
        response['Service-Worker-Allowed'] = '/'
        return response
    except Exception as e:
        from django.http import HttpResponse
        return HttpResponse(f"Service Worker not found: {e}", status=500)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("documents/", include("documents.urls", namespace="documents")),
    path("api/", include(("api.urls", "api"), namespace="api")),
    # Service Worker должен быть в корне для правильного scope
    path("sw.js", serve_service_worker, name="sw"),
    # django-filer URLs для обработки приватных файлов (с проверкой прав доступа)
    path("", include("filer.server.urls")),
]

# Публичные медиа файлы (без проверки прав) - только в режиме разработки
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

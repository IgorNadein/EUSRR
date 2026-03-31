# backend/eusrr_backend/middleware.py
"""
Кастомные middleware для проекта EUSRR.

Минимальный набор для работы Django Admin + REST API.
"""

from django.conf import settings


class AuthRequiredMiddleware:
    """
    Базовая защита: неавторизованные пользователи не могут заходить куда-либо,
    кроме API и админки (которые управляют аутентификацией сами).

    Разрешенные зоны без аутентификации:
    - /api/ - REST API с JWT/Token аутентификацией
    - /admin/ - Django Admin со своей системой аутентификации
    - /static/ - статические файлы
    - /media/ - медиафайлы
    """

    EXEMPT_PREFIXES = (
        "/api/",  # REST API управляет своей аутентификацией
        "/admin/",  # Django Admin использует встроенную аутентификацию
        "/static/",  # Статика
        "/media/",  # Медиа
    )

    def __init__(self, get_response):
        self.get_response = get_response
        self.allowed_prefixes = tuple(
            getattr(
                settings, "AUTH_REQUIRED_EXEMPT_PREFIXES", self.EXEMPT_PREFIXES
            )
        )

    def __call__(self, request):
        # Аутентифицированные пользователи проходят везде
        if request.user.is_authenticated:
            return self.get_response(request)

        path = request.path_info

        # Пропускаем разрешенные префиксы - они сами управляют аутентификацией
        # Django Admin сам редиректит на /admin/login/ если нужно
        if any(path.startswith(p) for p in self.allowed_prefixes):
            return self.get_response(request)

        # Все остальное - 403 Forbidden для неаутентифицированных
        from django.http import HttpResponseForbidden, JsonResponse

        # Для API запросов возвращаем JSON
        if request.headers.get("Accept", "").startswith("application/json"):
            return JsonResponse(
                {"detail": "Authentication required"}, status=403
            )

        # Для браузерных запросов - HTML 403
        return HttpResponseForbidden("403 Forbidden: Authentication required")


class CacheControlMiddleware:
    """
    Добавляет правильные заголовки Cache-Control для HTML-страниц.

    Стратегия:
    - HTML страницы: private cache на 60 секунд (только для браузера)
    - API: обрабатывается на уровне DRF
    - Статика/медиа: обрабатывается веб-сервером
    """

    NO_CACHE_PREFIXES = (
        "/api/",  # API управляет своим кэшем
        "/admin/",  # Админка всегда свежая
        "/static/",  # Обрабатывается веб-сервером
        "/media/",  # Обрабатывается веб-сервером
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Применяем только к успешным HTML GET-запросам
        if (
            response.status_code == 200
            and request.method == "GET"
            and response.get("Content-Type", "").startswith("text/html")
        ):
            path = request.path_info

            # Проверяем исключения
            if not any(path.startswith(p) for p in self.NO_CACHE_PREFIXES):
                # Если заголовок уже установлен - не перезаписываем
                if not response.has_header("Cache-Control"):
                    response["Cache-Control"] = "private, max-age=60"

        return response

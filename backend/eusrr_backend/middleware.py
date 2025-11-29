# backend/eusrr_backend/middleware.py
from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse, NoReverseMatch


class AuthRequiredMiddleware:
    """
    Разрешает доступ НЕавторизованным только к страницам логина/регистрации/верификации
    и к API (или его частям), чтобы DRF/JWT сами возвращали 200/401 JSON, а не 302 HTML.
    """

    # Префиксы, которые всегда пропускаем (настройка через settings при желании)

    EXEMPT_PREFIXES = (
        "/api/",
        "/auth/reset/",
        "/static/",  # статика
        "/media/",  # медиа
        # "/__debug__/",    # django-debug-toolbar, если используется
    )

    # Именованные маршруты, которые можно посещать анонимно (точные пути)
    EXEMPT_NAMES = (
        "auth_front:login",
        "auth_front:password_reset",
        "auth_front:register",
        "auth_front:verify_email",
        "auth_front:resend_email",
        "auth_front:password_reset_done",
        "auth_front",
    )

    def __init__(self, get_response):
        self.get_response = get_response
        # Разрешённые точные пути (резолвим имена; если имя отсутствует — просто пропускаем)
        allowed_exact = set()
        for name in self.EXEMPT_NAMES:
            try:
                allowed_exact.add(reverse(name))
            except NoReverseMatch:
                # ничего страшного, просто такого имени сейчас нет
                pass
        self.allowed_exact = tuple(allowed_exact)

        # Префиксы можно расширять из settings, если нужно
        self.allowed_prefixes = tuple(
            getattr(settings, "AUTH_REQUIRED_EXEMPT_PREFIXES", self.EXEMPT_PREFIXES)
        )

    def __call__(self, request):
        # уже залогинен — пропускаем
        if request.user.is_authenticated:
            return self.get_response(request)

        path = request.path_info  # нормализованный путь без домена/квери

        # 1) Пропускаем всё, что под разрешёнными префиксами (включая /api/)
        if any(path.startswith(p) for p in self.allowed_prefixes):
            return self.get_response(request)

        # 2) Пропускаем точные разрешённые пути (логин/регистрация и т.п.)
        if path in self.allowed_exact:
            return self.get_response(request)

        # 3) Иначе — редирект на страницу логина
        return redirect(settings.LOGIN_URL)  # у тебя name="login" -> /auth/login/


class EmailVerificationMiddleware:
    """
    Проверяет что залогиненные пользователи имеют подтверждённый email.
    Неверифицированные пользователи редиректятся на страницу верификации.
    
    Исключения:
    - Staff пользователи могут работать без верификации (админка)
    - API запросы обрабатываются на уровне permissions
    - Страницы верификации и статика доступны всем
    """

    EXEMPT_PREFIXES = (
        "/api/",  # API обрабатывает свои permissions
        "/static/",
        "/media/",
        "/admin/",  # Админка доступна staff
    )

    EXEMPT_NAMES = (
        "auth_front:verify_email",
        "auth_front:resend_email",
        "auth_front:login",
        "auth_front:logout",
        "auth_front:register",
    )

    def __init__(self, get_response):
        self.get_response = get_response
        
        # Резолвим разрешённые пути
        allowed_exact = set()
        for name in self.EXEMPT_NAMES:
            try:
                allowed_exact.add(reverse(name))
            except NoReverseMatch:
                pass
        self.allowed_exact = tuple(allowed_exact)
        
        self.allowed_prefixes = self.EXEMPT_PREFIXES

    def __call__(self, request):
        # Анонимные пользователи - обрабатываются AuthRequiredMiddleware
        if not request.user.is_authenticated:
            return self.get_response(request)

        # Staff пользователи могут работать без верификации
        if request.user.is_staff:
            return self.get_response(request)

        # Проверяем email_verified
        if not getattr(request.user, "email_verified", True):
            path = request.path_info

            # Пропускаем разрешённые префиксы
            if any(path.startswith(p) for p in self.allowed_prefixes):
                return self.get_response(request)

            # Пропускаем точные разрешённые пути
            if path in self.allowed_exact:
                return self.get_response(request)

            # Редирект на страницу верификации
            try:
                verify_url = reverse("auth_front:verify_email")
                if path != verify_url:
                    return redirect(verify_url)
            except NoReverseMatch:
                # Если нет страницы верификации - пропускаем
                pass

        return self.get_response(request)


class CacheControlMiddleware:
    """
    Добавляет правильные заголовки Cache-Control для страниц.
    
    Стратегия:
    - HTML страницы: private cache на 60 секунд (только для браузера)
    - API: обрабатывается на уровне DRF
    - Статика/медиа: обрабатывается Nginx
    """
    
    # Пути, для которых НЕ добавляем кэширование
    NO_CACHE_PREFIXES = (
        "/api/",  # API управляет своим кэшем
        "/admin/",  # Админка всегда свежая
        "/auth/",  # Страницы аутентификации
        "/static/",  # Nginx обрабатывает
        "/media/",  # Nginx обрабатывает
    )
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Применяем только к HTML страницам
        if (
            response.status_code == 200
            and request.method == "GET"
            and response.get("Content-Type", "").startswith("text/html")
        ):
            path = request.path_info
            
            # Проверяем исключения
            if not any(path.startswith(p) for p in self.NO_CACHE_PREFIXES):
                # Если заголовок уже установлен декоратором - не перезаписываем
                if not response.has_header("Cache-Control"):
                    response["Cache-Control"] = "private, max-age=60"
        
        return response

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


class RegistrationIPRestrictionMiddleware:
    """
    Проверяет IP-адрес для запросов к регистрации.
    
    Применяется только к URL-ам регистрации:
    - /auth/register/
    - /api/v1/auth/register/
    
    Все остальные URL пропускаются без проверки.
    """
    
    RESTRICTED_PATHS = (
        "/auth/register/",
        "/api/v1/auth/register/",
    )
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        from common.ip_restrictions import get_client_ip, is_ip_allowed
        
        path = request.path_info
        
        # Проверяем только запросы к регистрации
        if not any(path.startswith(p) for p in self.RESTRICTED_PATHS):
            return self.get_response(request)
        
        # Проверяем IP-адрес
        client_ip = get_client_ip(request)
        
        if not is_ip_allowed(client_ip):
            # IP не разрешен - блокируем
            
            # Для API возвращаем JSON
            if path.startswith("/api/"):
                from django.http import JsonResponse
                return JsonResponse(
                    {
                        "detail": "Регистрация доступна только из "
                                  "локальной сети.",
                        "client_ip": client_ip
                    },
                    status=403
                )
            
            # Для веб-страниц возвращаем HTML
            from django.http import HttpResponse
            return HttpResponse(
                f"""
                <!DOCTYPE html>
                <html lang="ru">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, 
                                                    initial-scale=1.0">
                    <title>403 Forbidden</title>
                    <style>
                        body {{
                            font-family: -apple-system, BlinkMacSystemFont,
                                         "Segoe UI", Roboto, sans-serif;
                            display: flex;
                            justify-content: center;
                            align-items: center;
                            min-height: 100vh;
                            margin: 0;
                            background: linear-gradient(135deg, 
                                        #667eea 0%, #764ba2 100%);
                        }}
                        .container {{
                            background: white;
                            padding: 3rem;
                            border-radius: 1rem;
                            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                            max-width: 500px;
                            text-align: center;
                        }}
                        h1 {{
                            color: #e53e3e;
                            font-size: 3rem;
                            margin: 0 0 1rem 0;
                        }}
                        h2 {{
                            color: #2d3748;
                            font-size: 1.5rem;
                            margin: 0 0 1.5rem 0;
                        }}
                        p {{
                            color: #4a5568;
                            line-height: 1.6;
                            margin: 0 0 1rem 0;
                        }}
                        .ip-info {{
                            background: #f7fafc;
                            border-left: 4px solid #667eea;
                            padding: 1rem;
                            margin: 1.5rem 0;
                            border-radius: 0.5rem;
                            font-family: monospace;
                        }}
                        .back-link {{
                            display: inline-block;
                            margin-top: 1.5rem;
                            padding: 0.75rem 2rem;
                            background: #667eea;
                            color: white;
                            text-decoration: none;
                            border-radius: 0.5rem;
                        }}
                        .back-link:hover {{
                            background: #5a67d8;
                        }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>🔒 403</h1>
                        <h2>Доступ запрещен</h2>
                        <p>Регистрация доступна только из локальной сети.</p>
                        <p>Если вы в офисе или подключены через VPN, 
                           обратитесь к администратору.</p>
                        <div class="ip-info">
                            Ваш IP: <strong>{client_ip}</strong>
                        </div>
                        <a href="/" class="back-link">← На главную</a>
                    </div>
                </body>
                </html>
                """,
                status=403,
                content_type="text/html; charset=utf-8"
            )
        
        # IP разрешен - продолжаем обработку
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

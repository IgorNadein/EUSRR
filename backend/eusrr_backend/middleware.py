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
        # "/static/",       # статика
        # "/media/",        # медиа
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
        
        "auth_front"
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

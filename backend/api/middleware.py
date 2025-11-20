# backend/api/middleware.py
"""
Middleware для автоматического обновления JWT токенов.
Обновляет access token за 5 минут до истечения.
"""
from datetime import datetime, timedelta

import jwt
from django.conf import settings

from .client import SESSION_KEY_ACCESS, SESSION_KEY_REFRESH, get_api_client


class JWTRefreshMiddleware:
    """
    Автоматически обновляет JWT access token, если он скоро истечёт.
    
    Проверяет токен при каждом запросе и обновляет его, если осталось
    меньше 5 минут до истечения (по умолчанию).
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        # За сколько минут до истечения обновлять токен
        self.refresh_threshold = timedelta(
            minutes=int(getattr(settings, 'JWT_REFRESH_THRESHOLD_MINUTES', 5))
        )
    
    def __call__(self, request):
        # Проверяем только для авторизованных пользователей
        if request.user.is_authenticated:
            access_token = request.session.get(SESSION_KEY_ACCESS)
            refresh_token = request.session.get(SESSION_KEY_REFRESH)
            
            if access_token and refresh_token:
                try:
                    # Декодируем токен БЕЗ проверки подписи (только для чтения exp)
                    decoded = jwt.decode(
                        access_token,
                        options={"verify_signature": False}
                    )
                    exp = decoded.get('exp')
                    
                    if exp:
                        # Время истечения токена
                        exp_time = datetime.fromtimestamp(exp)
                        # Текущее время
                        now = datetime.now()
                        # Оставшееся время
                        time_left = exp_time - now
                        
                        # Если осталось меньше порога - обновляем
                        if time_left < self.refresh_threshold:
                            client = get_api_client(request)
                            client.refresh_tokens()
                            
                except (jwt.DecodeError, jwt.InvalidTokenError, ValueError):
                    # Если токен невалидный - ничего не делаем,
                    # ApiClient сам обработает при запросе
                    pass
        
        response = self.get_response(request)
        return response

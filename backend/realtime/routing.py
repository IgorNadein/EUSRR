# realtime/routing.py
"""
WebSocket URL routing for real-time features.
All WebSocket connections are handled through this routing.
"""
from django.urls import re_path

from .consumers import UserConsumer

websocket_urlpatterns = [
    # Универсальный WebSocket для пользователя
    # Обрабатывает: чаты, уведомления, бейджи, онлайн-статус и др.
    re_path(r"^ws/$", UserConsumer.as_asgi(), name="ws_user"),
]

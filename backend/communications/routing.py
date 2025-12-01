# backend\communications\routing.py
from django.urls import re_path

from .user_consumer import UserConsumer

websocket_urlpatterns = [
    # Универсальный WebSocket для пользователя
    # Обрабатывает: чаты, уведомления, бейджи, онлайн-статус и др.
    re_path(r"^ws/$", UserConsumer.as_asgi(), name="ws_user"),
]

# backend\communications\routing.py
from django.urls import path
from django.urls import re_path
from .consumers import ChatConsumer, ChatListConsumer

websocket_urlpatterns = [
    re_path(r"^ws/chat/(?P<chat_id>\d+)/$", ChatConsumer.as_asgi(), name="ws_chat"),
    re_path(r"^ws/chats/$", ChatListConsumer.as_asgi(), name="ws_chat_list"),
]

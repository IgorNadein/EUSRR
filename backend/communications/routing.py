from django.urls import path
from django.urls import re_path
from .consumers import ChatConsumer, ChatListConsumer

websocket_urlpatterns = [
    path("ws/chat/<int:chat_id>/", ChatConsumer.as_asgi(), name="ws_chat"),
    re_path(r"^ws/chats/$", ChatListConsumer.as_asgi()),
]

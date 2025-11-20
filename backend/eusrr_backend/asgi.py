import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "eusrr_backend.settings")

from django.core.asgi import get_asgi_application
django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from communications.routing import websocket_urlpatterns as communications_ws
from notifications.routing import websocket_urlpatterns as notifications_ws
from eusrr_backend.channels_jwt import JWTAuthMiddleware


# Объединить все WebSocket маршруты
all_websocket_urlpatterns = communications_ws + notifications_ws


application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": JWTAuthMiddleware(
        AuthMiddlewareStack(
            URLRouter(all_websocket_urlpatterns)
        )
    ),
})
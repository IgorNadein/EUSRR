import os
from importlib import import_module

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "eusrr_backend.settings")

django_asgi_app = get_asgi_application()

JWTAuthMiddleware = import_module(
    "eusrr_backend.channels_jwt"
).JWTAuthMiddleware
websocket_urlpatterns = import_module(
    "realtime.routing"
).websocket_urlpatterns


application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": JWTAuthMiddleware(
        AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        )
    ),
})

import pytest

from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken

from api.auth.models import UserAuthSession
from eusrr_backend.channels_jwt import JWTAuthMiddleware

User = get_user_model()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_revoked_session_becomes_anonymous_for_websocket():
    user = await sync_to_async(User.objects.create_user)(
        email="ws-auth@example.com",
        password="testpass123",
        phone_number="+79997770011",
        first_name="Ws",
        last_name="User",
        is_active=True,
        email_verified=True,
    )
    session = await sync_to_async(UserAuthSession.objects.create)(
        user=user,
        refresh_token_hash="stub",
    )

    token = AccessToken.for_user(user)
    token["session_id"] = str(session.session_id)

    captured = {}

    async def app(scope, receive, send):
        captured["user"] = scope["user"]
        await send({"type": "websocket.accept"})
        await send({"type": "websocket.close"})

    communicator = WebsocketCommunicator(
        JWTAuthMiddleware(app),
        f"/ws/?token={str(token)}",
    )
    connected, _ = await communicator.connect()
    assert connected is True
    assert captured["user"].is_authenticated is True
    await communicator.disconnect()

    await sync_to_async(session.revoke)(reason="test")

    captured.clear()
    communicator = WebsocketCommunicator(
        JWTAuthMiddleware(app),
        f"/ws/?token={str(token)}",
    )
    connected, _ = await communicator.connect()
    assert connected is True
    assert captured["user"].is_authenticated is False
    await communicator.disconnect()

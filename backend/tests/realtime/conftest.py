# tests/realtime/conftest.py
"""
Pytest fixtures для тестирования WebSocket consumers.
"""
import pytest
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from communications.models import Chat, ChatMembership
from realtime.consumers import UserConsumer

User = get_user_model()


@pytest.fixture
def user(db):
    """Создает тестового пользователя."""
    return User.objects.create_user(
        email='testuser@example.com',
        password='testpass123',
        phone_number='+79991234567',
        first_name='Test',
        last_name='User'
    )


@pytest.fixture
def user2(db):
    """Создает второго тестового пользователя."""
    return User.objects.create_user(
        email='testuser2@example.com',
        password='testpass123',
        phone_number='+79991234568',
        first_name='Test2',
        last_name='User2'
    )


@pytest.fixture
def ws_communicator():
    """
    Фабрика для создания WebSocket communicator.
    
    Использование:
        communicator = await ws_communicator(user=test_user)
        connected, _ = await communicator.connect()
    """
    async def _create_communicator(user=None, path="/ws/"):
        """Создает WebsocketCommunicator с указанным пользователем."""
        application = UserConsumer.as_asgi()
        
        # Создаем scope с пользователем
        scope = {
            "type": "websocket",
            "path": path,
            "headers": [],
            "query_string": b"",
            "user": user if user else AnonymousUser(),
        }
        
        communicator = WebsocketCommunicator(application, path)
        communicator.scope.update(scope)
        
        return communicator
    
    return _create_communicator


@pytest.fixture
def test_chat(db, user):
    """Создает тестовый чат с пользователем."""
    chat = Chat.objects.create(
        name="Test Chat",
        type="group"
    )
    ChatMembership.objects.create(
        chat=chat,
        user=user,
        role="member"
    )
    return chat


@pytest.fixture
def test_chat_with_users(db, user, user2):
    """Создает чат с двумя пользователями."""
    chat = Chat.objects.create(
        name="Multi User Chat",
        type="group"
    )
    ChatMembership.objects.create(chat=chat, user=user, role="admin")
    ChatMembership.objects.create(chat=chat, user=user2, role="member")
    return chat

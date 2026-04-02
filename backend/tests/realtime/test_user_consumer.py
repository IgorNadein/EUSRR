# tests/realtime/test_user_consumer.py
"""
Тесты для UserConsumer - универсального WebSocket consumer'а.

Проверяем:
- Подключение/отключение
- Аутентификацию
- Подписку на чаты и каналы
- Ping/pong keepalive
- Открытие/закрытие активного чата
"""
import pytest
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

from communications.models import Chat, ChatMembership
from notifications.models import Notification

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.asyncio
class TestUserConsumerConnection:
    """Тесты подключения и отключения WebSocket."""
    
    async def test_anonymous_user_rejected(self, ws_communicator):
        """Анонимный пользователь не может подключиться."""
        communicator = await ws_communicator(user=AnonymousUser())
        
        connected, subprotocol = await communicator.connect()
        
        assert not connected, "Анонимный пользователь не должен подключиться"
        
        await communicator.disconnect()
    
    async def test_authenticated_user_connects(self, ws_communicator, user):
        """Аутентифицированный пользователь успешно подключается."""
        communicator = await ws_communicator(user=user)
        
        connected, subprotocol = await communicator.connect()
        
        assert connected, "Аутентифицированный пользователь должен подключиться"
        
        await communicator.disconnect()
    
    async def test_user_subscribes_to_chats(self, ws_communicator, user, test_chat):
        """При подключении пользователь подписывается на свои чаты."""
        # Создаем дополнительный чат
        chat2 = await database_sync_to_async(Chat.objects.create)(
            name="Second Chat", type="group"
        )
        await database_sync_to_async(ChatMembership.objects.create)(
            chat=chat2, user=user, role="member"
        )
        
        communicator = await ws_communicator(user=user)
        
        connected, _ = await communicator.connect()
        assert connected
        
        # Проверяем, что пользователь подписан на группы чатов
        # (это можно проверить через логи или mock channel_layer)
        
        await communicator.disconnect()
    
    async def test_disconnect_cleans_up(self, ws_communicator, user, test_chat):
        """При отключении происходит отписка от всех групп."""
        communicator = await ws_communicator(user=user)
        
        connected, _ = await communicator.connect()
        assert connected
        
        # Отключаемся
        await communicator.disconnect()
        
        # После отключения не должно быть ошибок

@pytest.mark.asyncio
class TestUserConsumerChatManagement:
    """Тесты управления активным чатом."""
    
    async def test_open_chat(self, ws_communicator, user, test_chat):
        """Открытие чата устанавливает active_chat_id."""
        communicator = await ws_communicator(user=user)
        
        connected, _ = await communicator.connect()
        assert connected
        
        # Отправляем команду открытия чата
        await communicator.send_json_to({
            "action": "open_chat",
            "chat_id": test_chat.id,
            "load_history": False
        })
        
        # Ожидаем подтверждение
        response = await communicator.receive_json_from(timeout=5)
        
        assert response["type"] == "chat_opened"
        assert response["chat_id"] == test_chat.id
        
        await communicator.disconnect()

    async def test_open_chat_marks_related_notifications_as_read(self, ws_communicator, user, test_chat):
        """Открытие конкретного чата читает только связанные с ним уведомления."""
        related_notification = await database_sync_to_async(Notification.objects.create)(
            recipient=user,
            verb='chat_new_message',
            description='Chat notification',
            action_url=f'/messages/{test_chat.id}',
            data={'chat_id': test_chat.id, 'message_id': 10},
        )
        unrelated_notification = await database_sync_to_async(Notification.objects.create)(
            recipient=user,
            verb='chat_new_message',
            description='Other chat notification',
            action_url='/messages/999',
            data={'chat_id': 999, 'message_id': 11},
        )

        communicator = await ws_communicator(user=user)

        connected, _ = await communicator.connect()
        assert connected

        await communicator.send_json_to({
            'action': 'open_chat',
            'chat_id': test_chat.id,
            'load_history': False,
        })

        response = await communicator.receive_json_from(timeout=5)
        assert response['type'] == 'chat_opened'
        assert response['chat_id'] == test_chat.id

        read_all_event = await communicator.receive_json_from(timeout=5)
        assert read_all_event['type'] == 'notifications_read_all'
        assert related_notification.id in read_all_event['notification_ids']
        assert unrelated_notification.id not in read_all_event['notification_ids']

        count_event = await communicator.receive_json_from(timeout=5)
        assert count_event['type'] == 'unread_count'
        assert count_event['count'] == 1

        related_notification = await database_sync_to_async(Notification.objects.get)(id=related_notification.id)
        unrelated_notification = await database_sync_to_async(Notification.objects.get)(id=unrelated_notification.id)

        assert related_notification.unread is False
        assert unrelated_notification.unread is True

        await communicator.disconnect()
    
    async def test_open_nonexistent_chat(self, ws_communicator, user):
        """Попытка открыть несуществующий чат возвращает ошибку."""
        communicator = await ws_communicator(user=user)
        
        connected, _ = await communicator.connect()
        assert connected
        
        # Пытаемся открыть несуществующий чат
        await communicator.send_json_to({
            "action": "open_chat",
            "chat_id": 99999
        })
        
        # Ожидаем ошибку
        response = await communicator.receive_json_from(timeout=5)
        
        assert response["type"] == "error"
        assert "not found" in response["error"].lower()
        
        await communicator.disconnect()
    
    async def test_open_chat_without_access(self, ws_communicator, user, user2):
        """Попытка открыть чат без доступа возвращает ошибку."""
        # Создаем чат только для user2
        chat = await database_sync_to_async(Chat.objects.create)(
            name="Private Chat", type="private"
        )
        await database_sync_to_async(ChatMembership.objects.create)(
            chat=chat, user=user2, role="member"
        )
        
        communicator = await ws_communicator(user=user)
        
        connected, _ = await communicator.connect()
        assert connected
        
        # Пытаемся открыть чужой чат
        await communicator.send_json_to({
            "action": "open_chat",
            "chat_id": chat.id
        })
        
        # Ожидаем ошибку
        response = await communicator.receive_json_from(timeout=5)
        
        assert response["type"] == "error"
        assert "access denied" in response["error"].lower()
        
        await communicator.disconnect()
    
    async def test_close_chat(self, ws_communicator, user, test_chat):
        """Закрытие чата сбрасывает active_chat_id."""
        communicator = await ws_communicator(user=user)
        
        connected, _ = await communicator.connect()
        assert connected
        
        # Открываем чат
        await communicator.send_json_to({
            "action": "open_chat",
            "chat_id": test_chat.id
        })
        await communicator.receive_json_from(timeout=5)
        
        # Закрываем чат
        await communicator.send_json_to({
            "action": "close_chat",
            "chat_id": test_chat.id
        })
        
        # Ожидаем подтверждение
        response = await communicator.receive_json_from(timeout=5)
        
        assert response["type"] == "chat_closed"
        assert response["chat_id"] == test_chat.id
        
        await communicator.disconnect()


@pytest.mark.asyncio
class TestUserConsumerTypingIndicator:
    """Тесты индикатора печати."""
    
    async def test_typing_indicator(self, ws_communicator, user, test_chat):
        """Отправка события 'typing' для активного чата."""
        communicator = await ws_communicator(user=user)
        
        connected, _ = await communicator.connect()
        assert connected
        
        # Открываем чат
        await communicator.send_json_to({
            "action": "open_chat",
            "chat_id": test_chat.id
        })
        await communicator.receive_json_from(timeout=5)
        
        # Отправляем typing
        await communicator.send_json_to({
            "action": "typing",
            "chat_id": test_chat.id
        })
        
        # Можем проверить через channel layer что событие отправлено
        # (требует mock или интеграционный тест)
        
        await communicator.disconnect()
    
    async def test_stop_typing_on_disconnect(self, ws_communicator, user, test_chat):
        """При отключении статус 'typing' сбрасывается."""
        communicator = await ws_communicator(user=user)
        
        connected, _ = await communicator.connect()
        assert connected
        
        # Открываем чат
        await communicator.send_json_to({
            "action": "open_chat",
            "chat_id": test_chat.id
        })
        await communicator.receive_json_from(timeout=5)
        
        # Устанавливаем typing
        await communicator.send_json_to({
            "action": "typing",
            "chat_id": test_chat.id
        })
        
        # Отключаемся (должно сбросить typing)
        await communicator.disconnect()


@pytest.mark.asyncio
class TestUserConsumerMessageActions:
    """Тесты действий с сообщениями через WebSocket."""
    
    async def test_send_message_requires_open_chat(self, ws_communicator, user, test_chat):
        """Отправка сообщения требует открытого чата."""
        communicator = await ws_communicator(user=user)
        
        connected, _ = await communicator.connect()
        assert connected
        
        # Пытаемся отправить сообщение без открытого чата
        await communicator.send_json_to({
            "action": "send_message",
            "content": "Test message"
        })
        
        # Должна быть ошибка или сообщение игнорируется
        # (зависит от реализации)
        
        await communicator.disconnect()
    
    async def test_mark_read(self, ws_communicator, user, test_chat):
        """Отметка сообщений как прочитанных."""
        communicator = await ws_communicator(user=user)
        
        connected, _ = await communicator.connect()
        assert connected
        
        # Открываем чат
        await communicator.send_json_to({
            "action": "open_chat",
            "chat_id": test_chat.id
        })
        await communicator.receive_json_from(timeout=5)
        
        # Отправляем mark_read
        await communicator.send_json_to({
            "action": "mark_read",
            "chat_id": test_chat.id
        })
        
        # Проверяем, что ChatReadState обновлен
        # (требует дополнительной проверки в БД)
        
        await communicator.disconnect()

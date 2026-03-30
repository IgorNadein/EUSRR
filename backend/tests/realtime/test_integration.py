# tests/realtime/test_integration.py
"""
Интеграционные тесты для realtime приложения.
Проверяем взаимодействие WebSocket с базой данных и channel layer.
"""
import pytest
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator

from communications.models import Chat, ChatMembership, Message

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.asyncio
class TestRealtimeIntegration:
    """Интеграционные тесты WebSocket с базой данных."""
    
    async def test_message_broadcast_to_chat_members(
        self, ws_communicator, user, user2, test_chat_with_users
    ):
        """
        Сообщение в чате должно транслироваться всем участникам.
        Интеграционный тест: создаем 2 подключения и проверяем broadcast.
        """
        # Подключаем обоих пользователей
        comm1 = await ws_communicator(user=user)
        comm2 = await ws_communicator(user=user2)
        
        connected1, _ = await comm1.connect()
        connected2, _ = await comm2.connect()
        
        assert connected1 and connected2
        
        # Оба открывают один чат
        await comm1.send_json_to({
            "action": "open_chat",
            "chat_id": test_chat_with_users.id
        })
        await comm2.send_json_to({
            "action": "open_chat",
            "chat_id": test_chat_with_users.id
        })
        
        # Получаем подтверждения
        await comm1.receive_json_from(timeout=5)
        await comm2.receive_json_from(timeout=5)
        
        # user1 отправляет сообщение через channel layer
        # (имитируем отправку через API или другой механизм)
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"chat_{test_chat_with_users.id}",
            {
                "type": "chat_message",
                "chat_id": test_chat_with_users.id,
                "payload": {
                    "id": 1,
                    "content": "Test broadcast message",
                    "author_id": user.id,
                    "author_name": user.get_full_name(),
                }
            }
        )
        
        # Оба пользователя должны получить сообщение
        msg1 = await comm1.receive_json_from(timeout=5)
        msg2 = await comm2.receive_json_from(timeout=5)
        
        assert msg1["type"] == "new_message"
        assert msg2["type"] == "new_message"
        assert msg1["message"]["content"] == "Test broadcast message"
        assert msg2["message"]["content"] == "Test broadcast message"
        
        await comm1.disconnect()
        await comm2.disconnect()
    
    async def test_notification_delivery(self, ws_communicator, user):
        """
        Уведомление должно доставляться через личный канал пользователя.
        """
        communicator = await ws_communicator(user=user)
        
        connected, _ = await communicator.connect()
        assert connected
        
        # Отправляем уведомление через channel layer
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"notifications_{user.id}",
            {
                "type": "notification_new",
                "notification": {
                    "id": 1,
                    "title": "Test Notification",
                    "message": "Test notification message"
                }
            }
        )
        
        # Пользователь должен получить уведомление
        notification = await communicator.receive_json_from(timeout=5)
        
        assert notification["type"] == "notification"
        assert notification["notification"]["title"] == "Test Notification"
        
        await communicator.disconnect()
    
    async def test_chat_list_update(self, ws_communicator, user, test_chat):
        """
        Обновление списка чатов при новом сообщении в неактивном чате.
        """
        communicator = await ws_communicator(user=user)
        
        connected, _ = await communicator.connect()
        assert connected
        
        # НЕ открываем чат (он неактивный)
        
        # Отправляем сообщение в чат через channel layer
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"chat_{test_chat.id}",
            {
                "type": "chat_message",
                "chat_id": test_chat.id,
                "payload": {
                    "id": 1,
                    "content": "Update list message",
                    "author_id": user.id,
                }
            }
        )
        
        # Должны получить обновление списка (list_update)
        update = await communicator.receive_json_from(timeout=5)
        
        assert update["type"] == "list_update"
        assert update["chat_id"] == test_chat.id
        
        await communicator.disconnect()

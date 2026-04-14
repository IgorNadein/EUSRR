# tests/realtime/test_integration.py
"""
Интеграционные тесты для realtime приложения.
Проверяем взаимодействие WebSocket с базой данных и channel layer.
"""
import pytest
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from django.contrib.contenttypes.models import ContentType

from communications.models import Chat, ChatMembership, Message
from employees.models import Department

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

    async def test_visible_department_comments_chat_updates_list_for_active_user(
        self, ws_communicator, user
    ):
        """
        Видимый comments-chat отдела должен попадать в realtime-подписки
        и присылать list_update для страницы списка чатов.
        """
        department = await database_sync_to_async(Department.objects.create)(
            name="Finance",
        )
        department_ct = await database_sync_to_async(ContentType.objects.get_for_model)(Department)
        comments_chat = await database_sync_to_async(Chat.objects.create)(
            type="comments",
            name=department.name,
            flags={"show_in_messages": True},
            context_content_type=department_ct,
            context_object_id=department.id,
        )

        communicator = await ws_communicator(user=user)

        connected, _ = await communicator.connect()
        assert connected

        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"chat_{comments_chat.id}",
            {
                "type": "chat_message",
                "chat_id": comments_chat.id,
                "payload": {
                    "id": 1,
                    "content": "Department chat message",
                    "author_id": user.id,
                },
            },
        )

        update = await communicator.receive_json_from(timeout=5)

        assert update["type"] == "list_update"
        assert update["chat_id"] == comments_chat.id

        await communicator.disconnect()

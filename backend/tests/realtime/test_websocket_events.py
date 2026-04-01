# tests/realtime/test_websocket_events.py
"""
Тесты для WebSocket событий из API.

Проверяем что Consumer правильно обрабатывает события от channel_layer:
- Создание сообщения
- Редактирование сообщения
- Удаление сообщения
- Добавление/удаление реакций
- Голосование в опросе
- Отметка прочтения

Тесты не создают реальные Django объекты, а проверяют только
правильность обработки событий Consumer'ом.
"""
import pytest
from channels.layers import get_channel_layer

pytestmark = pytest.mark.django_db(transaction=True)


class TestMessageWebSocketEvents:
    """Тесты WebSocket событий для сообщений."""
    
    @pytest.mark.asyncio
    async def test_new_message_broadcast(self, ws_communicator, user, user2, test_chat_with_users):
        """При создании нового сообщения оба участника получают событие."""
        # Подключаем обоих пользователей
        comm1 = await ws_communicator(user=user)
        comm2 = await ws_communicator(user=user2)
        
        connected1, _ = await comm1.connect()
        connected2, _ = await comm2.connect()
        assert connected1 and connected2
        
        # User1 открывает чат
        await comm1.send_json_to({
            "action": "open_chat",
            "chat_id": test_chat_with_users.id,
            "load_history": False
        })
        
        # User2 тоже открывает чат
        await comm2.send_json_to({
            "action": "open_chat",
            "chat_id": test_chat_with_users.id,
            "load_history": False
        })
        
        # Подтверждения открытия
        await comm1.receive_json_from(timeout=5)
        await comm2.receive_json_from(timeout=5)
        
        # Отправляем событие через channel layer (имитируем API)
        channel_layer = get_channel_layer()
        mock_payload = {
            'id': 999,
            'content': 'Test message',
            'author_id': user.id,
            'author_name': user.get_full_name(),
            'chat_id': test_chat_with_users.id,
            'created_at': '2026-01-21T10:00:00Z'
        }
        
        await channel_layer.group_send(
            f'chat_{test_chat_with_users.id}',
            {
                'type': 'chat.message',
                'chat_id': test_chat_with_users.id,
                'payload': mock_payload
            }
        )
        
        # User1 должен получить new_message (активный чат)
        response1 = await comm1.receive_json_from(timeout=5)
        assert response1["type"] == "new_message"
        assert response1["chat_id"] == test_chat_with_users.id
        assert response1["message"]["content"] == "Test message"
        
        # И list_update для списка чатов
        response1_list = await comm1.receive_json_from(timeout=5)
        assert response1_list["type"] == "list_update"
        
        # User2 тоже должен получить оба события
        response2 = await comm2.receive_json_from(timeout=5)
        assert response2["type"] == "new_message"
        
        response2_list = await comm2.receive_json_from(timeout=5)
        assert response2_list["type"] == "list_update"
        
        await comm1.disconnect()
        await comm2.disconnect()
    
    @pytest.mark.asyncio
    async def test_new_message_list_update_only(self, ws_communicator, user, user2, test_chat_with_users):
        """Если чат неактивен, пользователь получает только list_update."""
        comm = await ws_communicator(user=user)
        connected, _ = await comm.connect()
        assert connected
        
        # НЕ открываем чат (чтобы он был неактивным)
        
        # Отправляем событие (имитируем API)
        channel_layer = get_channel_layer()
        mock_payload = {
            'id': 998,
            'content': 'Message when chat is inactive',
            'author_id': user2.id,
            'author_name': user2.get_full_name(),
            'chat_id': test_chat_with_users.id
        }
        
        await channel_layer.group_send(
            f'chat_{test_chat_with_users.id}',
            {
                'type': 'chat.message',
                'chat_id': test_chat_with_users.id,
                'payload': mock_payload
            }
        )
        
        # Когда чат неактивен, Consumer отправляет только list_update
        response = await comm.receive_json_from(timeout=5)
        assert response["type"] == "list_update"
        assert response["chat_id"] == test_chat_with_users.id
    
    @pytest.mark.asyncio
    async def test_message_edited_broadcast(self, ws_communicator, user, test_chat):
        """При редактировании сообщения участники получают событие."""
        comm = await ws_communicator(user=user)
        connected, _ = await comm.connect()
        assert connected
        
        # Открываем чат
        await comm.send_json_to({
            "action": "open_chat",
            "chat_id": test_chat.id,
            "load_history": False
        })
        await comm.receive_json_from(timeout=5)  # chat_opened
        
        # Отправляем событие редактирования (имитируем API)
        channel_layer = get_channel_layer()
        mock_payload = {
            'id': 997,
            'content': 'Edited content',
            'is_edited': True,
            'author_id': user.id,
            'chat_id': test_chat.id
        }
        
        await channel_layer.group_send(
            f'chat_{test_chat.id}',
            {
                'type': 'chat.message_edited',
                'chat_id': test_chat.id,
                'payload': mock_payload
            }
        )
        
        # Должны получить message_updated для активного чата
        response1 = await comm.receive_json_from(timeout=5)
        assert response1["type"] == "message_updated"
        assert response1["message"]["content"] == "Edited content"
        assert response1["message"]["is_edited"] is True
        
        # И message_edited для списка
        response2 = await comm.receive_json_from(timeout=5)
        assert response2["type"] == "message_edited"
        
        await comm.disconnect()
    
    @pytest.mark.asyncio
    async def test_message_deleted_broadcast(self, ws_communicator, user, test_chat):
        """При удалении сообщения участники получают событие."""
        comm = await ws_communicator(user=user)
        connected, _ = await comm.connect()
        assert connected
        
        # Открываем чат
        await comm.send_json_to({
            "action": "open_chat",
            "chat_id": test_chat.id,
            "load_history": False
        })
        await comm.receive_json_from(timeout=5)  # chat_opened
        
        # Отправляем событие удаления (имитируем API)
        channel_layer = get_channel_layer()
        mock_message_id = 996
        
        await channel_layer.group_send(
            f'chat_{test_chat.id}',
            {
                'type': 'chat.message_deleted',
                'chat_id': test_chat.id,
                'message_id': mock_message_id
            }
        )
        
        # Должны получить message_deleted
        response = await comm.receive_json_from(timeout=5)
        assert response["type"] == "message_deleted"
        assert response["chat_id"] == test_chat.id
        assert response["message_id"] == mock_message_id
        
        await comm.disconnect()
    
    @pytest.mark.asyncio
    async def test_message_deleted_inactive_chat(self, ws_communicator, user, test_chat):
        """Если чат неактивен, событие удаления НЕ отправляется клиенту."""
        comm = await ws_communicator(user=user)
        connected, _ = await comm.connect()
        assert connected
        
        # НЕ открываем чат
        
        # Отправляем событие удаления (имитируем API)
        channel_layer = get_channel_layer()
        mock_message_id = 995
        
        await channel_layer.group_send(
            f'chat_{test_chat.id}',
            {
                'type': 'chat.message_deleted',
                'chat_id': test_chat.id,
                'message_id': mock_message_id
            }
        )
        
        # НЕ должны получить событие (чат неактивен)
        # Проверяем что не получим ничего в течение короткого таймаута
        import asyncio
        with pytest.raises(asyncio.TimeoutError):
            await comm.receive_json_from(timeout=2)


class TestReactionWebSocketEvents:
    """Тесты WebSocket событий для реакций."""
    
    @pytest.mark.asyncio
    async def test_reaction_added_broadcast(self, ws_communicator, user, user2, test_chat_with_users):
        """При добавлении реакции участники получают событие."""
        # Подключаем обоих пользователей
        comm1 = await ws_communicator(user=user)
        comm2 = await ws_communicator(user=user2)
        
        connected1, _ = await comm1.connect()
        connected2, _ = await comm2.connect()
        assert connected1 and connected2
        
        # Оба открывают чат
        await comm1.send_json_to({
            "action": "open_chat",
            "chat_id": test_chat_with_users.id,
            "load_history": False
        })
        await comm2.send_json_to({
            "action": "open_chat",
            "chat_id": test_chat_with_users.id,
            "load_history": False
        })
        
        await comm1.receive_json_from(timeout=5)  # chat_opened
        await comm2.receive_json_from(timeout=5)  # chat_opened
        
        # Отправляем событие реакции (имитируем API)
        channel_layer = get_channel_layer()
        mock_message_id = 994
        
        reactions_summary = {
            '👍': {
                'count': 1,
                'users': [user2.id],
                'user_names': [user2.get_full_name()]
            }
        }
        
        await channel_layer.group_send(
            f'chat_{test_chat_with_users.id}',
            {
                'type': 'chat.reaction_added',
                'chat_id': test_chat_with_users.id,
                'message_id': mock_message_id,
                'user_id': user2.id,
                'emoji': '👍',
                'reactions_summary': reactions_summary
            }
        )
        
        # User1 должен получить reaction_added
        response1 = await comm1.receive_json_from(timeout=5)
        assert response1["type"] == "reaction_added"
        assert response1["message_id"] == mock_message_id
        assert response1["emoji"] == '👍'
        assert response1["user_id"] == user2.id
        assert '👍' in response1["reactions_summary"]
        
        # User2 тоже должен получить
        response2 = await comm2.receive_json_from(timeout=5)
        assert response2["type"] == "reaction_added"
        assert response2["emoji"] == '👍'
        
        await comm1.disconnect()
        await comm2.disconnect()
    
    @pytest.mark.asyncio
    async def test_reaction_removed_broadcast(self, ws_communicator, user, test_chat):
        """При удалении реакции участники получают событие."""
        comm = await ws_communicator(user=user)
        connected, _ = await comm.connect()
        assert connected
        
        # Открываем чат
        await comm.send_json_to({
            "action": "open_chat",
            "chat_id": test_chat.id,
            "load_history": False
        })
        await comm.receive_json_from(timeout=5)  # chat_opened
        
        # Отправляем событие удаления реакции (имитируем API)
        channel_layer = get_channel_layer()
        mock_message_id = 993
        
        reactions_summary = {}  # Пустой - все реакции удалены
        
        await channel_layer.group_send(
            f'chat_{test_chat.id}',
            {
                'type': 'chat.reaction_removed',
                'chat_id': test_chat.id,
                'message_id': mock_message_id,
                'user_id': user.id,
                'emoji': '👍',
                'reactions_summary': reactions_summary
            }
        )
        
        # Должны получить reaction_removed
        response = await comm.receive_json_from(timeout=5)
        assert response["type"] == "reaction_removed"
        assert response["message_id"] == mock_message_id
        assert response["emoji"] == '👍'
        assert response["reactions_summary"] == {}
        
        await comm.disconnect()
    
    @pytest.mark.asyncio
    async def test_reaction_inactive_chat_no_event(self, ws_communicator, user, test_chat):
        """Если чат неактивен, событие реакции НЕ отправляется."""
        comm = await ws_communicator(user=user)
        connected, _ = await comm.connect()
        assert connected
        
        # НЕ открываем чат
        
        # Отправляем событие реакции (имитируем API)
        channel_layer = get_channel_layer()
        mock_message_id = 992
        
        await channel_layer.group_send(
            f'chat_{test_chat.id}',
            {
                'type': 'chat.reaction_added',
                'chat_id': test_chat.id,
                'message_id': mock_message_id,
                'user_id': user.id,
                'emoji': '👍',
                'reactions_summary': {}
            }
        )
        
        # НЕ должны получить событие
        import asyncio
        with pytest.raises(asyncio.TimeoutError):
            await comm.receive_json_from(timeout=2)


class TestPollWebSocketEvents:
    """Тесты WebSocket событий для голосований."""
    
    @pytest.mark.asyncio
    async def test_poll_vote_broadcast(self, ws_communicator, user, user2, test_chat_with_users):
        """При голосовании участники получают обновление."""
        comm1 = await ws_communicator(user=user)
        comm2 = await ws_communicator(user=user2)
        
        connected1, _ = await comm1.connect()
        connected2, _ = await comm2.connect()
        assert connected1 and connected2
        
        # Оба открывают чат
        await comm1.send_json_to({
            "action": "open_chat",
            "chat_id": test_chat_with_users.id,
            "load_history": False
        })
        await comm2.send_json_to({
            "action": "open_chat",
            "chat_id": test_chat_with_users.id,
            "load_history": False
        })
        
        await comm1.receive_json_from(timeout=5)
        await comm2.receive_json_from(timeout=5)
        
        # Отправляем событие обновления опроса (имитируем API)
        channel_layer = get_channel_layer()
        mock_poll_id = 991
        mock_message_id = 990
        
        await channel_layer.group_send(
            f'chat_{test_chat_with_users.id}',
            {
                'type': 'chat.poll_update',
                'chat_id': test_chat_with_users.id,
                'payload': {
                    'poll_id': mock_poll_id,
                    'message_id': mock_message_id,
                    'total_voters': 1,
                    'results': {
                        'options': [
                            {'id': 1, 'vote_count': 1}
                        ]
                    }
                }
            }
        )
        
        # User1 должен получить poll_update
        response1 = await comm1.receive_json_from(timeout=5)
        assert response1["type"] == "poll_update"
        assert response1["poll_id"] == mock_poll_id
        assert response1["message_id"] == mock_message_id
        
        # User2 тоже
        response2 = await comm2.receive_json_from(timeout=5)
        assert response2["type"] == "poll_update"
        
        await comm1.disconnect()
        await comm2.disconnect()
    
    @pytest.mark.asyncio
    async def test_poll_update_inactive_chat(self, ws_communicator, user, test_chat):
        """Если чат неактивен, событие опроса НЕ отправляется."""
        comm = await ws_communicator(user=user)
        connected, _ = await comm.connect()
        assert connected
        
        # НЕ открываем чат
        
        # Отправляем событие (имитируем API)
        channel_layer = get_channel_layer()
        mock_poll_id = 989
        
        await channel_layer.group_send(
            f'chat_{test_chat.id}',
            {
                'type': 'chat.poll_update',
                'chat_id': test_chat.id,
                'payload': {
                    'poll_id': mock_poll_id
                }
            }
        )
        
        # НЕ должны получить
        import asyncio
        with pytest.raises(asyncio.TimeoutError):
            await comm.receive_json_from(timeout=2)


class TestChatMarkedReadEvent:
    """Тесты WebSocket события отметки прочтения."""
    
    @pytest.mark.asyncio
    async def test_marked_read_sync_between_tabs(self, ws_communicator, user, test_chat):
        """Отметка прочтения синхронизируется между вкладками пользователя."""
        # Имитируем две вкладки одного пользователя
        comm1 = await ws_communicator(user=user)
        comm2 = await ws_communicator(user=user)
        
        connected1, _ = await comm1.connect()
        connected2, _ = await comm2.connect()
        assert connected1 and connected2
        
        # Отправляем событие marked_read в канал пользователя (имитируем API)
        channel_layer = get_channel_layer()
        mock_message_id = 988
        
        await channel_layer.group_send(
            f'user_{user.id}',
            {
                'type': 'chat_marked_read',
                'chat_id': test_chat.id,
                'last_read_at': '2026-01-21T10:00:00Z',
                'last_read_message_id': mock_message_id
            }
        )
        
        # Обе вкладки должны получить событие
        response1 = await comm1.receive_json_from(timeout=5)
        assert response1["type"] == "marked_read"
        assert response1["chat_id"] == test_chat.id
        assert response1["last_read_message_id"] == mock_message_id
        
        response2 = await comm2.receive_json_from(timeout=5)
        assert response2["type"] == "marked_read"
        assert response2["chat_id"] == test_chat.id
        
        await comm1.disconnect()
        await comm2.disconnect()
    
    @pytest.mark.asyncio
    async def test_marked_read_not_received_by_other_users(self, ws_communicator, user, user2, test_chat_with_users):
        """Событие marked_read получает только тот пользователь, который отметил."""
        comm1 = await ws_communicator(user=user)
        comm2 = await ws_communicator(user=user2)
        
        connected1, _ = await comm1.connect()
        connected2, _ = await comm2.connect()
        assert connected1 and connected2
        
        # User1 отмечает как прочитанное (имитируем API)
        channel_layer = get_channel_layer()
        mock_message_id = 987
        
        await channel_layer.group_send(
            f'user_{user.id}',  # ТОЛЬКО user1
            {
                'type': 'chat_marked_read',
                'chat_id': test_chat_with_users.id,
                'last_read_at': '2026-01-21T10:00:00Z',
                'last_read_message_id': mock_message_id
            }
        )
        
        # User1 должен получить
        response1 = await comm1.receive_json_from(timeout=5)
        assert response1["type"] == "marked_read"
        
        # User2 НЕ должен получить
        import asyncio
        with pytest.raises(asyncio.TimeoutError):
            await comm2.receive_json_from(timeout=2)
        await comm1.disconnect()
        await comm2.disconnect()

class TestNotificationStateEvents:
    """Тесты синхронизации состояния уведомлений через user channel."""

    @pytest.mark.asyncio
    async def test_notification_read_sync_between_sessions(self, ws_communicator, user):
        comm1 = await ws_communicator(user=user)
        comm2 = await ws_communicator(user=user)

        connected1, _ = await comm1.connect()
        connected2, _ = await comm2.connect()
        assert connected1 and connected2

        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f'user_{user.id}',
            {
                'type': 'notification_read',
                'notification_id': 321,
                'unread_count': 4,
            }
        )

        response1 = await comm1.receive_json_from(timeout=5)
        response2 = await comm2.receive_json_from(timeout=5)

        assert response1['type'] == 'notification_read'
        assert response1['notification_id'] == 321
        assert response1['unread_count'] == 4
        assert response2['type'] == 'notification_read'

        await comm1.disconnect()
        await comm2.disconnect()

    @pytest.mark.asyncio
    async def test_notifications_read_all_sync_between_sessions(self, ws_communicator, user):
        comm1 = await ws_communicator(user=user)
        comm2 = await ws_communicator(user=user)

        connected1, _ = await comm1.connect()
        connected2, _ = await comm2.connect()
        assert connected1 and connected2

        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f'user_{user.id}',
            {
                'type': 'notifications_read_all',
                'notification_ids': [11, 12, 13],
                'category': 'Заявки',
                'unread_count': 0,
            }
        )

        response1 = await comm1.receive_json_from(timeout=5)
        response2 = await comm2.receive_json_from(timeout=5)

        assert response1['type'] == 'notifications_read_all'
        assert response1['notification_ids'] == [11, 12, 13]
        assert response1['category'] == 'Заявки'
        assert response1['unread_count'] == 0
        assert response2['type'] == 'notifications_read_all'

        await comm1.disconnect()
        await comm2.disconnect()

# realtime/consumers.py
"""
WebSocket Consumer для пользователя.
Универсальное WebSocket соединение для всех real-time операций:
- Чаты и сообщения
- Уведомления
- Обновления бейджей
- Онлайн-статус
- Календарь и другие real-time события
"""
import asyncio
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from django.db.models import Q
from django.utils import timezone

from communications.models import Chat, ChatMembership, ChatReadState, Message, MessageReaction
from communications.consumers import serialize_message


class UserConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket Consumer для пользователя.
    Управляет всеми real-time обновлениями:
    - Чаты: обновления списка (бейдж, карточки), сообщения в активном чате
    - Реакции, редактирование, удаление сообщений
    - Индикатор "печатает..."
    - Уведомления
    - Бейджи в sidebar
    - Онлайн-статус
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ping_task = None
        self.ping_interval = 20  # Ping каждые 20 секунд
        self.active_chat_id = None  # ID открытого чата
        self.subscribed_chats = set()  # Чаты, на которые подписан
        self.user = None
    
    async def connect(self):
        """Подключение пользователя - подписка на все его чаты и каналы"""
        self.user = self.scope.get("user")
        
        if not self.user or isinstance(self.user, AnonymousUser) or not self.user.is_authenticated:
            await self.close(code=4401)
            return
        
        # Получаем все чаты пользователя
        chat_ids = await self._get_available_chat_ids(self.user)
        
        # Подписываемся на группы всех чатов
        for chat_id in chat_ids:
            group_name = f"chat_{chat_id}"
            await self.channel_layer.group_add(group_name, self.channel_name)
            self.subscribed_chats.add(chat_id)
        
        # Подписываемся на личный канал пользователя (для уведомлений)
        user_channel = f"user_{self.user.id}"
        await self.channel_layer.group_add(user_channel, self.channel_name)
        
        # Подписываемся на канал уведомлений
        notifications_channel = f"notifications_{self.user.id}"
        await self.channel_layer.group_add(notifications_channel, self.channel_name)
        
        await self.accept()
        
        # Запускаем ping цикл для keepalive
        self.ping_task = asyncio.create_task(self._ping_loop())
        
        print(f"[UserWS] User {self.user.id} connected, subscribed to {len(self.subscribed_chats)} chats")
    
    async def disconnect(self, code):
        """Отключение - отписка от всех групп"""
        # Останавливаем ping цикл
        if self.ping_task:
            self.ping_task.cancel()
            try:
                await self.ping_task
            except asyncio.CancelledError:
                pass
        
        # Сбрасываем статус "набирает текст" если был активный чат
        if self.active_chat_id and self.user:
            chat = await self._get_chat(self.active_chat_id)
            if chat:
                await self._set_typing_status(chat, self.user, False)
        
        # Отписываемся от всех групп чатов
        for chat_id in self.subscribed_chats:
            group_name = f"chat_{chat_id}"
            await self.channel_layer.group_discard(group_name, self.channel_name)
        
        # Отписываемся от личных каналов
        if self.user:
            user_channel = f"user_{self.user.id}"
            await self.channel_layer.group_discard(user_channel, self.channel_name)
            
            notifications_channel = f"notifications_{self.user.id}"
            await self.channel_layer.group_discard(notifications_channel, self.channel_name)
        
        print(f"[UserWS] User {self.user.id if self.user else 'unknown'} disconnected")
    
    async def _ping_loop(self):
        """Отправка ping каждые N секунд для keepalive"""
        try:
            while True:
                await asyncio.sleep(self.ping_interval)
                await self.send_json({
                    "type": "ping",
                    "timestamp": timezone.now().isoformat()
                })
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[UserWS] Ping loop error: {e}")
    
    async def receive_json(self, content, **kwargs):
        """Обработка входящих сообщений от клиента"""
        if not isinstance(content, dict):
            return
        
        action = content.get("action", "")
        
        print(f"[UserWS] receive_json: action={action}, user={self.user.id}, active_chat={self.active_chat_id}")
        
        # Управление активным чатом
        if action == "open_chat":
            await self._handle_open_chat(content)
        elif action == "close_chat":
            await self._handle_close_chat(content)
        
        # Работа с сообщениями (только для активного чата)
        elif action == "send_message":
            await self._handle_send_message(content)
        elif action == "edit_message":
            await self._handle_edit_message(content)
        elif action == "delete_message":
            await self._handle_delete_message(content)
        
        # Реакции
        elif action == "add_reaction":
            await self._handle_add_reaction(content)
        elif action == "remove_reaction":
            await self._handle_remove_reaction(content)
        
        # Индикатор печати
        elif action == "typing":
            await self._handle_typing(content)
        elif action == "stop_typing":
            await self._handle_stop_typing()
        
        # Отметка прочитанного
        elif action == "mark_read":
            await self._handle_mark_read(content)
        
        # Голосования
        elif action == "vote_poll":
            await self._handle_vote_poll(content)
    
    # ==================== Управление активным чатом ====================
    
    async def _handle_open_chat(self, content):
        """Открытие чата - установка активного чата и отправка начальной истории"""
        chat_id = content.get("chat_id")
        if not chat_id:
            return
        
        chat_id = int(chat_id)
        
        # Проверяем доступ
        chat = await self._get_chat(chat_id)
        if not chat or not await self._user_can_access(chat, self.user):
            await self.send_json({
                "type": "error",
                "error": "Chat not found or access denied",
                "chat_id": chat_id
            })
            return
        
        # Устанавливаем активный чат
        self.active_chat_id = chat_id
        
        # Отправляем начальную историю (если запрошена)
        if content.get("load_history", False):
            await self._send_initial_messages(chat_id)
        
        # Помечаем как прочитанное
        await self._mark_read(chat, self.user)
        
        await self.send_json({
            "type": "chat_opened",
            "chat_id": chat_id
        })
        
        print(f"[UserWS] User {self.user.id} opened chat {chat_id}")
    
    async def _handle_close_chat(self, content):
        """Закрытие чата - сброс активного чата"""
        chat_id = content.get("chat_id")
        
        if chat_id and int(chat_id) == self.active_chat_id:
            # Сбрасываем индикатор печати
            if self.active_chat_id:
                chat = await self._get_chat(self.active_chat_id)
                if chat:
                    await self._set_typing_status(chat, self.user, False)
            
            self.active_chat_id = None
            
            await self.send_json({
                "type": "chat_closed",
                "chat_id": chat_id
            })
            
            print(f"[UserWS] User {self.user.id} closed chat {chat_id}")
    
    # ==================== Обработчики событий из channel layer ====================
    
    async def chat_message(self, event):
        """
        Новое сообщение в чате.
        Отправляем полные данные для активного чата,
        компактные - для обновления списка.
        """
        chat_id = event.get("chat_id")
        payload = event.get("payload", {})
        
        # Для активного чата - полное сообщение
        if chat_id == self.active_chat_id:
            await self.send_json({
                "type": "new_message",
                "chat_id": chat_id,
                "message": payload
            })
        
        # Для списка чатов - компактное обновление
        await self.send_json({
            "type": "list_update",
            "chat_id": chat_id,
            "message": payload
        })
    
    async def chat_message_edited(self, event):
        """Сообщение отредактировано"""
        chat_id = event.get("chat_id")
        payload = event.get("payload", {})
        
        # Для активного чата - обновляем сообщение
        if chat_id == self.active_chat_id:
            await self.send_json({
                "type": "message_updated",
                "chat_id": chat_id,
                "message": payload
            })
        
        # Для списка - обновляем если это последнее сообщение
        await self.send_json({
            "type": "message_edited",
            "chat_id": chat_id,
            "message": payload
        })
    
    async def chat_message_deleted(self, event):
        """Сообщение удалено"""
        import logging
        logger = logging.getLogger(__name__)
        
        chat_id = event.get("chat_id")
        message_id = event.get("message_id")
        
        logger.info(
            "[USER_WS_DELETE] Received event: chat_id=%s, message_id=%s",
            chat_id, message_id
        )
        logger.info(
            "[USER_WS_DELETE] Active chat: %s, matches=%s",
            self.active_chat_id, chat_id == self.active_chat_id
        )
        
        if chat_id == self.active_chat_id:
            logger.info(
                "[USER_WS_DELETE] Sending to client: message_id=%s",
                message_id
            )
            await self.send_json({
                "type": "message_deleted",
                "chat_id": chat_id,
                "message_id": message_id
            })
            logger.info(
                "[USER_WS_DELETE] Sent to client successfully"
            )
        else:
            logger.info(
                "[USER_WS_DELETE] Skipping - not active chat"
            )
    
    async def chat_reaction_added(self, event):
        """Реакция добавлена"""
        chat_id = event.get("chat_id")
        
        if chat_id == self.active_chat_id:
            await self.send_json({
                "type": "reaction_added",
                "chat_id": chat_id,
                "message_id": event.get("message_id"),
                "emoji": event.get("emoji"),
                "user_id": event.get("user_id"),
                "user_name": event.get("user_name"),
                "reactions_summary": event.get("reactions_summary")
            })
    
    async def chat_reaction_removed(self, event):
        """Реакция удалена"""
        chat_id = event.get("chat_id")
        
        if chat_id == self.active_chat_id:
            await self.send_json({
                "type": "reaction_removed",
                "chat_id": chat_id,
                "message_id": event.get("message_id"),
                "emoji": event.get("emoji"),
                "user_id": event.get("user_id"),
                "reactions_summary": event.get("reactions_summary")
            })
    
    async def chat_user_typing(self, event):
        """Пользователь печатает"""
        chat_id = event.get("chat_id")
        user_id = event.get("user_id")
        
        # Показываем только в активном чате и не показываем свой статус
        if chat_id == self.active_chat_id and user_id != self.user.id:
            await self.send_json({
                "type": "typing_start",
                "chat_id": chat_id,
                "user_id": user_id,
                "user_name": event.get("user_name")
            })
    
    async def chat_user_stopped_typing(self, event):
        """Пользователь перестал печатать"""
        chat_id = event.get("chat_id")
        user_id = event.get("user_id")
        
        if chat_id == self.active_chat_id and user_id != self.user.id:
            await self.send_json({
                "type": "typing_stop",
                "chat_id": chat_id,
                "user_id": user_id
            })
    
    async def chat_poll_update(self, event):
        """Обновление голосования"""
        chat_id = event.get("chat_id")
        payload = event.get("payload", {})
        
        if chat_id == self.active_chat_id:
            await self.send_json({
                "type": "poll_update",
                "chat_id": chat_id,
                "poll_id": payload.get("poll_id"),
                "message_id": payload.get("message_id"),
                "results": payload.get("results")
            })
    
    # ==================== Обработчики уведомлений ====================
    
    async def notification_new(self, event):
        """Новое уведомление (вызывается из notifications/services.py)"""
        await self.send_json({
            "type": "notification",
            "notification": event.get("notification", {})
        })
    
    async def notification_count_update(self, event):
        """
        Обновление счетчика уведомлений.
        Вызывается из notifications/services.py
        """
        await self.send_json({
            "type": "unread_count",
            "count": event.get("count", 0)
        })
    
    # ==================== Обработка действий пользователя ====================
    
    async def _handle_send_message(self, content):
        """Отправка нового сообщения"""
        if not self.active_chat_id:
            await self.send_json({
                "type": "error",
                "error": "No active chat"
            })
            return
        
        text = str(content.get("content") or content.get("text") or "").strip()
        if not text:
            return
        
        chat = await self._get_chat(self.active_chat_id)
        if not chat:
            return
        
        # Проверка прав на отправку
        if chat.type == "announcement" and chat.created_by_id != self.user.id:
            await self.send_json({
                "type": "error",
                "error": "Только автор может публиковать в это объявление"
            })
            return
        
        # Создаем сообщение
        msg = await self._create_message(chat, self.user, text)
        
        if msg:
            # Сериализуем и отправляем всем в группе
            msg_data = await database_sync_to_async(serialize_message)(msg)
            
            await self.channel_layer.group_send(
                f"chat_{chat.id}",
                {
                    "type": "chat_message",
                    "chat_id": chat.id,
                    "payload": msg_data
                }
            )
    
    async def _handle_edit_message(self, content):
        """Редактирование сообщения"""
        if not self.active_chat_id:
            return
        
        message_id = content.get("message_id")
        new_content = content.get("content", "").strip()
        
        if not message_id or not new_content:
            return
        
        msg = await self._get_message(message_id)
        if not msg or msg.author_id != self.user.id:
            return
        
        # Обновляем сообщение
        await self._update_message(msg, new_content)
        
        # Сериализуем и отправляем
        msg_data = await database_sync_to_async(serialize_message)(msg)
        
        await self.channel_layer.group_send(
            f"chat_{msg.chat_id}",
            {
                "type": "chat_message_edited",
                "chat_id": msg.chat_id,
                "payload": msg_data
            }
        )
    
    async def _handle_delete_message(self, content):
        """Удаление сообщения"""
        if not self.active_chat_id:
            return
        
        message_id = content.get("message_id")
        if not message_id:
            return
        
        msg = await self._get_message(message_id)
        if not msg or msg.author_id != self.user.id:
            return
        
        chat_id = msg.chat_id
        
        # Помечаем как удаленное
        await self._soft_delete_message(msg)
        
        await self.channel_layer.group_send(
            f"chat_{chat_id}",
            {
                "type": "chat_message_deleted",
                "chat_id": chat_id,
                "message_id": message_id
            }
        )
    
    async def _handle_add_reaction(self, content):
        """Добавление реакции"""
        message_id = content.get("message_id")
        emoji = content.get("emoji")
        
        if not message_id or not emoji:
            return
        
        msg = await self._get_message(message_id)
        if not msg:
            return
        
        # Создаем реакцию
        created = await self._add_reaction(msg, self.user, emoji)
        
        if created:
            user_name = await database_sync_to_async(
                lambda: self.user.get_full_name() or self.user.username
            )()
            
            await self.channel_layer.group_send(
                f"chat_{msg.chat_id}",
                {
                    "type": "chat_reaction_added",
                    "chat_id": msg.chat_id,
                    "message_id": message_id,
                    "emoji": emoji,
                    "user_id": self.user.id,
                    "user_name": user_name
                }
            )
    
    async def _handle_remove_reaction(self, content):
        """Удаление реакции"""
        message_id = content.get("message_id")
        emoji = content.get("emoji")
        
        if not message_id or not emoji:
            return
        
        msg = await self._get_message(message_id)
        if not msg:
            return
        
        # Удаляем реакцию
        deleted = await self._remove_reaction(msg, self.user, emoji)
        
        if deleted:
            await self.channel_layer.group_send(
                f"chat_{msg.chat_id}",
                {
                    "type": "chat_reaction_removed",
                    "chat_id": msg.chat_id,
                    "message_id": message_id,
                    "emoji": emoji,
                    "user_id": self.user.id
                }
            )
    
    async def _handle_typing(self, content):
        """Индикатор печати"""
        if not self.active_chat_id:
            return
        
        chat = await self._get_chat(self.active_chat_id)
        if not chat:
            return
        
        await self._set_typing_status(chat, self.user, True)
        
        user_name = await database_sync_to_async(
            lambda: self.user.get_full_name() or self.user.username
        )()
        
        await self.channel_layer.group_send(
            f"chat_{chat.id}",
            {
                "type": "chat_user_typing",
                "chat_id": chat.id,
                "user_id": self.user.id,
                "user_name": user_name
            }
        )
    
    async def _handle_stop_typing(self):
        """Остановка индикатора печати"""
        if not self.active_chat_id:
            return
        
        chat = await self._get_chat(self.active_chat_id)
        if not chat:
            return
        
        await self._set_typing_status(chat, self.user, False)
        
        await self.channel_layer.group_send(
            f"chat_{chat.id}",
            {
                "type": "chat_user_stopped_typing",
                "chat_id": chat.id,
                "user_id": self.user.id
            }
        )
    
    async def _handle_mark_read(self, content):
        """Отметка сообщений как прочитанных"""
        chat_id = content.get("chat_id")
        if not chat_id:
            return
        
        chat = await self._get_chat(int(chat_id))
        if not chat:
            return
        
        await self._mark_read(chat, self.user)
    
    async def _handle_vote_poll(self, content):
        """Голосование в опросе"""
        # TODO: Реализовать логику голосования
        pass
    
    # ==================== Вспомогательные методы ====================
    
    async def _send_initial_messages(self, chat_id, limit=50):
        """Отправка начальной истории сообщений"""
        messages = await self._get_recent_messages(chat_id, limit)
        
        await self.send_json({
            "type": "initial_messages",
            "chat_id": chat_id,
            "messages": messages
        })
    
    @database_sync_to_async
    def _get_available_chat_ids(self, user):
        """Получить ID всех доступных чатов пользователя"""
        departments = user.departments.all()
        
        # Получаем ID через membership
        membership_chat_ids = list(
            ChatMembership.objects.filter(user=user).values_list('chat_id', flat=True)
        )
        
        chat_ids = list(
            Chat.objects.filter(
                Q(type="global")
                | Q(type="department", department__in=departments)
                | Q(type="private", participants=user)
                | Q(id__in=membership_chat_ids)
            ).values_list("id", flat=True).distinct()
        )
        
        return chat_ids
    
    @database_sync_to_async
    def _get_chat(self, chat_id):
        """Получить чат по ID"""
        try:
            return Chat.objects.get(pk=chat_id)
        except Chat.DoesNotExist:
            return None
    
    @database_sync_to_async
    def _get_message(self, message_id):
        """Получить сообщение по ID"""
        try:
            return Message.objects.select_related('author', 'chat').get(pk=message_id)
        except Message.DoesNotExist:
            return None
    
    @database_sync_to_async
    def _user_can_access(self, chat, user):
        """Проверка доступа пользователя к чату"""
        if chat.type == "global":
            return True
        
        if chat.type == "private":
            return chat.participants.filter(pk=user.pk).exists()
        
        if chat.type == "group":
            return (
                chat.participants.filter(pk=user.pk).exists()
                or ChatMembership.objects.filter(chat=chat, user=user).exists()
            )
        
        if chat.type == "department" and chat.department_id:
            return chat.get_participants.filter(pk=user.pk).exists()
        
        if chat.type in ("channel", "announcement"):
            if chat.include_all_employees:
                return user.is_active
            return (
                chat.participants.filter(pk=user.pk).exists()
                or ChatMembership.objects.filter(chat=chat, user=user).exists()
            )
        
        return False
    
    @database_sync_to_async
    def _create_message(self, chat, user, content):
        """Создать новое сообщение"""
        try:
            msg = Message.objects.create(
                chat=chat,
                author=user,
                content=content
            )
            return msg
        except Exception as e:
            print(f"Error creating message: {e}")
            return None
    
    @database_sync_to_async
    def _update_message(self, msg, new_content):
        """Обновить содержимое сообщения"""
        msg.content = new_content
        msg.is_edited = True
        msg.edited_at = timezone.now()
        msg.save(update_fields=['content', 'is_edited', 'edited_at'])
    
    @database_sync_to_async
    def _soft_delete_message(self, msg):
        """Мягкое удаление сообщения"""
        msg.is_deleted = True
        msg.content = "[Сообщение удалено]"
        msg.save(update_fields=['is_deleted', 'content'])
    
    @database_sync_to_async
    def _add_reaction(self, msg, user, emoji):
        """Добавить реакцию"""
        reaction, created = MessageReaction.objects.get_or_create(
            message=msg,
            user=user,
            emoji=emoji
        )
        return created
    
    @database_sync_to_async
    def _remove_reaction(self, msg, user, emoji):
        """Удалить реакцию"""
        deleted_count, _ = MessageReaction.objects.filter(
            message=msg,
            user=user,
            emoji=emoji
        ).delete()
        return deleted_count > 0
    
    @database_sync_to_async
    def _mark_read(self, chat, user):
        """Отметить чат как прочитанный"""
        ChatReadState.objects.update_or_create(
            chat=chat,
            user=user,
            defaults={"last_read_at": timezone.now()}
        )
    
    @database_sync_to_async
    def _set_typing_status(self, chat, user, is_typing):
        """Установить статус печати (можно кэшировать в Redis)"""
        # TODO: Реализовать через Redis для производительности
        pass
    
    @database_sync_to_async
    def _get_recent_messages(self, chat_id, limit=50):
        """Получить последние сообщения чата"""
        messages = Message.objects.filter(
            chat_id=chat_id
        ).select_related(
            'author'
        ).prefetch_related(
            'attachments', 'reactions'
        ).order_by('-created_at')[:limit]
        
        # Реверсируем порядок (старые -> новые)
        messages = list(reversed(messages))
        
        return [serialize_message(msg) for msg in messages]

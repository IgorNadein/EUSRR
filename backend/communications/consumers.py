# communications/consumers.py
"""
WebSocket Consumer Mixin для чатов.

Этот модуль содержит ChatConsumerMixin - миксин с chat-функциональностью
для WebSocket consumer'ов. Используется в realtime.UserConsumer для
обработки всех операций с чатами и сообщениями.

История:
- Создан: 11 марта 2026 (извлечен из realtime/consumers.py)
- Цель: Сделать приложение communications автономным и переиспользуемым
"""
import logging
from channels.db import database_sync_to_async
from django.db.models import Q
from django.utils import timezone

from .models import Chat, ChatMembership, ChatReadState, Message, MessageReaction
from .serialization import serialize_message

logger = logging.getLogger(__name__)


class ChatConsumerMixin:
    """
    Mixin для WebSocket consumer с chat-функциональностью.
    
    Предоставляет методы для обработки:
    - Сообщений (отправка, редактирование, удаление)
    - Реакций (добавление, удаление)
    - Индикатора "печатает..."
    - Отметки прочитанного
    - Голосований
    
    Использование:
        from communications.consumers import ChatConsumerMixin
        from channels.generic.websocket import AsyncJsonWebsocketConsumer
        
        class MyConsumer(ChatConsumerMixin, AsyncJsonWebsocketConsumer):
            # Mixin автоматически предоставляет все chat_* методы
            pass
    
    Требования:
    - Consumer должен иметь атрибуты: active_chat_id, user
    - Consumer должен иметь методы: send_json(), channel_layer
    
    События от клиента (action):
    - open_chat, close_chat - управление активным чатом
    - send_message, edit_message, delete_message - работа с сообщениями
    - add_reaction, remove_reaction - реакции
    - typing, stop_typing - индикатор печати
    - mark_read - отметка прочитанного
    - vote_poll - голосование
    
    События в channel layer (type):
    - chat_message - новое сообщение
    - chat_message_edited - сообщение отредактировано
    - chat_message_deleted - сообщение удалено
    - chat_reaction_added/removed - реакция добавлена/удалена
    - chat_user_typing/stopped_typing - индикатор печати
    - chat_poll_update - обновление голосования
    - chat_marked_read - синхронизация отметки прочитанного
    """
    
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
        
        # НЕ отмечаем как прочитанное при открытии!
        # Автоотметка происходит автоматически при загрузке сообщений через:
        # - GET /messages-around/ → отмечает последнее ЗАГРУЖЕННОЕ
        # - GET /messages/?after_id= → отмечает последнее ЗАГРУЖЕННОЕ
        # - WebSocket new_message → отмечает если внизу
        # Старый вызов chat.mark_read() отмечал ПОСЛЕДНЕЕ В ЧАТЕ, что неправильно!
        
        await self.send_json({
            "type": "chat_opened",
            "chat_id": chat_id
        })
        
        logger.info(f"[ChatMixin] User {self.user.id} opened chat {chat_id}")
    
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
            
            logger.info(f"[ChatMixin] User {self.user.id} closed chat {chat_id}")
    
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
        chat_id = event.get("chat_id")
        message_id = event.get("message_id")
        
        logger.info(
            "[ChatMixin] Received delete event: chat_id=%s, message_id=%s",
            chat_id, message_id
        )
        logger.info(
            "[ChatMixin] Active chat: %s, matches=%s",
            self.active_chat_id, chat_id == self.active_chat_id
        )
        
        if chat_id == self.active_chat_id:
            logger.info(
                "[ChatMixin] Sending to client: message_id=%s",
                message_id
            )
            await self.send_json({
                "type": "message_deleted",
                "chat_id": chat_id,
                "message_id": message_id
            })
            logger.info("[ChatMixin] Sent to client successfully")
        else:
            logger.info("[ChatMixin] Skipping - not active chat")
    
    async def chat_reaction_added(self, event):
        """Реакция добавлена"""
        chat_id = event.get("chat_id")
        logger.info(
            f"[ChatMixin] chat_reaction_added: chat_id={chat_id}, "
            f"active_chat_id={self.active_chat_id}, message_id={event.get('message_id')}"
        )
        
        if chat_id == self.active_chat_id:
            logger.info("[ChatMixin] Sending reaction_added to client")
            await self.send_json({
                "type": "reaction_added",
                "chat_id": chat_id,
                "message_id": event.get("message_id"),
                "emoji": event.get("emoji"),
                "user_id": event.get("user_id"),
                "user_name": event.get("user_name"),
                "reactions_summary": event.get("reactions_summary")
            })
        else:
            logger.info("[ChatMixin] Skipping - not active chat")
    
    async def chat_reaction_removed(self, event):
        """Реакция удалена"""
        chat_id = event.get("chat_id")
        logger.info(
            f"[ChatMixin] chat_reaction_removed: chat_id={chat_id}, "
            f"active_chat_id={self.active_chat_id}, message_id={event.get('message_id')}"
        )
        
        if chat_id == self.active_chat_id:
            logger.info("[ChatMixin] Sending reaction_removed to client")
            await self.send_json({
                "type": "reaction_removed",
                "chat_id": chat_id,
                "message_id": event.get("message_id"),
                "emoji": event.get("emoji"),
                "user_id": event.get("user_id"),
                "reactions_summary": event.get("reactions_summary")
            })
        else:
            logger.info("[ChatMixin] Skipping - not active chat")
    
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
    
    async def chat_marked_read(self, event):
        """Синхронизация отметки прочитанного между вкладками (Telegram-style)"""
        chat_id = event.get("chat_id")
        last_read_message_id = event.get("last_read_message_id")
        
        logger.info(
            f"[ChatMixin.chat_marked_read] Sending to client: "
            f"chat={chat_id}, last_read_message_id={last_read_message_id}"
        )
        
        await self.send_json({
            "type": "marked_read",
            "chat_id": chat_id,
            "last_read_message_id": last_read_message_id
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
        """
        [DEPRECATED] Отметка сообщений как прочитанных через WebSocket.
        
        Используйте POST /api/v1/communications/chats/{id}/mark-read/ вместо этого.
        Автоотметка происходит автоматически при загрузке сообщений.
        """
        chat_id = content.get("chat_id")
        if not chat_id:
            logger.warning("[ChatMixin._handle_mark_read] [DEPRECATED] No chat_id provided")
            return
        
        logger.warning(
            f"[ChatMixin._handle_mark_read] [DEPRECATED] "
            f"User {self.user.id} tried to mark chat {chat_id} as read via WebSocket. "
            f"This is deprecated. Use POST /mark-read/ API endpoint instead."
        )
        
        # НЕ вызываем _mark_read! Автоотметка происходит автоматически.
        # Если нужна точная отметка, frontend должен вызвать POST API endpoint.
    
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
        from django.contrib.contenttypes.models import ContentType
        
        departments = user.departments.all()
        dept_ids = list(departments.values_list('id', flat=True))
        
        dept_ct = None
        if dept_ids:
            from employees.models import Department
            dept_ct = ContentType.objects.get_for_model(Department)
        
        # Получаем ID через membership
        membership_chat_ids = list(
            ChatMembership.objects.filter(user=user).values_list('chat_id', flat=True)
        )
        
        chat_ids = list(
            Chat.objects.filter(
                Q(type="global")
                | Q(type="department", department__in=departments)  # OLD: department FK
                | (Q(type="department", context_content_type=dept_ct, context_object_id__in=dept_ids) if dept_ct else Q(pk__in=[]))  # NEW: GenericFK
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
        
        if chat.type == "department":
            # Используем get_participants() - поддерживает и department, и context_object
            return chat.get_participants().filter(pk=user.pk).exists()
        
        if chat.type in ("channel", "announcement"):
            if chat.include_all_users:
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
            logger.error(f"Error creating message: {e}")
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
        """
        [DEPRECATED] НЕ ИСПОЛЬЗУЕТСЯ!
        
        Автоотметка происходит автоматически через ChatViewSet._auto_mark_read()
        при загрузке сообщений через GET запросы.
        
        Этот метод отмечал ПОСЛЕДНЕЕ СООБЩЕНИЕ В ЧАТЕ, что неправильно!
        Правильная логика: отмечать последнее ЗАГРУЖЕННОЕ сообщение.
        """
        logger.warning(
            f"[ChatMixin._mark_read] [DEPRECATED] "
            f"Attempt to mark chat {chat.id} as read for user {user.id}. "
            f"This method is deprecated and does nothing. "
            f"Auto-mark happens automatically via ChatViewSet._auto_mark_read()"
        )
        
        # НЕ вызываем chat.mark_read(user)!
        # Это отмечало последнее сообщение в чате вместо последнего загруженного.
    
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


__all__ = ['ChatConsumerMixin']

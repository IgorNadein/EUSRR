# communications/consumers.py
import asyncio
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from .models import Chat, ChatReadState, Message, MessageReaction


def serialize_message(m: Message) -> dict:
    """Сериализация сообщения с поддержкой новых полей"""
    author = m.author
    author_name = author.get_full_name() or author.username
    avatar = ""
    try:
        if getattr(author, "avatar", None) and author.avatar:
            avatar = author.avatar.url
    except Exception:
        avatar = ""

    # Новые поля
    data = {
        "id": m.id,
        "content": m.content,
        "author_id": author.id if author else None,
        "author_name": author_name,
        "author_url": reverse("employees:employee_detail", args=[author.id]) if author else "",
        "avatar": avatar,
        "created": m.created_at.strftime("%d.%m.%Y %H:%M"),
        "created_ts": int(m.created_at.timestamp() * 1000),
        
        # Новые поля
        "is_edited": m.is_edited,
        "edited_at": m.edited_at.isoformat() if m.edited_at else None,
        "is_deleted": m.is_deleted,
        "is_pinned": m.is_pinned,
        "is_forwarded": m.is_forwarded,
        "is_system": m.is_system,
        "has_attachments": m.has_attachments,
    }
    
    # Информация о пересылке (используем forward_metadata)
    if m.is_forwarded:
        try:
            metadata = m.forward_metadata
            forwarded_data = {
                "author_id": metadata.original_author.id if metadata.original_author else None,
                "author_name": (
                    metadata.original_author.get_full_name() if metadata.original_author
                    else metadata.original_author.username if metadata.original_author
                    else "Неизвестно"
                ),
                "message_id": metadata.original_message_id if metadata.original_message else None,
            }
            
            # Добавляем дату оригинального сообщения
            if metadata.original_created_at:
                forwarded_data["created_at"] = (
                    metadata.original_created_at.strftime("%d.%m.%Y %H:%M")
                )
                forwarded_data["created_ts"] = int(
                    metadata.original_created_at.timestamp() * 1000
                )
            
            # Добавляем название исходного чата
            if metadata.original_chat_name:
                forwarded_data["chat_name"] = metadata.original_chat_name
            
            data["forwarded_from"] = forwarded_data
        except Exception:
            # Если метаданных нет, просто не добавляем информацию о пересылке
            pass
    
    # Реакции - сериализуем из связанной модели MessageReaction
    reactions_summary = {}
    for reaction in m.reactions.select_related('user'):
        emoji = reaction.emoji
        if emoji not in reactions_summary:
            reactions_summary[emoji] = {
                'count': 0,
                'users': [],
                'user_names': []
            }
        reactions_summary[emoji]['count'] += 1
        reactions_summary[emoji]['users'].append(reaction.user_id)
        reactions_summary[emoji]['user_names'].append(
            reaction.user.get_full_name() or reaction.user.username
        )
    data["reactions_summary"] = reactions_summary
    
    # Вложения - всегда включаем поле attachments
    attachments = []
    if m.has_attachments:
        for att in m.attachments.all():
            attachments.append({
                "id": att.id,
                "file_name": att.file_name,
                "file_type": att.file_type,
                "file_url": att.file.url,
                "file_size": att.file_size,
                "mime_type": att.mime_type,
                "width": att.width,  # Размеры для CSS aspect-ratio
                "height": att.height,
                "thumbnail": (
                    att.thumbnail.url
                    if getattr(att, "thumbnail", None)
                    else None
                ),
            })
    data["attachments"] = attachments
    
    # Голосование
    if hasattr(m, 'poll'):
        poll = m.poll
        poll_data = {
            "id": poll.id,
            "question": poll.question,
            "is_anonymous": poll.is_anonymous,
            "is_multiple_choice": poll.is_multiple_choice,
            "is_quiz": poll.is_quiz,
            "is_closed": poll.is_closed,
            "closes_at": poll.closes_at.isoformat() if poll.closes_at else None,
            "total_voters": poll.total_voters,
            "options": []
        }
        for option in poll.options.all():
            poll_data["options"].append({
                "id": option.id,
                "text": option.text,
                "position": option.position,
                "vote_count": option.vote_count,
                "percentage": 0  # Будет пересчитан на клиенте
            })
        data["poll"] = poll_data
    
    # Ответ на сообщение
    if m.reply_to_id:
        try:
            reply_msg = m.reply_to if hasattr(m, 'reply_to') else None
            if not reply_msg:
                from communications.models import Message as Msg
                reply_msg = Msg.objects.select_related('author').get(
                    pk=m.reply_to_id
                )

            data["reply_to"] = {
                "id": reply_msg.id,
                "content": (
                    reply_msg.content[:100] if reply_msg.content else ""
                ),
                "author_name": (
                    reply_msg.author.get_full_name()
                    if reply_msg.author
                    else "Неизвестный"
                )
            }
            print(f"[DEBUG] serialize_message: added reply_to "
                  f"id={reply_msg.id}, author={data['reply_to']['author_name']}")
        except Exception as e:
            # Если не удалось загрузить reply_to, просто пропускаем
            print(f"[DEBUG] serialize_message: failed to load reply_to: {e}")
            pass

    
    # Информация о пересылке
    if m.is_forwarded and hasattr(m, 'forward_info'):
        fw = m.forward_info
        data["forward_info"] = {
            "original_author": fw.preserved_author_name,
            "forward_count": fw.forward_count,
        }
    
    return data


class ChatConsumer(AsyncJsonWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ping_task = None
        self.ping_interval = 20  # Ping каждые 20 секунд
    
    async def connect(self):
        user = self.scope.get("user")
        if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close(code=4401); return

        self.chat_id = int(self.scope["url_route"]["kwargs"]["chat_id"])
        self.group_name = f"chat_{self.chat_id}"

        chat = await self._get_chat(self.chat_id)
        if not await self._user_can_access(chat, user):
            await self.close(code=4403); return

        self.chat = chat
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Отправляем начальную историю сообщений
        await self._send_initial_messages()

        # помечаем как прочитанное «до текущего»
        await self._mark_read(self.chat, user)
        
        # Запускаем ping цикл для keepalive
        self.ping_task = asyncio.create_task(self._ping_loop())

    async def disconnect(self, code):
        # Останавливаем ping цикл
        if self.ping_task:
            self.ping_task.cancel()
            try:
                await self.ping_task
            except asyncio.CancelledError:
                pass
        
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            # Сбрасываем статус "набирает текст"
            if hasattr(self, 'chat'):
                await self._set_typing_status(self.chat, self.scope["user"], False)
    
    async def _ping_loop(self):
        """Отправка ping каждые N секунд для keepalive"""
        try:
            while True:
                await asyncio.sleep(self.ping_interval)
                await self.send_json({"type": "ping", "timestamp": timezone.now().isoformat()})
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Ping loop error: {e}")

    async def receive_json(self, content, **kwargs):
        """Обработка входящих сообщений и действий"""
        if not isinstance(content, dict):
            return
        
        action = content.get("action", "send_message")
        user = self.scope["user"]
        
        print(f"[DEBUG] receive_json: action={action}, user={user.id}, content={content}")
        
        # Обработка разных действий
        if action == "send_message":
            await self._handle_send_message(content, user)
        elif action == "edit_message":
            await self._handle_edit_message(content, user)
        elif action == "delete_message":
            await self._handle_delete_message(content, user)
        elif action == "add_reaction":
            await self._handle_add_reaction(content, user)
        elif action == "remove_reaction":
            await self._handle_remove_reaction(content, user)
        elif action == "typing":
            await self._handle_typing(content, user)
        elif action == "stop_typing":
            await self._handle_stop_typing(user)

    async def _handle_send_message(self, content, user):
        """Отправка нового сообщения"""
        text = str(content.get("content") or content.get("text") or "").strip()
        if not text:
            return
        
        # Проверка прав на отправку сообщений
        if self.chat.type == "announcement":
            # Только создатель может писать в объявление
            if self.chat.created_by_id != user.id:
                await self.send_json({
                    "type": "error",
                    "error": "Только автор может публиковать в это объявление"
                })
                return
        else:
            # В других типах проверяем can_send_messages
            has_permission = await self._check_send_permission(user)
            if not has_permission:
                await self.send_json({
                    "type": "error",
                    "error": "У вас нет прав для отправки сообщений"
                })
                return
        
        # Проверка на ответ (reply)
        reply_to_id = content.get("reply_to_id")
        
        # Запрет на reply в чатах где can_reply=False
        if reply_to_id and not self.chat.can_reply:
            await self.send_json({
                "type": "error",
                "error": "В этом чате запрещены ответы на сообщения"
            })
            return
        
        msg = await self._create_message(self.chat, user, text, reply_to_id)
        await self._mark_read(self.chat, user)
        
        # Сбрасываем статус "набирает"
        await self._set_typing_status(self.chat, user, False)
        
        payload = await self._serialize_message_full(msg)
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "chat.message", "chat_id": self.chat_id, "payload": payload},
        )

    async def _handle_edit_message(self, content, user):
        """Редактирование сообщения"""
        message_id = content.get("message_id")
        new_content = content.get("content", "").strip()
        
        if not message_id or not new_content:
            return
        
        # Запрет на редактирование в объявлениях
        if self.chat.type == "announcement":
            await self.send_json({
                "type": "error",
                "error": "Редактирование запрещено в объявлениях"
            })
            return
        
        success = await self._edit_message(message_id, user, new_content)
        if success:
            msg = await self._get_message(message_id)
            payload = await self._serialize_message_full(msg)
            
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "chat.message_edited",
                    "chat_id": self.chat_id,
                    "payload": payload
                },
            )

    async def _handle_delete_message(self, content, user):
        """Удаление сообщения"""
        import logging
        logger = logging.getLogger(__name__)
        
        message_id = content.get("message_id")
        logger.info(
            "[WS_DELETE] Received delete request: message_id=%s, user=%s",
            message_id, user.username
        )
        
        if not message_id:
            logger.warning("[WS_DELETE] No message_id provided")
            return
        
        # Запрет на удаление в объявлениях
        if self.chat.type == "announcement":
            logger.warning(
                "[WS_DELETE] Delete blocked: announcement chat"
            )
            await self.send_json({
                "type": "error",
                "error": "Удаление запрещено в объявлениях"
            })
            return
        
        logger.info("[WS_DELETE] Calling _delete_message")
        success = await self._delete_message(message_id, user)
        logger.info("[WS_DELETE] Delete result: %s", success)
        
        if success:
            logger.info(
                "[WS_DELETE] Broadcasting to group: %s", self.group_name
            )
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "chat.message_deleted",
                    "chat_id": self.chat_id,
                    "message_id": message_id
                },
            )
            logger.info(
                "[WS_DELETE] Broadcast sent for message_id=%s", message_id
            )

    async def _handle_add_reaction(self, content, user):
        """Добавление реакции"""
        message_id = content.get("message_id")
        emoji = content.get("emoji", "").strip()
        
        if not message_id or not emoji:
            return
        
        reactions = await self._add_reaction(message_id, user, emoji)
        if reactions is not None:
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "chat.reaction_added",
                    "chat_id": self.chat_id,
                    "message_id": message_id,
                    "user_id": user.id,
                    "emoji": emoji,
                    "reactions_summary": reactions
                },
            )

    async def _handle_remove_reaction(self, content, user):
        """Удаление реакции"""
        message_id = content.get("message_id")
        emoji = content.get("emoji", "").strip()
        
        if not message_id or not emoji:
            return
        
        reactions = await self._remove_reaction(message_id, user, emoji)
        if reactions is not None:
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "chat.reaction_removed",
                    "chat_id": self.chat_id,
                    "message_id": message_id,
                    "user_id": user.id,
                    "emoji": emoji,
                    "reactions_summary": reactions
                },
            )

    async def _handle_typing(self, content, user):
        """Индикатор набора текста"""
        await self._set_typing_status(self.chat, user, True)
        
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "chat.user_typing",
                "chat_id": self.chat_id,
                "user_id": user.id,
                "user_name": user.get_full_name() or user.username
            },
        )

    async def _handle_stop_typing(self, user):
        """Остановка индикатора набора"""
        await self._set_typing_status(self.chat, user, False)
        
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "chat.user_stopped_typing",
                "chat_id": self.chat_id,
                "user_id": user.id
            },
        )

    # Обработчики событий от group_send
    async def chat_message(self, event):
        """Новое сообщение"""
        await self.send_json({
            "type": "message",
            **event["payload"]
        })

    async def chat_message_edited(self, event):
        """Сообщение отредактировано"""
        await self.send_json({
            "type": "message_edited",
            "message": event["payload"]
        })

    async def chat_message_deleted(self, event):
        """Сообщение удалено"""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(
            "[WS_DELETE] chat_message_deleted handler called: %s",
            event
        )
        
        await self.send_json({
            "type": "message_deleted",
            "message_id": event["message_id"]
        })
        
        logger.info(
            "[WS_DELETE] Sent to client: message_id=%s",
            event["message_id"]
        )

    async def poll_update(self, event):
        """Обновление результатов голосования"""
        await self.send_json({
            "type": "poll_update",
            **event["payload"]
        })

    async def chat_reaction_added(self, event):
        """Реакция добавлена"""
        logger.info(f"[Consumer] chat_reaction_added called: message_id={event.get('message_id')}, emoji={event.get('emoji')}")
        await self.send_json({
            "type": "reaction_added",
            "message_id": event["message_id"],
            "user_id": event.get("user_id"),
            "emoji": event.get("emoji"),
            "reactions_summary": event.get("reactions_summary", {})
        })
        logger.info(f"[Consumer] reaction_added sent to client")

    async def chat_reaction_removed(self, event):
        """Реакция удалена"""
        logger.info(f"[Consumer] chat_reaction_removed called: message_id={event.get('message_id')}, emoji={event.get('emoji')}")
        await self.send_json({
            "type": "reaction_removed",
            "message_id": event["message_id"],
            "user_id": event.get("user_id"),
            "emoji": event.get("emoji"),
            "reactions_summary": event.get("reactions_summary", {})
        })
        logger.info(f"[Consumer] reaction_removed sent to client")

    async def chat_user_typing(self, event):
        """Пользователь набирает текст"""
        # Не отправляем самому себе
        if event["user_id"] != self.scope["user"].id:
            await self.send_json({
                "type": "user_typing",
                "user_id": event["user_id"],
                "user_name": event["user_name"]
            })

    async def chat_user_stopped_typing(self, event):
        """Пользователь закончил набор"""
        if event["user_id"] != self.scope["user"].id:
            await self.send_json({
                "type": "user_stopped_typing",
                "user_id": event["user_id"]
            })

    # --- DB helpers ---
    @database_sync_to_async
    def _get_chat(self, chat_id: int) -> Chat:
        return (
            Chat.objects.select_related("department")
            .prefetch_related("participants")
            .get(pk=chat_id)
        )

    @database_sync_to_async
    def _check_send_permission(self, user) -> bool:
        """Проверка права на отправку сообщений"""
        from .models import ChatMembership
        membership = ChatMembership.objects.filter(
            chat=self.chat, user=user
        ).first()
        if membership:
            return membership.can_send_messages
        return True  # По умолчанию можно писать

    @database_sync_to_async
    def _user_can_access(self, chat: Chat, user) -> bool:
        if chat.type == "global":
            return True
        if chat.type == "department":
            dept = chat.department
            if not dept:
                return False
            return (
                user.is_staff
                or dept.head_id == user.id
                or dept.active_employees.filter(id=user.id).exists()
            )
        if chat.type == "private":
            return chat.participants.filter(id=user.id).exists()
        if chat.type in ["group", "channel", "announcement"]:
            # Проверка через ChatMembership
            from communications.models import ChatMembership
            return ChatMembership.objects.filter(
                chat=chat, user=user
            ).exists()
        return False

    @database_sync_to_async
    def _create_message(self, chat: Chat, user, text: str, reply_to_id=None) -> Message:
        print(f"[DEBUG] Creating message: chat={chat.id}, user={user.id}, text='{text[:50]}...'")
        msg = Message.objects.create(
            chat=chat,
            author=user,
            content=text[:2000],
            reply_to_id=reply_to_id
        )
        print(f"[DEBUG] Message created: id={msg.id}")
        return msg

    @database_sync_to_async
    def _get_message(self, message_id: int) -> Message:
        return Message.objects.select_related(
            'author', 'reply_to', 'reply_to__author', 
            'forward_metadata', 'forward_metadata__original_author', 'poll'
        ).prefetch_related(
            'attachments', 'reactions', 'reactions__user', 'poll__options'
        ).get(pk=message_id)

    @database_sync_to_async
    def _serialize_message_full(self, msg: Message) -> dict:
        return serialize_message(msg)

    @database_sync_to_async
    def _edit_message(self, message_id: int, user, new_content: str) -> bool:
        from .models import MessageEditHistory
        
        try:
            msg = Message.objects.get(pk=message_id, author=user)
            
            # Сохраняем старый контент в историю редактирования
            MessageEditHistory.objects.create(
                message=msg,
                previous_content=msg.content,
                edited_by=user
            )
            
            msg.content = new_content
            msg.is_edited = True
            msg.edited_at = timezone.now()
            msg.save()
            return True
        except Message.DoesNotExist:
            return False

    @database_sync_to_async
    def _delete_message(self, message_id: int, user) -> bool:
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            logger.info(
                "[WS_DELETE_DB] Looking for message: id=%s, author=%s",
                message_id, user.username
            )
            msg = Message.objects.get(pk=message_id, author=user)
            logger.info(
                "[WS_DELETE_DB] Message found: chat_id=%s",
                msg.chat_id
            )
            
            msg.is_deleted = True
            msg.deleted_at = timezone.now()
            msg.deleted_by = user
            msg.save()
            
            logger.info(
                "[WS_DELETE_DB] Message marked as deleted: %s",
                message_id
            )
            return True
        except Message.DoesNotExist:
            logger.warning(
                "[WS_DELETE_DB] Message not found or wrong author: %s",
                message_id
            )
            return False

    @database_sync_to_async
    def _add_reaction(self, message_id: int, user, emoji: str):
        """Добавить реакцию (новая реализация с MessageReaction)"""
        try:
            msg = Message.objects.get(pk=message_id)
            
            # Создаём или обновляем реакцию
            reaction, created = MessageReaction.objects.update_or_create(
                message=msg,
                user=user,
                defaults={'emoji': emoji}
            )
            
            # Возвращаем сводку по всем реакциям
            return msg.get_reactions_summary()
        except Message.DoesNotExist:
            return None

    @database_sync_to_async
    def _remove_reaction(self, message_id: int, user, emoji: str):
        """Удалить реакцию (новая реализация с MessageReaction)"""
        try:
            msg = Message.objects.get(pk=message_id)
            
            # Удаляем реакцию пользователя (если указан emoji - только этот, иначе все)
            if emoji:
                MessageReaction.objects.filter(
                    message=msg,
                    user=user,
                    emoji=emoji
                ).delete()
            else:
                MessageReaction.objects.filter(
                    message=msg,
                    user=user
                ).delete()
            
            # Возвращаем обновлённую сводку
            return msg.get_reactions_summary()
        except Message.DoesNotExist:
            return None

    @database_sync_to_async
    def _set_typing_status(self, chat: Chat, user, is_typing: bool):
        ChatReadState.objects.update_or_create(
            chat=chat,
            user=user,
            defaults={
                'is_typing': is_typing,
                'typing_updated_at': timezone.now() if is_typing else None
            }
        )

    async def _send_initial_messages(self):
        """Отправить начальную историю сообщений при подключении"""
        messages = await self._get_initial_messages(self.chat_id, limit=50)
        
        # Отправляем все сообщения одним пакетом
        await self.send_json({
            "type": "initial_messages",
            "messages": messages
        })

    @database_sync_to_async
    def _get_initial_messages(self, chat_id: int, limit: int = 50):
        """Получить последние N сообщений из чата"""
        messages = Message.objects.filter(
            chat_id=chat_id
        ).select_related(
            'author'
        ).prefetch_related(
            'attachments',
            'reactions__user'
        ).order_by('-created_at')[:limit]
        
        # Возвращаем в прямом порядке (старые -> новые)
        return [serialize_message(msg) for msg in reversed(list(messages))]

    @database_sync_to_async
    def _mark_read(self, chat: Chat, user):
        last = chat.messages.order_by("-created_at").first()
        ts = last.created_at if last else timezone.now()
        ChatReadState.objects.update_or_create(
            chat=chat, user=user, defaults={"last_read_at": ts}
        )


class ChatListConsumer(AsyncJsonWebsocketConsumer):
    """
    Список чатов подписывается на все chat_{id} пользователя, и каждое
    новое сообщение получает как компактное обновление для карточки.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ping_task = None
        self.ping_interval = 20  # Ping каждые 20 секунд
    
    async def connect(self):
        user = self.scope.get("user")
        if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close(code=4401); return

        self.group_names = []
        chat_ids = await self._get_available_chat_ids(user)
        for cid in chat_ids:
            g = f"chat_{cid}"
            await self.channel_layer.group_add(g, self.channel_name)
            self.group_names.append(g)

        await self.accept()
        
        # Запускаем ping цикл для keepalive
        self.ping_task = asyncio.create_task(self._ping_loop())

    async def disconnect(self, code):
        # Останавливаем ping цикл
        if self.ping_task:
            self.ping_task.cancel()
            try:
                await self.ping_task
            except asyncio.CancelledError:
                pass
        
        for g in getattr(self, "group_names", []):
            await self.channel_layer.group_discard(g, self.channel_name)
    
    async def _ping_loop(self):
        """Отправка ping каждые N секунд для keepalive"""
        try:
            while True:
                await asyncio.sleep(self.ping_interval)
                await self.send_json({"type": "ping", "timestamp": timezone.now().isoformat()})
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Ping loop error: {e}")

    async def chat_message(self, event):
        # Проксируем компактное событие в UI списка
        await self.send_json(
            {
                "type": "list_update",
                "chat_id": event.get("chat_id"),
                "message": event.get("payload")
            }
        )
    
    async def chat_message_edited(self, event):
        """Сообщение отредактировано - обновляем в списке если это последнее"""
        await self.send_json({
            "type": "message_edited",
            "chat_id": event.get("chat_id"),
            "message": event.get("payload")
        })
    
    async def chat_user_typing(self, event):
        """Индикатор набора текста в списке чатов"""
        await self.send_json({
            "type": "user_typing",
            "chat_id": event.get("chat_id"),
            "user_id": event.get("user_id"),
            "user_name": event.get("user_name")
        })
    
    async def chat_user_stopped_typing(self, event):
        """Остановка индикатора набора текста"""
        await self.send_json({
            "type": "user_stopped_typing",
            "chat_id": event.get("chat_id"),
            "user_id": event.get("user_id")
        })

    async def chat_reaction_added(self, event):
        """Реакция добавлена (игнорируем в списке чатов)"""
        pass

    async def chat_reaction_removed(self, event):
        """Реакция удалена (игнорируем в списке чатов)"""
        pass

    async def chat_poll_update(self, event):
        """Обновление голосования (игнорируем в списке чатов)"""
        pass

    @database_sync_to_async
    def _get_available_chat_ids(self, user):
        departments = user.departments.all()
        return list(
            Chat.objects.filter(
                Q(type="global")
                | Q(type="department", department__in=departments)
                | Q(type="private", participants=user)
            ).values_list("id", flat=True)
        )

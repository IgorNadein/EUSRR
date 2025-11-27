# communications/consumers.py
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from .models import Chat, ChatReadState, Message


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

    # Базовая информация
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
        "reactions": m.reactions or {},
        "has_attachments": m.has_attachments,
    }
    
    # Ответ на сообщение
    if m.reply_to_id:
        data["reply_to"] = {
            "id": m.reply_to_id,
            "content": m.reply_to.content[:100] if m.reply_to else "",
            "author_name": m.reply_to.author.get_full_name() if m.reply_to else ""
        }
    
    # Вложения (если есть)
    if m.has_attachments:
        attachments = []
        for att in m.attachments.all():
            attachments.append({
                "id": att.id,
                "file_name": att.file_name,
                "file_type": att.file_type,
                "file_url": att.file.url,
                "file_size": att.file_size,
                "thumbnail": att.thumbnail.url if att.thumbnail else None
            })
        data["attachments"] = attachments
    
    # Информация о пересылке
    if m.is_forwarded and hasattr(m, 'forward_info'):
        fw = m.forward_info
        data["forward_info"] = {
            "original_author": fw.preserved_author_name,
            "forward_count": fw.forward_count,
        }
    
    return data


class ChatConsumer(AsyncJsonWebsocketConsumer):
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

        # помечаем как прочитанное «до текущего»
        await self._mark_read(self.chat, user)

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            # Сбрасываем статус "набирает текст"
            if hasattr(self, 'chat'):
                await self._set_typing_status(self.chat, self.scope["user"], False)

    async def receive_json(self, content, **kwargs):
        """Обработка входящих сообщений и действий"""
        if not isinstance(content, dict):
            return
        
        action = content.get("action", "send_message")
        user = self.scope["user"]
        
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
        
        # Проверка на ответ
        reply_to_id = content.get("reply_to_id")
        
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
        message_id = content.get("message_id")
        if not message_id:
            return
        
        success = await self._delete_message(message_id, user)
        if success:
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "chat.message_deleted",
                    "chat_id": self.chat_id,
                    "message_id": message_id
                },
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
                    "reactions": reactions
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
                    "reactions": reactions
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
        await self.send_json(event["payload"])

    async def chat_message_edited(self, event):
        """Сообщение отредактировано"""
        await self.send_json({
            "type": "message_edited",
            "message": event["payload"]
        })

    async def chat_message_deleted(self, event):
        """Сообщение удалено"""
        await self.send_json({
            "type": "message_deleted",
            "message_id": event["message_id"]
        })

    async def chat_reaction_added(self, event):
        """Реакция добавлена"""
        await self.send_json({
            "type": "reaction_added",
            "message_id": event["message_id"],
            "reactions": event["reactions"]
        })

    async def chat_reaction_removed(self, event):
        """Реакция удалена"""
        await self.send_json({
            "type": "reaction_removed",
            "message_id": event["message_id"],
            "reactions": event["reactions"]
        })

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
        msg = Message.objects.create(
            chat=chat,
            author=user,
            content=text[:2000],
            reply_to_id=reply_to_id
        )
        return msg

    @database_sync_to_async
    def _get_message(self, message_id: int) -> Message:
        return Message.objects.select_related(
            'author', 'reply_to', 'reply_to__author'
        ).prefetch_related('attachments').get(pk=message_id)

    @database_sync_to_async
    def _serialize_message_full(self, msg: Message) -> dict:
        return serialize_message(msg)

    @database_sync_to_async
    def _edit_message(self, message_id: int, user, new_content: str) -> bool:
        try:
            msg = Message.objects.get(pk=message_id, author=user)
            if not msg.is_edited:
                msg.edit_history = []
            
            msg.edit_history.append({
                'timestamp': timezone.now().isoformat(),
                'old_content': msg.content
            })
            
            msg.content = new_content
            msg.is_edited = True
            msg.edited_at = timezone.now()
            msg.save()
            return True
        except Message.DoesNotExist:
            return False

    @database_sync_to_async
    def _delete_message(self, message_id: int, user) -> bool:
        try:
            msg = Message.objects.get(pk=message_id, author=user)
            msg.is_deleted = True
            msg.deleted_at = timezone.now()
            msg.deleted_by = user
            msg.save()
            return True
        except Message.DoesNotExist:
            return False

    @database_sync_to_async
    def _add_reaction(self, message_id: int, user, emoji: str):
        try:
            msg = Message.objects.get(pk=message_id)
            reactions = msg.reactions or {}
            
            if emoji not in reactions:
                reactions[emoji] = []
            
            if user.id not in reactions[emoji]:
                reactions[emoji].append(user.id)
            
            msg.reactions = reactions
            msg.save()
            return reactions
        except Message.DoesNotExist:
            return None

    @database_sync_to_async
    def _remove_reaction(self, message_id: int, user, emoji: str):
        try:
            msg = Message.objects.get(pk=message_id)
            reactions = msg.reactions or {}
            
            if emoji in reactions and user.id in reactions[emoji]:
                reactions[emoji].remove(user.id)
                if not reactions[emoji]:
                    del reactions[emoji]
            
            msg.reactions = reactions
            msg.save()
            return reactions
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

    async def disconnect(self, code):
        for g in getattr(self, "group_names", []):
            await self.channel_layer.group_discard(g, self.channel_name)

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

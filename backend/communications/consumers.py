# communications/consumers.py
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from django.urls import reverse
from django.utils import timezone

from django.db.models import Q
from .models import Chat, Message, ChatReadState


def serialize_message(m: Message) -> dict:
    author = m.author
    author_name = author.get_full_name() or author.username
    avatar = ""
    try:
        if getattr(author, "avatar", None) and author.avatar:
            avatar = author.avatar.url
    except Exception:
        avatar = ""

    return {
        "id": m.id,
        "content": m.content,
        "author_id": author.id if author else None,
        "author_name": author_name,
        "author_url": reverse("employees:employee_detail", args=[author.id]) if author else "",
        "avatar": avatar,
        "created": m.created_at.strftime("%d.%m.%Y %H:%M"),
        "created_ts": int(m.created_at.timestamp() * 1000),   # ⬅ важно для сортировки на клиенте
    }


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

    async def receive_json(self, content, **kwargs):
        # ждём {"content": "..."} или {"action": "...", "text": "..."}
        text = ""
        if isinstance(content, dict):
            text = str(content.get("content") or content.get("text") or "").strip()
        if not text:
            return

        user = self.scope["user"]
        msg = await self._create_message(self.chat, user, text)

        # автору — сразу «прочитано»
        await self._mark_read(self.chat, user)

        payload = serialize_message(msg)
        # ⬇ кладём chat_id для листа чатов (ChatListConsumer)
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "chat.message", "chat_id": self.chat_id, "payload": payload},
        )

    async def chat_message(self, event):
        # detail-страница чата просто получает payload
        await self.send_json(event["payload"])

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
        return chat.participants.filter(id=user.id).exists()

    @database_sync_to_async
    def _create_message(self, chat: Chat, user, text: str) -> Message:
        return Message.objects.create(chat=chat, author=user, content=text[:2000])

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
            {"type": "list_update", "chat_id": event.get("chat_id"), "message": event.get("payload")}
        )

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

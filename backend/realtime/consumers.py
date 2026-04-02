# realtime/consumers.py
"""
WebSocket Consumer для пользователя.
Универсальное WebSocket соединение для всех real-time операций:
- Чаты и сообщения (через ChatConsumerMixin)
- Уведомления
- Обновления бейджей
- Онлайн-статус
- Закупки и другие real-time события

История:
- 11 марта 2026: Извлечен ChatConsumerMixin в communications.consumers
"""

import asyncio
import logging
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

from communications.consumers import ChatConsumerMixin

logger = logging.getLogger(__name__)


class UserConsumer(ChatConsumerMixin, AsyncJsonWebsocketConsumer):
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

        if (
            not self.user
            or isinstance(self.user, AnonymousUser)
            or not self.user.is_authenticated
        ):
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
        await self.channel_layer.group_add(
            notifications_channel, self.channel_name
        )

        await self.accept()

        # Запускаем ping цикл для keepalive
        self.ping_task = asyncio.create_task(self._ping_loop())

        print(
            f"[UserWS] User {self.user.id} connected, subscribed to {
                len(self.subscribed_chats)
            } chats"
        )

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
            await self.channel_layer.group_discard(
                group_name, self.channel_name
            )

        # Отписываемся от личных каналов
        if self.user:
            user_channel = f"user_{self.user.id}"
            await self.channel_layer.group_discard(
                user_channel, self.channel_name
            )

            notifications_channel = f"notifications_{self.user.id}"
            await self.channel_layer.group_discard(
                notifications_channel, self.channel_name
            )

        print(
            f"[UserWS] User {
                self.user.id if self.user else 'unknown'
            } disconnected"
        )

    async def _ping_loop(self):
        """Отправка ping каждые N секунд для keepalive"""
        try:
            while True:
                await asyncio.sleep(self.ping_interval)
                await self.send_json(
                    {"type": "ping", "timestamp": timezone.now().isoformat()}
                )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[UserWS] Ping loop error: {e}")

    async def receive_json(self, content, **kwargs):
        """Обработка входящих сообщений от клиента"""
        if not isinstance(content, dict):
            return

        action = content.get("action", "")

        print(
            f"[UserWS] receive_json: action={action}, user={
                self.user.id
            }, active_chat={self.active_chat_id}"
        )

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

    @staticmethod
    def _extract_notification_chat_id(notification):
        """Достаёт chat_id из payload уведомления, если он есть."""
        if not isinstance(notification, dict):
            return None

        data = notification.get("data")
        if not isinstance(data, dict):
            return None

        chat_id = data.get("chat_id")
        try:
            return int(chat_id)
        except (TypeError, ValueError):
            return None

    def _should_suppress_active_chat_notification(self, notification):
        """Не показываем уведомление о сообщении в уже открытом чате."""
        if self.active_chat_id is None:
            return False

        notification_chat_id = self._extract_notification_chat_id(notification)
        return notification_chat_id == self.active_chat_id

    # ==================== Обработчики уведомлений ====================

    async def notification_message(self, event):
        """
        Новое уведомление от WebSocketNotificationSender.
        Вызывается из notifications/senders/websocket.py
        """
        notification = event.get("message", {})

        if self._should_suppress_active_chat_notification(notification):
            logger.info(
                "[UserWS] Suppressed notification for active chat %s in session %s",
                self.active_chat_id,
                self.channel_name,
            )
            return

        await self.send_json(
            {"type": "notification", "notification": notification}
        )

    async def notification_new(self, event):
        """Новое уведомление (вызывается из notifications/services.py)"""
        notification = event.get("notification", {})

        if self._should_suppress_active_chat_notification(notification):
            logger.info(
                "[UserWS] Suppressed notification_new for active chat %s in session %s",
                self.active_chat_id,
                self.channel_name,
            )
            return

        await self.send_json(
            {
                "type": "notification",
                "notification": notification,
            }
        )

    async def notification_count_update(self, event):
        """
        Обновление счетчика уведомлений.
        Вызывается из notifications/services.py
        """
        await self.send_json(
            {"type": "unread_count", "count": event.get("count", 0)}
        )

    async def notification_read(self, event):
        """Синхронизация прочтения одного уведомления между сессиями."""
        await self.send_json(
            {
                "type": "notification_read",
                "notification_id": event.get("notification_id"),
                "unread_count": event.get("unread_count"),
            }
        )

    async def notifications_read_all(self, event):
        """Синхронизация массового прочтения уведомлений между сессиями."""
        await self.send_json(
            {
                "type": "notifications_read_all",
                "notification_ids": event.get("notification_ids", []),
                "category": event.get("category"),
                "unread_count": event.get("unread_count"),
            }
        )

    # ==================== Обработка событий закупок ====================

    async def poll_update(self, event):
        """Обработчик для события poll.update (алиас для chat_poll_update)"""
        await self.chat_poll_update(event)

    async def procurement_update(self, event):
        """
        Обновление заявки на закупку.
        Вызывается из procurement/signals.py
        """
        await self.send_json(
            {
                "type": "procurement_update",
                "event": event.get("event", "request_updated"),
                "data": event.get("data", {}),
            }
        )

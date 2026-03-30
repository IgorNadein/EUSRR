"""
Утилиты для модуля communications.
Переиспользуемые функции для API, WebSocket и других компонентов.
"""
from __future__ import annotations

import datetime
from datetime import datetime as dt
from datetime import timezone as dt_tz

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import Chat, ChatMembership


def _coerce_ts(val: str | None) -> datetime.datetime:
    """
    Принимает миллисекунды/секунды с эпохи или ISO-дату.
    Возвращает aware-дату (UTC). Фоллбек — timezone.now().
    
    Args:
        val: Строка с timestamp (ms/sec) или ISO-дата
        
    Returns:
        datetime: Aware datetime объект в UTC
        
    Examples:
        >>> _coerce_ts("1640000000000")  # миллисекунды
        datetime.datetime(2021, 12, 20, 13, 33, 20, tzinfo=UTC)
        
        >>> _coerce_ts("1640000000")  # секунды
        datetime.datetime(2021, 12, 20, 13, 33, 20, tzinfo=UTC)
        
        >>> _coerce_ts("2021-12-20T13:33:20Z")  # ISO
        datetime.datetime(2021, 12, 20, 13, 33, 20, tzinfo=UTC)
    """
    if not val:
        return timezone.now()
    
    # Сначала пробуем число (sec/ms)
    try:
        iv = int(val)
        if iv > 10**12:   # пришли миллисекунды
            iv //= 1000
        return dt.fromtimestamp(iv, tz=dt_tz.utc)
    except Exception:
        pass
    
    # Потом пробуем ISO-строку
    d = parse_datetime(val)
    if d is None:
        return timezone.now()
    if timezone.is_naive(d):
        return timezone.make_aware(d, timezone=timezone.get_current_timezone())
    return d


def user_can_access_chat(chat: Chat, user) -> bool:
    """
    Проверяет, имеет ли пользователь доступ к чату.
    
    Правила доступа по типам чатов:
    - global: доступ всем
    - private: активное ChatMembership
    - group: активное ChatMembership (или context-based resolver)
    - channel/announcement: include_all_users или активное ChatMembership
    - comments: context-based доступ через get_participants()
    
    Args:
        chat: Объект Chat
        user: Объект User
        
    Returns:
        bool: True если пользователь имеет доступ
        
    Note:
        Использует прямые запросы к БД в обход prefetch cache
    """
    if not chat or not user:
        return False

    if chat.type == "global":
        return True

    def _has_direct_participation() -> bool:
        return chat.participants.filter(pk=user.pk).exists()

    if chat.type == "private":
        return ChatMembership.objects.filter(
            chat=chat, user=user, is_active=True
        ).exists() or _has_direct_participation()

    if chat.type == "group":
        # Групповые чаты с контекстным объектом используют resolver
        if chat.context_object_id:
            try:
                participants = chat.get_participants()
                return participants.filter(pk=user.pk).exists()
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"[user_can_access_chat] Failed to resolve for chat "
                    f"{chat.id}: {e}"
                )
        return ChatMembership.objects.filter(
            chat=chat, user=user, is_active=True
        ).exists() or _has_direct_participation()

    if chat.type in ("channel", "announcement"):
        if chat.include_all_users:
            return user.is_active
        return ChatMembership.objects.filter(
            chat=chat, user=user, is_active=True
        ).exists() or _has_direct_participation()
    
    if chat.type == "comments":
        # Чаты-комментарии используют context-based доступ через get_participants()
        if chat.context_object_id:
            try:
                participants = chat.get_participants()
                return participants.filter(pk=user.pk).exists()
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"[user_can_access_chat] Failed to resolve for "
                    f"comments chat {chat.id}: {e}"
                )
                return False
        return ChatMembership.objects.filter(
            chat=chat, user=user, is_active=True
        ).exists() or _has_direct_participation()

    return False

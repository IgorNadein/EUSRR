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
    - private: только участники (participants)
    - group: участники (participants) или ChatMembership
    - department: через get_participants() (поддерживает department и context_object)
    - channel/announcement: include_all_users или participants/membership
    
    Args:
        chat: Объект Chat
        user: Объект User (Employee)
        
    Returns:
        bool: True если пользователь имеет доступ
    """
    if not chat or not user:
        return False

    if chat.type == "global":
        return True

    if chat.type == "private":
        # Личные чаты только через participants
        return chat.participants.filter(pk=user.pk).exists()

    if chat.type == "group":
        # Групповые чаты через participants ИЛИ ChatMembership
        in_participants = chat.participants.filter(pk=user.pk).exists()
        in_membership = ChatMembership.objects.filter(chat=chat, user=user).exists()
        return in_participants or in_membership

    if chat.type == "department":
        # Проверяем через get_participants() (поддерживает и department, и context_object)
        return chat.get_participants().filter(pk=user.pk).exists()

    if chat.type in ("channel", "announcement"):
        # Для каналов и объявлений может быть include_all_users или membership
        if chat.include_all_users:
            return user.is_active
        # Проверяем и participants и membership для гибкости
        return (
            chat.participants.filter(pk=user.pk).exists()
            or ChatMembership.objects.filter(chat=chat, user=user).exists()
        )

    return False

import datetime

from django.db import models
from django.db.models import Count, F, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import Chat, ChatReadState, Message


def chat_unread_total(request):
    """
    Считает общее количество непрочитанных сообщений пользователя.
    Использует last_read_message_id (Telegram-style) вместо last_read_at.
    """
    if not request.user.is_authenticated:
        return {"chat_unread_total": 0}

    user = request.user

    # last_read_message_id для каждого чата текущего юзера
    last_read_msg_sq = ChatReadState.objects.filter(
        chat=models.OuterRef("pk"), user=user
    ).values("last_read_message_id")[:1]

    # доступные юзеру чаты
    deps = getattr(user, "departments", None)
    deps_qs = deps.all() if deps is not None else []

    chats_qs = (
        Chat.objects.filter(
            Q(type="global")
            | Q(type="private", participants=user)
            | Q(type="department", department__in=deps_qs)
        )
        .distinct()
        .annotate(last_read_msg_id=Coalesce(Subquery(last_read_msg_sq), Value(0)))
        .annotate(
            unread=Count(
                "messages",
                filter=Q(messages__id__gt=F("last_read_msg_id"))
                & ~Q(messages__author=user),
                distinct=True,
            )
        )
    )

    total = chats_qs.aggregate(total=models.Sum("unread"))["total"] or 0
    return {"chat_unread_total": total}

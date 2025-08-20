import datetime

from django.db import models
from django.db.models import Count, F, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import Chat, ChatReadState, Message


def chat_unread_total(request):
    if not request.user.is_authenticated:
        return {"chat_unread_total": 0}

    user = request.user
    default_dt = timezone.make_aware(datetime.datetime(1970, 1, 1))

    # last_read_at для каждого чата текущего юзера
    last_read_sq = ChatReadState.objects.filter(
        chat=models.OuterRef("pk"), user=user
    ).values("last_read_at")[:1]

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
        .annotate(last_read_at=Coalesce(Subquery(last_read_sq), Value(default_dt)))
        .annotate(
            unread=Count(
                "messages",
                filter=Q(messages__created_at__gt=F("last_read_at"))
                & ~Q(messages__author=user),
                distinct=True,
            )
        )
    )

    total = chats_qs.aggregate(total=models.Sum("unread"))["total"] or 0
    return {"chat_unread_total": total}

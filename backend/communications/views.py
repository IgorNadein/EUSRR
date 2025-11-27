from __future__ import annotations

import datetime
from datetime import datetime as dt
from datetime import timezone as dt_tz

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError, models
from django.db.models import Count, F, Prefetch, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, FormView, ListView

from .forms import MessageForm
from .models import Chat, ChatReadState, Message

# ===== helpers =====


def _coerce_ts(val: str | None) -> datetime.datetime:
    """
    Принимает миллисекунды/секунды с эпохи или ISO-дату.
    Возвращает aware-дату (UTC). Фоллбек — timezone.now().
    """
    if not val:
        return timezone.now()
    # сначала — число (sec/ms)
    try:
        iv = int(val)
        if iv > 10**12:   # пришли миллисекунды
            iv //= 1000
        return dt.fromtimestamp(iv, tz=dt_tz.utc)
    except Exception:
        pass
    # потом — ISO-строка
    d = parse_datetime(val)
    if d is None:
        return timezone.now()
    if timezone.is_naive(d):
        return timezone.make_aware(d, timezone=timezone.get_current_timezone())
    return d


class ChatListView(LoginRequiredMixin, ListView):
    model = Chat
    template_name = "communications/chat_list.html"
    context_object_name = "chats"

    def get_queryset(self):
        user = self.request.user
        # ВАЖНО: у Employee.departments это property, а не менеджер
        departments = user.departments  # уже queryset

        last_qs = (
            Message.objects.filter(chat=models.OuterRef("pk"))
            .values("created_at")
            .order_by("-created_at")[:1]
        )
        last_read_qs = ChatReadState.objects.filter(
            chat=models.OuterRef("pk"), user=user
        ).values("last_read_at")[:1]

        default_dt = timezone.make_aware(
            datetime.datetime(1970, 1, 1), timezone.get_current_timezone()
        ).astimezone(dt_tz.utc)

        # Получаем ID чатов, где пользователь является участником
        # через membership
        from communications.models import ChatMembership
        membership_chat_ids = ChatMembership.objects.filter(
            user=user
        ).values_list('chat_id', flat=True)

        qs = (
            Chat.objects.filter(
                Q(type="global")
                | Q(type="department", department__in=departments)
                | Q(type="private", participants=user)
                | Q(id__in=membership_chat_ids)  # group/channel/announcement
            )
            .distinct()
            .select_related("department")
            .annotate(last_msg_at=Subquery(last_qs))
            .annotate(
                last_read_at=Coalesce(
                    Subquery(last_read_qs),
                    Value(default_dt, output_field=models.DateTimeField()),
                    output_field=models.DateTimeField(),
                )
            )
            .annotate(
                # считаем только чужие сообщения после last_read_at
                unread_count=Count(
                    "messages",
                    filter=Q(messages__created_at__gt=F("last_read_at"))
                    & ~Q(messages__author=user),
                    distinct=True,
                )
            )
            .prefetch_related(
                "participants",
                Prefetch(
                    "messages",
                    queryset=Message.objects.select_related("author").order_by(
                        "-created_at"
                    )[:1],
                    to_attr="last_message",
                ),
            )
            .order_by(models.F("last_msg_at").desc(nulls_last=True), "-created_at")
        )
        return qs


class ChatDetailView(LoginRequiredMixin, DetailView, FormView):
    model = Chat
    template_name = "communications/chat_detail.html"
    context_object_name = "chat"
    form_class = MessageForm

    def get_success_url(self):
        return reverse("communications:chat_detail", kwargs={"pk": self.object.pk})

    def _user_has_access(self, chat: Chat, user) -> bool:
        if chat.type == "global":
            return True
        if chat.type == "private":
            return chat.participants.filter(pk=user.pk).exists()
        if chat.type == "department" and chat.department_id:
            return chat.get_participants.filter(pk=user.pk).exists()
        if chat.type in ["group", "channel", "announcement"]:
            # Проверяем membership для групповых чатов, каналов и объявлений
            from communications.models import ChatMembership
            return ChatMembership.objects.filter(
                chat=chat, user=user
            ).exists()
        return False

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        chat: Chat = self.object
        user = self.request.user

        # защита доступа
        if not self._user_has_access(chat, user):
            from django.http import Http404

            raise Http404("Chat not found")

        # сообщения + участники
        context["messages"] = chat.messages.select_related("author").order_by(
            "created_at"
        )
        context["form"] = context.get("form", MessageForm())
        context["participants"] = chat.get_participants

        # отдаём клиенту last_read_at и «первое непрочитанное»
        read_state = (
            ChatReadState.objects.filter(chat=chat, user=user)
            .only("last_read_at")
            .first()
        )
        last_read_at = (
            read_state.last_read_at if read_state and read_state.last_read_at else None
        )
        context["last_read_at"] = last_read_at

        first_unread = None
        if last_read_at:
            first_unread = (
                chat.messages.exclude(author=user)
                .filter(created_at__gt=last_read_at)
                .order_by("created_at")
                .only("id", "created_at")
                .first()
            )
        context["first_unread_id"] = first_unread.id if first_unread else None
        if first_unread:
            context["unread_from_ts"] = int(first_unread.created_at.timestamp() * 1000)
        elif last_read_at:
            context["unread_from_ts"] = int(last_read_at.timestamp() * 1000) + 1
        else:
            context["unread_from_ts"] = None

        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        user = request.user

        if not ChatDetailView._user_has_access(self, self.object, user):
            from django.http import HttpResponseForbidden

            return HttpResponseForbidden("forbidden")

        form = self.get_form()
        if form.is_valid():
            msg = form.save(commit=False)
            msg.chat = self.object
            msg.author = user
            msg.save()

            # автору сразу «прочитано» — делаем безопасно
            ts = msg.created_at
            updated = ChatReadState.objects.filter(
                chat=self.object, user=user, last_read_at__lt=ts
            ).update(last_read_at=ts)
            if not updated:
                try:
                    ChatReadState.objects.create(
                        chat=self.object, user=user, last_read_at=ts
                    )
                except IntegrityError:
                    ChatReadState.objects.filter(
                        chat=self.object, user=user, last_read_at__lt=ts
                    ).update(last_read_at=ts)

            return redirect(self.get_success_url())
        return self.render_to_response(self.get_context_data(form=form))


def start_private_chat(request, employee_pk):
    from employees.models import Employee

    target = get_object_or_404(Employee, pk=employee_pk)
    user = request.user
    chat = (
        Chat.objects.filter(type="private", participants=user)
        .filter(participants=target)
        .first()
    )
    if not chat:
        chat = Chat.objects.create(type="private")
        chat.participants.add(user, target)
        # новый чат помечаем прочитанным для создателя (нет непрочитанных)
        now_ts = timezone.now()
        try:
            ChatReadState.objects.create(chat=chat, user=user, last_read_at=now_ts)
        except IntegrityError:
            ChatReadState.objects.filter(
                chat=chat, user=user, last_read_at__lt=now_ts
            ).update(last_read_at=now_ts)

    return redirect("communications:chat_detail", pk=chat.pk)


@login_required
@require_POST
def chat_mark_read(request, pk: int):
    chat = get_object_or_404(Chat, pk=pk)
    user = request.user

    # доступ
    def has_access(c: Chat, u) -> bool:
        if c.type == "global": return True
        if c.type == "private": return c.participants.filter(pk=u.pk).exists()
        if c.type == "department" and c.department_id:
            return c.get_participants.filter(pk=u.pk).exists()
        return False

    if not has_access(chat, user):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    # целевая точка времени: приоритет у upto_id, затем upto_ts, затем последний месседж
    ts = None
    upto_id = request.POST.get("upto_id")
    if upto_id:
        m = Message.objects.filter(chat=chat, pk=upto_id).only("created_at").first()
        ts = m.created_at if m else None
    if ts is None:
        ts = _coerce_ts(request.POST.get("upto_ts"))

    if ts is None:
        ts = chat.messages.order_by("-created_at").values_list("created_at", flat=True).first() or timezone.now()

    # обновляем только если новее; без update_or_create — устойчиво к SQLite/гонкам
    updated = ChatReadState.objects.filter(chat=chat, user=user, last_read_at__lt=ts).update(last_read_at=ts)
    if not updated:
        try:
            ChatReadState.objects.create(chat=chat, user=user, last_read_at=ts)
        except IntegrityError:
            ChatReadState.objects.filter(chat=chat, user=user, last_read_at__lt=ts).update(last_read_at=ts)

    return JsonResponse({"ok": True, "last_read_at": int(ts.timestamp() * 1000)})

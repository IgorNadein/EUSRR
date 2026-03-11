from __future__ import annotations

import datetime
import logging
from datetime import datetime as dt
from datetime import timezone as dt_tz

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError, models

logger = logging.getLogger(__name__)
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
from .models import Chat, ChatMembership, ChatReadState, Message

CHAT_MESSAGES_PAGE_SIZE = getattr(settings, "CHAT_MESSAGES_PAGE_SIZE", 50)

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


def user_can_access_chat(chat: Chat, user) -> bool:
    if not chat or not user:
        return False

    print(f"[CHAT DEBUG] user_can_access_chat: chat={chat.id}, type={chat.type}, user={user.id}")

    if chat.type == "global":
        return True

    if chat.type == "private":
        # Личные чаты только через participants
        result = chat.participants.filter(pk=user.pk).exists()
        print(f"[CHAT DEBUG] Private chat, participants check: {result}")
        return result

    if chat.type == "group":
        # Групповые чаты через participants ИЛИ ChatMembership
        in_participants = chat.participants.filter(pk=user.pk).exists()
        in_membership = ChatMembership.objects.filter(chat=chat, user=user).exists()
        result = in_participants or in_membership
        print(f"[CHAT DEBUG] Group chat, participants={in_participants}, membership={in_membership}, result={result}")
        return result

    if chat.type == "department":
        # Проверяем через get_participants() (поддерживает и department, и context_object)
        result = chat.get_participants().filter(pk=user.pk).exists()
        print(f"[CHAT DEBUG] Department chat, result={result}")
        return result

    if chat.type in ("channel", "announcement"):
        # Для каналов и объявлений может быть include_all_users или membership
        if chat.include_all_users:
            return user.is_active
        # Проверяем и participants и membership для гибкости
        result = (
            chat.participants.filter(pk=user.pk).exists()
            or ChatMembership.objects.filter(chat=chat, user=user).exists()
        )
        print(f"[CHAT DEBUG] Channel/announcement chat, result={result}")
        return result

    return False


class ChatListView(LoginRequiredMixin, ListView):
    model = Chat
    template_name = "communications/chat_list.html"
    context_object_name = "chats"

    def dispatch(self, request, *args, **kwargs):
        """Добавляем заголовки для отключения кэширования"""
        response = super().dispatch(request, *args, **kwargs)
        # Запрещаем кэширование списка чатов
        response['Cache-Control'] = (
            'no-cache, no-store, must-revalidate, max-age=0'
        )
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Добавляем список отделов для выбора при создании чата
        from employees.models import Department
        context['departments'] = Department.objects.all().order_by('name')
        return context

    def get_queryset(self):
        user = self.request.user
        # ВАЖНО: у Employee.departments это property, а не менеджер
        departments = user.departments  # уже queryset

        last_qs = (
            Message.objects.filter(chat=models.OuterRef("pk"))
            .values("created_at")
            .order_by("-created_at")[:1]
        )
        last_read_msg_qs = ChatReadState.objects.filter(
            chat=models.OuterRef("pk"), user=user
        ).values("last_read_message_id")[:1]

        # Получаем ID чатов, где пользователь является участником
        # через membership
        from communications.models import ChatMembership
        from django.contrib.contenttypes.models import ContentType
        
        membership_chat_ids = ChatMembership.objects.filter(
            user=user
        ).values_list('chat_id', flat=True)
        
        # Для department: проверяем и старое поле department, и новое context_object
        dept_ct = ContentType.objects.get_for_model(departments.model)
        dept_ids = list(departments.values_list('id', flat=True))

        qs = (
            Chat.objects.filter(
                Q(type="global")
                | Q(type="department", department__in=departments)  # старое поле
                | Q(type="department", context_content_type=dept_ct, context_object_id__in=dept_ids)  # новое поле
                | Q(type="private", participants=user)
                | Q(id__in=membership_chat_ids)  # group/channel/announcement
            )
            .exclude(
                # Скрываем заблокированные announcement
                Q(type="announcement", is_blocked=True) &
                ~Q(created_by=user)  # Создателю показываем
            )
            .exclude(
                # Скрываем заблокированные announcement и для создателя
                # если он не staff (чтобы staff мог разблокировать)
                Q(type="announcement", is_blocked=True, created_by=user) &
                Q(created_by__is_staff=False)
            )
            .distinct()
            .select_related("department", "created_by", "blocked_by")
            .annotate(last_msg_at=Subquery(last_qs))
            .annotate(
                last_read_msg_id=Coalesce(
                    Subquery(last_read_msg_qs),
                    Value(0, output_field=models.IntegerField()),
                    output_field=models.IntegerField(),
                )
            )
            .annotate(
                # Считаем только чужие сообщения с ID больше last_read_message_id
                unread_count=Count(
                    "messages",
                    filter=Q(messages__id__gt=F("last_read_msg_id"))
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
            .order_by(
                models.F("last_msg_at").desc(nulls_last=True),
                "-created_at",
            )
        )
        return qs


class ChatDetailView(LoginRequiredMixin, DetailView, FormView):
    model = Chat
    template_name = "communications/chat_detail.html"
    context_object_name = "chat"
    form_class = MessageForm

    def dispatch(self, request, *args, **kwargs):
        """Добавляем заголовки для отключения кэширования"""
        response = super().dispatch(request, *args, **kwargs)
        # Запрещаем кэширование страницы чата в браузере
        response['Cache-Control'] = (
            'no-cache, no-store, must-revalidate, max-age=0'
        )
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response

    def get_queryset(self):
        """Возвращает только чаты, к которым пользователь имеет доступ"""
        user = self.request.user
        departments = user.departments

        print(f"=" * 80)
        print(f"[CHAT DEBUG] ChatDetailView.get_queryset called")
        print(f"[CHAT DEBUG] User: {user.id} ({user.username or 'NO USERNAME'})")
        print(f"[CHAT DEBUG] Requested chat PK: {self.kwargs.get('pk')}")

        logger.info(
            f"ChatDetailView.get_queryset: user={user.id} ({user.username}), "
            f"pk={self.kwargs.get('pk')}"
        )

        # Получаем ID чатов через membership
        from communications.models import ChatMembership
        from django.contrib.contenttypes.models import ContentType
        
        membership_chat_ids = list(
            ChatMembership.objects.filter(user=user).values_list('chat_id', flat=True)
        )

        dept_ids = list(departments.values_list('id', flat=True))
        print(f"[CHAT DEBUG] User departments IDs: {dept_ids}")
        print(f"[CHAT DEBUG] User membership_chat_ids: {membership_chat_ids}")

        logger.info(
            f"User departments: {list(departments.values_list('id', flat=True))}, "
            f"membership_chat_ids: {membership_chat_ids}"
        )
        
        # Для department: проверяем и старое поле, и новое
        dept_ct = ContentType.objects.get_for_model(departments.model)

        qs = Chat.objects.filter(
            Q(type="global")
            | Q(type="department", department__in=departments)  # старое поле
            | Q(type="department", context_content_type=dept_ct, context_object_id__in=dept_ids)  # новое поле
            | Q(type="private", participants=user)
            | Q(id__in=membership_chat_ids)
        ).distinct()

        available_ids = list(qs.values_list('id', flat=True))
        print(f"[CHAT DEBUG] Available chats for user: {available_ids}")
        print(f"[CHAT DEBUG] Access to requested chat: {self.kwargs.get('pk') in available_ids}")
        print(f"=" * 80)

        logger.info(f"Available chats for user: {list(qs.values_list('id', flat=True))}")

        return qs

    def get_object(self, queryset=None):
        """Получаем объект чата с дополнительным логированием"""
        print(f"[CHAT DEBUG] get_object called")
        try:
            obj = super().get_object(queryset)
            print(f"[CHAT DEBUG] Object found: Chat {obj.id}, type={obj.type}")
            return obj
        except Exception as e:
            print(f"[CHAT DEBUG] Exception in get_object: {type(e).__name__}: {e}")
            raise

    def get_success_url(self):
        return reverse(
            "communications:chat_detail", kwargs={"pk": self.object.pk}
        )

    def _user_has_access(self, chat: Chat, user) -> bool:
        return user_can_access_chat(chat, user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        chat: Chat = self.object
        user = self.request.user

        print(f"[CHAT DEBUG] get_context_data called for chat {chat.id}")

        # защита доступа
        has_access = self._user_has_access(chat, user)
        print(f"[CHAT DEBUG] _user_has_access returned: {has_access}")

        if not has_access:
            from django.http import Http404
            print(f"[CHAT DEBUG] Raising Http404 because user has no access")
            raise Http404("Chat not found")

        # сообщения + участники
        messages_qs = (
            chat.messages
            .select_related("author")
            .prefetch_related("attachments")
            .order_by("-created_at")
        )

        page_size = CHAT_MESSAGES_PAGE_SIZE
        raw_messages = list(messages_qs[: page_size + 1])
        has_more = len(raw_messages) > page_size

        next_cursor = None
        if has_more:
            next_cursor = raw_messages.pop()

        displayed_messages = list(reversed(raw_messages))
        oldest_displayed = raw_messages[-1] if raw_messages else next_cursor

        context["messages"] = displayed_messages
        context["messages_has_more"] = has_more
        context["messages_oldest_id"] = (
            oldest_displayed.id if oldest_displayed else None
        )
        context["messages_oldest_ts"] = (
            int(oldest_displayed.created_at.timestamp() * 1000)
            if oldest_displayed
            else None
        )
        context["messages_page_size"] = page_size
        context["form"] = context.get("form", MessageForm())
        context["participants"] = chat.get_participants

        # Получаем last_read_message_id для определения непрочитанных (Telegram-style)
        read_state = (
            ChatReadState.objects.filter(chat=chat, user=user)
            .only("last_read_message_id")
            .first()
        )
        last_read_message_id = (
            read_state.last_read_message_id
            if read_state and read_state.last_read_message_id
            else None
        )
        context["last_read_message_id"] = last_read_message_id

        # Передаем last_read_message_id в chat объект для data-атрибута
        chat.last_read_message_id = last_read_message_id

        first_unread = None
        if last_read_message_id:
            # Первое непрочитанное = сообщение с ID > last_read_message_id
            first_unread = (
                chat.messages.exclude(author=user)
                .filter(id__gt=last_read_message_id)
                .order_by("id")
                .only("id", "created_at")
                .first()
            )
        context["first_unread_id"] = first_unread.id if first_unread else None
        if first_unread:
            context["unread_from_ts"] = int(
                first_unread.created_at.timestamp() * 1000
            )
        else:
            context["unread_from_ts"] = None

        # Права на отправку сообщений в объявлениях
        if chat.type == "announcement":
            # Только создатель может писать в объявление
            context["can_send_messages"] = (chat.created_by == user)
            context["is_announcement_creator"] = (chat.created_by == user)
        else:
            # В других типах чатов проверяем can_send_messages
            membership = ChatMembership.objects.filter(
                chat=chat, user=user
            ).first()
            context["can_send_messages"] = (
                membership.can_send_messages if membership
                else True  # По умолчанию можно писать
            )
            context["is_announcement_creator"] = False

        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        user = request.user
        chat = self.object

        if not ChatDetailView._user_has_access(self, chat, user):
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden("forbidden")

        # Проверка прав на отправку сообщений
        if chat.type == "announcement":
            # Только создатель может писать в объявление
            if chat.created_by != user:
                from django.http import HttpResponseForbidden
                return HttpResponseForbidden(
                    "Только автор может публиковать в это объявление"
                )
        else:
            # В других типах чатов проверяем can_send_messages
            membership = ChatMembership.objects.filter(
                chat=chat, user=user
            ).first()
            if membership and not membership.can_send_messages:
                from django.http import HttpResponseForbidden
                return HttpResponseForbidden(
                    "У вас нет прав для отправки сообщений"
                )

        form = self.get_form()
        if form.is_valid():
            msg = form.save(commit=False)
            msg.chat = chat
            msg.author = user
            msg.save()

            # Автоматически отмечаем свое сообщение как прочитанное (Telegram-style)
            read_state, created = ChatReadState.objects.get_or_create(
                chat=chat,
                user=user,
                defaults={'last_read_message': msg}
            )
            if not created:
                # Обновляем только если новое сообщение НОВЕЕ
                if not read_state.last_read_message_id or msg.id > read_state.last_read_message_id:
                    read_state.last_read_message = msg
                    read_state.save(update_fields=['last_read_message', 'updated_at'])

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
            ChatReadState.objects.create(
                chat=chat,
                user=user,
                last_read_at=now_ts,
            )
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
        if c.type == "global":
            return True
        if c.type in ("private", "group"):  # Групповые и личные чаты
            return c.participants.filter(pk=u.pk).exists()
        if c.type == "department":
            # Используем get_participants() - поддерживает и department, и context_object
            return c.get_participants().filter(pk=u.pk).exists()
        if c.type in ("channel", "announcement"):
            # Для каналов и объявлений проверяем participants или include_all_users
            if c.include_all_users:
                return u.is_active
            return c.participants.filter(pk=u.pk).exists()
        return False

    if not has_access(chat, user):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    # Целевая точка времени: приоритет у upto_ts, затем последний месседж
    ts = _coerce_ts(request.POST.get("upto_ts"))

    if ts is None:
        # Фоллбек на последнее сообщение
        ts = (
            chat.messages.order_by("-created_at")
            .values_list("created_at", flat=True)
            .first()
            or timezone.now()
        )

    # Обновляем только если новее; без update_or_create — устойчиво к SQLite/гонкам
    updated = ChatReadState.objects.filter(
        chat=chat, user=user, last_read_at__lt=ts
    ).update(last_read_at=ts)
    if not updated:
        try:
            ChatReadState.objects.create(chat=chat, user=user, last_read_at=ts)
        except IntegrityError:
            ChatReadState.objects.filter(
                chat=chat, user=user, last_read_at__lt=ts
            ).update(last_read_at=ts)

    return JsonResponse(
        {"ok": True, "last_read_at": int(ts.timestamp() * 1000)}
    )

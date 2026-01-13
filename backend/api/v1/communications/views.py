# backend/api/v1/communications/views.py
"""API views для чатов и сообщений"""

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from django.db.models import Q, Max, Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from communications.models import (
    Chat,
    ChatMembership,
    ChatUserSettings,
    Message,
    MessageAttachment,
    MessageReaction,
)
from communications.consumers import serialize_message
from communications.views import _coerce_ts, user_can_access_chat


@login_required
@require_GET
def get_user_chats(request):
    """Получить список чатов пользователя"""
    user = request.user
    
    # Получаем все чаты, к которым пользователь имеет доступ
    chats = Chat.objects.filter(
        Q(type='global') |  # Глобальные чаты доступны всем
        Q(participants=user) |  # Личные чаты где пользователь участник
        Q(memberships__user=user,
          memberships__is_active=True) |  # Групповые
        Q(department__employeedepartment__employee=user,
          department__employeedepartment__is_active=True) |  # Отдельские
        Q(department__head=user)  # Руководитель отдела
    ).distinct().annotate(
        last_message_time=Max('messages__created_at')
    ).prefetch_related(
        Prefetch('messages',
                 queryset=Message.objects.order_by('-created_at')[:1],
                 to_attr='latest_messages')
    ).order_by('-last_message_time')
    
    # Сериализуем чаты
    chat_list = []
    for chat in chats:
        # Получаем аватар чата
        avatar = None
        if chat.type == 'private':
            # Для личных чатов - аватар собеседника
            other_user = chat.participants.exclude(id=user.id).first()
            if (other_user and hasattr(other_user, 'avatar')
                    and other_user.avatar):
                try:
                    avatar = request.build_absolute_uri(other_user.avatar.url)
                except Exception:
                    pass
        elif chat.type == 'department' and chat.department:
            # Для отдельских - аватар руководителя
            head = chat.department.head
            if head and hasattr(head, 'avatar'):
                try:
                    avatar = request.build_absolute_uri(head.avatar.url)
                except Exception:
                    pass

        # Последнее сообщение
        last_message = None
        if hasattr(chat, 'latest_messages') and chat.latest_messages:
            msg = chat.latest_messages[0]
            last_message = {
                'content': msg.content[:50],
                'created_at': msg.created_at.isoformat(),
                'author_name': (
                    msg.author.get_full_name()
                    or msg.author.username
                )
            }
        
        chat_list.append({
            'id': chat.id,
            'name': chat.name,
            'type': chat.type,
            'avatar': avatar,
            'last_message': last_message,
            'created_at': chat.created_at.isoformat(),
        })
    
    return JsonResponse({'results': chat_list})


@csrf_protect
@login_required
@require_POST
def upload_message_with_attachments(request):
    """Отправка сообщения с вложениями"""
    chat_id = request.POST.get('chat_id')
    content = request.POST.get('content', '').strip()
    reply_to_id = request.POST.get('reply_to')
    
    # Логируем для отладки
    print(f"[DEBUG] upload_message: chat_id={chat_id}, "
          f"reply_to_id={reply_to_id}, "
          f"content_length={len(content)}")
    
    if not chat_id:
        return JsonResponse(
            {'ok': False, 'error': 'chat_id required'},
            status=400
        )
    
    chat = get_object_or_404(Chat, pk=chat_id)
    
    # Проверка доступа к чату
    # Для групповых, канальных и объявлений проверяем ChatMembership
    if chat.type in ['group', 'channel', 'announcement']:
        membership = ChatMembership.objects.filter(
            chat=chat,
            user=request.user,
            is_active=True,
            can_send_messages=True
        ).first()
        
        if not membership:
            return JsonResponse(
                {'ok': False, 'error': 'Cannot send messages to this chat'},
                status=403
            )
    # Для личных чатов проверяем, что пользователь - участник
    elif chat.type == 'private':
        if not chat.participants.filter(id=request.user.id).exists():
            return JsonResponse(
                {'ok': False, 'error': 'You are not a participant'},
                status=403
            )
    # Для чатов отдела проверяем принадлежность к отделу
    elif chat.type == 'department':
        if chat.department:
            from employees.models import EmployeeDepartment
            is_member = EmployeeDepartment.objects.filter(
                department=chat.department,
                employee=request.user,
                is_active=True
            ).exists()
            if not is_member and chat.department.head_id != request.user.id:
                return JsonResponse(
                    {'ok': False, 'error': 'Not a department member'},
                    status=403
                )
    # Глобальный чат доступен всем активным пользователям
    elif chat.type == 'global':
        if not request.user.is_active:
            return JsonResponse(
                {'ok': False, 'error': 'User is not active'},
                status=403
            )
    
    # Если нет ни текста, ни файлов
    if not content and not request.FILES:
        return JsonResponse(
            {'ok': False, 'error': 'Content or files required'},
            status=400
        )
    
    with transaction.atomic():
        # Получаем reply_to сообщение если указано
        reply_to = None
        if reply_to_id:
            try:
                reply_to = Message.objects.get(pk=reply_to_id, chat=chat)
                print(f"[DEBUG] Found reply_to message: id={reply_to.id}, "
                      f"author={reply_to.author.username}")
            except Message.DoesNotExist:
                print(f"[DEBUG] reply_to message {reply_to_id} not found")
                pass  # Игнорируем если сообщение не найдено
        
        # Создаем сообщение
        message = Message.objects.create(
            chat=chat,
            author=request.user,
            content=content or '',
            has_attachments=bool(request.FILES),
            reply_to=reply_to
        )
        
        print(f"[DEBUG] Created message: id={message.id}, "
              f"reply_to_id={message.reply_to_id}")
        
        # Обрабатываем все загруженные файлы
        attachments = []
        for file_key in request.FILES:
            uploaded_file = request.FILES[file_key]
            
            # Определение типа файла
            mime_type = uploaded_file.content_type or ''
            if mime_type.startswith('image/'):
                file_type = 'image'
            elif mime_type.startswith('video/'):
                file_type = 'video'
            elif mime_type.startswith('audio/'):
                file_type = 'audio'
            else:
                file_type = 'file'
            
            attachment = MessageAttachment.objects.create(
                message=message,
                file=uploaded_file,
                file_type=file_type,
                file_name=uploaded_file.name,
                file_size=uploaded_file.size,
                mime_type=mime_type
            )
            
            attachments.append({
                'id': attachment.id,
                'file_name': attachment.file_name,
                'file_type': attachment.file_type,
                'file_url': attachment.file.url,
                'file_size': attachment.file_size,
                'mime_type': attachment.mime_type
            })
    
    # Отправляем сообщение через WebSocket всем участникам чата
    channel_layer = get_channel_layer()
    group_name = f"chat_{chat.id}"
    
    # Перезагружаем сообщение с предзагрузкой связей для правильной сериализации
    message = Message.objects.select_related(
        'author',
        'reply_to__author'
    ).prefetch_related('attachments').get(pk=message.id)
    
    # Сериализуем сообщение для WebSocket
    message_data = serialize_message(message)
    
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": "chat.message",
            "chat_id": chat.id,
            "payload": message_data
        }
    )
    
    avatar_url = None
    if hasattr(request.user, 'avatar') and request.user.avatar:
        avatar_url = request.user.avatar.url
    
    return JsonResponse({
        'ok': True,
        'message_id': message.id,
        'chat_id': chat.id,
        'author': {
            'id': request.user.id,
            'full_name': request.user.get_full_name(),
            'avatar': avatar_url
        },
        'content': message.content,
        'created_at': message.created_at.isoformat(),
        'attachments': attachments
    })


@login_required
@require_GET
def load_chat_messages(request, pk: int):
    """
    Постраничная загрузка сообщений чата.
    
    Поддерживает двунаправленную загрузку как в Telegram:
    - before_id / before_ts: загрузка старых сообщений (история)
    - after_id / after_ts: загрузка новых сообщений (при прокрутке вниз после перехода по дате)
    """
    chat = get_object_or_404(Chat, pk=pk)
    user = request.user

    if not user_can_access_chat(chat, user):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    try:
        limit = int(request.GET.get("limit", 30))
    except (TypeError, ValueError):
        limit = 30
    limit = max(1, min(limit, 100))

    before_id = request.GET.get("before_id")
    before_ts = request.GET.get("before_ts")
    after_id = request.GET.get("after_id")
    after_ts = request.GET.get("after_ts")

    qs = (
        Message.objects.filter(chat=chat)
        .select_related("author", "reply_to__author")
        .prefetch_related("attachments")
    )

    # Определяем направление загрузки
    is_loading_newer = bool(after_id or after_ts)
    
    if after_id:
        # Загрузка НОВЫХ сообщений (after_id) - для прокрутки вниз после перехода по дате
        boundary = (
            Message.objects.filter(chat=chat, pk=after_id)
            .only("created_at")
            .first()
        )
        if boundary:
            qs = qs.filter(created_at__gt=boundary.created_at).order_by("created_at")
        else:
            qs = qs.order_by("created_at")
    elif after_ts:
        # Загрузка НОВЫХ по timestamp
        boundary_ts = _coerce_ts(after_ts)
        qs = qs.filter(created_at__gt=boundary_ts).order_by("created_at")
    elif before_id:
        # Загрузка СТАРЫХ сообщений (before_id) - обычная история
        boundary = (
            Message.objects.filter(chat=chat, pk=before_id)
            .only("created_at")
            .first()
        )
        if boundary:
            qs = qs.filter(created_at__lt=boundary.created_at).order_by("-created_at")
        else:
            qs = qs.order_by("-created_at")
    elif before_ts:
        # Загрузка СТАРЫХ по timestamp
        boundary_ts = _coerce_ts(before_ts)
        qs = qs.filter(created_at__lt=boundary_ts).order_by("-created_at")
    else:
        # По умолчанию - последние сообщения
        qs = qs.order_by("-created_at")

    batch = list(qs[: limit + 1])
    has_more = len(batch) > limit

    if has_more:
        batch = batch[:-1]

    # Для after_id сообщения уже в правильном порядке (от старых к новым)
    # Для before_id нужно перевернуть (сейчас от новых к старым)
    if not is_loading_newer:
        batch = list(reversed(batch))

    serialized = [serialize_message(m) for m in batch]

    # Определяем next cursor в зависимости от направления
    if is_loading_newer:
        next_cursor = batch[-1] if batch else None
        return JsonResponse({
            "ok": True,
            "messages": serialized,
            "has_more": has_more,
            "has_more_after": has_more,
            "next_after_id": next_cursor.id if next_cursor else None,
            "next_after_ts": (
                int(next_cursor.created_at.timestamp() * 1000)
                if next_cursor else None
            ),
        })
    else:
        next_cursor = batch[0] if batch else None
        return JsonResponse({
            "ok": True,
            "messages": serialized,
            "has_more": has_more,
            "has_more_before": has_more,
            "next_before_id": next_cursor.id if next_cursor else None,
            "next_before_ts": (
                int(next_cursor.created_at.timestamp() * 1000)
                if next_cursor else None
            ),
        })


@login_required
@require_GET
def load_chat_messages_around(request, pk: int):
    """
    Загрузка сообщений ВОКРУГ конкретного message_id.
    Современная архитектура как в Telegram/Discord/WhatsApp.
    
    Параметры:
    - around_id: ID сообщения-якоря (обычно last_read_message_id)
    - limit: Общее количество сообщений (по умолчанию 50)
    
    Возвращает примерно limit/2 сообщений ДО и limit/2 ПОСЛЕ якоря.
    """
    chat = get_object_or_404(Chat, pk=pk)
    user = request.user

    if not user_can_access_chat(chat, user):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    try:
        limit = int(request.GET.get("limit", 50))
    except (TypeError, ValueError):
        limit = 50
    limit = max(10, min(limit, 100))
    
    around_id = request.GET.get("around_id")
    
    # Если нет around_id, пытаемся получить last_read_message_id
    if not around_id:
        try:
            from communications.models import ChatReadState
            read_state = ChatReadState.objects.filter(
                chat=chat, user=user
            ).first()
            
            if read_state and read_state.last_read_message_id:
                around_id = read_state.last_read_message_id
        except Exception:
            pass
    
    # Если все еще нет around_id - загружаем последние сообщения
    if not around_id:
        return load_chat_messages(request, pk)
    
    # Находим anchor message
    # ВАЖНО: around_id может быть либо message_id, либо timestamp
    # Определяем по размеру: message_id обычно < 1000000, timestamp > 1000000000
    try:
        around_value = int(around_id)
        
        # Если это большое число (> 1 миллиард) - вероятно timestamp в миллисекундах
        if around_value > 1_000_000_000:
            # Конвертируем timestamp из миллисекунд в seconds
            from datetime import datetime, timezone
            timestamp_seconds = around_value / 1000
            anchor_dt = datetime.fromtimestamp(timestamp_seconds, tz=timezone.utc)
            
            # Ищем ближайшее сообщение к этому timestamp
            anchor = Message.objects.filter(
                chat=chat,
                created_at__lte=anchor_dt
            ).order_by('-created_at').first()
            
            # Если не нашли до этого времени, берем первое после
            if not anchor:
                anchor = Message.objects.filter(
                    chat=chat,
                    created_at__gte=anchor_dt
                ).order_by('created_at').first()
        else:
            # Это обычный message_id
            anchor = Message.objects.filter(chat=chat, pk=around_value).first()
            
    except (ValueError, TypeError):
        # Невалидный ID - загружаем последние
        return load_chat_messages(request, pk)
    
    if not anchor:
        # Сообщение не найдено - загружаем последние
        return load_chat_messages(request, pk)
    
    half = limit // 2
    
    # Сообщения ДО anchor (более старые)
    before_qs = (
        Message.objects.filter(chat=chat, created_at__lt=anchor.created_at)
        .select_related("author", "reply_to__author")
        .prefetch_related("attachments", "reactions__user")
        .order_by("-created_at")[: half]
    )
    before_messages = list(reversed(list(before_qs)))
    
    # Сообщения ПОСЛЕ anchor включая само anchor (более новые)
    after_qs = (
        Message.objects.filter(chat=chat, created_at__gte=anchor.created_at)
        .select_related("author", "reply_to__author")
        .prefetch_related("attachments", "reactions__user")
        .order_by("created_at")[: half + 1]
    )
    after_messages = list(after_qs)
    
    # Объединяем
    all_messages = before_messages + after_messages
    serialized = [serialize_message(m) for m in all_messages]
    
    return JsonResponse({
        "ok": True,
        "messages": serialized,
        "anchor_id": anchor.id,  # ИСПРАВЛЕНО: возвращаем реальный message_id, а не входной параметр
        "anchor_index": len(before_messages),  # Позиция anchor в массиве
        "has_more_before": len(before_messages) >= half,
        "has_more_after": len(after_messages) > half,
        "total_loaded": len(all_messages)
    })


# ============ MESSAGE REACTIONS ============

@login_required
@require_GET
def get_available_reactions(request):
    """Получить список доступных реакций"""
    from communications.models import AvailableReaction
    
    reactions = AvailableReaction.objects.filter(is_active=True)
    
    return JsonResponse({
        'ok': True,
        'reactions': [
            {
                'emoji': reaction.emoji,
                'name': reaction.name,
                'order': reaction.order
            }
            for reaction in reactions
        ]
    })


@login_required
@require_POST
def add_reaction(request, message_id):
    """Добавить или изменить реакцию на сообщение"""
    import json
    
    message = get_object_or_404(Message, pk=message_id)
    
    # Проверка доступа к чату
    if not user_can_access_chat(message.chat, request.user):
        return JsonResponse(
            {'ok': False, 'error': 'Access denied'}, status=403
        )
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse(
            {'ok': False, 'error': 'Invalid JSON'}, status=400
        )
    
    emoji = data.get('emoji', '').strip()
    
    if not emoji:
        return JsonResponse(
            {'ok': False, 'error': 'emoji required'}, status=400
        )
    
    # Один пользователь может иметь только одну реакцию на сообщение
    # Если уже есть - обновляем emoji, иначе создаём новую
    reaction, created = MessageReaction.objects.update_or_create(
        message=message,
        user=request.user,
        defaults={'emoji': emoji}
    )
    
    # Получаем все реакции для этого сообщения
    reactions_data = get_reactions_summary(message)
    
    # Отправляем WebSocket уведомление
    channel_layer = get_channel_layer()
    if channel_layer:
        group_name = f"chat_{message.chat_id}"
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "chat.reaction_added",
                "chat_id": message.chat_id,
                "message_id": message.id,
                "user_id": request.user.id,
                "emoji": emoji,
                "reactions_summary": reactions_data,
            },
        )
    
    return JsonResponse({
        'ok': True,
        'created': created,
        'reaction': {
            'id': reaction.id,
            'emoji': reaction.emoji,
            'user_id': reaction.user_id,
            'created_at': reaction.created_at.isoformat()
        },
        'reactions_summary': reactions_data
    })


@login_required
@require_POST
def remove_reaction(request, message_id):
    """Удалить свою реакцию с сообщения"""
    
    message = get_object_or_404(Message, pk=message_id)
    
    # Проверка доступа к чату
    if not user_can_access_chat(message.chat, request.user):
        return JsonResponse(
            {'ok': False, 'error': 'Access denied'}, status=403
        )
    
    # Сохраняем emoji перед удалением
    reaction_to_delete = MessageReaction.objects.filter(
        message=message,
        user=request.user
    ).first()
    
    deleted_emoji = reaction_to_delete.emoji if reaction_to_delete else None
    
    # Удаляем реакцию текущего пользователя
    deleted_count, _ = MessageReaction.objects.filter(
        message=message,
        user=request.user
    ).delete()
    
    if deleted_count == 0:
        return JsonResponse(
            {'ok': False, 'error': 'Reaction not found'}, status=404
        )
    
    # Получаем обновлённый список реакций
    reactions_data = get_reactions_summary(message)
    
    # Отправляем WebSocket уведомление
    channel_layer = get_channel_layer()
    if channel_layer:
        group_name = f"chat_{message.chat_id}"
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "chat.reaction_removed",
                "chat_id": message.chat_id,
                "message_id": message.id,
                "user_id": request.user.id,
                "emoji": deleted_emoji,
                "reactions_summary": reactions_data,
            },
        )
    
    return JsonResponse({
        'ok': True,
        'reactions_summary': reactions_data
    })


@login_required
@require_GET
def get_message_reactions(request, message_id):
    """Получить все реакции для сообщения"""
    message = get_object_or_404(Message, pk=message_id)
    
    # Проверка доступа к чату
    if not user_can_access_chat(message.chat, request.user):
        return JsonResponse(
            {'ok': False, 'error': 'Access denied'}, status=403
        )
    
    reactions_data = get_reactions_summary(message)
    
    return JsonResponse({
        'ok': True,
        'message_id': message_id,
        'reactions': reactions_data
    })


def get_reactions_summary(message):
    """
    Вспомогательная функция для получения сводки по реакциям
    Возвращает словарь вида:
    {
        '👍': {'count': 3, 'users': [1, 2, 3], 'user_names': [...]},
        '❤️': {'count': 1, 'users': [4], 'user_names': [...]}
    }
    """
    
    reactions = MessageReaction.objects.filter(
        message=message
    ).select_related('user')
    
    # Группируем по эмодзи
    summary = {}
    for reaction in reactions:
        emoji = reaction.emoji
        if emoji not in summary:
            summary[emoji] = {
                'count': 0,
                'users': [],
                'user_names': []
            }
        summary[emoji]['count'] += 1
        summary[emoji]['users'].append(reaction.user_id)
        summary[emoji]['user_names'].append(
            reaction.user.get_full_name() or reaction.user.username
        )
    
    return summary


# ============ CHAT USER SETTINGS ============

@login_required
@require_POST
def pin_chat(request, chat_id):
    """Закрепление/открепление чата"""
    chat = get_object_or_404(Chat, pk=chat_id)
    is_pinned = request.POST.get('pinned', 'true').lower() == 'true'
    
    settings, created = ChatUserSettings.objects.get_or_create(
        chat=chat,
        user=request.user
    )
    
    settings.is_pinned = is_pinned
    if is_pinned:
        settings.pinned_at = timezone.now()
        # Определяем порядок
        max_order = ChatUserSettings.objects.filter(
            user=request.user,
            is_pinned=True
        ).aggregate(max_order=models.Max('pin_order'))['max_order'] or 0
        settings.pin_order = max_order + 1
    else:
        settings.pinned_at = None
        settings.pin_order = 0
    
    settings.save()
    
    return JsonResponse({'ok': True, 'pinned': is_pinned})


@login_required
@require_POST
@csrf_protect
def toggle_chat_notifications(request, chat_id):
    """Включение/выключение уведомлений для чата"""
    import json
    
    chat = get_object_or_404(Chat, pk=chat_id)
    
    # Проверка доступа к чату
    if not user_can_access_chat(chat, request.user):
        return JsonResponse(
            {'ok': False, 'error': 'Access denied'}, 
            status=403
        )
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse(
            {'ok': False, 'error': 'Invalid JSON'}, 
            status=400
        )
    
    enabled = data.get('enabled', True)
    
    settings, created = ChatUserSettings.objects.get_or_create(
        chat=chat,
        user=request.user
    )
    
    settings.notifications_enabled = enabled
    settings.save()
    
    return JsonResponse({
        'ok': True, 
        'enabled': enabled,
        'message': f'Уведомления {"включены" if enabled else "отключены"}'
    })


# ============ MESSAGE FORWARDING ============

@login_required
@require_POST
@csrf_protect
def forward_messages(request):
    """Пересылка сообщений в другой чат"""
    import json
    import traceback
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        return JsonResponse(
            {'ok': False, 'error': 'Invalid JSON'},
            status=400
        )
    
    try:
        message_ids = data.get('message_ids', [])
        target_chat_id = data.get('target_chat_id')
        
        print(f"Forward request: message_ids={message_ids}, target_chat_id={target_chat_id}")
        
        if not message_ids or not target_chat_id:
            return JsonResponse(
                {'ok': False, 'error': 'message_ids and target_chat_id required'},
                status=400
            )
        
        # Получаем целевой чат
        target_chat = get_object_or_404(Chat, pk=target_chat_id)
        
        # Проверяем доступ к целевому чату
        if not user_can_access_chat(target_chat, request.user):
            return JsonResponse(
                {'ok': False, 'error': 'Access denied to target chat'},
                status=403
            )
        
        # Проверяем право отправки в целевой чат
        if target_chat.type in ['group', 'channel', 'announcement']:
            membership = ChatMembership.objects.filter(
                chat=target_chat,
                user=request.user,
                is_active=True,
                can_send_messages=True
            ).first()
            if not membership:
                return JsonResponse(
                    {'ok': False, 'error': 'Cannot send messages to target chat'},
                    status=403
                )
        
        # Получаем исходные сообщения
        messages = Message.objects.filter(
            id__in=message_ids
        ).select_related('author', 'chat').order_by('created_at')
        
        if not messages:
            return JsonResponse(
                {'ok': False, 'error': 'No messages found'},
                status=404
            )
        
        # Проверяем доступ к исходным чатам
        for msg in messages:
            if not user_can_access_chat(msg.chat, request.user):
                return JsonResponse(
                    {'ok': False, 'error': f'Access denied to message {msg.id}'},
                    status=403
                )
        
        # Пересылаем сообщения
        forwarded_messages = []
        channel_layer = get_channel_layer()
        
        with transaction.atomic():
            for original_msg in messages:
                # Создаем новое сообщение с пометкой "переслано"
                forwarded_content = original_msg.content
                
                # Получаем название исходного чата
                source_chat_name = original_msg.chat.name or "Чат"
                if original_msg.chat.type == "private":
                    # Для личных чатов показываем "от кого"
                    other_user = original_msg.chat.get_other_user(
                        request.user
                    )
                    if other_user:
                        source_chat_name = (
                            other_user.get_full_name() or
                            other_user.username
                        )
                
                # Если пересылаем уже пересланное сообщение -
                # сохраняем оригинальную цепочку
                if original_msg.is_forwarded:
                    # Берём метаданные из оригинального сообщения
                    # (первого в цепочке)
                    forwarded_from_author = (
                        original_msg.forwarded_from_author
                    )
                    forwarded_from_created_at = (
                        original_msg.forwarded_from_created_at
                    )
                    forwarded_from_chat_name = (
                        original_msg.forwarded_from_chat_name
                    )
                else:
                    # Это первая пересылка - берём метаданные
                    # из текущего сообщения
                    forwarded_from_author = original_msg.author
                    forwarded_from_created_at = original_msg.created_at
                    forwarded_from_chat_name = source_chat_name
                
                # Создаем переслаанное сообщение с метаданными
                forwarded_msg = Message.objects.create(
                    chat=target_chat,
                    author=request.user,
                    content=forwarded_content,
                    is_forwarded=True,
                    forwarded_from_message_id=original_msg.id,
                    forwarded_from_author=forwarded_from_author,
                    forwarded_from_created_at=forwarded_from_created_at,
                    forwarded_from_chat_name=forwarded_from_chat_name,
                )
                
                # Копируем вложения если есть
                attachments = MessageAttachment.objects.filter(
                    message=original_msg
                )
                for attachment in attachments:
                    MessageAttachment.objects.create(
                        message=forwarded_msg,
                        file=attachment.file,
                        file_name=attachment.file_name,
                        file_size=attachment.file_size,
                        file_type=attachment.file_type
                    )
                
                forwarded_messages.append(forwarded_msg)
                
                # Отправляем WebSocket уведомление в целевой чат
                serialized = serialize_message(forwarded_msg)
                async_to_sync(channel_layer.group_send)(
                    f'chat_{target_chat.id}',
                    {
                        'type': 'chat_message',
                        'payload': serialized
                    }
                )
        
        return JsonResponse({
            'ok': True,
            'forwarded_count': len(forwarded_messages),
            'message_ids': [msg.id for msg in forwarded_messages]
        })
    
    except Exception as e:
        print(f"Error forwarding messages: {e}")
        print(traceback.format_exc())
        return JsonResponse(
            {'ok': False, 'error': str(e)},
            status=500
        )


@login_required
@require_POST
@csrf_protect
def bulk_delete_messages(request):
    """Массовое удаление сообщений"""
    import json
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse(
            {'ok': False, 'error': 'Invalid JSON'},
            status=400
        )
    
    message_ids = data.get('message_ids', [])
    
    if not message_ids:
        return JsonResponse(
            {'ok': False, 'error': 'message_ids required'},
            status=400
        )
    
    # Получаем сообщения
    messages = Message.objects.filter(
        id__in=message_ids,
        author=request.user  # Можно удалять только свои сообщения
    )
    
    if not messages:
        return JsonResponse(
            {'ok': False, 'error': 'No messages found or access denied'},
            status=404
        )
    
    # Удаляем сообщения и отправляем WebSocket уведомления
    channel_layer = get_channel_layer()
    deleted_count = 0
    
    with transaction.atomic():
        for msg in messages:
            chat_id = msg.chat_id
            message_id = msg.id
            
            # Удаляем сообщение
            msg.delete()
            deleted_count += 1
            
            # Отправляем WebSocket уведомление
            async_to_sync(channel_layer.group_send)(
                f'chat_{chat_id}',
                {
                    'type': 'chat_message_deleted',
                    'message_id': message_id
                }
            )
    
    return JsonResponse({
        'ok': True,
        'deleted_count': deleted_count
    })


@csrf_protect
@login_required
@require_POST
def edit_message(request, message_id):
    """Редактирование сообщения"""
    import json
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse(
            {'ok': False, 'error': 'Invalid JSON'},
            status=400
        )
    
    new_content = data.get('content', '').strip()
    
    if not new_content:
        return JsonResponse(
            {'ok': False, 'error': 'content required'},
            status=400
        )
    
    # Получаем сообщение
    try:
        message = Message.objects.get(pk=message_id, author=request.user)
    except Message.DoesNotExist:
        return JsonResponse(
            {'ok': False, 'error': 'Message not found or access denied'},
            status=404
        )
    
    # Проверяем тип чата (запрет редактирования в объявлениях)
    if message.chat.type == "announcement":
        return JsonResponse(
            {'ok': False, 'error': 'Editing is not allowed in announcements'},
            status=403
        )
    
    # Сохраняем старый контент в историю редактирования
    if not message.is_edited:
        message.edit_history = []
    
    message.edit_history.append({
        'timestamp': timezone.now().isoformat(),
        'old_content': message.content
    })
    
    # Обновляем сообщение
    message.content = new_content
    message.is_edited = True
    message.edited_at = timezone.now()
    message.save()
    
    # Перезагружаем сообщение со всеми связанными объектами
    # для корректной сериализации
    message = Message.objects.select_related(
        'author',
        'reply_to',
        'reply_to__author',
        'forwarded_from_author',
        'poll'  # OneToOne связь
    ).prefetch_related(
        'attachments',
        'reactions',
        'reactions__user',
        'poll__options'  # Опции голосования
    ).get(pk=message.id)
    
    # Отправляем WebSocket уведомление о редактировании
    channel_layer = get_channel_layer()
    payload = serialize_message(message)
    
    async_to_sync(channel_layer.group_send)(
        f'chat_{message.chat_id}',
        {
            'type': 'chat.message_edited',
            'chat_id': message.chat_id,
            'payload': payload
        }
    )
    
    # Находим все сообщения, которые ссылаются на это (reply_to)
    # и отправляем обновления для них тоже
    import logging
    logger = logging.getLogger(__name__)
    
    reply_messages = Message.objects.filter(
        reply_to=message,
        chat=message.chat
    ).select_related(
        'author',
        'reply_to',
        'reply_to__author',
        'forwarded_from_author',
        'poll'
    ).prefetch_related(
        'attachments',
        'reactions',
        'reactions__user',
        'poll__options'
    )
    
    reply_count = reply_messages.count()
    logger.info(
        "[EDIT_MSG] Message %s edited, found %s reply messages",
        message.id, reply_count
    )
    
    for reply_msg in reply_messages:
        reply_payload = serialize_message(reply_msg)
        logger.info(
            "[EDIT_MSG] Updating reply message %s (reply_to.content='%s')",
            reply_msg.id, reply_msg.reply_to.content[:50]
        )
        async_to_sync(channel_layer.group_send)(
            f'chat_{message.chat_id}',
            {
                'type': 'chat.message_edited',
                'chat_id': message.chat_id,
                'payload': reply_payload
            }
        )
    
    return JsonResponse({
        'ok': True,
        'message': payload
    })


@csrf_protect
@login_required
@require_POST
def delete_message(request, message_id):
    """Удаление одного сообщения"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(
        "[API_DELETE] API called: message_id=%s, user=%s",
        message_id, request.user.username
    )
    
    # Получаем сообщение
    try:
        message = Message.objects.get(pk=message_id, author=request.user)
    except Message.DoesNotExist:
        logger.warning(
            "[API_DELETE] Message not found: message_id=%s", message_id
        )
        return JsonResponse(
            {'ok': False, 'error': 'Message not found or access denied'},
            status=404
        )
    
    chat_id = message.chat_id
    logger.info("[API_DELETE] Message found: chat_id=%s", chat_id)
    
    # Удаляем сообщение
    message.delete()
    logger.info("[API_DELETE] Message deleted from DB")
    
    # Отправляем WebSocket уведомление об удалении
    logger.info(
        "[API_DELETE] Sending WebSocket to group: chat_%s", chat_id
    )
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'chat_{chat_id}',
        {
            'type': 'chat.message_deleted',  # ✅ С ТОЧКОЙ!
            'chat_id': chat_id,  # ✅ Добавили chat_id!
            'message_id': message_id
        }
    )
    logger.info("[API_DELETE] WebSocket event sent")
    
    return JsonResponse({
        'ok': True,
        'message_id': message_id
    })


@csrf_protect
@login_required
@require_POST
def create_chat(request):
    """Создание нового чата (группового, канала, объявлений и т.д.)"""
    user = request.user
    
    # Получаем параметры
    chat_type = request.POST.get('type', 'group')
    name = request.POST.get('name', '').strip()
    description = request.POST.get('description', '').strip()
    department_id = request.POST.get('department_id')
    include_all = request.POST.get('include_all_employees') == 'true'
    is_main = request.POST.get('is_main') == 'true'
    participant_ids = request.POST.getlist('participant_ids')
    avatar_file = request.FILES.get('avatar')
    
    # Валидация
    if not name:
        return JsonResponse({'error': 'Название чата обязательно'}, status=400)
    
    # Проверка на существующий чат объявлений
    if chat_type == 'announcement':
        existing = Chat.objects.filter(
            type='announcement',
            created_by=user
        ).first()
        
        if existing:
            return JsonResponse({
                'error': 'У вас уже есть чат объявлений',
                'existing_chat_id': existing.id
            }, status=400)
    
    try:
        with transaction.atomic():
            # Создаём чат
            chat = Chat.objects.create(
                type=chat_type,
                name=name,
                description=description,
                created_by=user,
                include_all_employees=include_all,
                is_main=is_main
            )
            
            # Аватар
            if avatar_file:
                chat.avatar = avatar_file
                chat.save()
            
            # Привязка к отделу
            if chat_type == 'department' and department_id:
                from employees.models import Department
                try:
                    dept = Department.objects.get(id=department_id)
                    chat.department = dept
                    chat.save()
                except Department.DoesNotExist:
                    pass
            
            # Добавляем участников для группового чата
            if chat_type == 'group' and participant_ids:
                from employees.models import Employee
                participants = Employee.objects.filter(id__in=participant_ids)
                chat.participants.add(*participants)
                # Добавляем создателя
                chat.participants.add(user)
            
            # Для канала/объявлений добавляем создателя как участника
            if chat_type in ('channel', 'announcement'):
                chat.participants.add(user)
        
        return JsonResponse({
            'ok': True,
            'chat_id': chat.id,
            'message': 'Чат успешно создан'
        })
        
    except Exception as e:
        return JsonResponse({
            'error': f'Ошибка при создании чата: {str(e)}'
        }, status=500)



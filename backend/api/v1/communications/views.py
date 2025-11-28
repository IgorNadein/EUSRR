# backend/api/v1/communications/views.py
"""API views для чатов и сообщений"""

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from communications.models import (
    Chat,
    ChatMembership,
    Message,
    MessageAttachment,
)
from communications.consumers import serialize_message
from communications.views import _coerce_ts, user_can_access_chat


@csrf_protect
@login_required
@require_POST
def upload_message_with_attachments(request):
    """Отправка сообщения с вложениями"""
    chat_id = request.POST.get('chat_id')
    content = request.POST.get('content', '').strip()
    
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
        # Создаем сообщение
        message = Message.objects.create(
            chat=chat,
            author=request.user,
            content=content or '',
            has_attachments=bool(request.FILES)
        )
        
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
    """Постраничная загрузка истории чата (старые сообщения)."""
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

    qs = (
        Message.objects.filter(chat=chat)
        .select_related("author")
        .prefetch_related("attachments")
        .order_by("-created_at")
    )

    if before_id:
        boundary = (
            Message.objects.filter(chat=chat, pk=before_id)
            .only("created_at")
            .first()
        )
        if boundary:
            qs = qs.filter(created_at__lt=boundary.created_at)
    elif before_ts:
        boundary_ts = _coerce_ts(before_ts)
        qs = qs.filter(created_at__lt=boundary_ts)

    batch = list(qs[: limit + 1])
    has_more = len(batch) > limit
    next_cursor = None

    if has_more:
        next_cursor = batch[-1]
        batch = batch[:-1]
    elif batch:
        next_cursor = batch[-1]

    serialized = [serialize_message(m) for m in reversed(batch)]

    return JsonResponse(
        {
            "ok": True,
            "messages": serialized,
            "has_more": has_more,
            "next_before_id": next_cursor.id if next_cursor else None,
            "next_before_ts": (
                int(next_cursor.created_at.timestamp() * 1000)
                if next_cursor
                else None
            ),
        }
    )

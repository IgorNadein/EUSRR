# backend/api/v1/communications/views.py
"""API views для чатов и сообщений"""

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from communications.models import (
    Chat,
    ChatMembership,
    Message,
    MessageAttachment,
)


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

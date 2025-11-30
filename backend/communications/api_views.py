# communications/api_views.py
"""API для расширенных функций мессенджера"""

from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (
    Chat,
    ChatMembership,
    ChatUserSettings,
    ForwardedMessage,
    Message,
    MessageAttachment,
    MessageReply,
)


# ============ CHAT MANAGEMENT ============

@login_required
@require_POST
def create_chat(request):
    """
    Создание нового чата
    (group, department, channel, announcement, global)
    """
    import json

    # Читаем данные из FormData или JSON
    if request.content_type and 'multipart/form-data' in request.content_type:
        # FormData (с файлами)
        chat_type = request.POST.get('type', 'group')
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        department_id = request.POST.get('department_id')
        include_all = request.POST.get('include_all_employees') == 'true'
        is_main = request.POST.get('is_main') == 'true'
        avatar = request.FILES.get('avatar')
        participant_ids = request.POST.getlist('participant_ids')
    else:
        # JSON (без файлов - legacy)
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse(
                {'ok': False, 'error': 'Invalid JSON'}, status=400
            )

        chat_type = data.get('type', 'group')
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        department_id = data.get('department_id')
        include_all = data.get('include_all_employees', False)
        is_main = data.get('is_main', False)
        avatar = None
        participant_ids = data.get('participant_ids', [])

    # Валидация типа чата
    valid_types = ['group', 'department', 'channel', 'announcement', 'global']
    if chat_type not in valid_types:
        types_str = ", ".join(valid_types)
        return JsonResponse(
            {
                'ok': False,
                'error': f'Invalid chat type. Must be one of: {types_str}'
            },
            status=400
        )

    # Валидация названия
    if not name and chat_type != 'private':
        return JsonResponse(
            {'ok': False, 'error': 'Name is required'}, status=400
        )

    # Валидация для чата отдела
    if chat_type == 'department':
        if not department_id:
            return JsonResponse(
                {
                    'ok': False,
                    'error': 'Department is required for department chat'
                },
                status=400
            )
        try:
            from employees.models import Department
            department = Department.objects.get(id=department_id)
        except Department.DoesNotExist:
            return JsonResponse(
                {'ok': False, 'error': 'Department not found'},
                status=400
            )
    else:
        department = None

    # Валидация для основного чата
    if is_main:
        if chat_type == 'global':
            # Проверяем, нет ли уже основного глобального чата
            if Chat.objects.filter(type='global', is_main=True).exists():
                return JsonResponse(
                    {'ok': False, 'error': 'Main global chat already exists'},
                    status=400
                )
        elif chat_type == 'department' and department:
            # Проверяем, нет ли уже основного чата для этого отдела
            exists = Chat.objects.filter(
                type='department',
                department=department,
                is_main=True
            ).exists()
            if exists:
                return JsonResponse(
                    {
                        'ok': False,
                        'error': 'Main department chat already exists'
                    },
                    status=400
                )

    # Создаем чат
    chat = Chat.objects.create(
        type=chat_type,
        name=name,
        description=description,
        created_by=request.user,
        department=department,
        include_all_employees=include_all,
        is_main=is_main
    )

    # Добавляем аватар если был загружен
    if avatar:
        chat.avatar = avatar
        chat.save()

    # Создатель - владелец с полными правами
    ChatMembership.objects.create(
        chat=chat,
        user=request.user,
        role='owner',
        can_send_messages=True,
        can_add_members=True,
        can_remove_members=True,
        can_pin_messages=True
    )

    # Добавляем участников для группового чата
    if chat_type == 'group' and participant_ids:
        from employees.models import Employee
        for emp_id in participant_ids:
            try:
                employee = Employee.objects.get(id=emp_id)
                if employee != request.user:  # Создателя уже добавили
                    ChatMembership.objects.create(
                        chat=chat,
                        user=employee,
                        role='member',
                        can_send_messages=True
                    )
            except Employee.DoesNotExist:
                pass

    # Для чатов с include_all_employees - добавляем всех активных
    if include_all:
        from employees.models import Employee
        all_employees = Employee.objects.filter(is_active=True).exclude(
            id=request.user.id
        )
        for employee in all_employees:
            can_send = chat_type not in ['channel', 'announcement']
            ChatMembership.objects.get_or_create(
                chat=chat,
                user=employee,
                defaults={
                    'role': 'member',
                    'can_send_messages': can_send
                }
            )

    # Для чата отдела - добавляем всех сотрудников отдела
    if chat_type == 'department' and department:
        from employees.models import EmployeeDepartment
        dept_employees = EmployeeDepartment.objects.filter(
            department=department,
            is_active=True
        ).select_related('employee')

        for ed in dept_employees:
            if ed.employee != request.user:  # Создателя уже добавили
                ChatMembership.objects.get_or_create(
                    chat=chat,
                    user=ed.employee,
                    defaults={
                        'role': 'member',
                        'can_send_messages': True
                    }
                )

    return JsonResponse({
        'ok': True,
        'chat_id': chat.id,
        'chat_type': chat.type,
        'name': chat.name
    })


@login_required
@require_POST
def update_chat(request, chat_id):
    """Обновление названия/описания/аватара чата"""
    chat = get_object_or_404(Chat, pk=chat_id)
    
    # Проверка прав (только owner/admin)
    membership = ChatMembership.objects.filter(
        chat=chat,
        user=request.user,
        role__in=['owner', 'admin']
    ).first()
    
    if not membership:
        return JsonResponse({'ok': False, 'error': 'Forbidden'}, status=403)
    
    # Обновление полей
    if 'name' in request.POST:
        chat.name = request.POST['name'].strip()
    if 'description' in request.POST:
        chat.description = request.POST['description'].strip()
    if 'avatar' in request.FILES:
        chat.avatar = request.FILES['avatar']
    
    chat.save()
    
    return JsonResponse({'ok': True})


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
def set_chat_notifications(request, chat_id):
    """Включение/выключение уведомлений"""
    chat = get_object_or_404(Chat, pk=chat_id)
    enabled = request.POST.get('enabled', 'true').lower() == 'true'
    
    settings, created = ChatUserSettings.objects.get_or_create(
        chat=chat,
        user=request.user
    )
    settings.notifications_enabled = enabled
    settings.save()
    
    return JsonResponse({'ok': True, 'enabled': enabled})


# ============ MESSAGE ACTIONS ============

@login_required
@require_POST
def edit_message(request, message_id):
    """Редактирование сообщения"""
    message = get_object_or_404(Message, pk=message_id)
    
    if message.author != request.user:
        return JsonResponse({'ok': False, 'error': 'Forbidden'}, status=403)
    
    new_content = request.POST.get('content', '').strip()
    if not new_content:
        return JsonResponse({'ok': False, 'error': 'Empty content'}, status=400)
    
    # Сохраняем историю
    if not message.is_edited:
        message.edit_history = []
    
    message.edit_history.append({
        'timestamp': timezone.now().isoformat(),
        'old_content': message.content
    })
    
    message.content = new_content
    message.is_edited = True
    message.edited_at = timezone.now()
    message.save()
    
    return JsonResponse({'ok': True, 'edited_at': message.edited_at.isoformat()})


@login_required
@require_POST
def delete_message(request, message_id):
    """Удаление сообщения"""
    message = get_object_or_404(Message, pk=message_id)
    
    # Проверка: автор или модератор/админ чата
    can_delete = False
    if message.author == request.user:
        can_delete = True
    else:
        membership = ChatMembership.objects.filter(
            chat=message.chat,
            user=request.user,
            role__in=['owner', 'admin', 'moderator']
        ).first()
        if membership:
            can_delete = True
    
    if not can_delete:
        return JsonResponse({'ok': False, 'error': 'Forbidden'}, status=403)
    
    message.is_deleted = True
    message.deleted_at = timezone.now()
    message.deleted_by = request.user
    message.save()
    
    return JsonResponse({'ok': True})


@login_required
@require_POST
def add_reaction(request, message_id):
    """Добавление реакции на сообщение"""
    message = get_object_or_404(Message, pk=message_id)
    emoji = request.POST.get('emoji', '').strip()
    
    if not emoji:
        return JsonResponse({'ok': False, 'error': 'Emoji required'}, status=400)
    
    reactions = message.reactions or {}
    
    if emoji not in reactions:
        reactions[emoji] = []
    
    if request.user.id not in reactions[emoji]:
        reactions[emoji].append(request.user.id)
    
    message.reactions = reactions
    message.save()
    
    return JsonResponse({'ok': True, 'reactions': reactions})


@login_required
@require_POST
def remove_reaction(request, message_id):
    """Удаление реакции"""
    message = get_object_or_404(Message, pk=message_id)
    emoji = request.POST.get('emoji', '').strip()
    
    reactions = message.reactions or {}
    
    if emoji in reactions and request.user.id in reactions[emoji]:
        reactions[emoji].remove(request.user.id)
        if not reactions[emoji]:
            del reactions[emoji]
    
    message.reactions = reactions
    message.save()
    
    return JsonResponse({'ok': True, 'reactions': reactions})


@login_required
@require_POST
def pin_message(request, message_id):
    """Закрепление сообщения в чате"""
    message = get_object_or_404(Message, pk=message_id)
    
    # Проверка прав
    membership = ChatMembership.objects.filter(
        chat=message.chat,
        user=request.user,
        can_pin_messages=True
    ).first()
    
    if not membership:
        return JsonResponse({'ok': False, 'error': 'Forbidden'}, status=403)
    
    is_pinned = request.POST.get('pinned', 'true').lower() == 'true'
    
    message.is_pinned = is_pinned
    if is_pinned:
        message.pinned_by = request.user
        message.pinned_at = timezone.now()
    else:
        message.pinned_by = None
        message.pinned_at = None
    
    message.save()
    
    return JsonResponse({'ok': True, 'pinned': is_pinned})


# ============ ATTACHMENTS ============
# Примечание: endpoint для загрузки сообщений с файлами
# перенесён в api/v1/communications/views.py

@login_required
@require_POST
def upload_attachment(request):
    """Загрузка вложения к существующему сообщению"""
    if 'file' not in request.FILES:
        return JsonResponse({'ok': False, 'error': 'No file'}, status=400)
    
    message_id = request.POST.get('message_id')
    if not message_id:
        return JsonResponse(
            {'ok': False, 'error': 'message_id required'},
            status=400
        )
    
    message = get_object_or_404(Message, pk=message_id)
    
    if message.author != request.user:
        return JsonResponse({'ok': False, 'error': 'Forbidden'}, status=403)
    
    uploaded_file = request.FILES['file']
    
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
    
    message.has_attachments = True
    message.save()
    
    return JsonResponse({
        'ok': True,
        'attachment_id': attachment.id,
        'file_name': attachment.file_name,
        'file_type': attachment.file_type,
        'file_url': attachment.file.url
    })


# ============ FORWARDING ============

@login_required
@require_POST
def forward_message(request, message_id):
    """Пересылка сообщения в другой чат"""
    original = get_object_or_404(Message, pk=message_id)
    target_chat_id = request.POST.get('target_chat_id')
    
    if not target_chat_id:
        return JsonResponse({'ok': False, 'error': 'target_chat_id required'}, status=400)
    
    target_chat = get_object_or_404(Chat, pk=target_chat_id)
    
    # Проверка доступа к целевому чату
    membership = ChatMembership.objects.filter(
        chat=target_chat,
        user=request.user,
        can_send_messages=True
    ).first()
    
    if not membership:
        return JsonResponse({'ok': False, 'error': 'Cannot send to this chat'}, status=403)
    
    with transaction.atomic():
        # Создаем новое сообщение
        forwarded = Message.objects.create(
            chat=target_chat,
            author=request.user,
            content=original.content,
            is_forwarded=True
        )
        
        # Определяем оригинальное сообщение в цепочке
        if hasattr(original, 'forward_info'):
            original_message = original.forward_info.original_message
            forward_count = original.forward_info.forward_count + 1
        else:
            original_message = original
            forward_count = 1
        
        # Создаем информацию о пересылке
        ForwardedMessage.objects.create(
            message=forwarded,
            original_message=original_message,
            immediate_source=original,
            original_chat=original.chat,
            original_author=original.author,
            forwarded_by=request.user,
            forward_count=forward_count,
            preserved_content=original.content,
            preserved_author_name=original.author.get_full_name()
        )
    
    return JsonResponse({'ok': True, 'new_message_id': forwarded.id})


# ============ REPLIES ============

@login_required
@require_POST
def reply_to_message(request, message_id):
    """Ответ на сообщение"""
    replied_to = get_object_or_404(Message, pk=message_id)
    content = request.POST.get('content', '').strip()
    reply_type = request.POST.get('reply_type', 'inline')
    
    if not content:
        return JsonResponse({'ok': False, 'error': 'Content required'}, status=400)
    
    # Создаем сообщение-ответ
    reply = Message.objects.create(
        chat=replied_to.chat,
        author=request.user,
        content=content,
        reply_to=replied_to
    )
    
    # Создаем расширенную информацию об ответе
    MessageReply.objects.create(
        message=reply,
        replied_to=replied_to,
        is_cross_chat_reply=False,
        preserved_text=replied_to.content[:200],
        preserved_author_name=replied_to.author.get_full_name(),
        reply_type=reply_type
    )
    
    # Если это тред, обновляем счетчик
    if reply_type == 'thread':
        if replied_to.thread_root:
            root = replied_to.thread_root
        else:
            root = replied_to
        
        reply.thread_root = root
        reply.save()
        
        root.thread_reply_count += 1
        root.save()
    
    return JsonResponse({
        'ok': True,
        'reply_id': reply.id,
        'replied_to_id': replied_to.id
    })


# ============ CHAT MEMBERSHIP ============

@login_required
@require_POST
def add_member(request, chat_id):
    """Добавление участника в чат"""
    chat = get_object_or_404(Chat, pk=chat_id)
    user_id = request.POST.get('user_id')
    
    if not user_id:
        return JsonResponse({'ok': False, 'error': 'user_id required'}, status=400)
    
    # Проверка прав
    membership = ChatMembership.objects.filter(
        chat=chat,
        user=request.user,
        can_add_members=True
    ).first()
    
    if not membership:
        return JsonResponse({'ok': False, 'error': 'Forbidden'}, status=403)
    
    from employees.models import Employee
    new_user = get_object_or_404(Employee, pk=user_id)
    
    # Создаем или активируем участие
    new_membership, created = ChatMembership.objects.get_or_create(
        chat=chat,
        user=new_user,
        defaults={
            'role': 'member',
            'invited_by': request.user,
            'can_send_messages': True
        }
    )
    
    if not created and not new_membership.is_active:
        new_membership.is_active = True
        new_membership.left_at = None
        new_membership.save()
    
    return JsonResponse({'ok': True, 'created': created})


@login_required
@require_POST
def remove_member(request, chat_id):
    """Удаление участника из чата"""
    chat = get_object_or_404(Chat, pk=chat_id)
    user_id = request.POST.get('user_id')
    
    if not user_id:
        return JsonResponse({'ok': False, 'error': 'user_id required'}, status=400)
    
    # Проверка прав
    membership = ChatMembership.objects.filter(
        chat=chat,
        user=request.user,
        can_remove_members=True
    ).first()
    
    if not membership:
        return JsonResponse({'ok': False, 'error': 'Forbidden'}, status=403)
    
    target_membership = ChatMembership.objects.filter(
        chat=chat,
        user_id=user_id
    ).first()
    
    if target_membership:
        target_membership.is_active = False
        target_membership.left_at = timezone.now()
        target_membership.save()
    
    return JsonResponse({'ok': True})

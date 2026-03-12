"""
django-rules: декларативные правила доступа для communications (мессенджер)

Правила используются для проверки permissions на уровне объектов.
https://github.com/dfunckt/django-rules
"""

import rules
import logging

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# ПРЕДИКАТЫ (predicates)
# -----------------------------------------------------------------------------

@rules.predicate
def is_superuser(user):
    """Суперпользователь имеет все права"""
    return user.is_superuser


@rules.predicate
def is_chat_member(user, chat):
    """Пользователь является участником чата"""
    if chat is None:
        return False
    
    # Используем прямые запросы к БД в обход prefetch cache
    from .models import Chat, ChatMembership
    
    # Глобальный чат доступен всем
    if chat.type == "global":
        return True
    
    # MIGRATION: Используем только ChatMembership для всех типов чатов
    # Для любого типа чата проверяем активное membership
    return ChatMembership.objects.filter(
        chat=chat, 
        user=user, 
        is_active=True
    ).exists()


@rules.predicate
def is_chat_owner(user, chat):
    """Пользователь является владельцем/создателем чата"""
    if chat is None:
        logger.warning(f"[is_chat_owner] chat is None")
        return False
    
    if hasattr(chat, 'owner'):
        owner = chat.owner
        result = owner.id == user.id if owner else False
        logger.warning(f"[is_chat_owner] checking via owner: user={user.id}, owner={owner.id if owner else None}, result={result}")
        return result
    
    if hasattr(chat, 'created_by'):
        created_by = chat.created_by
        result = created_by.id == user.id if created_by else False
        logger.warning(f"[is_chat_owner] checking via created_by: user={user.id}, created_by={created_by.id if created_by else None}, result={result}")
        return result
    
    logger.warning(f"[is_chat_owner] no owner or created_by attribute")
    return False


@rules.predicate
def is_chat_admin(user, chat):
    """Пользователь является администратором чата"""
    if chat is None:
        return False
    
    # Проверка через admins
    if hasattr(chat, 'admins'):
        return user in chat.admins.all()
    
    # Проверка через membership с ролью admin (только активные)
    if hasattr(chat, 'memberships'):
        result = chat.memberships.filter(
            user=user,
            role__in=['admin', 'moderator'],
            is_active=True
        ).exists()
        logger.warning(
            f"[is_chat_admin] user={user.id}, chat={chat.id}, "
            f"result={result}"
        )
        return result

    logger.warning(
        f"[is_chat_admin] no memberships for chat {chat.id}"
    )
    return False


@rules.predicate
def can_add_members_flag(user, chat):
    """Пользователь имеет флаг can_add_members в ChatMembership"""
    if chat is None:
        return False

    if hasattr(chat, 'memberships'):
        result = chat.memberships.filter(
            user=user,
            can_add_members=True,
            is_active=True
        ).exists()
        logger.warning(
            f"[can_add_members_flag] user={user.id}, "
            f"chat={chat.id}, result={result}"
        )
        return result

    return False


@rules.predicate
def can_remove_members_flag(user, chat):
    """Пользователь имеет флаг can_remove_members в ChatMembership"""
    if chat is None:
        return False

    if hasattr(chat, 'memberships'):
        result = chat.memberships.filter(
            user=user,
            can_remove_members=True,
            is_active=True
        ).exists()
        logger.warning(
            f"[can_remove_members_flag] user={user.id}, "
            f"chat={chat.id}, result={result}"
        )
        return result

    return False


@rules.predicate
def can_pin_messages_flag(user, chat):
    """Пользователь имеет флаг can_pin_messages в ChatMembership"""
    if chat is None:
        return False

    if hasattr(chat, 'memberships'):
        result = chat.memberships.filter(
            user=user,
            can_pin_messages=True,
            is_active=True
        ).exists()
        logger.warning(
            f"[can_pin_messages_flag] user={user.id}, "
            f"chat={chat.id}, result={result}"
        )
        return result

    return False


@rules.predicate
def has_send_messages_permission(user, chat):
    """
    Пользователь имеет право отправлять сообщения в чат
    
    Проверяет:
    1. Если НЕТ ChatMembership - разрешено (для обратной совместимости)
    2. Если ЕСТЬ ChatMembership - проверяется флаг can_send_messages
    """
    if chat is None:
        return False
    
    # Для личных/глобальных чатов без ChatMembership - разрешено всем
    if chat.type in ['private', 'global']:
        return True
    
    # Для чатов с ChatMembership проверяем флаг can_send_messages
    if hasattr(chat, 'memberships'):
        from .models import ChatMembership
        
        # Проверяем, есть ли membership для пользователя
        try:
            membership = chat.memberships.get(
                user=user,
                is_active=True
            )
            result = membership.can_send_messages
            logger.warning(
                f"[has_send_messages_permission] user={user.id}, "
                f"chat={chat.id}, can_send={result}"
            )
            return result
        except ChatMembership.DoesNotExist:
            # MIGRATION: Убрали fallback на participants
            # После миграции все участники должны быть в ChatMembership
            logger.warning(
                f"[has_send_messages_permission] no membership found: "
                f"user={user.id}, chat={chat.id}, denying access"
            )
            return False
    
    # Если нет memberships (не должно быть после миграции) - запрещено
    return False


@rules.predicate
def is_direct_chat_participant(user, chat):
    """Пользователь участвует в личном чате"""
    if chat is None:
        return False
    
    # Проверка типа чата
    chat_type = getattr(chat, 'chat_type', None) or getattr(chat, 'type', None)
    if chat_type not in ['direct', 'private', 'personal']:
        return False
    
    return is_chat_member(user, chat)


@rules.predicate
def is_message_author(user, message):
    """Пользователь является автором сообщения"""
    if message is None:
        return False
    
    return message.author == user or message.sender == user


@rules.predicate
def can_access_message_chat(user, message):
    """Пользователь имеет доступ к чату, где находится сообщение"""
    if message is None or not hasattr(message, 'chat'):
        return False
    
    return is_chat_member(user, message.chat)


@rules.predicate
def is_public_chat(user, chat):
    """Чат является публичным (доступен всем)"""
    if chat is None:
        return False
    
    return getattr(chat, 'is_public', False)


@rules.predicate
def deprecated_is_department_chat(user, chat):
    """
    DEPRECATED: This predicate is deprecated.
    Use callback resolver pattern via get_participants() instead.
    
    For backward compatibility, always returns False.
    Configure COMMUNICATIONS_PARTICIPANT_RESOLVER in settings.py.
    """
    return False


# -----------------------------------------------------------------------------
# ПРАВИЛА (rules)
# -----------------------------------------------------------------------------

# Просмотр чата (доступ к чату)
rules.add_rule(
    'communications.view_chat',
    is_superuser | is_chat_member | is_public_chat
)

# Отправка сообщений в чат
rules.add_rule(
    'communications.send_message',
    is_superuser | (is_chat_member & has_send_messages_permission)
)

# Изменение чата (название, описание, настройки)
rules.add_rule(
    'communications.change_chat',
    is_superuser | is_chat_owner | is_chat_admin
)

# Удаление чата
rules.add_rule(
    'communications.delete_chat',
    is_superuser | is_chat_owner | is_chat_admin
)

# Просмотр сообщения
rules.add_rule(
    'communications.view_message',
    is_superuser | can_access_message_chat
)

# Изменение сообщения (редактирование)
rules.add_rule(
    'communications.change_message',
    is_superuser | is_message_author
)

# Удаление сообщения
rules.add_rule(
    'communications.delete_message',
    is_superuser | is_message_author | is_chat_admin
)

# Добавление участников в чат
rules.add_rule(
    'communications.add_members',
    is_superuser | is_chat_owner | is_chat_admin | can_add_members_flag
)

# Удаление участников из чата
rules.add_rule(
    'communications.remove_members',
    is_superuser | is_chat_owner | is_chat_admin | can_remove_members_flag
)

# Закрепление сообщений
rules.add_rule(
    'communications.pin_message',
    is_superuser | is_chat_owner | is_chat_admin | can_pin_messages_flag
)

# Изменение ролей участников
rules.add_rule(
    'communications.change_member_role',
    is_superuser | is_chat_owner
)

# Выход из чата (покинуть чат)
rules.add_rule(
    'communications.leave_chat',
    is_chat_member & ~is_chat_owner  # Все кроме владельца
)

# Просмотр истории чата
rules.add_rule(
    'communications.view_chat_history',
    is_superuser | is_chat_member
)

# Поиск по чатам/сообщениям
rules.add_rule(
    'communications.search_messages',
    rules.is_authenticated  # Все авторизованные
)


# -----------------------------------------------------------------------------
# ИСПОЛЬЗОВАНИЕ В КОДЕ
# -----------------------------------------------------------------------------

"""
# В views:
from django.core.exceptions import PermissionDenied
import rules

def chat_detail(request, pk):
    chat = get_object_or_404(Chat, pk=pk)
    
    if not rules.test_rule('communications.view_chat', request.user, chat):
        raise PermissionDenied("У вас нет доступа к этому чату")
    
    messages = chat.messages.all()
    return render(request, 'communications/chat.html', {
        'chat': chat,
        'messages': messages
    })


def send_message(request, chat_pk):
    chat = get_object_or_404(Chat, pk=chat_pk)
    
    if not rules.test_rule('communications.send_message', request.user, chat):
        return JsonResponse({'error': 'Нет прав на отправку сообщений'}, status=403)
    
    message = Message.objects.create(
        chat=chat,
        author=request.user,
        text=request.POST.get('text')
    )
    
    return JsonResponse({'message_id': message.pk})


def delete_message(request, pk):
    message = get_object_or_404(Message, pk=pk)
    
    if not rules.test_rule('communications.delete_message', request.user, message):
        return JsonResponse({'error': 'Нет прав на удаление'}, status=403)
    
    message.delete()
    return JsonResponse({'success': True})


# В templates:
{% load rules %}

{% has_rule 'communications.send_message' user chat as can_send %}
{% if can_send %}
    <form method="post" action="{% url 'communications:send' chat.pk %}" id="message-form">
        {% csrf_token %}
        <textarea name="text" class="form-control" placeholder="Введите сообщение..."></textarea>
        <button type="submit" class="btn btn-primary">Отправить</button>
    </form>
{% else %}
    <p class="text-muted">Вы не можете отправлять сообщения в этот чат</p>
{% endif %}

{% for message in messages %}
    <div class="message">
        <strong>{{ message.author }}</strong>: {{ message.text }}
        
        {% has_rule 'communications.delete_message' user message as can_delete %}
        {% if can_delete %}
            <button class="btn btn-sm btn-danger" onclick="deleteMessage({{ message.pk }})">
                Удалить
            </button>
        {% endif %}
    </div>
{% endfor %}


# В DRF permissions:
from rest_framework import permissions
import rules

class ChatPermission(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return rules.test_rule('communications.view_chat', request.user, obj)
        elif request.method in ['PUT', 'PATCH']:
            return rules.test_rule('communications.change_chat', request.user, obj)
        elif request.method == 'DELETE':
            return rules.test_rule('communications.delete_chat', request.user, obj)
        return False


class MessagePermission(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return rules.test_rule('communications.view_message', request.user, obj)
        elif request.method in ['PUT', 'PATCH']:
            return rules.test_rule('communications.change_message', request.user, obj)
        elif request.method == 'DELETE':
            return rules.test_rule('communications.delete_message', request.user, obj)
        return False


# В WebSocket consumer:
from channels.generic.websocket import AsyncJsonWebsocketConsumer
import rules

class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        chat_id = self.scope['url_route']['kwargs']['chat_id']
        chat = await database_sync_to_async(Chat.objects.get)(pk=chat_id)
        
        # Проверка доступа
        if not await database_sync_to_async(rules.test_rule)(
            'communications.view_chat', self.scope['user'], chat
        ):
            await self.close()
            return
        
        await self.accept()
        # Добавляем в группу чата
        await self.channel_layer.group_add(f'chat_{chat_id}', self.channel_name)
    
    async def receive_json(self, content):
        action = content.get('action')
        
        if action == 'send_message':
            chat = await database_sync_to_async(Chat.objects.get)(pk=self.chat_id)
            
            # Проверка прав на отправку
            if not await database_sync_to_async(rules.test_rule)(
                'communications.send_message', self.scope['user'], chat
            ):
                await self.send_json({'error': 'Permission denied'})
                return
            
            # Сохранение сообщения
            message = await database_sync_to_async(Message.objects.create)(
                chat=chat,
                author=self.scope['user'],
                text=content['text']
            )
            
            # Рассылка всем участникам
            await self.channel_layer.group_send(
                f'chat_{chat.pk}',
                {'type': 'chat.message', 'message': message.to_dict()}
            )


# Фильтрация QuerySet (только доступные чаты):
from django.db.models import Q

def get_accessible_chats(user):
    return Chat.objects.filter(
        Q(members=user) |  # Участник чата
        Q(is_public=True)  # Публичный чат
    ).distinct()
"""

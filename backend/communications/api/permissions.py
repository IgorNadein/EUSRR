"""
Permissions для communications API
"""

import rules
from rest_framework import permissions
from ..utils import user_can_access_chat


class ChatPermission(permissions.BasePermission):
    """
    Проверка прав доступа к чатам
    
    Правила:
    - GET/HEAD/OPTIONS - проверка через user_can_access_chat (учитывает participants)
    - PUT/PATCH - владелец или админ (change_chat через django-rules)
    - DELETE - только владелец (delete_chat через django-rules)
    """
    
    def has_permission(self, request, view):
        """Базовая проверка - пользователь авторизован"""
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """Проверка прав на конкретный объект (чат)"""
        # Custom actions имеют свои проверки прав внутри
        if hasattr(view, 'action') and view.action in [
            'add_member', 'remove_member', 'pin', 'notifications', 
            'change_role', 'leave', 'mark_read', 'messages', 'messages_around'
        ]:
            # Для mark_read и загрузки сообщений достаточно иметь доступ к чату
            if view.action in ['mark_read', 'messages', 'messages_around']:
                return user_can_access_chat(obj, request.user)
            return True
        
        # Безопасные методы - проверяем доступ через user_can_access_chat
        # (это обходит prefetch cache и делает прямой запрос)
        if request.method in permissions.SAFE_METHODS:
            return user_can_access_chat(obj, request.user)
        
        # Изменение чата - только владелец или админ
        if request.method in ['PUT', 'PATCH']:
            return rules.test_rule(
                'communications.change_chat', request.user, obj
            )
        
        # Удаление чата - только владелец
        if request.method == 'DELETE':
            return rules.test_rule(
                'communications.delete_chat', request.user, obj
            )
        
        return False


class MessagePermission(permissions.BasePermission):
    """
    Проверка прав доступа к сообщениям через django-rules
    
    Правила:
    - GET - доступ к чату сообщения
    - POST создание - участник чата + can_send_messages
    - POST react/unreact - участник чата (включая гостей)
    - PUT/PATCH - автор сообщения
    - DELETE - автор или админ чата
    """
    
    def has_permission(self, request, view):
        """Базовая проверка - пользователь авторизован"""
        if not (request.user and request.user.is_authenticated):
            return False
        
        # При создании сообщения проверяем права на отправку в чат
        if request.method == 'POST' and view.action in ['create', 'upload']:
            # Получаем chat_id из данных запроса
            chat_id = (
                request.data.get('chat') or
                request.data.get('chat_id')
            )

            if not chat_id:
                # Если нет chat_id, DRF вернет ошибку валидации позже
                return True

            # Проверяем права на отправку сообщений
            try:
                from ..models import Chat
                chat = Chat.objects.get(pk=chat_id)

                # Используем django-rules проверку
                return rules.test_rule(
                    'communications.send_message',
                    request.user,
                    chat
                )
            except Chat.DoesNotExist:
                # Если чат не найден, DRF вернет 404 позже
                return False

        return True
    
    def has_object_permission(self, request, view, obj):
        """Проверка прав на конкретное сообщение"""
        # Custom actions с POST (react, unreact) - доступны всем участникам
        if hasattr(view, 'action') and view.action in ['react', 'unreact']:
            # Для реакций достаточно быть участником чата
            # (даже гость может ставить реакции)
            return rules.test_rule(
                'communications.view_message',
                request.user,
                obj
            )
        
        # Просмотр - доступ к чату
        if request.method in permissions.SAFE_METHODS:
            return rules.test_rule('communications.view_message', request.user, obj)
        
        # Редактирование - автор
        if request.method in ['PUT', 'PATCH']:
            return rules.test_rule('communications.change_message', request.user, obj)
        
        # Удаление - автор или админ
        if request.method == 'DELETE':
            return rules.test_rule('communications.delete_message', request.user, obj)
        
        return False

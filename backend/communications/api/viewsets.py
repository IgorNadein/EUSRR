"""
Communications API ViewSets

DRF ViewSets для управления чатами, сообщениями и голосованиями.
Полностью заменяет устаревшие function-based views.

Endpoints:
- /api/v1/communications/chats/ - ChatViewSet
- /api/v1/communications/messages/ - MessageViewSet
- /api/v1/communications/polls/ - PollViewSet

История:
- Миграция с FBV на ViewSets завершена: 14 января 2026
- Удаление legacy кода: 15 января 2026
"""
import logging
from datetime import datetime
from datetime import timezone as dt_tz

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Prefetch, Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .permissions import ChatPermission, MessagePermission
from .serializers import (
    BulkDeleteSerializer,
    ChatDetailSerializer,
    ChatListSerializer,
    ForwardMessageSerializer,
    MessageCreateSerializer,
    MessageDetailSerializer,
    MessageEditSerializer,
    MessageListSerializer,
    PollSerializer,
    ReactionSerializer,
)
from ..models import (
    Chat,
    ChatMembership,
    ChatReadState,
    ChatUserSettings,
    Message,
    MessageAttachment,
    MessageReaction,
    Poll,
    PollVote,
)
from ..utils import _coerce_ts, user_can_access_chat
from communications.serialization import serialize_message

logger = logging.getLogger(__name__)
User = get_user_model()


def _parse_bool_query_param(value, default=True):
    if value is None:
        return default

    normalized = str(value).strip().lower()
    if normalized in {'1', 'true', 'yes', 'on'}:
        return True
    if normalized in {'0', 'false', 'no', 'off'}:
        return False
    return default


def _build_message_search_snippet(message, query, max_length=140):
    query_normalized = (query or '').strip().lower()
    content = (message.content or '').strip()

    if content:
        if not query_normalized:
            return f"{content[:max_length].rstrip()}…" if len(content) > max_length else content

        content_normalized = content.lower()
        match_index = content_normalized.find(query_normalized)

        if match_index < 0:
            return f"{content[:max_length].rstrip()}…" if len(content) > max_length else content

        context_before = max_length // 3
        context_after = max_length - context_before - len(query_normalized)
        start = max(0, match_index - context_before)
        end = min(len(content), match_index + len(query_normalized) + context_after)
        snippet = content[start:end].strip()

        if start > 0:
            snippet = f"…{snippet}"
        if end < len(content):
            snippet = f"{snippet}…"
        return snippet

    attachment_names = [a.file_name for a in getattr(message, 'attachments').all() if a.file_name]
    if attachment_names:
        joined_names = ', '.join(attachment_names)
        return f"Файлы: {joined_names}"

    return 'Сообщение без текста'


class ChatViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления чатами

    list: GET /api/v1/communications/chats/ - список чатов пользователя
    retrieve: GET /api/v1/communications/chats/{id}/ - детали чата
    create: POST /api/v1/communications/chats/ - создать чат

    Actions:
    - pin: POST /api/v1/communications/chats/{id}/pin/ - закрепить/открепить
    - notifications: POST /api/v1/communications/chats/{id}/notifications/ - вкл/выкл уведомления
    - messages: GET /api/v1/communications/chats/{id}/messages/ - список сообщений (автоотметка)
    - messages_around: GET /api/v1/communications/chats/{id}/messages_around/ - сообщения вокруг (автоотметка)
    - mark_read: POST /api/v1/communications/chats/{id}/mark_read/ - [DEPRECATED] используйте GET /messages/

    Автоматическая отметка прочитанных (Telegram-style):
    При любой загрузке сообщений (messages, messages_around) последнее загруженное
    сообщение автоматически отмечается как прочитанное через last_read_message_id.
    Ручной вызов /mark-read/ больше не требуется.
    """

    queryset = Chat.objects.none()
    permission_classes = [ChatPermission]

    def get_serializer_class(self):
        if self.action == 'list':
            return ChatListSerializer
        return ChatDetailSerializer

    def get_queryset(self):
        """
        Чаты доступные пользователю с аннотацией непрочитанных.

        ОПТИМИЗИРОВАНО: Используем денормализованное поле unread_count из ChatReadState
        вместо подзапросов COUNT(*). Это убирает N+1 проблему и ускоряет в ~100x.

        ФИЛЬТРАЦИЯ: Чаты типа 'comments' исключены из списка (list action),
        но доступны по прямой ссылке (retrieve action).
        """
        user = self.request.user

        queryset = Chat.objects.filter(
            Q(memberships__user=user, memberships__is_active=True)
            | Q(participants=user)
            | Q(include_all_users=True)
            | Q(created_by=user)  # Создатель всегда видит свои чаты
        ).select_related(
            'created_by', 'context_content_type'
        ).prefetch_related(
            # Prefetch ChatMembership с информацией о пользователе
            Prefetch(
                'memberships',
                queryset=ChatMembership.objects.select_related(
                    'user').filter(is_active=True)
            ),
            # Prefetch ChatUserSettings для текущего пользователя
            Prefetch(
                'user_settings',
                queryset=ChatUserSettings.objects.filter(user=user),
                to_attr='my_settings'
            ),
            # Prefetch ChatReadState для текущего пользователя (с unread_count!)
            Prefetch(
                'read_states',
                queryset=ChatReadState.objects.filter(user=user),
                to_attr='my_read_state'
            ),
            # Prefetch последнее сообщение чата (1 запрос вместо N)
            Prefetch(
                'messages',
                queryset=Message.objects.filter(
                    is_deleted=False,
                ).select_related('author').order_by('-created_at')[:1],
                to_attr='_prefetched_last_message'
            ),
        ).distinct()

        # Исключаем чаты-комментарии из общего списка
        # Они доступны только через прямой запрос (retrieve) или через контекст поста
        if self.action == 'list':
            queryset = queryset.exclude(type='comments')

        return queryset.order_by('-created_at')

    def create(self, request, *args, **kwargs):
        """Создание чата"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Устанавливаем создателя
        chat = serializer.save(created_by=request.user)

        if chat.type == 'global':
            chat.include_all_users = True
            chat.save()
        else:
            role = 'admin' if chat.type in [
                'group', 'channel', 'announcement'] else 'member'
            chat.participants.add(request.user)
            ChatMembership.objects.create(
                chat=chat,
                user=request.user,
                role=role,
                invited_by=request.user,
                is_active=True
            )

            # Добавляем остальных участников из запроса
            participant_ids = request.data.get('participants', [])
            if participant_ids:
                for user_id in participant_ids:
                    if user_id == request.user.id:
                        continue
                    try:
                        participant = User.objects.get(id=user_id)
                        chat.participants.add(participant)
                        ChatMembership.objects.get_or_create(
                            chat=chat,
                            user=participant,
                            defaults={
                                'role': 'member',
                                'invited_by': request.user,
                                'is_active': True
                            }
                        )
                    except User.DoesNotExist:
                        logger.warning(
                            f"User {user_id} not found when creating chat {
                                chat.id}")

        headers = self.get_success_headers(serializer.data)
        return Response(
            ChatDetailSerializer(chat, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
            headers=headers
        )

    @action(detail=True, methods=['post'])
    def pin(self, request, pk=None):
        """Закрепить/открепить чат"""
        chat = self.get_object()
        settings, created = ChatUserSettings.objects.get_or_create(
            chat=chat,
            user=request.user
        )
        settings.is_pinned = not settings.is_pinned
        settings.save()

        return Response({
            'ok': True,
            'is_pinned': settings.is_pinned
        })

    @action(detail=True, methods=['post'])
    def notifications(self, request, pk=None):
        """Включить/выключить уведомления"""
        chat = self.get_object()
        settings, created = ChatUserSettings.objects.get_or_create(
            chat=chat,
            user=request.user
        )
        settings.notifications_enabled = not settings.notifications_enabled
        settings.save()

        return Response({
            'ok': True,
            'notifications_enabled': settings.notifications_enabled
        })

    @action(detail=True, methods=['post'])
    def leave(self, request, pk=None):
        """Покинуть чат (выход пользователя из чата)"""
        import rules

        chat = self.get_object()

        # Проверка прав через django-rules
        if not rules.test_rule('communications.leave_chat', request.user, chat):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Нельзя покинуть чат, если ты его владелец
        if chat.created_by == request.user:
            return Response(
                {'error': 'Chat owner cannot leave the chat'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # MIGRATION: Убрали participants.remove, только деактивируем membership
        membership = ChatMembership.objects.filter(
            chat=chat,
            user=request.user
        ).first()

        if membership:
            membership.is_active = False
            membership.left_at = timezone.now()
            membership.save(update_fields=['is_active', 'left_at'])
            chat.participants.remove(request.user)
        else:
            return Response(
                {'error': 'You are not a member of this chat'},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response({
            'ok': True,
            'message': 'Successfully left the chat'
        })

    @action(detail=True, methods=['post'], url_path='add-member')
    def add_member(self, request, pk=None):
        """Добавить участника в чат"""
        import rules

        chat = self.get_object()
        user_id = request.data.get('user_id')

        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Проверка прав
        if not rules.test_rule('communications.add_members', request.user, chat):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            user_to_add = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # MIGRATION: Проверяем через memberships вместо participants
        if ChatMembership.objects.filter(
            chat=chat,
            user=user_to_add,
            is_active=True
        ).exists():
            return Response(
                {'error': 'User is already a member'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Создаем или восстанавливаем membership для чатов с управлением участниками
        if chat.type in ['group', 'channel', 'announcement']:
            membership, created = ChatMembership.objects.get_or_create(
                chat=chat,
                user=user_to_add,
                defaults={
                    'role': 'member',
                    'invited_by': request.user,
                    'is_active': True
                }
            )

            # Если membership уже существовал (например, пользователь раньше покинул чат),
            # восстанавливаем его активность
            if not created and not membership.is_active:
                membership.is_active = True
                membership.left_at = None
                membership.invited_by = request.user  # Обновляем кто пригласил повторно
                membership.save()
            chat.participants.add(user_to_add)

        return Response({
            'ok': True,
            'message': 'User added successfully'
        })

    @action(detail=True, methods=['post'], url_path='remove-member')
    def remove_member(self, request, pk=None):
        """Удалить участника из чата"""
        import rules

        chat = self.get_object()
        user_id = request.data.get('user_id')

        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Проверка прав
        if not rules.test_rule('communications.remove_members', request.user, chat):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            user_to_remove = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Нельзя удалить владельца
        if chat.created_by == user_to_remove:
            return Response(
                {'error': 'Cannot remove chat owner'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # MIGRATION: Убрали participants.remove, только деактивируем membership
        membership = ChatMembership.objects.filter(
            chat=chat,
            user=user_to_remove
        ).first()

        if not membership:
            return Response(
                {'error': 'User is not a member'},
                status=status.HTTP_400_BAD_REQUEST
            )

        membership.is_active = False
        membership.left_at = timezone.now()
        membership.save(update_fields=['is_active', 'left_at'])
        chat.participants.remove(user_to_remove)

        return Response({
            'ok': True,
            'message': 'User removed successfully'
        })

    @action(detail=True, methods=['post'], url_path='change-role')
    def change_role(self, request, pk=None):
        """Изменить роль участника чата"""
        import rules

        chat = self.get_object()
        user_id = request.data.get('user_id')
        new_role = request.data.get('role')

        if not user_id or not new_role:
            return Response(
                {'error': 'user_id and role are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Проверка валидности роли
        valid_roles = ['admin', 'moderator', 'member', 'guest']
        if new_role not in valid_roles:
            return Response(
                {'error': f'Invalid role. Must be one of: {", ".join(valid_roles)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Проверка прав (только владелец может менять роли)
        can_change = rules.test_rule(
            'communications.change_member_role', request.user, chat)

        # Добавляем логирование для отладки
        logger.warning(
            f"[change_role] User {
                request.user.id} trying to change role in chat {
                chat.id}. " f"chat.created_by={
                chat.created_by.id if chat.created_by else None}, " f"request.user.id={
                    request.user.id}, " f"can_change={can_change}")

        if not can_change:
            return Response(
                {'error': 'Permission denied. Only chat owner can change roles.'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            user_to_change = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Нельзя изменить роль владельца
        if chat.created_by == user_to_change:
            return Response(
                {'error': 'Cannot change role of chat owner'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Получаем или создаем membership
        membership, created = ChatMembership.objects.get_or_create(
            chat=chat,
            user=user_to_change,
            defaults={
                'role': new_role,
                'invited_by': request.user,
                'is_active': True  # Явно устанавливаем is_active при создании
            }
        )

        logger.warning(
            f"[change_role] membership found: created={created}, " f"user_id={
                user_to_change.id}, old_role={
                membership.role}, new_role={new_role}, " f"is_active={
                membership.is_active}")

        if not created:
            # Обновляем существующий membership
            old_role = membership.role
            old_is_active = membership.is_active
            membership.role = new_role
            membership.is_active = True  # Убеждаемся что is_active = True
            membership.left_at = None  # Сбрасываем left_at если был
            membership.set_permissions_for_role()
            membership.save()

            # Перезагружаем из БД чтобы убедиться что сохранилось
            membership.refresh_from_db()
            logger.warning(
                f"[change_role] after save: user_id={
                    user_to_change.id}, " f"old_role={old_role}, new_role={
                    membership.role}, " f"old_is_active={old_is_active}, new_is_active={
                    membership.is_active}, " f"saved_correctly={
                    membership.role == new_role and membership.is_active}")

        return Response({
            'ok': True,
            'message': f'User role changed to {new_role}',
            'membership': {
                'user_id': membership.user_id,
                'role': membership.role,
                'can_send_messages': membership.can_send_messages,
                'can_add_members': membership.can_add_members,
                'can_remove_members': membership.can_remove_members,
                'can_pin_messages': membership.can_pin_messages,
                'can_manage_members': membership.can_manage_members
            }
        })

    def _auto_mark_read(self, chat, user, messages):
        """
        Автоматически отмечает последнее загруженное сообщение как прочитанное.
        Pragmatic подход: "загрузил = прочитал" с ограничением количества новых сообщений.

        Защита от откатов: обновляет только если новое сообщение НОВЕЕ текущего.
        Денормализация: обнуляет unread_count при прочтении.
        """
        if not messages:
            return

        last_message = messages[-1]

        read_state, created = ChatReadState.objects.get_or_create(
            chat=chat,
            user=user,
            defaults={
                'last_read_message': last_message,
                'unread_count': 0  # Прочитали → обнуляем
            }
        )

        if created:
            logger.info(
                f"[auto_mark_read] Created: user={
                    user.id}, chat={
                    chat.id}, msg={
                    last_message.id}")
            self._send_marked_read_event(user.id, chat.id, last_message.id)
            return

        # Защита от откатов: только если НОВЕЕ
        if read_state.last_read_message_id and last_message.id <= read_state.last_read_message_id:
            logger.debug(
                f"[auto_mark_read] Skip: {
                    last_message.id} <= {
                    read_state.last_read_message_id}")
            return

        read_state.last_read_message = last_message
        read_state.unread_count = 0  # Прочитали → обнуляем
        read_state.save(
            update_fields=[
                'last_read_message',
                'unread_count',
                'updated_at'])

        logger.info(
            f"[auto_mark_read] Updated: user={
                user.id}, chat={
                chat.id}, msg={
                last_message.id}")
        self._send_marked_read_event(user.id, chat.id, last_message.id)

    def _send_marked_read_event(self, user_id, chat_id, message_id):
        """WebSocket событие для синхронизации и read receipts."""
        channel_layer = get_channel_layer()
        event_payload = {
            'chat_id': chat_id,
            'last_read_message_id': message_id,
            'reader_user_id': user_id,
        }

        async_to_sync(channel_layer.group_send)(
            f'user_{user_id}',
            {
                'type': 'chat_marked_read_sync',
                **event_payload,
            }
        )

        async_to_sync(channel_layer.group_send)(
            f'chat_{chat_id}',
            {
                'type': 'chat_marked_read',
                **event_payload,
            }
        )

    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        """Загрузка сообщений чата (пагинация по времени).

        Query params:
        - mark_read=false: не обновлять last_read_message при after_id/after_ts.
          Нужен для тихой синхронизации клиента после разрыва WebSocket.
        """
        chat = self.get_object()

        # Проверка доступа
        if not user_can_access_chat(chat, request.user):
            return Response(
                {'error': 'Access denied'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Параметры пагинации
        before_ts = request.query_params.get('before')
        before_id = request.query_params.get('before_id')
        after_ts = request.query_params.get('after')
        after_id = request.query_params.get('after_id')
        try:
            limit = min(int(request.query_params.get('limit', 50)), 100)
        except (ValueError, TypeError):
            limit = 50
        mark_read = _parse_bool_query_param(
            request.query_params.get('mark_read'),
            default=True,
        )

        queryset = chat.messages.filter(is_deleted=False).select_related(
            'author', 'reply_to', 'reply_to__author', 'poll'
        ).prefetch_related(
            'attachments',
            'reactions',
            'reactions__user',
            'poll__options',
            Prefetch(
                'chat__read_states',
                queryset=ChatReadState.objects.select_related('user'),
            ),
        )

        # Определяем порядок сортировки в зависимости от типа запроса
        if after_id or after_ts:
            # Для загрузки новых сообщений - сортируем по возрастанию (от старых к
            # новым)
            queryset = queryset.order_by('created_at')
        else:
            # Для загрузки старых или начальной загрузки - по убыванию (от новых к
            # старым)
            queryset = queryset.order_by('-created_at')

        # Фильтрация по ID (приоритет) или timestamp
        if before_id:
            try:
                queryset = queryset.filter(id__lt=int(before_id))
            except ValueError:
                pass
        elif before_ts:
            before_dt = _coerce_ts(before_ts)
            if before_dt:
                queryset = queryset.filter(created_at__lt=before_dt)

        if after_id:
            try:
                queryset = queryset.filter(id__gt=int(after_id))
            except ValueError:
                pass
        elif after_ts:
            after_dt = _coerce_ts(after_ts)
            if after_dt:
                queryset = queryset.filter(created_at__gt=after_dt)

        # Берем limit+1 чтобы определить has_more
        messages = list(queryset[:limit + 1])
        has_more = len(messages) > limit

        if has_more:
            messages = messages[:limit]  # Убираем лишнее

        # Если загружали с after - уже в прямом порядке, иначе переворачиваем
        if not (after_id or after_ts):
            messages.reverse()

        # Автоотметка при загрузке НОВЫХ сообщений (after_id/after_ts)
        # При scroll вверх (before_id) - не отмечаем
        if mark_read and (after_id or after_ts) and messages:
            self._auto_mark_read(chat, request.user, messages)

        return Response({
            'messages': [serialize_message(m) for m in messages],
            'has_more': has_more
        })

    @action(detail=True, methods=['get'], url_path='messages-around')
    def messages_around(self, request, pk=None):
        """
        Загрузка сообщений вокруг указанного (last_read_message_id).

        Асимметричная загрузка для браузерных приложений:
        - 24 сообщения ДО (контекст прочитанных)
        - 10 сообщений ПОСЛЕ (новые непрочитанные)

        Автоматическая отметка последнего загруженного как прочитанного.
        Погрешность: макс 1-2 невидимых сообщения (приемлемо для веб).
        """
        chat = self.get_object()

        if not user_can_access_chat(chat, request.user):
            return Response(
                {'error': 'Access denied'},
                status=status.HTTP_403_FORBIDDEN
            )

        around_id = request.query_params.get('around_id')

        # Асимметричные лимиты (24 + 10 = 34 сообщения )
        try:
            before_limit = int(request.query_params.get('before_limit', 24))
        except (ValueError, TypeError):
            before_limit = 24
        try:
            after_limit = int(request.query_params.get('after_limit', 10))
        except (ValueError, TypeError):
            after_limit = 10

        # Для обратной совместимости с limit параметром
        if 'limit' in request.query_params and 'before_limit' not in request.query_params:
            try:
                total_limit = min(int(request.query_params.get('limit', 30)), 100)
            except (ValueError, TypeError):
                total_limit = 30
            before_limit = int(total_limit * 0.8)  # 80% на контекст
            after_limit = total_limit - before_limit  # 20% на новые

        queryset = chat.messages.filter(is_deleted=False).select_related(
            'author', 'reply_to', 'reply_to__author', 'poll'
        ).prefetch_related(
            'attachments',
            'reactions',
            'reactions__user',
            'poll__options',
            Prefetch(
                'chat__read_states',
                queryset=ChatReadState.objects.select_related('user'),
            ),
        )

        # Если нет around_id, пытаемся получить last_read_message_id
        if not around_id:
            read_state = ChatReadState.objects.filter(
                chat=chat, user=request.user
            ).first()

            if read_state and read_state.last_read_message_id:
                around_id = read_state.last_read_message_id

        # Если все еще нет around_id - возвращаем последние сообщения
        if not around_id:
            fallback_limit = before_limit + after_limit
            messages = list(queryset.order_by('-created_at')[:fallback_limit])
            messages.reverse()

            # Автоотметка: последнее ЗАГРУЖЕННОЕ становится last_read
            # Frontend при следующей загрузке запросит вокруг ЭТОГО сообщения
            if messages:
                self._auto_mark_read(chat, request.user, messages)

            return Response({
                'messages': [serialize_message(m) for m in messages],
                'messages_count': len(messages),
                'anchor_id': None,
                'anchor_index': 0
            })

        # Определяем, это ID сообщения или timestamp
        anchor_msg = None

        try:
            around_value = int(around_id)

            # Если это большое число (> 1 миллиард) - вероятно timestamp в миллисекундах
            if around_value > 1_000_000_000:
                # Конвертируем timestamp из миллисекунд в seconds
                timestamp_seconds = around_value / 1000
                anchor_dt = datetime.fromtimestamp(
                    timestamp_seconds, tz=dt_tz.utc)

                # Ищем ближайшее сообщение к этому timestamp (ДО или на момент)
                anchor_msg = queryset.filter(
                    created_at__lte=anchor_dt
                ).order_by('-created_at').first()

                # Если не нашли до этого времени, берем первое после
                if not anchor_msg:
                    anchor_msg = queryset.filter(
                        created_at__gte=anchor_dt
                    ).order_by('created_at').first()

                logger.info(
                    f"[messages_around] Searching by timestamp: {anchor_dt}, found: {anchor_msg}")
            else:
                # Это обычный message_id
                try:
                    anchor_msg = queryset.get(pk=around_value)
                    logger.info(
                        f"[messages_around] Found message by ID: {around_value}")
                except Message.DoesNotExist:
                    logger.warning(
                        f"[messages_around] Message with ID {around_value} not found")
        except (ValueError, TypeError):
            logger.warning(
                f"[messages_around] Invalid around_id format: {around_id}")

        if not anchor_msg:
            # Если не найдено - возвращаем последние сообщения
            fallback_limit = before_limit + after_limit
            messages = list(queryset.order_by('-created_at')[:fallback_limit])
            messages.reverse()

            # Автоотметка: последнее ЗАГРУЖЕННОЕ становится last_read
            # Frontend при следующей загрузке запросит вокруг ЭТОГО сообщения
            if messages:
                self._auto_mark_read(chat, request.user, messages)

            return Response({
                'messages': [serialize_message(m) for m in messages],
                'messages_count': len(messages),
                'anchor_id': None,
                'anchor_index': 0
            })

        # Асимметричная загрузка: больше контекста, меньше новых
        before = list(queryset.filter(
            created_at__lt=anchor_msg.created_at
        ).order_by('-created_at')[:before_limit])
        before.reverse()

        after = list(queryset.filter(
            created_at__gte=anchor_msg.created_at
        ).order_by('created_at')[:after_limit + 1])  # +1 для включения anchor

        messages = before + after
        anchor_index = len(before)

        # Автоотметка: последнее ЗАГРУЖЕННОЕ становится last_read (24 контекста + 6 новых)
        # Frontend при следующей загрузке запросит вокруг последнего из ЭТИХ сообщений
        # НЕ отмечается последнее в чате, а последнее из того что мы загрузили!
        if messages:
            self._auto_mark_read(chat, request.user, messages)

        return Response({
            'messages': [serialize_message(m) for m in messages],
            'messages_count': len(messages),
            'anchor_id': anchor_msg.id,
            'anchor_index': anchor_index,
            'has_more_before': len(before) >= before_limit,
            'has_more_after': len(after) > after_limit
        })

    @action(detail=True, methods=['get'], url_path='search-messages')
    def search_messages(self, request, pk=None):
        """Поиск сообщений внутри одного чата с пагинацией и сниппетами."""
        chat = self.get_object()

        if not user_can_access_chat(chat, request.user):
            return Response(
                {'error': 'Access denied'},
                status=status.HTTP_403_FORBIDDEN
            )

        query = (request.query_params.get('q') or '').strip()

        try:
            limit = min(max(int(request.query_params.get('limit', 20)), 1), 100)
        except (ValueError, TypeError):
            limit = 20

        try:
            offset = max(int(request.query_params.get('offset', 0)), 0)
        except (ValueError, TypeError):
            offset = 0

        if len(query) < 2:
            return Response({
                'query': query,
                'count': 0,
                'offset': offset,
                'next_offset': None,
                'results': [],
            })

        queryset = chat.messages.filter(
            is_deleted=False,
        ).select_related(
            'author'
        ).prefetch_related(
            'attachments'
        ).filter(
            Q(content__icontains=query) | Q(attachments__file_name__icontains=query)
        ).distinct().order_by('-created_at', '-id')

        total_count = queryset.count()
        matches = list(queryset[offset:offset + limit])
        next_offset = offset + limit if (offset + limit) < total_count else None

        results = []
        for message in matches:
            author = message.author
            author_name = (
                f"{getattr(author, 'last_name', '')} {getattr(author, 'first_name', '')}".strip()
                or getattr(author, 'username', '')
                or 'Сотрудник'
            )
            attachments = list(message.attachments.all())
            results.append({
                'message_id': message.id,
                'content': message.content or '',
                'snippet': _build_message_search_snippet(message, query),
                'author_name': author_name,
                'created_at': message.created_at,
                'attachments_count': len(attachments),
                'has_attachments': bool(attachments),
            })

        return Response({
            'query': query,
            'count': total_count,
            'offset': offset,
            'next_offset': next_offset,
            'results': results,
        })

    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        """
        Ручная отметка прочитанных сообщений (опционально).

        Обычно используется автоматическая отметка при GET /messages-around/.
        Этот endpoint полезен для точной отметки через IntersectionObserver.

        Параметры:
        - message_id: ID последнего прочитанного сообщения (рекомендуется)
        - upto_ts: timestamp (legacy, используйте message_id)
        """
        chat = self.get_object()

        logger.info(
            f"[mark_read] Manual mark by user {request.user.id} for chat {chat.id}")

        # Основная логика: поддерживаем message_id
        message_id = request.data.get('message_id')
        upto_ts = request.data.get('upto_ts')

        if not message_id and not upto_ts:
            last_msg = chat.messages.filter(
                is_deleted=False).order_by('-created_at').first()
            if not last_msg:
                return Response({'ok': True, 'last_read_message_id': None})

            self._auto_mark_read(chat, request.user, [last_msg])
            return Response({
                'ok': True,
                'last_read_message_id': last_msg.id,
                'deprecated': True,
                'message': 'message_id was not provided, latest message was marked as read.'
            })

        if message_id:
            try:
                message = chat.messages.get(
                    pk=int(message_id), is_deleted=False)

                # Используем новую логику через _auto_mark_read
                self._auto_mark_read(chat, request.user, [message])

                return Response({
                    'ok': True,
                    'last_read_message_id': message.id
                })
            except (Message.DoesNotExist, ValueError) as e:
                logger.error(
                    f"[mark_read] Invalid message_id {message_id}: {e}")
                return Response(
                    {'error': f'Message {message_id} not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

        # Fallback: если передан upto_ts (старая логика)
        if upto_ts:
            try:
                ts_value = float(upto_ts)
                if ts_value > 10000000000:
                    ts_value = ts_value / 1000
                timestamp = datetime.fromtimestamp(ts_value, tz=dt_tz.utc)

                # Находим последнее сообщение до этого времени
                last_msg = chat.messages.filter(
                    created_at__lte=timestamp,
                    is_deleted=False
                ).order_by('-created_at').first()

                if last_msg:
                    self._auto_mark_read(chat, request.user, [last_msg])
                    return Response({
                        'ok': True,
                        'last_read_message_id': last_msg.id,
                        'deprecated': True,
                        'message': 'Using upto_ts is deprecated. Use message_id instead.'
                    })
                else:
                    return Response(
                        {'error': 'No messages found before specified timestamp'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            except (ValueError, OSError) as e:
                logger.error(f"[mark_read] Invalid timestamp: {e}")
                return Response(
                    {'error': 'Invalid timestamp format'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Ни message_id ни upto_ts не переданы
        return Response(
            {'error': 'Either message_id or upto_ts required'},
            status=status.HTTP_400_BAD_REQUEST
        )


class MessageViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления сообщениями

    create: POST /api/v1/communications/messages/ - создать сообщение (с файлами)
    update: PUT/PATCH /api/v1/communications/messages/{id}/ - редактировать
    destroy: DELETE /api/v1/communications/messages/{id}/ - удалить

    Actions:
    - react: POST /api/v1/communications/messages/{id}/react/ - добавить реакцию
    - unreact: POST /api/v1/communications/messages/{id}/unreact/ - убрать реакцию
    - forward: POST /api/v1/communications/messages/forward/ - переслать сообщения
    - bulk_delete: POST /api/v1/communications/messages/bulk_delete/ - массовое удаление
    - upload: POST /api/v1/communications/messages/upload/ - загрузить с вложениями
    """

    queryset = Message.objects.none()
    permission_classes = [MessagePermission]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_serializer_class(self):
        if self.action in ['create', 'upload']:
            return MessageCreateSerializer
        elif self.action == 'update' or self.action == 'partial_update':
            return MessageEditSerializer
        elif self.action == 'list':
            return MessageListSerializer
        return MessageDetailSerializer

    def get_queryset(self):
        """
        Сообщения доступные пользователю

        Включает сообщения из чатов:
        - где user в participants (прямое участие)
        - где user в ChatMembership (роли)
        - где include_all_users=True (открытые чаты)
        - context-based чаты (type=comments с context_object)

        Детальная проверка доступа выполняется через MessagePermission
        """
        user = self.request.user

        # MIGRATION: Чаты где пользователь состоит через memberships (убрали
        # participants)
        accessible_chats = Chat.objects.filter(
            Q(memberships__user=user, memberships__is_active=True)
            | Q(participants=user)
            | Q(include_all_users=True)
        ).distinct()

        # Context-based чаты (комментарии к постам и т.д.)
        # Проверка доступа к context_object будет в permissions
        context_based_chats = Chat.objects.filter(
            Q(type='comments') & ~Q(context_object_id=None)
        ).distinct()

        # Объединяем оба набора
        all_chats = accessible_chats | context_based_chats

        return Message.objects.filter(
            chat__in=all_chats
        ).select_related(
            'author', 'chat', 'reply_to', 'reply_to__author', 'poll'
        ).prefetch_related(
            'attachments', 'reactions', 'reactions__user', 'poll__options'
        ).order_by('-created_at')

    @action(detail=False, methods=['post'])
    def upload(self, request):
        """
        Загрузка сообщения с вложениями
        POST /api/v1/communications/messages/upload/
        """
        chat_id = request.data.get('chat_id')
        content = request.data.get('content', '').strip()
        reply_to_id = request.data.get(
            'reply_to') or request.data.get('reply_to_id')

        # Валидация чата
        try:
            chat = Chat.objects.get(pk=chat_id)
        except Chat.DoesNotExist:
            return Response(
                {'error': 'Chat not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        if not user_can_access_chat(chat, request.user):
            return Response(
                {'error': 'Access denied'},
                status=status.HTTP_403_FORBIDDEN
            )

        reply_to_message = None
        if reply_to_id:
            try:
                reply_to_message = chat.messages.get(
                    pk=int(reply_to_id), is_deleted=False)
            except (Message.DoesNotExist, ValueError):
                return Response(
                    {'error': 'Reply target not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

        # Получаем файлы
        files = []
        for key in request.FILES:
            if key.startswith('file_'):
                files.append(request.FILES[key])

        # Валидация: либо текст, либо файлы
        if not content and not files:
            return Response(
                {'error': 'Message must have either content or attachments'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Создаем сообщение
        with transaction.atomic():
            message = Message.objects.create(
                chat=chat,
                author=request.user,
                content=content,
                reply_to=reply_to_message,
                has_attachments=len(files) > 0
            )

            # Сохраняем файлы
            for file in files:
                MessageAttachment.objects.create(
                    message=message,
                    file=file,
                    file_name=file.name,
                    file_size=file.size,
                    mime_type=file.content_type or 'application/octet-stream',
                    file_type=self._detect_file_type(file.content_type)
                )

        # Перезагружаем с prefetch
        message = Message.objects.select_related(
            'author', 'reply_to', 'reply_to__author', 'poll', 'chat'
        ).prefetch_related(
            'attachments',
            'reactions',
            'reactions__user',
            Prefetch(
                'chat__read_states',
                queryset=ChatReadState.objects.select_related('user'),
            ),
        ).get(pk=message.id)

        # Отправляем через WebSocket
        channel_layer = get_channel_layer()
        payload = serialize_message(message)

        async_to_sync(channel_layer.group_send)(
            f'chat_{chat.id}',
            {
                'type': 'chat.message',
                'chat_id': chat.id,
                'payload': payload
            }
        )

        return Response({
            'ok': True,
            'message': payload
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='upload-temp')
    def upload_temp(self, request):
        """
        Временная загрузка файлов для редактирования сообщения
        POST /api/v1/communications/messages/upload-temp/
        Создает MessageAttachment без привязки к сообщению (message=null)
        """
        # Получаем файлы
        files = []
        for key in request.FILES:
            if key.startswith('file_'):
                files.append(request.FILES[key])

        if not files:
            return Response(
                {'error': 'No files provided'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Создаем attachments БЕЗ привязки к сообщению
        attachment_ids = []
        with transaction.atomic():
            for file in files:
                attachment = MessageAttachment.objects.create(
                    message=None,  # Без сообщения!
                    file=file,
                    file_name=file.name,
                    file_size=file.size,
                    mime_type=file.content_type or 'application/octet-stream',
                    file_type=self._detect_file_type(file.content_type)
                )
                attachment_ids.append(attachment.id)

        return Response({
            'ok': True,
            'attachment_ids': attachment_ids
        }, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        """Редактирование сообщения"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()

        # Проверка прав
        if instance.author != request.user:
            return Response(
                {'error': 'You can only edit your own messages'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Проверка типа чата
        if instance.chat.type == 'announcement':
            return Response(
                {'error': 'Editing is not allowed in announcements'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = self.get_serializer(
            instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        new_content = serializer.validated_data.get('content', '').strip()
        existing_attachment_ids = serializer.validated_data.get(
            'existing_attachment_ids')

        # Валидация вложений
        current_attachments_count = instance.attachments.count()
        will_have_attachments = (
            (existing_attachment_ids is not None and len(existing_attachment_ids) > 0) or (
                existing_attachment_ids is None and current_attachments_count > 0))

        if not new_content and not will_have_attachments:
            return Response(
                {'error': 'Message must have either content or attachments'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Сохраняем историю редактирования в отдельную таблицу
        from communications.models import MessageEditHistory

        MessageEditHistory.objects.create(
            message=instance,
            previous_content=instance.content,
            edited_by=request.user
        )

        instance.content = new_content
        instance.is_edited = True
        instance.edited_at = timezone.now()

        # Управление вложениями
        if existing_attachment_ids is not None:
            from communications.models import MessageAttachment

            current_ids = set(str(att.id)
                              for att in instance.attachments.all())
            keep_ids = set(str(id) for id in existing_attachment_ids)
            ids_to_remove = current_ids - keep_ids
            ids_to_add = keep_ids - current_ids

            # Удаляем attachments которых нет в списке
            if ids_to_remove:
                attachments_to_delete = instance.attachments.filter(
                    id__in=ids_to_remove)
                for att in attachments_to_delete:
                    if att.file and att.file.storage.exists(att.file.name):
                        att.file.delete(save=False)
                attachments_to_delete.delete()
                logger.info(f"[update] Removed attachments: {ids_to_remove}")

            # Переносим новые attachments из других сообщений к этому
            if ids_to_add:
                attachments_to_move = MessageAttachment.objects.filter(
                    id__in=ids_to_add)
                updated_count = attachments_to_move.update(message=instance)
                logger.info(
                    f"[update] Moved {updated_count} attachments to message {
                        instance.id}: {
                        list(ids_to_add)}")

        instance.save()

        # ВАЖНО: Очищаем кэш attachments перед подсчетом
        instance.refresh_from_db()

        # Обновляем has_attachments (заново считаем из БД)
        from communications.models import MessageAttachment
        instance.has_attachments = MessageAttachment.objects.filter(
            message=instance).count() > 0
        instance.save(update_fields=['has_attachments'])

        # Перезагружаем с нуля чтобы получить обновленные attachments
        # Используем новый запрос, чтобы избежать кэширования
        instance = Message.objects.select_related(
            'author', 'reply_to', 'reply_to__author', 'poll', 'chat'
        ).prefetch_related(
            'attachments',
            'reactions',
            'reactions__user',
            'poll__options',
            Prefetch(
                'chat__read_states',
                queryset=ChatReadState.objects.select_related('user'),
            ),
        ).get(pk=instance.id)

        # WebSocket уведомление
        channel_layer = get_channel_layer()
        payload = serialize_message(instance)

        group_name = f'chat_{instance.chat_id}'

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'chat.message_edited',
                'chat_id': instance.chat_id,
                'payload': payload
            }
        )

        return Response(payload)

    def destroy(self, request, *args, **kwargs):
        """Мягкое удаление сообщения"""
        instance = self.get_object()

        if instance.author != request.user:
            return Response(
                {'error': 'You can only delete your own messages'},
                status=status.HTTP_403_FORBIDDEN
            )

        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.deleted_by = request.user
        instance.save()

        # WebSocket уведомление
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'chat_{instance.chat_id}',
            {
                'type': 'chat.message_deleted',
                'chat_id': instance.chat_id,
                'message_id': instance.id
            }
        )

        return Response({'ok': True}, status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def react(self, request, pk=None):
        """Добавить реакцию"""
        message = self.get_object()
        logger.info(
            f"[react] User {request.user.id} adding reaction to message {message.id}")

        serializer = ReactionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        emoji = serializer.validated_data['emoji']
        logger.info(f"[react] Emoji: {emoji}")

        # Создаем или получаем реакцию (по message + user, т.к. unique_together)
        reaction, created = MessageReaction.objects.get_or_create(
            message=message,
            user=request.user,
            defaults={'emoji': emoji}
        )

        # Если реакция уже существует, обновляем emoji
        if not created:
            old_emoji = reaction.emoji
            if old_emoji == emoji:
                return Response(
                    {'error': 'Reaction already exists'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            reaction.emoji = emoji
            reaction.save(update_fields=['emoji'])
            logger.info(f"[react] Updated emoji from {old_emoji} to {emoji}")
        else:
            logger.info(f"[react] Created new reaction, id={reaction.id}")

        # Пересчитываем reactions_summary
        reactions_summary = {}
        for r in message.reactions.select_related('user'):
            if r.emoji not in reactions_summary:
                reactions_summary[r.emoji] = {
                    'count': 0,
                    'users': [],
                    'user_names': []
                }
            reactions_summary[r.emoji]['count'] += 1
            reactions_summary[r.emoji]['users'].append(r.user_id)
            reactions_summary[r.emoji]['user_names'].append(
                r.user.get_full_name())

        logger.info(f"[react] reactions_summary: {reactions_summary}")

        # WebSocket уведомление
        channel_layer = get_channel_layer()
        logger.info(f"[react] Sending to chat_{message.chat_id} group")

        async_to_sync(channel_layer.group_send)(
            f'chat_{message.chat_id}',
            {
                'type': 'chat.reaction_added',
                'chat_id': message.chat_id,
                'message_id': message.id,
                'user_id': request.user.id,
                'emoji': emoji,
                'reactions_summary': reactions_summary
            }
        )

        logger.info("[react] WebSocket message sent successfully")

        return Response({'ok': True, 'reactions_summary': reactions_summary})

    @action(detail=True, methods=['post'])
    def unreact(self, request, pk=None):
        """Убрать реакцию"""
        message = self.get_object()
        logger.info(
            f"[unreact] User {
                request.user.id} removing reaction from message {
                message.id}")

        serializer = ReactionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        emoji = serializer.validated_data['emoji']
        logger.info(f"[unreact] Emoji: {emoji}")

        deleted_count = MessageReaction.objects.filter(
            message=message,
            user=request.user,
            emoji=emoji
        ).delete()[0]

        logger.info(f"[unreact] Deleted count: {deleted_count}")

        if deleted_count == 0:
            return Response(
                {'error': 'Reaction not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Пересчитываем reactions_summary
        reactions_summary = {}
        for r in message.reactions.select_related('user'):
            if r.emoji not in reactions_summary:
                reactions_summary[r.emoji] = {
                    'count': 0,
                    'users': [],
                    'user_names': []
                }
            reactions_summary[r.emoji]['count'] += 1
            reactions_summary[r.emoji]['users'].append(r.user_id)
            reactions_summary[r.emoji]['user_names'].append(
                r.user.get_full_name())

        logger.info(f"[unreact] reactions_summary: {reactions_summary}")

        # WebSocket уведомление
        channel_layer = get_channel_layer()
        logger.info(f"[unreact] Sending to chat_{message.chat_id} group")

        async_to_sync(channel_layer.group_send)(
            f'chat_{message.chat_id}',
            {
                'type': 'chat.reaction_removed',
                'chat_id': message.chat_id,
                'message_id': message.id,
                'user_id': request.user.id,
                'emoji': emoji,
                'reactions_summary': reactions_summary
            }
        )

        logger.info("[unreact] WebSocket message sent successfully")

        return Response({'ok': True, 'reactions_summary': reactions_summary})

    @action(detail=False, methods=['post'])
    def forward(self, request):
        """Переслать сообщения в другой чат"""
        serializer = ForwardMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message_ids = serializer.validated_data['message_ids']
        target_chat_id = serializer.validated_data['target_chat_id']

        # Получаем целевой чат
        try:
            target_chat = Chat.objects.get(pk=target_chat_id)
        except Chat.DoesNotExist:
            return Response(
                {'error': 'Target chat not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        if not user_can_access_chat(target_chat, request.user):
            return Response(
                {'error': 'Access denied to target chat'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Пересылаем сообщения
        forwarded_ids = []
        with transaction.atomic():
            messages = Message.objects.filter(
                id__in=message_ids
            ).select_related('author')

            for original_msg in messages:
                # Создаём пересланное сообщение
                forwarded = Message.objects.create(
                    chat=target_chat,
                    author=request.user,
                    content=original_msg.content,
                    is_forwarded=True
                )

                # Создаём метаданные пересылки
                from communications.models import MessageForwardMetadata
                MessageForwardMetadata.objects.create(
                    message=forwarded,
                    original_message=original_msg,
                    original_author=original_msg.author,
                    original_chat=original_msg.chat,
                    original_chat_name=original_msg.chat.name or 'Unknown',
                    original_created_at=original_msg.created_at,
                    forwarded_by=request.user,
                    forward_count=1
                )

                forwarded_ids.append(forwarded.id)

        return Response({
            'ok': True,
            'forwarded_count': len(forwarded_ids),
            'forwarded_ids': forwarded_ids
        })

    @action(detail=False, methods=['post'], url_path='bulk-delete')
    def bulk_delete(self, request):
        """Массовое удаление сообщений"""
        serializer = BulkDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message_ids = serializer.validated_data['message_ids']

        # Удаляем только свои сообщения
        deleted_count = Message.objects.filter(
            id__in=message_ids,
            author=request.user
        ).update(
            is_deleted=True,
            deleted_at=timezone.now(),
            deleted_by=request.user
        )

        return Response({
            'ok': True,
            'deleted_count': deleted_count
        })

    def _detect_file_type(self, mime_type):
        """Определение типа файла по MIME"""
        if not mime_type:
            return 'file'

        if mime_type.startswith('image/'):
            return 'image'
        elif mime_type.startswith('video/'):
            return 'video'
        elif mime_type.startswith('audio/'):
            return 'audio'
        elif 'pdf' in mime_type:
            return 'pdf'
        elif any(x in mime_type for x in ['document', 'word', 'text', 'sheet', 'excel']):
            return 'document'
        else:
            return 'file'


class PollViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления голосованиями

    create: POST /api/v1/communications/polls/ - создать голосование
    retrieve: GET /api/v1/communications/polls/{id}/ - детали голосования

    Actions:
    - vote: POST /api/v1/communications/polls/{id}/vote/ - проголосовать
    - close: POST /api/v1/communications/polls/{id}/close/ - закрыть голосование
    - results: GET /api/v1/communications/polls/{id}/results/ - результаты
    """

    queryset = Poll.objects.all()
    serializer_class = PollSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        """Автоматически устанавливаем автора голосования"""
        serializer.save(author=self.request.user)

    @action(detail=True, methods=['post'])
    def vote(self, request, pk=None):
        """Проголосовать"""
        poll = self.get_object()

        if poll.is_closed:
            return Response(
                {'error': 'Poll is closed'},
                status=status.HTTP_400_BAD_REQUEST
            )

        option_ids = request.data.get('option_ids', [])
        if not option_ids:
            return Response(
                {'error': 'No options selected'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Проверка что опции существуют и принадлежат этому poll
        try:
            options = poll.options.filter(pk__in=option_ids)
            if options.count() != len(option_ids):
                return Response(
                    {'error': 'Invalid option IDs'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid option IDs format'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Проверка множественного выбора
        if not poll.is_multiple_choice and len(option_ids) > 1:
            return Response(
                {'error': 'Only one option allowed'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            # Удаляем ВСЕ старые голоса пользователя (и для single и для multiple
            # choice)
            PollVote.objects.filter(
                poll=poll,
                voter=request.user
            ).delete()

            # Добавляем новые голоса
            for option in options:
                PollVote.objects.create(
                    poll=poll,
                    option=option,
                    voter=request.user
                )

            # Пересчитываем голоса
            for option in poll.options.all():
                option.vote_count = option.votes.count()
                option.save()

            poll.total_voters = PollVote.objects.filter(
                poll=poll).values('voter').distinct().count()
            poll.save()

        # WebSocket уведомление
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'chat_{poll.message.chat_id}',
            {
                'type': 'poll.update',
                'chat_id': poll.message.chat_id,
                'payload': {
                    'poll_id': poll.id,
                    'message_id': poll.message_id,
                    'total_voters': poll.total_voters
                }
            }
        )

        # Возвращаем полные результаты
        results_serializer = PollSerializer(poll, context={'request': request})
        return Response({'ok': True, 'results': results_serializer.data})

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """Закрыть голосование"""
        poll = self.get_object()

        # Проверка прав (только автор сообщения)
        if poll.message.author != request.user:
            return Response(
                {'error': 'Only poll author can close it'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Используем метод модели для установки is_closed и closed_at
        poll.close()

        return Response(PollSerializer(poll, context={'request': request}).data)

    @action(detail=True, methods=['get', 'post'])
    def results(self, request, pk=None):
        """Получить результаты голосования"""
        poll = self.get_object()
        serializer = PollSerializer(poll, context={'request': request})
        return Response(serializer.data)

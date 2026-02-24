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
# pyright: reportAttributeAccessIssue=false, reportCallIssue=false, reportOptionalMemberAccess=false, reportOptionalSubscript=false

import logging
from typing import Any, cast
from datetime import datetime, timezone as dt_tz
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q, Count, Prefetch, Exists, OuterRef
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from communications.models import (
    Chat, Message, MessageAttachment, MessageReaction,
    Poll, PollOption, PollVote, ChatMembership, ChatUserSettings,
    ChatReadState
)
from communications.serialization import serialize_message
from communications.views import user_can_access_chat, _coerce_ts
from .serializers import (
    ChatListSerializer, ChatDetailSerializer,
    MessageListSerializer, MessageDetailSerializer,
    MessageCreateSerializer, MessageEditSerializer,
    PollSerializer, ReactionSerializer,
    ForwardMessageSerializer, BulkDeleteSerializer,
    MessageAttachmentSerializer
)

logger = logging.getLogger(__name__)
Employee = get_user_model()


class ChatViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления чатами
    
    list: GET /api/v1/communications/chats/ - список чатов пользователя
    retrieve: GET /api/v1/communications/chats/{id}/ - детали чата
    create: POST /api/v1/communications/chats/ - создать чат
    
    Actions:
    - pin: POST /api/v1/communications/chats/{id}/pin/ - закрепить/открепить
    - notifications: POST /api/v1/communications/chats/{id}/notifications/ - вкл/выкл уведомления
    - messages: GET /api/v1/communications/chats/{id}/messages/ - список сообщений
    - messages_around: GET /api/v1/communications/chats/{id}/messages_around/ - сообщения вокруг
    - mark_read: POST /api/v1/communications/chats/{id}/mark_read/ - пометить как прочитанное
    """
    
    permission_classes = [IsAuthenticated]
    # Явно задаем базовые атрибуты для корректной типизации DRF/Pylance
    queryset = Chat.objects.none()
    serializer_class = ChatDetailSerializer
    
    def get_serializer_class(self):  # pyright: ignore[reportIncompatibleMethodOverride]
        if self.action == 'list':
            return ChatListSerializer
        return ChatDetailSerializer
    
    def get_queryset(self):  # pyright: ignore[reportIncompatibleMethodOverride]
        """Чаты доступные пользователю с аннотацией непрочитанных"""
        user = self.request.user
        
        # Подзапрос для последнего прочитанного времени
        read_state_subq = ChatReadState.objects.filter(
            chat=OuterRef('pk'),
            user=user
        ).values('last_read_at')[:1]
        
        # Подзапрос для количества непрочитанных
        unread_count_subq = Message.objects.filter(
            chat=OuterRef('pk'),
            created_at__gt=read_state_subq,
            is_deleted=False
        ).exclude(author=user).values('chat').annotate(
            count=Count('id')
        ).values('count')
        
        queryset = Chat.objects.filter(
            Q(participants=user) |
            Q(department__in=user.departments_links.filter(
                is_active=True
            ).values('department')) |
            Q(include_all_employees=True)
        ).select_related(
            'department', 'created_by'
        ).prefetch_related(
            'participants',
            Prefetch('user_settings', queryset=ChatUserSettings.objects.filter(user=user))
        ).annotate(
            unread_count=unread_count_subq
        ).distinct().order_by('-created_at')
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        """Создание чата"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Устанавливаем создателя
        chat = serializer.save(created_by=request.user)
        
        # Для приватного чата добавляем создателя в участники
        if chat.type == 'private':
            chat.participants.add(request.user)
        
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
    
    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        """Загрузка сообщений чата (пагинация по времени)"""
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
        limit = min(int(request.query_params.get('limit', 50)), 100)
        
        queryset = chat.messages.filter(is_deleted=False).select_related(
            'author', 'reply_to', 'reply_to__author', 'poll'
        ).prefetch_related(
            'attachments', 'reactions', 'reactions__user', 'poll__options'
        )
        
        # Определяем порядок сортировки в зависимости от типа запроса
        if after_id or after_ts:
            # Для загрузки новых сообщений - сортируем по возрастанию (от старых к новым)
            queryset = queryset.order_by('created_at')
        else:
            # Для загрузки старых или начальной загрузки - по убыванию (от новых к старым)
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
        
        return Response({
            'messages': [serialize_message(m) for m in messages],
            'has_more': has_more
        })
    
    @action(detail=True, methods=['get'], url_path='messages-around')
    def messages_around(self, request, pk=None):
        """Загрузка сообщений вокруг указанного"""
        chat = self.get_object()
        
        if not user_can_access_chat(chat, request.user):
            return Response(
                {'error': 'Access denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        around_id = request.query_params.get('around_id')
        limit = min(int(request.query_params.get('limit', 30)), 100)
        half = limit // 2
        
        queryset = chat.messages.filter(is_deleted=False).select_related(
            'author', 'reply_to', 'reply_to__author', 'poll'
        ).prefetch_related(
            'attachments', 'reactions', 'reactions__user', 'poll__options'
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
            messages = list(queryset.order_by('-created_at')[:limit])
            messages.reverse()
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
                anchor_dt = datetime.fromtimestamp(timestamp_seconds, tz=dt_tz.utc)
                
                # Ищем ближайшее сообщение к этому timestamp (ДО или на момент)
                anchor_msg = queryset.filter(
                    created_at__lte=anchor_dt
                ).order_by('-created_at').first()
                
                # Если не нашли до этого времени, берем первое после
                if not anchor_msg:
                    anchor_msg = queryset.filter(
                        created_at__gte=anchor_dt
                    ).order_by('created_at').first()
                
                logger.info(f"[messages_around] Searching by timestamp: {anchor_dt}, found: {anchor_msg}")
            else:
                # Это обычный message_id
                try:
                    anchor_msg = queryset.get(pk=around_value)
                    logger.info(f"[messages_around] Found message by ID: {around_value}")
                except Message.DoesNotExist:
                    logger.warning(f"[messages_around] Message with ID {around_value} not found")
        except (ValueError, TypeError):
            logger.warning(f"[messages_around] Invalid around_id format: {around_id}")
        
        if not anchor_msg:
            # Если не найдено - возвращаем последние сообщения
            messages = list(queryset.order_by('-created_at')[:limit])
            messages.reverse()
            return Response({
                'messages': [serialize_message(m) for m in messages],
                'messages_count': len(messages),
                'anchor_id': None,
                'anchor_index': 0
            })
        
        # Загружаем половину до и половину после
        before = list(queryset.filter(
            created_at__lt=anchor_msg.created_at
        ).order_by('-created_at')[:half])
        before.reverse()
        
        after = list(queryset.filter(
            created_at__gte=anchor_msg.created_at
        ).order_by('created_at')[:half+1])
        
        messages = before + after
        anchor_index = len(before)
        
        return Response({
            'messages': [serialize_message(m) for m in messages],
            'messages_count': len(messages),
            'anchor_id': anchor_msg.id,  # Возвращаем реальный message_id
            'anchor_index': anchor_index,
            'has_more_before': len(before) >= half,
            'has_more_after': len(after) > half
        })
    
    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        """
        Пометить чат как прочитанный
        
        Параметры:
        - upto_ts: timestamp последнего прочитанного сообщения (опционально)
        - message_id: ID последнего прочитанного сообщения (опционально)
        """
        chat = self.get_object()
        
        logger.info(f"[mark_read] User {request.user.id} marking chat {chat.id} as read")
        logger.info(f"[mark_read] Request data: {request.data}")
        
        read_state, created = ChatReadState.objects.get_or_create(
            chat=chat,
            user=request.user
        )
        
        logger.info(f"[mark_read] ReadState {'created' if created else 'found'}: last_read_at={read_state.last_read_at}, last_read_message_id={read_state.last_read_message_id}")
        
        # Обновляем timestamp
        upto_ts = request.data.get('upto_ts')
        new_timestamp = None
        
        if upto_ts:
            try:
                # Конвертируем timestamp (может быть в миллисекундах)
                ts_value = float(upto_ts)
                if ts_value > 10000000000:  # Timestamp в миллисекундах
                    ts_value = ts_value / 1000
                new_timestamp = datetime.fromtimestamp(ts_value, tz=dt_tz.utc)
                logger.info(f"[mark_read] Parsed timestamp: {new_timestamp}")
            except (ValueError, OSError) as e:
                new_timestamp = timezone.now()
                logger.warning(f"[mark_read] Invalid timestamp, using now: {e}")
        else:
            new_timestamp = timezone.now()
            logger.info(f"[mark_read] No timestamp provided, using now: {new_timestamp}")
        
        # Проверка: не откатываем назад
        if read_state.last_read_at and new_timestamp <= read_state.last_read_at:
            logger.warning(f"[mark_read] SKIPPING - new timestamp {new_timestamp} is not newer than current {read_state.last_read_at}")
            return Response({
                'ok': True,
                'last_read_at': read_state.last_read_at.isoformat() if read_state.last_read_at else None,
                'last_read_message_id': read_state.last_read_message_id,
                'skipped': True,
                'reason': 'timestamp_not_newer'
            })
        
        # Обновляем только если новее
        read_state.last_read_at = new_timestamp
        logger.info(f"[mark_read] Updated last_read_at to: {read_state.last_read_at}")
        
        # Обновляем last_read_message если передан message_id
        message_id = request.data.get('message_id')
        if message_id:
            try:
                message = chat.messages.get(pk=int(message_id))
                read_state.last_read_message = message
                logger.info(f"[mark_read] Set last_read_message from request: {message.id}")
            except (Message.DoesNotExist, ValueError) as e:
                logger.warning(f"[mark_read] Could not find message {message_id}: {e}")
        else:
            # Если не передан явно, находим последнее сообщение до указанного времени
            if read_state.last_read_at:
                last_msg = chat.messages.filter(
                    created_at__lte=read_state.last_read_at,
                    is_deleted=False
                ).order_by('-created_at').first()
                if last_msg:
                    read_state.last_read_message = last_msg
                    logger.info(f"[mark_read] Auto-detected last_read_message: {last_msg.id}")
                else:
                    logger.warning(f"[mark_read] No messages found before {read_state.last_read_at}")
        
        read_state.save()
        
        logger.info(f"[mark_read] SAVED ReadState: chat={chat.id}, user={request.user.id}, last_read_at={read_state.last_read_at}, last_read_message_id={read_state.last_read_message_id}")
        
        # Отправляем WebSocket событие для синхронизации между вкладками
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'user_{request.user.id}',
            {
                'type': 'chat_marked_read',
                'chat_id': chat.id,
                'last_read_at': read_state.last_read_at.isoformat() if read_state.last_read_at else None,
                'last_read_message_id': read_state.last_read_message_id,
            }
        )
        logger.info(f"[mark_read] Sent WebSocket event: chat_marked_read for chat {chat.id}")
        
        return Response({
            'ok': True,
            'last_read_at': read_state.last_read_at.isoformat() if read_state.last_read_at else None,
            'last_read_message_id': read_state.last_read_message_id
        })


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
    
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    # Явно задаем базовые атрибуты для корректной типизации DRF/Pylance
    queryset = Message.objects.none()
    serializer_class = MessageDetailSerializer
    
    def get_serializer_class(self):  # pyright: ignore[reportIncompatibleMethodOverride]
        if self.action in ['create', 'upload']:
            return MessageCreateSerializer
        elif self.action == 'update' or self.action == 'partial_update':
            return MessageEditSerializer
        elif self.action == 'list':
            return MessageListSerializer
        return MessageDetailSerializer
    
    def get_queryset(self):  # pyright: ignore[reportIncompatibleMethodOverride]
        """Сообщения доступные пользователю"""
        user = self.request.user
        
        # Чаты пользователя
        user_chats = Chat.objects.filter(
            Q(participants=user) |
            Q(department__in=user.departments_links.filter(
                is_active=True
            ).values('department')) |
            Q(include_all_employees=True)
        )
        
        return Message.objects.filter(
            chat__in=user_chats
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
        reply_to_id = request.data.get('reply_to') or request.data.get('reply_to_id')
        
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
                reply_to_id=reply_to_id if reply_to_id else None,
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
            'author', 'reply_to', 'reply_to__author', 'poll'
        ).prefetch_related(
            'attachments', 'reactions', 'reactions__user'
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
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        new_content = serializer.validated_data.get('content', '').strip()
        existing_attachment_ids = serializer.validated_data.get('existing_attachment_ids')
        
        # Валидация вложений
        current_attachments_count = instance.attachments.count()
        will_have_attachments = (
            (existing_attachment_ids is not None and len(existing_attachment_ids) > 0) or
            (existing_attachment_ids is None and current_attachments_count > 0)
        )
        
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
            
            current_ids = set(str(att.id) for att in instance.attachments.all())
            keep_ids = set(str(id) for id in existing_attachment_ids)
            ids_to_remove = current_ids - keep_ids
            ids_to_add = keep_ids - current_ids
            
            # Удаляем attachments которых нет в списке
            if ids_to_remove:
                attachments_to_delete = instance.attachments.filter(id__in=ids_to_remove)
                for att in attachments_to_delete:
                    if att.file and att.file.storage.exists(att.file.name):
                        att.file.delete(save=False)
                attachments_to_delete.delete()
                logger.info(f"[update] Removed attachments: {ids_to_remove}")
            
            # Переносим новые attachments из других сообщений к этому
            if ids_to_add:
                attachments_to_move = MessageAttachment.objects.filter(id__in=ids_to_add)
                updated_count = attachments_to_move.update(message=instance)
                logger.info(f"[update] Moved {updated_count} attachments to message {instance.id}: {list(ids_to_add)}")
        
        instance.save()
        
        # ВАЖНО: Очищаем кэш attachments перед подсчетом
        instance.refresh_from_db()
        
        # Обновляем has_attachments (заново считаем из БД)
        from communications.models import MessageAttachment
        instance.has_attachments = MessageAttachment.objects.filter(message=instance).count() > 0
        instance.save(update_fields=['has_attachments'])
        
        # Перезагружаем с нуля чтобы получить обновленные attachments
        # Используем новый запрос, чтобы избежать кэширования
        instance = Message.objects.select_related(
            'author', 'reply_to', 'reply_to__author', 'poll'
        ).prefetch_related(
            'attachments', 'reactions', 'reactions__user', 'poll__options'
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
        logger.info(f"[react] User {request.user.id} adding reaction to message {message.id}")
        
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
            reactions_summary[r.emoji]['user_names'].append(r.user.get_full_name())
        
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
        
        logger.info(f"[react] WebSocket message sent successfully")
        
        return Response({'ok': True, 'reactions_summary': reactions_summary})
    
    @action(detail=True, methods=['post'])
    def unreact(self, request, pk=None):
        """Убрать реакцию"""
        message = self.get_object()
        logger.info(f"[unreact] User {request.user.id} removing reaction from message {message.id}")
        
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
            reactions_summary[r.emoji]['user_names'].append(r.user.get_full_name())
        
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
        
        logger.info(f"[unreact] WebSocket message sent successfully")
        
        return Response({'ok': True, 'reactions_summary': reactions_summary})
    
    @action(detail=False, methods=['post'])
    def forward(self, request):
        """Переслать сообщения в другой чат"""
        serializer = ForwardMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated = cast(dict[str, Any], serializer.validated_data)
        message_ids = validated['message_ids']
        target_chat_id = validated['target_chat_id']
        
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

        validated = cast(dict[str, Any], serializer.validated_data)
        message_ids = validated['message_ids']
        
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
            # Удаляем ВСЕ старые голоса пользователя (и для single и для multiple choice)
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
            
            poll.total_voters = PollVote.objects.filter(poll=poll).values('voter').distinct().count()
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

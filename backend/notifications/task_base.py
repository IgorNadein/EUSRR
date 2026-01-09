"""
Базовые классы и утилиты для Celery задач уведомлений.

Предоставляет общую логику для обработки уведомлений,
чтобы избежать дублирования кода в tasks.py
"""
import logging
from typing import Set, Optional, Dict, Any
from django.contrib.auth import get_user_model
from celery import Task

logger = logging.getLogger(__name__)
User = get_user_model()


class BaseNotificationProcessor:
    """
    Базовый класс для процессоров уведомлений.
    
    Содержит общую логику определения получателей и отправки уведомлений.
    """
    
    def __init__(self, task: Task = None):
        """
        Args:
            task: Celery task для retry при ошибках
        """
        self.task = task
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def send_notifications(
        self,
        recipients: Set[User],
        notification_type: str,
        title: str,
        message: str,
        content_object=None,
        action_url: str = '',
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Отправляет уведомления списку получателей.
        
        Args:
            recipients: Набор получателей
            notification_type: Код типа уведомления
            title: Заголовок
            message: Текст сообщения
            content_object: Связанный объект
            action_url: URL для действия
            metadata: Дополнительные данные
            
        Returns:
            Количество отправленных уведомлений
        """
        from notifications.services import NotificationService
        
        count = 0
        for recipient in recipients:
            try:
                NotificationService.create_notification(
                    recipient=recipient,
                    notification_type_code=notification_type,
                    title=title,
                    message=message,
                    content_object=content_object,
                    action_url=action_url,
                    metadata=metadata or {}
                )
                count += 1
            except Exception as e:
                self.logger.error(
                    f"Failed to send notification to user {recipient.id}: {e}"
                )
        
        return count
    
    def get_active_employees(self, exclude_ids: Set[int] = None) -> Set[User]:
        """
        Получает всех активных сотрудников.
        
        Args:
            exclude_ids: ID пользователей для исключения
            
        Returns:
            Набор активных сотрудников
        """
        queryset = User.objects.filter(is_active=True)
        
        if exclude_ids:
            queryset = queryset.exclude(id__in=exclude_ids)
        
        return set(queryset)
    
    def get_department_employees(
        self,
        department_ids: list,
        exclude_ids: Set[int] = None
    ) -> Set[User]:
        """
        Получает сотрудников отделов.
        
        Args:
            department_ids: Список ID отделов
            exclude_ids: ID пользователей для исключения
            
        Returns:
            Набор сотрудников отделов
        """
        queryset = User.objects.filter(
            departments_links__department_id__in=department_ids,
            departments_links__is_active=True,
            is_active=True
        ).distinct()
        
        if exclude_ids:
            queryset = queryset.exclude(id__in=exclude_ids)
        
        return set(queryset)
    
    def log_result(
        self,
        entity_type: str,
        entity_id: int,
        action: str,
        notifications_sent: int
    ) -> Dict[str, Any]:
        """
        Логирует результат обработки и возвращает словарь результата.
        
        Args:
            entity_type: Тип сущности (message, event, post и т.д.)
            entity_id: ID сущности
            action: Выполненное действие
            notifications_sent: Количество отправленных уведомлений
            
        Returns:
            Словарь с результатом операции
        """
        self.logger.info(
            f"Processed {entity_type} {entity_id} ({action}): "
            f"sent {notifications_sent} notifications"
        )
        
        return {
            "status": "success",
            f"{entity_type}_id": entity_id,
            "action": action,
            "notifications_sent": notifications_sent
        }
    
    def handle_not_found(
        self,
        entity_type: str,
        entity_id: int
    ) -> Dict[str, Any]:
        """
        Обрабатывает случай когда сущность не найдена.
        
        Args:
            entity_type: Тип сущности
            entity_id: ID сущности
            
        Returns:
            Словарь с ошибкой
        """
        self.logger.error(f"{entity_type.capitalize()} {entity_id} not found")
        return {
            "status": "error",
            "reason": f"{entity_type}_not_found"
        }
    
    def handle_exception(self, exc: Exception):
        """
        Обрабатывает исключение - логирует и делает retry.
        
        Args:
            exc: Исключение для обработки
        """
        self.logger.exception(f"Failed to process notifications: {exc}")
        if self.task:
            raise self.task.retry(exc=exc)
        else:
            raise


class MessageNotificationProcessor(BaseNotificationProcessor):
    """Процессор уведомлений для сообщений в чатах"""
    
    def process(self, message_id: int) -> Dict[str, Any]:
        """
        Обрабатывает уведомления для сообщения.
        
        Args:
            message_id: ID сообщения
            
        Returns:
            Результат обработки
        """
        try:
            from communications.models import Message
            from communications.notification_signals import (
                get_users_with_notifications_enabled,
                extract_mentions,
                truncate_message,
                get_chat_name
            )
            
            # Загружаем сообщение
            message = Message.objects.select_related(
                'chat', 'author', 'reply_to__author'
            ).get(id=message_id)
            
            if message.is_system or message.is_deleted:
                return {"status": "skipped", "reason": "system_or_deleted"}
            
            chat = message.chat
            author = message.author
            content = message.content
            
            # Получаем участников
            if chat.type in ['announcement', 'channel', 'department', 'global']:
                participants = chat.get_participants.exclude(id=author.id)
            else:
                participants = chat.participants.exclude(id=author.id)
            
            participants_list = list(participants)
            if not participants_list:
                return {"status": "success", "notifications_sent": 0}
            
            # Настройки уведомлений
            notification_settings = get_users_with_notifications_enabled(
                chat, participants_list
            )
            
            notifications_count = 0
            mentioned_user_ids = []
            
            # 1. Упоминания
            mentioned_users = extract_mentions(content)
            if mentioned_users:
                for email in mentioned_users:
                    try:
                        user = User.objects.get(email=email)
                        if user in participants_list and user.id != author.id:
                            if notification_settings.get(user.id, True):
                                notifications_count += self.send_notifications(
                                    {user},
                                    'chat_mention',
                                    f'Вас упомянул {author.get_full_name() or author.username}',
                                    truncate_message(content, 100),
                                    message,
                                    f'/communications/chats/{chat.id}/?message={message.id}',
                                    {
                                        'chat_id': chat.id,
                                        'chat_name': get_chat_name(chat),
                                        'message_id': message.id,
                                        'author_id': author.id,
                                    }
                                )
                            mentioned_user_ids.append(user.id)
                    except User.DoesNotExist:
                        continue
            
            # 2. Ответы на сообщения
            if message.reply_to and message.reply_to.author_id != author.id:
                original_author = message.reply_to.author
                if original_author.id not in mentioned_user_ids:
                    if notification_settings.get(original_author.id, True):
                        notifications_count += self.send_notifications(
                            {original_author},
                            'chat_reply',
                            f'{author.get_full_name() or author.username} ответил на ваше сообщение',
                            truncate_message(content, 100),
                            message,
                            f'/communications/chats/{chat.id}/?message={message.id}',
                            {
                                'chat_id': chat.id,
                                'chat_name': get_chat_name(chat),
                                'message_id': message.id,
                                'reply_to_id': message.reply_to.id,
                                'author_id': author.id,
                            }
                        )
            
            # 3. Обычные уведомления
            excluded_ids = set(mentioned_user_ids)
            if message.reply_to and message.reply_to.author_id != author.id:
                excluded_ids.add(message.reply_to.author_id)
            
            if chat.type == 'announcement':
                notification_type = 'announcement_new_message'
                title = f'Новое объявление от {author.get_full_name() or author.username}'
                is_announcement = True
            else:
                notification_type = 'chat_new_message'
                if chat.type == 'private':
                    title = f'Новое сообщение от {author.get_full_name() or author.username}'
                else:
                    title = f'{author.get_full_name() or author.username} в {get_chat_name(chat)}'
                is_announcement = False
            
            for recipient in participants_list:
                if recipient.id in excluded_ids:
                    continue
                if not notification_settings.get(recipient.id, True):
                    continue
                
                metadata = {
                    'chat_id': chat.id,
                    'chat_name': get_chat_name(chat),
                    'message_id': message.id,
                    'author_id': author.id,
                }
                if is_announcement:
                    metadata['is_announcement'] = True
                
                notifications_count += self.send_notifications(
                    {recipient},
                    notification_type,
                    title,
                    truncate_message(content, 150 if is_announcement else 100),
                    message,
                    f'/communications/chats/{chat.id}/',
                    metadata
                )
            
            return self.log_result('message', message_id, 'created', notifications_count)
            
        except Message.DoesNotExist:
            return self.handle_not_found('message', message_id)
        except Exception as exc:
            self.handle_exception(exc)


def truncate_text(text: str, max_length: int = 100) -> str:
    """
    Обрезает текст до указанной длины, добавляя троеточие.
    
    Args:
        text: Исходный текст
        max_length: Максимальная длина
        
    Returns:
        Обрезанный текст
    """
    if not text or len(text) <= max_length:
        return text or ''
    return text[:max_length].rstrip() + '...'


class EventNotificationProcessor(BaseNotificationProcessor):
    """Процессор уведомлений о событиях в календаре"""
    
    def process(self, event_id: int) -> Dict[str, Any]:
        """Обработка уведомлений для события календаря"""
        try:
            from calendar_app.models import CalendarEvent
            from django.contrib.auth import get_user_model
            
            User = get_user_model()
            
            event = CalendarEvent.objects.select_related('creator').get(id=event_id)
            
            # Собираем всех получателей
            recipients = set()
            
            # Участники события
            for participant in event.participants.all():
                recipients.add(participant)
            
            # Департаменты (если есть)
            if event.departments.exists():
                recipients.update(self.get_department_employees(event.departments.all()))
            
            # Исключаем создателя и неактивных
            recipients = self.get_active_employees(recipients)
            if event.creator:
                recipients.discard(event.creator)
            
            if not recipients:
                return self.log_result(event_id, 0)
            
            # Отправляем уведомления
            notifications_sent = self.send_notifications(
                recipients=recipients,
                notification_type='calendar_event_created',
                title=f'Новое событие: {event.title}',
                message=truncate_text(event.description or '', 150),
                content_object=event,
                action_url=f'/calendar/?event={event.id}',
                metadata={
                    'event_id': event.id,
                    'event_title': event.title,
                    'start_time': event.start_time.isoformat() if event.start_time else None,
                    'end_time': event.end_time.isoformat() if event.end_time else None,
                }
            )
            
            return self.log_result(event_id, notifications_sent)
            
        except Exception as exc:
            return self.handle_exception(exc, f"event {event_id}")


class PostNotificationProcessor(BaseNotificationProcessor):
    """Процессор уведомлений о постах в ленте"""
    
    def process(self, post_id: int) -> Dict[str, Any]:
        """Обработка уведомлений для поста"""
        try:
            from feed.models import Post
            
            post = Post.objects.select_related('author').get(id=post_id)
            
            if post.is_deleted:
                return {"status": "skipped", "reason": "deleted"}
            
            # Собираем получателей
            recipients = set()
            
            # Департаменты
            if post.target_departments.exists():
                recipients.update(self.get_department_employees(post.target_departments.all()))
            
            # Конкретные пользователи
            for user in post.target_users.all():
                recipients.add(user)
            
            # Если нет конкретных получателей - всем активным
            if not recipients:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                recipients = set(User.objects.filter(is_active=True))
            
            # Исключаем автора и неактивных
            recipients = self.get_active_employees(recipients)
            if post.author:
                recipients.discard(post.author)
            
            if not recipients:
                return self.log_result(post_id, 0)
            
            # Отправляем уведомления
            notifications_sent = self.send_notifications(
                recipients=recipients,
                notification_type='feed_new_post',
                title=f'Новая публикация от {post.author.get_full_name() if post.author else "Система"}',
                message=truncate_text(post.content, 200),
                content_object=post,
                action_url=f'/feed/?post={post.id}',
                metadata={
                    'post_id': post.id,
                    'author_id': post.author.id if post.author else None,
                }
            )
            
            return self.log_result(post_id, notifications_sent)
            
        except Exception as exc:
            return self.handle_exception(exc, f"post {post_id}")


class RequestNotificationProcessor(BaseNotificationProcessor):
    """Процессор уведомлений о заявках"""
    
    def process(self, request_id: int, notification_type: str = 'created') -> Dict[str, Any]:
        """
        Обработка уведомлений для заявки
        
        Args:
            request_id: ID заявки
            notification_type: Тип уведомления (created, status_changed, comment_added)
        """
        try:
            from requests_app.models import Request
            
            request_obj = Request.objects.select_related('requester', 'handler').get(id=request_id)
            
            # Собираем получателей в зависимости от типа уведомления
            recipients = set()
            
            if notification_type == 'created':
                # Уведомляем исполнителя и копии
                if request_obj.handler:
                    recipients.add(request_obj.handler)
                
                for user in request_obj.recipients.all():
                    recipients.add(user)
                    
                for user in request_obj.cc_users.all():
                    recipients.add(user)
                    
            elif notification_type == 'status_changed':
                # Уведомляем создателя
                if request_obj.requester:
                    recipients.add(request_obj.requester)
                    
            elif notification_type == 'comment_added':
                # Уведомляем всех участников кроме автора комментария
                if request_obj.requester:
                    recipients.add(request_obj.requester)
                if request_obj.handler:
                    recipients.add(request_obj.handler)
                for user in request_obj.recipients.all():
                    recipients.add(user)
                for user in request_obj.cc_users.all():
                    recipients.add(user)
            
            # Исключаем неактивных
            recipients = self.get_active_employees(recipients)
            
            if not recipients:
                return self.log_result(request_id, 0)
            
            # Формируем заголовок
            title_map = {
                'created': f'Новая заявка #{request_obj.id}: {request_obj.subject}',
                'status_changed': f'Изменён статус заявки #{request_obj.id}',
                'comment_added': f'Новый комментарий к заявке #{request_obj.id}',
            }
            
            type_code_map = {
                'created': 'request_created',
                'status_changed': 'request_status_changed',
                'comment_added': 'request_comment_added',
            }
            
            # Отправляем уведомления
            notifications_sent = self.send_notifications(
                recipients=recipients,
                notification_type=type_code_map.get(notification_type, 'request_created'),
                title=title_map.get(notification_type, f'Обновление заявки #{request_obj.id}'),
                message=truncate_text(request_obj.description, 150),
                content_object=request_obj,
                action_url=f'/requests/{request_obj.id}/',
                metadata={
                    'request_id': request_obj.id,
                    'subject': request_obj.subject,
                    'status': request_obj.status,
                }
            )
            
            return self.log_result(request_id, notifications_sent)
            
        except Exception as exc:
            return self.handle_exception(exc, f"request {request_id}")


class DocumentNotificationProcessor(BaseNotificationProcessor):
    """Процессор уведомлений о документах"""
    
    def process(self, document_id: int) -> Dict[str, Any]:
        """Обработка уведомлений для документа"""
        try:
            from documents.models import Document
            
            document = Document.objects.select_related('author').get(id=document_id)
            
            if document.is_deleted:
                return {"status": "skipped", "reason": "deleted"}
            
            # Собираем получателей
            recipients = set()
            
            # Департаменты
            if document.departments.exists():
                recipients.update(self.get_department_employees(document.departments.all()))
            
            # Конкретные пользователи
            for user in document.readers.all():
                recipients.add(user)
            
            # Исключаем автора и неактивных
            recipients = self.get_active_employees(recipients)
            if document.author:
                recipients.discard(document.author)
            
            if not recipients:
                return self.log_result(document_id, 0)
            
            # Отправляем уведомления
            notifications_sent = self.send_notifications(
                recipients=recipients,
                notification_type='document_created',
                title=f'Новый документ: {document.title}',
                message=truncate_text(document.description or '', 150),
                content_object=document,
                action_url=f'/documents/{document.id}/',
                metadata={
                    'document_id': document.id,
                    'document_title': document.title,
                    'document_type': document.document_type,
                }
            )
            
            return self.log_result(document_id, notifications_sent)
            
        except Exception as exc:
            return self.handle_exception(exc, f"document {document_id}")

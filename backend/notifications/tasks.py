"""
Celery задачи для асинхронной обработки уведомлений.

Эти задачи выполняются в фоновом режиме через Celery workers,
что позволяет значительно ускорить отклик API при отправке уведомлений.
"""
from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(
    name="notifications.send_notification",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_notification_task(
    self,
    notification_type: str,
    user_id: int,
    title: str,
    message: str,
    link: Optional[str] = None,
    sender_id: Optional[int] = None,
    metadata: Optional[dict] = None,
):
    """
    Асинхронная отправка уведомления одному пользователю.
    
    Args:
        notification_type: Тип уведомления (message, document, request и т.д.)
        user_id: ID пользователя-получателя
        title: Заголовок уведомления
        message: Текст уведомления
        link: Ссылка (опционально)
        sender_id: ID отправителя (опционально)
        metadata: Дополнительные данные (опционально)
    """
    try:
        from notifications.services import NotificationService
        
        user = User.objects.get(id=user_id)
        sender = User.objects.get(id=sender_id) if sender_id else None
        
        # Вызываем синхронный метод создания уведомления
        NotificationService.create_notification(
            recipient=user,
            notification_type_code=notification_type,
            title=title,
            message=message,
            action_url=link or '',
            metadata=metadata or {},
        )
        
        logger.debug(
            f"Notification sent to user {user_id} (type: {notification_type})"
        )
        return {"status": "success", "user_id": user_id}
        
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for notification")
        return {"status": "error", "reason": "user_not_found"}
        
    except Exception as exc:
        logger.exception(f"Failed to send notification to user {user_id}: {exc}")
        # Повторяем попытку через 60 секунд
        raise self.retry(exc=exc)


@shared_task(
    name="notifications.send_bulk_notifications",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_bulk_notifications_task(
    self,
    notification_type: str,
    user_ids: List[int],
    title: str,
    message: str,
    link: Optional[str] = None,
    sender_id: Optional[int] = None,
    metadata: Optional[dict] = None,
):
    """
    Асинхронная массовая отправка уведомлений нескольким пользователям.
    
    Оптимизирована для отправки большого количества уведомлений.
    
    Args:
        notification_type: Тип уведомления
        user_ids: Список ID пользователей-получателей
        title: Заголовок уведомления
        message: Текст уведомления
        link: Ссылка (опционально)
        sender_id: ID отправителя (опционально)
        metadata: Дополнительные данные (опционально)
    """
    try:
        from notifications.services import NotificationService
        from notifications.models import Notification
        
        # Получаем всех пользователей одним запросом
        users = User.objects.filter(id__in=user_ids)
        sender = User.objects.get(id=sender_id) if sender_id else None
        
        # Создаем уведомления массово
        notifications = []
        for user in users:
            notification = Notification(
                user=user,
                notification_type=notification_type,
                title=title,
                message=message,
                link=link or "",
                sender=sender,
                metadata=metadata or {},
                created_at=timezone.now(),
            )
            notifications.append(notification)
        
        # Bulk create для производительности
        Notification.objects.bulk_create(notifications)
        
        # Отправляем WebSocket уведомления
        for user in users:
            NotificationService.send_websocket_notification(user.id)
        
        logger.debug(
            f"Bulk notification sent to {len(user_ids)} users (type: {notification_type})"
        )
        return {
            "status": "success",
            "sent_count": len(notifications),
            "user_ids": user_ids,
        }
        
    except Exception as exc:
        logger.exception(f"Failed to send bulk notifications: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name="notifications.cleanup_old_notifications",
    bind=True,
)
def cleanup_old_notifications_task(self, days: int = 90):
    """
    Периодическая задача для удаления старых прочитанных уведомлений.
    
    Args:
        days: Количество дней, после которого удаляются прочитанные уведомления
    """
    try:
        from notifications.models import Notification
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        deleted_count, _ = Notification.objects.filter(
            is_read=True,
            created_at__lt=cutoff_date
        ).delete()
        
        logger.info(
            f"Cleaned up {deleted_count} old notifications (older than {days} days)"
        )
        return {"status": "success", "deleted_count": deleted_count}
        
    except Exception as exc:
        logger.exception(f"Failed to cleanup old notifications: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name="notifications.send_digest_email",
    bind=True,
)
def send_digest_email_task(self, user_id: int):
    """
    Отправка email-дайджеста непрочитанных уведомлений пользователю.
    
    Может вызываться периодически для пользователей с настроенными email-дайджестами.
    
    Args:
        user_id: ID пользователя
    """
    try:
        from notifications.models import Notification
        from common.emails import send_email
        
        user = User.objects.get(id=user_id)
        
        # Получаем непрочитанные уведомления за последние 24 часа
        cutoff_time = timezone.now() - timezone.timedelta(hours=24)
        unread_notifications = Notification.objects.filter(
            user=user,
            is_read=False,
            created_at__gte=cutoff_time
        ).order_by('-created_at')[:20]
        
        if not unread_notifications:
            logger.debug(f"No unread notifications for user {user_id}, skipping digest")
            return {"status": "skipped", "reason": "no_notifications"}
        
        # Формируем HTML для email
        notification_html = ""
        for notif in unread_notifications:
            notification_html += f"""
            <div style="margin-bottom: 15px; padding: 10px; border-left: 3px solid #007bff;">
                <strong>{notif.title}</strong><br>
                <span style="color: #666;">{notif.message}</span><br>
                <small style="color: #999;">{notif.created_at.strftime('%H:%M, %d.%m.%Y')}</small>
            </div>
            """
        
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>У вас {len(unread_notifications)} непрочитанных уведомлений</h2>
            <div style="margin-top: 20px;">
                {notification_html}
            </div>
            <p style="margin-top: 30px;">
                <a href="{settings.BASE_URL}/notifications/" style="color: #007bff;">
                    Посмотреть все уведомления
                </a>
            </p>
        </body>
        </html>
        """
        
        send_email(
            subject=f"У вас {len(unread_notifications)} новых уведомлений",
            to_email=user.email,
            html_content=html_content,
        )
        
        logger.info(f"Digest email sent to user {user_id} with {len(unread_notifications)} notifications")
        return {
            "status": "success",
            "user_id": user_id,
            "notification_count": len(unread_notifications),
        }
        
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for digest email")
        return {"status": "error", "reason": "user_not_found"}
        
    except Exception as exc:
        logger.exception(f"Failed to send digest email to user {user_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name="communications.process_message_notifications",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def process_message_notifications_task(self, message_id: int):
    """
    Обрабатывает ВСЕ уведомления для нового сообщения в чате асинхронно.
    
    Это позволяет signal handler сразу вернуть управление,
    а всю логику обработки (поиск упоминаний, проверка настроек, отправка)
    выполнить в фоновом режиме.
    
    Args:
        message_id: ID сообщения
    """
    try:
        from communications.models import Message
        from notifications.services import NotificationService
        from communications.notification_signals import (
            get_users_with_notifications_enabled,
            extract_mentions,
            truncate_message,
            get_chat_name
        )
        
        # Загружаем сообщение с оптимизацией
        message = Message.objects.select_related(
            'chat', 'author', 'reply_to__author'
        ).get(id=message_id)
        
        if message.is_system or message.is_deleted:
            return {"status": "skipped", "reason": "system_or_deleted"}
        
        chat = message.chat
        author = message.author
        content = message.content
        
        # Получаем всех участников чата кроме автора
        if chat.type in ['announcement', 'channel', 'department', 'global']:
            participants = chat.get_participants.exclude(id=author.id)
        else:
            participants = chat.participants.exclude(id=author.id)
        
        participants_list = list(participants)
        if not participants_list:
            return {"status": "success", "notifications_sent": 0}
        
        # Загружаем настройки уведомлений ОДНИМ запросом
        notification_settings = get_users_with_notifications_enabled(chat, participants_list)
        
        notifications_count = 0
        
        # 1. Обработка упоминаний (@username)
        mentioned_users = extract_mentions(content)
        mentioned_user_ids = []
        
        if mentioned_users:
            for email in mentioned_users:
                try:
                    user = User.objects.get(email=email)
                    if user in participants_list and user.id != author.id:
                        if notification_settings.get(user.id, True):
                            NotificationService.create_notification(
                                recipient=user,
                                notification_type_code='chat_mention',
                                title=f'Вас упомянул {author.get_full_name() or author.username}',
                                message=truncate_message(content, 100),
                                content_object=message,
                                action_url=f'/communications/chats/{chat.id}/?message={message.id}',
                                metadata={
                                    'chat_id': chat.id,
                                    'chat_name': get_chat_name(chat),
                                    'message_id': message.id,
                                    'author_id': author.id,
                                }
                            )
                            notifications_count += 1
                        mentioned_user_ids.append(user.id)
                except User.DoesNotExist:
                    continue
        
        # 2. Обработка ответов на сообщения
        if message.reply_to and message.reply_to.author_id != author.id:
            original_author = message.reply_to.author
            
            if original_author.id not in mentioned_user_ids:
                if notification_settings.get(original_author.id, True):
                    NotificationService.create_notification(
                        recipient=original_author,
                        notification_type_code='chat_reply',
                        title=f'{author.get_full_name() or author.username} ответил на ваше сообщение',
                        message=truncate_message(content, 100),
                        content_object=message,
                        action_url=f'/communications/chats/{chat.id}/?message={message.id}',
                        metadata={
                            'chat_id': chat.id,
                            'chat_name': get_chat_name(chat),
                            'message_id': message.id,
                            'reply_to_id': message.reply_to.id,
                            'author_id': author.id,
                        }
                    )
                    notifications_count += 1
        
        # 3. Обычное уведомление о новом сообщении
        excluded_ids = set(mentioned_user_ids)
        if message.reply_to and message.reply_to.author_id != author.id:
            excluded_ids.add(message.reply_to.author_id)
        
        # Определяем тип уведомления
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
        
        # Отправляем уведомления
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
            
            NotificationService.create_notification(
                recipient=recipient,
                notification_type_code=notification_type,
                title=title,
                message=truncate_message(content, 150 if is_announcement else 100),
                content_object=message,
                action_url=f'/communications/chats/{chat.id}/',
                metadata=metadata
            )
            notifications_count += 1
        
        logger.info(
            f"Processed message {message_id}: sent {notifications_count} notifications"
        )
        
        return {
            "status": "success",
            "message_id": message_id,
            "notifications_sent": notifications_count
        }
        
    except Message.DoesNotExist:
        logger.error(f"Message {message_id} not found")
        return {"status": "error", "reason": "message_not_found"}
        
    except Exception as exc:
        logger.exception(f"Failed to process notifications for message {message_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name="calendar.process_event_notifications",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def process_event_notifications_task(
    self,
    event_id: int,
    action: str,  # 'created', 'updated', 'cancelled'
    changed_fields: list = None
):
    """
    Обрабатывает уведомления для событий календаря асинхронно.
    
    Args:
        event_id: ID события
        action: Тип действия ('created', 'updated', 'cancelled')
        changed_fields: Список изменённых полей (для updated)
    """
    try:
        from calendar_app.models import CalendarEvent
        from notifications.services import NotificationService
        
        event = CalendarEvent.objects.select_related(
            'department', 'creator'
        ).prefetch_related('participants').get(id=event_id)
        
        # Определяем получателей
        recipients = set()
        
        if event.is_company:
            from employees.models import Employee
            recipients = set(Employee.objects.filter(is_active=True).exclude(id=event.creator.id))
        elif event.department:
            recipients = set(event.department.employees.filter(is_active=True).exclude(id=event.creator.id))
        else:
            recipients = set(event.participants.exclude(id=event.creator.id))
        
        if not recipients:
            return {"status": "success", "notifications_sent": 0}
        
        # Определяем тип и текст уведомления
        if action == 'created':
            notification_type = 'event_created'
            title = 'Новое событие в календаре'
            message = f'"{event.title}" ({event.start_date.strftime("%d.%m.%Y")})'
        elif action == 'cancelled':
            notification_type = 'event_cancelled'
            title = 'Событие отменено'
            message = f'Событие "{event.title}" ({event.start_date.strftime("%d.%m.%Y")}) отменено'
        else:  # updated
            notification_type = 'event_updated'
            title = 'Событие изменено'
            message = f'Изменено событие "{event.title}"'
        
        # URL календаря
        if event.department:
            action_url = f'/calendar/?department={event.department.id}'
        else:
            action_url = '/calendar/'
        
        notifications_count = 0
        
        # Отправляем уведомления
        for recipient in recipients:
            NotificationService.create_notification(
                recipient=recipient,
                notification_type_code=notification_type,
                title=title,
                message=message,
                content_object=event,
                action_url=action_url,
                metadata={
                    'event_id': event.id,
                    'event_title': event.title,
                    'event_date': event.start_date.isoformat(),
                    'department_id': event.department.id if event.department else None,
                    'is_company_event': event.is_company,
                }
            )
            notifications_count += 1
        
        logger.info(
            f"Processed event {event_id} ({action}): sent {notifications_count} notifications"
        )
        
        return {
            "status": "success",
            "event_id": event_id,
            "action": action,
            "notifications_sent": notifications_count
        }
        
    except CalendarEvent.DoesNotExist:
        logger.error(f"CalendarEvent {event_id} not found")
        return {"status": "error", "reason": "event_not_found"}
        
    except Exception as exc:
        logger.exception(f"Failed to process event notifications: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name="feed.process_post_notifications",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def process_post_notifications_task(self, post_id: int, action: str = 'created'):
    """
    Обрабатывает уведомления для публикаций асинхронно.
    
    Args:
        post_id: ID публикации
        action: Тип действия ('created', 'comment')
    """
    try:
        from feed.models import Post
        from notifications.services import NotificationService
        
        post = Post.objects.select_related(
            'author', 'department'
        ).get(id=post_id)
        
        # Определяем получателей
        recipients = set()
        
        if post.type == 'company':
            from employees.models import Employee
            recipients = set(Employee.objects.filter(is_active=True).exclude(id=post.author.id))
        elif post.type == 'department' and post.department:
            recipients = set(post.department.employees.filter(is_active=True).exclude(id=post.author.id))
        
        if not recipients:
            return {"status": "success", "notifications_sent": 0}
        
        # Определяем контекст
        if post.type == 'company':
            context = 'компании'
        elif post.type == 'department' and post.department:
            context = f'отдела {post.department.name}'
        else:
            context = f'от {post.author.get_full_name() or post.author.username}'
        
        notifications_count = 0
        
        # Отправляем уведомления
        for recipient in recipients:
            NotificationService.create_notification(
                recipient=recipient,
                notification_type_code='feed_new_post',
                title=f'Новая публикация {context}',
                message=post.title,
                content_object=post,
                action_url=f'/post/{post.id}/',
                metadata={
                    'post_id': post.id,
                    'post_title': post.title,
                    'author_id': post.author.id,
                    'post_type': post.type,
                }
            )
            notifications_count += 1
        
        logger.info(
            f"Processed post {post_id}: sent {notifications_count} notifications"
        )
        
        return {
            "status": "success",
            "post_id": post_id,
            "notifications_sent": notifications_count
        }
        
    except Post.DoesNotExist:
        logger.error(f"Post {post_id} not found")
        return {"status": "error", "reason": "post_not_found"}
        
    except Exception as exc:
        logger.exception(f"Failed to process post notifications: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name="requests.process_request_notifications",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def process_request_notifications_task(
    self,
    request_id: int,
    action: str,  # 'created', 'approved', 'rejected', 'comment'
    comment_id: int = None
):
    """
    Обрабатывает уведомления для заявлений асинхронно.
    
    Args:
        request_id: ID заявления
        action: Тип действия
        comment_id: ID комментария (если action='comment')
    """
    try:
        from requests_app.models import Request, RequestComment
        from notifications.services import NotificationService
        
        request_obj = Request.objects.select_related(
            'employee'
        ).prefetch_related('departments').get(id=request_id)
        
        recipients = set()
        
        if action == 'comment' and comment_id:
            comment = RequestComment.objects.select_related('author').get(id=comment_id)
            
            # Уведомляем автора заявления
            recipients.add(request_obj.employee)
            
            # Уведомляем руководителей отделов
            for dept in request_obj.departments.all():
                dept_heads = dept.employees.filter(
                    departments_links__role='head',
                    departments_links__is_active=True,
                    is_active=True
                )
                recipients.update(dept_heads)
            
            # Исключаем автора комментария
            recipients.discard(comment.author)
            
            notification_type = 'request_comment'
            title = f"💬 Новый комментарий к заявлению от {request_obj.employee.get_full_name()}"
            message = f"{comment.author.get_full_name()} прокомментировал: {comment.text[:100]}"
            
        elif action == 'approved':
            recipients = {request_obj.employee}
            notification_type = 'request_approved'
            title = f"✅ Заявление одобрено"
            message = f'Ваше заявление "{request_obj.get_type_display()}" одобрено'
            
        elif action == 'rejected':
            recipients = {request_obj.employee}
            notification_type = 'request_rejected'
            title = f"❌ Заявление отклонено"
            message = f'Ваше заявление "{request_obj.get_type_display()}" отклонено'
            
        else:  # created
            # Уведомляем руководителей
            for dept in request_obj.departments.all():
                dept_heads = dept.employees.filter(
                    departments_links__role='head',
                    departments_links__is_active=True,
                    is_active=True
                )
                recipients.update(dept_heads)
            
            notification_type = 'request_new'
            title = f"📋 Новое заявление от {request_obj.employee.get_full_name()}"
            message = f'Тип: {request_obj.get_type_display()}'
        
        if not recipients:
            return {"status": "success", "notifications_sent": 0}
        
        notifications_count = 0
        
        # Отправляем уведомления
        for recipient in recipients:
            NotificationService.create_notification(
                recipient=recipient,
                notification_type_code=notification_type,
                title=title,
                message=message,
                content_object=request_obj,
                action_url=f'/requests/{request_obj.id}/',
                metadata={
                    'request_id': request_obj.id,
                    'request_type': request_obj.type,
                    'employee_id': request_obj.employee.id,
                }
            )
            notifications_count += 1
        
        logger.info(
            f"Processed request {request_id} ({action}): sent {notifications_count} notifications"
        )
        
        return {
            "status": "success",
            "request_id": request_id,
            "action": action,
            "notifications_sent": notifications_count
        }
        
    except Request.DoesNotExist:
        logger.error(f"Request {request_id} not found")
        return {"status": "error", "reason": "request_not_found"}
        
    except Exception as exc:
        logger.exception(f"Failed to process request notifications: {exc}")
        raise self.retry(exc=exc)

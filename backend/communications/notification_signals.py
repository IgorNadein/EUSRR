"""
Signals для автоматической генерации уведомлений в модуле Communications.

Обрабатывает события:
- Новое сообщение в чате
- Упоминание (@username) в сообщении
- Ответ на сообщение
- Добавление в чат
"""

import re
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from .models import Message, Chat
from notifications.services import NotificationService

Employee = get_user_model()


@receiver(post_save, sender=Message)
def create_message_notifications(sender, instance, created, **kwargs):
    """
    Создает уведомления при создании нового сообщения.
    
    Обрабатывает:
    1. Новое сообщение в чате (для всех участников кроме автора)
    2. Упоминания (@username) в тексте
    3. Ответ на сообщение (reply_to)
    """
    if not created or instance.is_system or instance.is_deleted:
        return
    
    chat = instance.chat
    author = instance.author
    content = instance.content
    
    # Получаем всех участников чата кроме автора
    participants = chat.participants.exclude(id=author.id)
    
    # 1. Обработка упоминаний (@username)
    mentioned_users = extract_mentions(content)
    mentioned_user_ids = []
    
    if mentioned_users:
        # Проверяем, что упомянутые пользователи есть в чате
        for email in mentioned_users:
            try:
                user = Employee.objects.get(email=email)
                if user in participants and user.id != author.id:
                    # Создаем уведомление об упоминании
                    NotificationService.create_notification(
                        recipient=user,
                        notification_type_code='chat_mention',
                        title=f'Вас упомянул {author.get_full_name() or author.username}',
                        message=truncate_message(content, 100),
                        content_object=instance,
                        action_url=f'/communications/chats/{chat.id}/?message={instance.id}',
                        metadata={
                            'chat_id': chat.id,
                            'chat_name': get_chat_name(chat),
                            'message_id': instance.id,
                            'author_id': author.id,
                        }
                    )
                    mentioned_user_ids.append(user.id)
            except Employee.DoesNotExist:
                continue
    
    # 2. Обработка ответов на сообщения
    if instance.reply_to and instance.reply_to.author_id != author.id:
        original_author = instance.reply_to.author
        
        # Создаем уведомление об ответе (если автор не упомянут явно)
        if original_author.id not in mentioned_user_ids:
            NotificationService.create_notification(
                recipient=original_author,
                notification_type_code='chat_reply',
                title=f'{author.get_full_name() or author.username} ответил на ваше сообщение',
                message=truncate_message(content, 100),
                content_object=instance,
                action_url=f'/communications/chats/{chat.id}/?message={instance.id}',
                metadata={
                    'chat_id': chat.id,
                    'chat_name': get_chat_name(chat),
                    'message_id': instance.id,
                    'reply_to_id': instance.reply_to.id,
                    'author_id': author.id,
                }
            )
    
    # 3. Обычное уведомление о новом сообщении
    # Отправляем только тем, кто НЕ получил упоминание или ответ
    excluded_ids = set(mentioned_user_ids)
    if instance.reply_to and instance.reply_to.author_id != author.id:
        excluded_ids.add(instance.reply_to.author_id)
    
    # Определяем, кому отправлять обычные уведомления
    # Для приватных чатов - всегда отправляем
    # Для announcement - отправляем ВСЕМ участникам (это важные объявления)
    # Для групповых - можно добавить логику (например, только онлайн или с настройками)
    if chat.type == 'private':
        recipients_for_new_message = participants.exclude(id__in=excluded_ids)
        
        for recipient in recipients_for_new_message:
            NotificationService.create_notification(
                recipient=recipient,
                notification_type_code='chat_new_message',
                title=f'Новое сообщение от {author.get_full_name() or author.username}',
                message=truncate_message(content, 100),
                content_object=instance,
                action_url=f'/communications/chats/{chat.id}/',
                metadata={
                    'chat_id': chat.id,
                    'chat_name': get_chat_name(chat),
                    'message_id': instance.id,
                    'author_id': author.id,
                }
            )
    elif chat.type == 'announcement':
        # Для объявлений отправляем ВСЕМ участникам
        recipients_for_announcement = participants.exclude(id__in=excluded_ids)
        
        for recipient in recipients_for_announcement:
            NotificationService.create_notification(
                recipient=recipient,
                notification_type_code='announcement_new_message',
                title=f'Новое объявление от {author.get_full_name() or author.username}',
                message=truncate_message(content, 150),
                content_object=instance,
                action_url=f'/communications/chats/{chat.id}/',
                metadata={
                    'chat_id': chat.id,
                    'chat_name': get_chat_name(chat),
                    'message_id': instance.id,
                    'author_id': author.id,
                    'is_announcement': True,
                }
            )
    elif chat.type in ['group', 'department', 'channel']:
        # Для групповых чатов - отправляем уведомление только если есть упоминание или ответ
        # Обычные сообщения не создают уведомления, чтобы не спамить
        pass


@receiver(m2m_changed, sender=Chat.participants.through)
def create_chat_added_notifications(sender, instance, action, pk_set, **kwargs):
    """
    Создает уведомления когда пользователя добавляют в чат.
    """
    if action != 'post_add':
        return
    
    chat = instance
    
    # Получаем информацию о том, кто добавил (если доступно)
    # Это может быть последний изменивший или создатель чата
    added_by = getattr(chat, 'created_by', None) or chat.participants.first()
    
    # Создаем уведомления для новых участников
    for user_id in pk_set:
        try:
            user = Employee.objects.get(id=user_id)
            
            # Не отправляем уведомление тому, кто сам себя добавил
            if added_by and user.id == added_by.id:
                continue
            
            NotificationService.create_notification(
                recipient=user,
                notification_type_code='chat_added_to_chat',
                title=f'Вас добавили в чат',
                message=f'Вы были добавлены в чат "{get_chat_name(chat)}"',
                content_object=chat,
                action_url=f'/communications/chats/{chat.id}/',
                metadata={
                    'chat_id': chat.id,
                    'chat_type': chat.type,
                    'chat_name': get_chat_name(chat),
                    'added_by_id': added_by.id if added_by else None,
                }
            )
        except Employee.DoesNotExist:
            continue


# ===== Вспомогательные функции =====

def extract_mentions(text):
    """
    Извлекает email'ы из упоминаний вида @email.
    
    Returns:
        list: Список email'ов без символа @
    """
    if not text:
        return []
    
    # Паттерн: @ + email формат
    pattern = r'@([\w.+-]+@[\w.-]+\.[\w]+)'
    mentions = re.findall(pattern, text)
    
    return list(set(mentions))  # Уникальные значения


def truncate_message(text, max_length=100):
    """
    Обрезает текст сообщения до указанной длины.
    """
    if not text:
        return ''
    
    if len(text) <= max_length:
        return text
    
    return text[:max_length - 3] + '...'


def get_chat_name(chat):
    """
    Возвращает название чата в зависимости от типа.
    """
    if chat.name:
        return chat.name
    
    if chat.type == 'global':
        return 'Глобальный чат'
    
    if chat.type == 'department' and chat.department:
        return f'Чат отдела: {chat.department.name}'
    
    if chat.type == 'private':
        # Для приватного чата можно вернуть имена участников
        participants = chat.participants.all()[:2]
        if participants:
            names = [p.get_full_name() or p.username for p in participants]
            return ', '.join(names)
    
    return 'Чат'

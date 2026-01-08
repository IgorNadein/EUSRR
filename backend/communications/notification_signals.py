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

from .models import Message, Chat, ChatUserSettings
from notifications.services import NotificationService

Employee = get_user_model()


def should_send_notification(chat, user):
    """
    Проверяет, нужно ли отправлять уведомление пользователю для данного чата.
    
    Args:
        chat: Chat объект
        user: Employee объект
        
    Returns:
        bool: True если нужно отправить уведомление, False если пользователь отключил уведомления
    """
    try:
        settings = ChatUserSettings.objects.get(chat=chat, user=user)
        return settings.notifications_enabled
    except ChatUserSettings.DoesNotExist:
        # Если настройки не найдены, считаем что уведомления включены по умолчанию
        return True


def get_users_with_notifications_enabled(chat, users):
    """
    Получает словарь пользователей с их настройками уведомлений.
    Оптимизированная версия - один запрос к БД вместо N.
    
    Args:
        chat: Chat объект
        users: QuerySet или список пользователей
        
    Returns:
        dict: {user_id: notifications_enabled}
    """
    if not users:
        return {}
    
    user_ids = [u.id for u in users]
    
    # Один запрос для всех пользователей
    settings = ChatUserSettings.objects.filter(
        chat=chat,
        user_id__in=user_ids
    ).values('user_id', 'notifications_enabled')
    
    # Создаем словарь для быстрого доступа
    settings_dict = {s['user_id']: s['notifications_enabled'] for s in settings}
    
    # Для пользователей без настроек - по умолчанию True
    return {uid: settings_dict.get(uid, True) for uid in user_ids}


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
    # Для announcement/channel/department используем get_participants
    if chat.type in ['announcement', 'channel', 'department', 'global']:
        participants = chat.get_participants.exclude(id=author.id)
    else:
        participants = chat.participants.exclude(id=author.id)
    
    # ОПТИМИЗАЦИЯ: Загружаем настройки уведомлений ОДНИМ запросом для всех участников
    participants_list = list(participants)
    if not participants_list:
        return  # Нет получателей - выходим
    
    notification_settings = get_users_with_notifications_enabled(chat, participants_list)
    
    # 1. Обработка упоминаний (@username)
    mentioned_users = extract_mentions(content)
    mentioned_user_ids = []
    
    if mentioned_users:
        # Проверяем, что упомянутые пользователи есть в чате
        for email in mentioned_users:
            try:
                user = Employee.objects.get(email=email)
                if user in participants_list and user.id != author.id:
                    # Проверяем настройки уведомлений (из предзагруженного словаря)
                    if notification_settings.get(user.id, True):
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
            # Проверяем настройки уведомлений (из предзагруженного словаря)
            if notification_settings.get(original_author.id, True):
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
    
    # СТАНДАРТИЗИРОВАННАЯ ЛОГИКА УВЕДОМЛЕНИЙ:
    # Все типы чатов могут отправлять уведомления, но пользователь может их отключить
    # через настройки ChatUserSettings.notifications_enabled
    
    # Определяем тип уведомления и заголовок в зависимости от типа чата
    if chat.type == 'announcement':
        notification_type = 'announcement_new_message'
        title = f'Новое объявление от {author.get_full_name() or author.username}'
        is_announcement = True
    else:
        # Для private, group, department, channel используем единый тип
        notification_type = 'chat_new_message'
        if chat.type == 'private':
            title = f'Новое сообщение от {author.get_full_name() or author.username}'
        else:  # group, department, channel
            title = f'{author.get_full_name() or author.username} в {get_chat_name(chat)}'
        is_announcement = False
    
    # Отправляем уведомления всем участникам (с учетом их настроек)
    for recipient in participants_list:
        # Пропускаем тех, кто уже получил упоминание или ответ
        if recipient.id in excluded_ids:
            continue
        
        # Проверяем настройки уведомлений (из предзагруженного словаря)
        if not notification_settings.get(recipient.id, True):
            continue
        
        metadata = {
            'chat_id': chat.id,
            'chat_name': get_chat_name(chat),
            'message_id': instance.id,
            'author_id': author.id,
        }
        if is_announcement:
            metadata['is_announcement'] = True
        
        NotificationService.create_notification(
            recipient=recipient,
            notification_type_code=notification_type,
            title=title,
            message=truncate_message(content, 150 if is_announcement else 100),
            content_object=instance,
            action_url=f'/communications/chats/{chat.id}/',
            metadata=metadata
        )


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
    
    # ОПТИМИЗАЦИЯ: Получаем всех новых пользователей одним запросом
    new_users = Employee.objects.filter(id__in=pk_set)
    
    # ОПТИМИЗАЦИЯ: Загружаем настройки одним запросом
    notification_settings = get_users_with_notifications_enabled(chat, new_users)
    
    # Создаем уведомления для новых участников
    for user in new_users:
        # Не отправляем уведомление тому, кто сам себя добавил
        if added_by and user.id == added_by.id:
            continue
        
        # Проверяем настройки уведомлений (из предзагруженного словаря)
        if not notification_settings.get(user.id, True):
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

"""
Бизнес-логика отправки уведомлений для модуля Communications.

Функции:
- get_users_with_notifications_enabled - проверка настроек уведомлений
- notify_new_message - уведомление о новом сообщении (с упоминаниями и ответами)
- notify_chat_added - уведомление о добавлении в чат
"""

from django.contrib.auth import get_user_model
from notifications.signals import notify

from ..models import ChatUserSettings
from .config import (
    NotificationVerbs,
    MessageTemplates,
    ActionURLs,
    extract_mentions,
    truncate_message,
    get_chat_name,
)

Employee = get_user_model()


def get_users_with_notifications_enabled(chat, users) -> dict[int, bool]:
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


def notify_new_message(message):
    """
    Отправляет уведомления о новом сообщении в чате.
    
    Обрабатывает три типа уведомлений:
    1. Упоминания (@username) - высокий приоритет
    2. Ответы на сообщения - средний приоритет
    3. Обычные сообщения в чате - низкий приоритет
    
    Args:
        message: Экземпляр модели Message
    """
    chat = message.chat
    author = message.author
    content = message.content
    
    # Получаем всех участников чата кроме автора
    if chat.type in ['announcement', 'channel', 'department', 'global']:
        participants = chat.get_participants.exclude(id=author.id)
    else:
        participants = chat.participants.exclude(id=author.id)
    
    # ОПТИМИЗАЦИЯ: Загружаем настройки уведомлений ОДНИМ запросом
    participants_list = list(participants)
    if not participants_list:
        return  # Нет получателей
    
    notification_settings = get_users_with_notifications_enabled(chat, participants_list)
    
    # Отслеживаем, кому уже отправили уведомления
    notified_user_ids = set()
    
    # 1. УПОМИНАНИЯ (@username)
    mentioned_users = extract_mentions(content)
    author_name = author.get_full_name() or author.username
    
    if mentioned_users:
        for email in mentioned_users:
            try:
                user = Employee.objects.get(email=email)
                if user in participants_list and user.id != author.id:
                    if notification_settings.get(user.id, True):
                        notify.send(
                            sender=author,
                            recipient=user,
                            verb=NotificationVerbs.MENTION,
                            action_object=message,
                            description=truncate_message(content, 100),
                            action_url=ActionURLs.MESSAGES,
                            data={
                                'title': MessageTemplates.mention(author_name),
                                'chat_id': chat.id,
                                'chat_name': get_chat_name(chat),
                                'message_id': message.id,
                                'author_id': author.id,
                            }
                        )
                    notified_user_ids.add(user.id)
            except Employee.DoesNotExist:
                continue
    
    # 2. ОТВЕТЫ НА СООБЩЕНИЯ
    if message.reply_to and message.reply_to.author_id != author.id:
        original_author = message.reply_to.author
        
        if original_author.id not in notified_user_ids:
            if notification_settings.get(original_author.id, True):
                notify.send(
                    sender=author,
                    recipient=original_author,
                    verb=NotificationVerbs.REPLY,
                    action_object=message,
                    description=truncate_message(content, 100),
                    action_url=ActionURLs.MESSAGES,
                    data={
                        'title': MessageTemplates.reply(author_name),
                        'chat_id': chat.id,
                        'chat_name': get_chat_name(chat),
                        'message_id': message.id,
                        'reply_to_id': message.reply_to.id,
                        'author_id': author.id,
                    }
                )
            notified_user_ids.add(original_author.id)
    
    # 3. ОБЫЧНЫЕ УВЕДОМЛЕНИЯ О НОВОМ СООБЩЕНИИ
    if chat.type == 'announcement':
        notification_verb = NotificationVerbs.ANNOUNCEMENT
        title = MessageTemplates.announcement(author_name)
        max_length = 150
        is_announcement = True
    else:
        notification_verb = NotificationVerbs.NEW_MESSAGE
        if chat.type == 'private':
            title = MessageTemplates.private_message(author_name)
        else:
            title = MessageTemplates.group_message(author_name, get_chat_name(chat))
        max_length = 100
        is_announcement = False
    
    for recipient in participants_list:
        # Пропускаем тех, кому уже отправили уведомление
        if recipient.id in notified_user_ids:
            continue
        
        # Проверяем настройки уведомлений
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
        
        notify.send(
            sender=author,
            recipient=recipient,
            verb=notification_verb,
            action_object=message,
            description=truncate_message(content, max_length),
            action_url=ActionURLs.MESSAGES,
            data={**metadata, 'title': title},
        )


def notify_chat_added(chat, new_users, added_by=None):
    """
    Отправляет уведомления пользователям о добавлении в чат.
    
    Args:
        chat: Объект Chat
        new_users: Список/QuerySet новых пользователей
        added_by: Пользователь, который добавил (опционально)
    """
    # ОПТИМИЗАЦИЯ: Загружаем настройки одним запросом
    notification_settings = get_users_with_notifications_enabled(chat, new_users)
    
    # Создаем уведомления для новых участников
    for user in new_users:
        # Не отправляем уведомление тому, кто сам себя добавил
        if added_by and user.id == added_by.id:
            continue
        
        # Проверяем настройки уведомлений
        if not notification_settings.get(user.id, True):
            continue
        
        notify.send(
            sender=added_by,
            recipient=user,
            verb=NotificationVerbs.ADDED_TO_CHAT,
            action_object=chat,
            description=MessageTemplates.added_to_chat(get_chat_name(chat)),
            action_url=ActionURLs.MESSAGES,
            data={
                'title': MessageTemplates.added_to_chat_title(),
                'chat_id': chat.id,
                'chat_name': get_chat_name(chat),
                'added_by_id': added_by.id if added_by else None,
            }
        )

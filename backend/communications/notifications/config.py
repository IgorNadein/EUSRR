"""
Конфигурация уведомлений для модуля Communications.

Содержит:
- NotificationVerbs - глаголы для уведомлений
- MessageTemplates - шаблоны сообщений
- ActionURLs - URL-адреса действий
- Вспомогательные функции для обработки сообщений
"""

import re


class NotificationVerbs:
    """Глаголы (verbs) для уведомлений communications."""
    
    NEW_MESSAGE = 'chat_new_message'
    ANNOUNCEMENT = 'announcement_new_message'
    MENTION = 'chat_mention'
    REPLY = 'chat_reply'
    ADDED_TO_CHAT = 'chat_added_to_chat'


class MessageTemplates:
    """Шаблоны сообщений для уведомлений communications."""
    
    @staticmethod
    def mention(author_name: str) -> str:
        """Шаблон для упоминания пользователя."""
        return f'Вас упомянул {author_name}'
    
    @staticmethod
    def reply(author_name: str) -> str:
        """Шаблон для ответа на сообщение."""
        return f'{author_name} ответил на ваше сообщение'
    
    @staticmethod
    def announcement(author_name: str) -> str:
        """Шаблон для нового объявления."""
        return f'Новое объявление от {author_name}'
    
    @staticmethod
    def private_message(author_name: str) -> str:
        """Шаблон для приватного сообщения."""
        return f'Новое сообщение от {author_name}'
    
    @staticmethod
    def group_message(author_name: str, chat_name: str) -> str:
        """Шаблон для сообщения в группе."""
        return f'{author_name} в {chat_name}'
    
    @staticmethod
    def added_to_chat(chat_name: str) -> str:
        """Шаблон для добавления в чат."""
        return f'Вы были добавлены в чат "{chat_name}"'
    
    @staticmethod
    def added_to_chat_title() -> str:
        """Заголовок для уведомления о добавлении в чат."""
        return 'Вас добавили в чат'


class ActionURLs:
    """URL-адреса для действий с сообщениями."""
    
    MESSAGES = '/messages'
    
    @staticmethod
    def chat_detail(chat_id: int) -> str:
        """
        Возвращает URL-адрес чата.
        """
        return f'/messages/{chat_id}'
    
    @staticmethod
    def message_detail(chat_id: int, message_id: int) -> str:
        """
        Возвращает URL-адрес сообщения.
        
        В будущем можно добавить прокрутку к конкретному сообщению.
        """
        return f'/messages/{chat_id}?message={message_id}'


# ===== Вспомогательные функции =====

def extract_mentions(text: str) -> list[str]:
    """
    Извлекает email'ы из упоминаний вида @email.
    
    Args:
        text: Текст сообщения
    
    Returns:
        list: Список email'ов без символа @
    
    Examples:
        >>> extract_mentions("Привет @user@example.com и @test@mail.com")
        ['user@example.com', 'test@mail.com']
    """
    if not text:
        return []
    
    # Паттерн: @ + email формат
    pattern = r'@([\w.+-]+@[\w.-]+\.[\w]+)'
    mentions = re.findall(pattern, text)
    
    return list(set(mentions))  # Уникальные значения


def truncate_message(text: str, max_length: int = 100) -> str:
    """
    Обрезает текст сообщения до указанной длины.
    
    Args:
        text: Исходный текст
        max_length: Максимальная длина (по умолчанию 100)
    
    Returns:
        Обрезанный текст с многоточием если нужно
    """
    if not text:
        return ''
    
    if len(text) <= max_length:
        return text
    
    return text[:max_length - 3] + '...'


def get_chat_name(chat) -> str:
    """
    Возвращает название чата в зависимости от типа.
    
    Args:
        chat: Объект Chat
    
    Returns:
        str: Название чата
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

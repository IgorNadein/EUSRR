"""
Django signals для автоматической генерации уведомлений в модуле Communications.

Обрабатывает события:
- post_save для Message - новое сообщение (с упоминаниями, ответами)
- m2m_changed для Chat.participants - добавление пользователей в чат

ВАЖНО: Эти сигналы ОПЦИОНАЛЬНЫ и могут быть отключены через настройку:
    COMMUNICATIONS_AUTO_NOTIFY = False  # в settings.py

По умолчанию включены для обратной совместимости с EUSRR.
Для standalone использования рекомендуется вызывать handlers вручную
или отключить автоматические уведомления.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver

from ..models import Message, Chat
from .handlers import notify_new_message, notify_chat_added

User = get_user_model()

# Проверяем, включены ли автоматические уведомления
_AUTO_NOTIFY_ENABLED = getattr(settings, 'COMMUNICATIONS_AUTO_NOTIFY', True)


@receiver(post_save, sender=Message)
def create_message_notifications(sender, instance, created, **kwargs):
    """
    Создает уведомления при создании нового сообщения.
    
    Обрабатывает:
    1. Новое сообщение в чате (для всех участников кроме автора)
    2. Упоминания (@username) в тексте
    3. Ответ на сообщение (reply_to)
    
    ОПТИМИЗАЦИЯ: Уведомления отправляются через универсальную систему
    channels.py → Celery → WebSocket/Email/Push
    
    NOTE: Можно отключить через COMMUNICATIONS_AUTO_NOTIFY = False
    """
    if not _AUTO_NOTIFY_ENABLED:
        return
    
    if not created or instance.is_system or instance.is_deleted:
        return
    
    # Отправляем через универсальную систему
    notify_new_message(instance)


@receiver(m2m_changed, sender=Chat.participants.through)
def create_chat_added_notifications(sender, instance, action, pk_set, **kwargs):
    """
    Создает уведомления когда пользователя добавляют в чат.
    
    Args:
        instance: Chat объект
        action: Тип изменения ('post_add', 'post_remove', etc.)
        pk_set: Набор ID добавленных/удаленных пользователей
    
    NOTE: Можно отключить через COMMUNICATIONS_AUTO_NOTIFY = False
    """
    if not _AUTO_NOTIFY_ENABLED:
        return
    
    if action != 'post_add':
        return
    
    chat = instance
    
    # Получаем информацию о том, кто добавил (если доступно)
    # Это может быть последний изменивший или создатель чата
    added_by = getattr(chat, 'created_by', None) or chat.participants.first()
    
    # ОПТИМИЗАЦИЯ: Получаем всех новых пользователей одним запросом
    new_users = User.objects.filter(id__in=pk_set)
    
    # Отправляем уведомления через handlers
    notify_chat_added(chat, new_users, added_by=added_by)

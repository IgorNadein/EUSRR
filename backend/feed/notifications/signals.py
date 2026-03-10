"""
Django signals для автоматической генерации уведомлений в модуле Feed.

Обрабатывает события:
- post_save для Post - создание новой публикации
- post_save для Comment - добавление комментария
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from ..models import Post, Comment
from .handlers import notify_new_post, notify_comment


@receiver(post_save, sender=Post)
def create_post_notification(sender, instance, created, **kwargs):
    """
    Создает уведомления при создании новой публикации.
    
    Уведомления отправляются в зависимости от типа:
    - TYPE_COMPANY - всем сотрудникам
    - TYPE_DEPARTMENT - сотрудникам отдела
    - TYPE_EMPLOYEE - подписчикам автора (если реализовано)
    """
    if not created:
        return
    
    # Отправляем уведомления через универсальную систему
    # channels.py автоматически обработает через Celery
    notify_new_post(instance)


@receiver(post_save, sender=Comment)
def create_comment_notification(sender, instance, created, **kwargs):
    """
    Создает уведомления при добавлении комментария к публикации.
    
    Уведомляет автора публикации о новом комментарии.
    """
    if not created:
        return
    
    notify_comment(instance)

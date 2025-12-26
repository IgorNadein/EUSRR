"""
Signals для автоматической генерации уведомлений в модуле Feed.

Обрабатывает события:
- Новая публикация (для подписчиков/отдела/компании)
- Комментарий к публикации
- Реакция (лайк) на публикацию - через отдельный механизм
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from .models import Post, Comment
from .constants import TYPE_COMPANY, TYPE_DEPARTMENT, TYPE_EMPLOYEE
from notifications.services import NotificationService

Employee = get_user_model()


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
    
    post = instance
    notify_new_post(post)


@receiver(post_save, sender=Comment)
def create_comment_notification(sender, instance, created, **kwargs):
    """
    Создает уведомления при добавлении комментария к публикации.
    """
    if not created:
        return
    
    comment = instance
    post = comment.post
    comment_author = comment.author
    
    # Уведомляем автора публикации (если комментарий не от него)
    if post.author.id != comment_author.id:
        NotificationService.create_notification(
            recipient=post.author,
            notification_type_code='feed_post_comment',
            title='Новый комментарий к вашей публикации',
            message=(
                f'{comment_author.get_full_name() or comment_author.username}'
                f' прокомментировал: {truncate_text(comment.text, 80)}'
            ),
            content_object=post,
            action_url=f'/post/{post.id}/',
            metadata={
                'post_id': post.id,
                'post_title': post.title,
                'comment_id': comment.id,
                'author_id': comment_author.id,
            }
        )


# ===== Вспомогательные функции =====

def notify_new_post(post):
    """
    Отправляет уведомления о новой публикации.
    """
    recipients = get_post_recipients(post)
    
    # Исключаем автора
    recipients = [r for r in recipients if r.id != post.author.id]
    
    # Определяем контекст публикации
    if post.type == TYPE_COMPANY:
        context = 'компании'
    elif post.type == TYPE_DEPARTMENT and post.department:
        context = f'отдела {post.department.name}'
    else:
        context = (
            f'от {post.author.get_full_name() or post.author.username}'
        )
    
    for recipient in recipients:
        NotificationService.create_notification(
            recipient=recipient,
            notification_type_code='feed_new_post',
            title=f'Новая публикация {context}',
            message=f'{post.title}',
            content_object=post,
            action_url=f'/post/{post.id}/',
            metadata={
                'post_id': post.id,
                'post_type': post.type,
                'post_title': post.title,
                'author_id': post.author.id,
                'department_id': (
                    post.department.id if post.department else None
                ),
            }
        )


def get_post_recipients(post):
    """
    Возвращает список получателей уведомлений для публикации.
    
    - TYPE_COMPANY - все активные сотрудники
    - TYPE_DEPARTMENT - сотрудники отдела
    - TYPE_EMPLOYEE - подписчики (если реализовано)
    """
    if post.type == TYPE_COMPANY:
        # Новость компании - всем
        return list(Employee.objects.filter(is_active=True))
    
    elif post.type == TYPE_DEPARTMENT and post.department:
        # Новость отдела - сотрудникам отдела
        return list(post.department.employees.filter(is_active=True))
    
    elif post.type == TYPE_EMPLOYEE:
        # Личная публикация - подписчикам
        # TODO: реализовать систему подписок
        # Пока отправляем всем активным или никому
        return []
    
    return []


def truncate_text(text, max_length=100):
    """
    Обрезает текст до указанной длины.
    """
    if not text:
        return ''
    
    text = text.strip()
    if len(text) <= max_length:
        return text
    
    return text[:max_length - 3] + '...'


# ===== Функция для уведомлений о лайках =====
# Используется во views при добавлении лайка

def notify_post_reaction(post, user):
    """
    Создает уведомление о реакции (лайке) на публикацию.
    
    Вызывается вручную из view, так как лайки не имеют отдельной модели.
    
    Args:
        post: Публикация, которую лайкнули
        user: Пользователь, который поставил лайк
    """
    # Уведомляем автора (если лайк не от него)
    if post.author.id != user.id:
        NotificationService.create_notification(
            recipient=post.author,
            notification_type_code='feed_post_reaction',
            title='Ваша публикация понравилась',
            message=(
                f'{user.get_full_name() or user.username} '
                f'понравилась публикация "{post.title}"'
            ),
            content_object=post,
            action_url=f'/post/{post.id}/',
            metadata={
                'post_id': post.id,
                'post_title': post.title,
                'user_id': user.id,
                'reaction_type': 'like',
            }
        )

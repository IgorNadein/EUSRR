"""
Бизнес-логика отправки уведомлений для модуля Feed.

Функции:
- notify_new_post - уведомление о новой публикации
- notify_post_reaction - уведомление о реакции (лайке)
- get_post_recipients - определение получателей уведомлений
"""

from django.contrib.auth import get_user_model
from notifications.signals import notify

from ..constants import TYPE_COMPANY, TYPE_DEPARTMENT, TYPE_EMPLOYEE
from .config import (
    NotificationVerbs,
    MessageTemplates,
    ActionURLs,
)

Employee = get_user_model()


def notify_new_post(post):
    """
    Отправляет уведомления о новой публикации.

    Args:
        post: Экземпляр модели Post
    """
    recipients = get_post_recipients(post)

    # Исключаем автора
    recipients = [r for r in recipients if r.id != post.author.id]

    # Определяем заголовок в зависимости от типа публикации
    if post.type == TYPE_COMPANY:
        title = MessageTemplates.new_post_company()
    elif post.type == TYPE_DEPARTMENT and post.department:
        title = MessageTemplates.new_post_department(post.department.name)
    else:
        author_name = post.author.get_full_name() or post.author.username
        title = MessageTemplates.new_post_employee(author_name)

    # Отправляем уведомление каждому получателю
    for recipient in recipients:
        notify.send(
            sender=post.author,
            recipient=recipient,
            verb=NotificationVerbs.NEW_POST,
            action_object=post,
            description=post.title,
            action_url=ActionURLs.FEED_HOME,
            data={
                'title': title,
                'post_id': post.id,
                'post_type': post.type,
                'post_title': post.title,
                'author_id': post.author.id,
                'department_id': (
                    post.department.id if post.department else None
                ),
            }
        )


def notify_post_reaction(post, user):
    """
    Создает уведомление о реакции (лайке) на публикацию.

    Вызывается вручную из view, так как лайки не имеют отдельной модели.

    Args:
        post: Публикация, которую лайкнули
        user: Пользователь, который поставил лайк
    """
    # Уведомляем автора (если лайк не от него)
    if post.author.id == user.id:
        return

    user_name = user.get_full_name() or user.username

    notify.send(
        sender=user,
        recipient=post.author,
        verb=NotificationVerbs.POST_REACTION,
        action_object=post,
        description=MessageTemplates.reaction(user_name, post.title),
        action_url=ActionURLs.FEED_HOME,
        data={
            'title': MessageTemplates.reaction_title(),
            'post_id': post.id,
            'post_title': post.title,
            'user_id': user.id,
            'reaction_type': 'like',
        }
    )


def get_post_recipients(post):
    """
    Возвращает список получателей уведомлений для публикации.

    Args:
        post: Экземпляр модели Post

    Returns:
        Список пользователей (Employee), которые должны получить уведомление:
        - TYPE_COMPANY - все активные сотрудники
        - TYPE_DEPARTMENT - сотрудники отдела
        - TYPE_EMPLOYEE - подписчики (пока не реализовано)
    """
    if post.type == TYPE_COMPANY:
        # Новость компании - всем активным сотрудникам
        return list(Employee.objects.filter(is_active=True))

    elif post.type == TYPE_DEPARTMENT and post.department:
        # Новость отдела - сотрудникам отдела
        return list(post.department.employees.filter(is_active=True))

    elif post.type == TYPE_EMPLOYEE:
        # Личная публикация - подписчикам
        # TODO: реализовать систему подписок
        # Пока возвращаем пустой список
        return []

    return []

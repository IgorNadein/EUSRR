"""
Бизнес-логика отправки уведомлений для модуля Communications.

Функции:
- get_users_with_notifications_enabled - проверка настроек уведомлений
- notify_new_message - уведомление о новом сообщении (с упоминаниями и ответами)
- notify_chat_added - уведомление о добавлении в чат

ПРИМЕЧАНИЕ: Опциональная зависимость от notifications модуля.
Если notifications не установлен - уведомления просто не отправляются.
"""

from django.contrib.auth import get_user_model

# Опциональная зависимость от notifications (graceful degradation)
try:
    from notifications.signals import notify
    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    NOTIFICATIONS_AVAILABLE = False
    notify = None

from ..models import ChatUserSettings
from .config import (
    NotificationVerbs,
    MessageTemplates,
    ActionURLs,
    extract_mentions,
    truncate_message,
    get_chat_name,
)

User = get_user_model()


def _send_notification(**kwargs):
    """
    Обертка для отправки уведомлений.
    Если notifications модуль не доступен - ничего не делает.
    """
    if NOTIFICATIONS_AVAILABLE and notify:
        notify.send(**kwargs)
    # Иначе тихо игнорируем - модуль работает без уведомлений


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

    Специальная обработка для чатов комментариев (type='comments'):
    - Уведомляет автора объекта (поста/документа/заявки)
    - Уведомляет других участников дискуссии

    Args:
        message: Экземпляр модели Message
    """
    chat = message.chat
    author = message.author
    content = message.content

    # Специальная обработка для чатов комментариев
    if chat.type == 'comments':
        _notify_comment(message)
        return

    # Получаем всех участников чата кроме автора
    if chat.type in ['announcement', 'channel', 'global']:
        participants = chat.get_participants().exclude(id=author.id)
    else:
        participants = chat.participants.exclude(id=author.id)

    # ОПТИМИЗАЦИЯ: Загружаем настройки уведомлений ОДНИМ запросом
    participants_list = list(participants)
    if not participants_list:
        return  # Нет получателей

    notification_settings = get_users_with_notifications_enabled(
        chat, participants_list)

    # Отслеживаем, кому уже отправили уведомления
    notified_user_ids = set()

    # 1. УПОМИНАНИЯ (@username)
    mentioned_users = extract_mentions(content)
    author_name = author.get_full_name() or author.username

    if mentioned_users:
        for email in mentioned_users:
            try:
                user = User.objects.get(email=email)
                if user in participants_list and user.id != author.id:
                    if notification_settings.get(user.id, True):
                        _send_notification(
                            sender=author,
                            recipient=user,
                            verb=NotificationVerbs.MENTION,
                            action_object=message,
                            description=truncate_message(content, 100),
                            action_url=ActionURLs.chat_detail(chat.id),
                            data={
                                'title': MessageTemplates.mention(author_name),
                                'chat_id': chat.id,
                                'chat_name': get_chat_name(chat),
                                'message_id': message.id,
                                'author_id': author.id,
                            }
                        )
                    notified_user_ids.add(user.id)
            except User.DoesNotExist:
                continue

    # 2. ОТВЕТЫ НА СООБЩЕНИЯ
    if message.reply_to and message.reply_to.author_id != author.id:
        original_author = message.reply_to.author

        if original_author.id not in notified_user_ids:
            if notification_settings.get(original_author.id, True):
                _send_notification(
                    sender=author,
                    recipient=original_author,
                    verb=NotificationVerbs.REPLY,
                    action_object=message,
                    description=truncate_message(content, 100),
                    action_url=ActionURLs.chat_detail(chat.id),
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
            title = MessageTemplates.group_message(
                author_name, get_chat_name(chat))
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

        _send_notification(
            sender=author,
            recipient=recipient,
            verb=notification_verb,
            action_object=message,
            description=truncate_message(content, max_length),
            action_url=ActionURLs.chat_detail(chat.id),
            data={**metadata, 'title': title},
        )


def _notify_comment(message):
    """
    Отправляет уведомления о новом комментарии к объекту.

    Уведомляет:
    1. Автора объекта (Post/Document/Request)
    2. Для Department: сотрудников отдела и role-only участников отдела
    3. Автора parent comment, если это reply

    Args:
        message: Экземпляр модели Message (в чате type='comments')
    """
    chat = message.chat
    author = message.author
    content = message.content

    if not chat.context_object:
        # Нет привязанного объекта - обычная обработка
        return

    recipient_ids = set()
    context_obj = chat.context_object

    # Определяем автора объекта в зависимости от типа
    object_author = None
    object_url = None
    object_type = "объекта"

    # Проверяем тип объекта через модель
    model_name = context_obj.__class__.__name__

    if model_name == 'Post':
        object_author = getattr(context_obj, 'author', None)
        object_url = f"/?post={context_obj.id}"
        object_type = "публикации"
    elif model_name == 'Document':
        object_author = getattr(context_obj, 'uploaded_by', None)
        object_url = f"/documents?document={context_obj.id}"
        object_type = "документа"
    elif model_name == 'Department':
        from employees.models import EmployeeDepartment, RoleAssignment

        object_url = ActionURLs.chat_detail(chat.id)
        object_type = "отдела"

        member_ids = EmployeeDepartment.objects.filter(
            department_id=context_obj.id,
            is_active=True,
        ).values_list("employee_id", flat=True)
        recipient_ids.update(member_ids)

        role_only_ids = RoleAssignment.objects.filter(
            role__department_id=context_obj.id,
            is_active=True,
        ).values_list("employee_id", flat=True)
        recipient_ids.update(role_only_ids)
    elif hasattr(context_obj, 'employee'):  # Request
        object_author = getattr(context_obj, 'employee', None)
        object_url = f"/requests?request={context_obj.id}"
        object_type = "заявки"
        recipient_ids.update(
            context_obj.recipients.filter(is_active=True).values_list(
                "id", flat=True
            )
        )
        recipient_ids.update(
            context_obj.cc_users.filter(is_active=True).values_list(
                "id", flat=True
            )
        )
        if getattr(context_obj, "approver_id", None):
            recipient_ids.add(context_obj.approver_id)
        if getattr(context_obj, "sent_to_all_department", False):
            from employees.models import EmployeeDepartment

            dept_employee_ids = EmployeeDepartment.objects.filter(
                department__in=context_obj.departments.all(),
                is_active=True,
                employee__is_active=True,
            ).values_list("employee_id", flat=True)
            recipient_ids.update(dept_employee_ids)

    # 1. Уведомляем автора объекта
    if object_author and object_author.id != author.id:
        recipient_ids.add(object_author.id)

    # 2. Reply notification for comments is opt-in by explicit reply target.
    if message.reply_to and message.reply_to.author_id != author.id:
        recipient_ids.add(message.reply_to.author_id)

    recipient_ids.discard(author.id)
    if not recipient_ids:
        return

    recipients = User.objects.filter(id__in=recipient_ids, is_active=True)

    # Отправляем уведомления
    author_name = author.get_full_name() or author.username

    for recipient in recipients:
        _send_notification(
            sender=author,
            recipient=recipient,
            verb='commented',
            action_object=message,
            target=context_obj,
            description=truncate_message(content, 100),
            action_url=object_url or f"/chat/{chat.id}/",
            data={
                'title': f'{author_name} оставил комментарий к {object_type}',
                'chat_id': chat.id,
                'message_id': message.id,
                'author_id': author.id,
                'object_type': model_name,
                'object_id': context_obj.id,
            }
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
    notification_settings = get_users_with_notifications_enabled(
        chat, new_users)

    # Создаем уведомления для новых участников
    for user in new_users:
        # Не отправляем уведомление тому, кто сам себя добавил
        if added_by and user.id == added_by.id:
            continue

        # Проверяем настройки уведомлений
        if not notification_settings.get(user.id, True):
            continue

        _send_notification(
            sender=added_by,
            recipient=user,
            verb=NotificationVerbs.ADDED_TO_CHAT,
            action_object=chat,
            description=MessageTemplates.added_to_chat(get_chat_name(chat)),
            action_url=ActionURLs.chat_detail(chat.id),
            data={
                'title': MessageTemplates.added_to_chat_title(),
                'chat_id': chat.id,
                'chat_name': get_chat_name(chat),
                'added_by_id': added_by.id if added_by else None,
            }
        )

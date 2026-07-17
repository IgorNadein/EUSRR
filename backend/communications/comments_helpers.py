"""
Helpers для работы с комментариями через Communications.

Этот модуль предоставляет unified API для создания и получения комментариев
к любым объектам через систему чатов Communications (type='comments').

Использование:
    from communications.comments_helpers import (
        get_or_create_comments_chat,
        create_comment,
        get_comments
    )

    # Для любого объекта (Document, Post, Request, etc.)
    chat = get_or_create_comments_chat(document)
    comment = create_comment(document, author=user, content="Отлично!")
    comments = get_comments(document)

История:
    - Создан: 11 марта 2026
    - Цель: Унификация системы комментариев для миграции с legacy моделей
"""

from typing import Optional
from django.contrib.contenttypes.models import ContentType
from django.db.models import QuerySet

from .models import Chat, Message, MessageAttachment, MessageEditHistory


def get_or_create_comments_chat(
    obj, created_by=None, name: Optional[str] = None, **extra_flags
) -> Chat:
    """
    Получить или создать чат комментариев для объекта.

    Использует GenericForeignKey для привязки к ЛЮБОЙ модели.

    Args:
        obj: Любой Django model instance (Post, Document, Request, etc.)
        created_by: User - создатель чата (опционально)
        name: str - название чата (по умолчанию: "Комментарии: {obj}")
        **extra_flags: Дополнительные флаги для chat.flags

    Returns:
        Chat instance с type='comments'

    Examples:
        >>> from documents.models import Document
        >>> doc = Document.objects.get(id=123)
        >>> chat = get_or_create_comments_chat(doc)
        >>> print(chat.type)
        'comments'
        >>> print(chat.context_object)
        <Document: My Document>
    """
    ct = ContentType.objects.get_for_model(obj)

    # Базовые флаги для чата комментариев
    default_flags = {
        "allow_replies": True,
        "allow_reactions": True,
        "allow_attachments": True,
        "allow_editing": True,
    }
    default_flags.update(extra_flags)

    # Генерация имени если не указано
    if name is None:
        obj_str = str(obj)
        name = f"Комментарии: {obj_str[:50]}"
        if len(obj_str) > 50:
            name += "..."

    chat, created = Chat.objects.get_or_create(
        type="comments",
        context_content_type=ct,
        context_object_id=obj.id,
        defaults={
            "name": name,
            "created_by": created_by,
            "flags": default_flags,
            "can_reply": True,  # Разрешаем ответы
        },
    )

    return chat


def create_comment(
    obj,
    author,
    content: str,
    reply_to: Optional[Message] = None,
    attachments: Optional[list] = None,
    **system_metadata,
) -> Message:
    """
    Создать комментарий к объекту.

    Автоматически создает чат комментариев если его нет.

    Args:
        obj: Объект для комментирования
        author: User - автор комментария
        content: str - текст комментария
        reply_to: Message - родительский комментарий для threading (опционально)
        attachments: list - список файлов для вложений (опционально)
        **system_metadata: Дополнительные данные для message.system_metadata

    Returns:
        Message instance

    Examples:
        >>> comment = create_comment(
        ...     obj=document,
        ...     author=request.user,
        ...     content="Отличный документ!"
        ... )

        >>> # С ответом на другой комментарий
        >>> reply = create_comment(
        ...     obj=document,
        ...     author=request.user,
        ...     content="Согласен!",
        ...     reply_to=parent_comment
        ... )

        >>> # С вложениями
        >>> comment = create_comment(
        ...     obj=document,
        ...     author=request.user,
        ...     content="См. файл",
        ...     attachments=[image_file, pdf_file]
        ... )
    """
    chat = get_or_create_comments_chat(obj, created_by=author)

    # Определяем thread_root для threading
    thread_root = None
    if reply_to:
        # Если это ответ на ответ - берем корень треда
        thread_root = reply_to.thread_root or reply_to

    # Создаем сообщение
    message = Message.objects.create(
        chat=chat,
        author=author,
        content=content,
        reply_to=reply_to,
        thread_root=thread_root,
        has_attachments=bool(attachments),
        system_metadata=system_metadata,
    )

    # Добавляем вложения
    if attachments:
        for file in attachments:
            # Определяем тип файла
            file_type = "file"
            if hasattr(file, "content_type"):
                if file.content_type.startswith("image/"):
                    file_type = "image"
                elif file.content_type.startswith("video/"):
                    file_type = "video"

            MessageAttachment.objects.create(
                message=message,
                file=file,
                file_type=file_type,
                file_name=getattr(file, "name", "file"),
                file_size=getattr(file, "size", 0),
            )

    return message


def get_comments(
    obj, include_deleted: bool = False, only_roots: bool = False
) -> QuerySet:
    """
    Получить все комментарии объекта.

    Args:
        obj: Объект для получения комментариев
        include_deleted: bool - включать удаленные комментарии
        only_roots: bool - только корневые комментарии (без ответов)

    Returns:
        QuerySet[Message] отсортированный по created_at

    Examples:
        >>> # Все комментарии
        >>> comments = get_comments(document)

        >>> # Только корневые (без ответов)
        >>> root_comments = get_comments(document, only_roots=True)

        >>> # Включая удаленные
        >>> all_comments = get_comments(document, include_deleted=True)
    """
    try:
        ct = ContentType.objects.get_for_model(obj)
        chat = Chat.objects.get(
            type="comments", context_content_type=ct, context_object_id=obj.id
        )

        qs = chat.messages.select_related("author")

        if not include_deleted:
            qs = qs.filter(is_deleted=False)

        if only_roots:
            qs = qs.filter(reply_to__isnull=True)

        return qs.order_by("created_at")

    except Chat.DoesNotExist:
        # Чат не создан - нет комментариев
        return Message.objects.none()


def get_comment_count(obj, include_deleted: bool = False) -> int:
    """
    Получить количество комментариев для объекта.

    Args:
        obj: Объект для подсчета комментариев
        include_deleted: bool - включать удаленные

    Returns:
        int - количество комментариев
    """
    return get_comments(obj, include_deleted=include_deleted).count()


def delete_comment(message: Message, deleted_by, soft_delete: bool = True):
    """
    Удалить комментарий (мягкое или жесткое удаление).

    Args:
        message: Message - комментарий для удаления
        deleted_by: User - кто удаляет
        soft_delete: bool - использовать мягкое удаление (recommended)

    Examples:
        >>> delete_comment(comment, user=request.user)  # Мягкое удаление
        >>> delete_comment(
        ...     comment, user=request.user, soft_delete=False
        ... )  # Жесткое
    """
    if soft_delete:
        from django.utils import timezone

        message.is_deleted = True
        message.deleted_by = deleted_by
        message.deleted_at = timezone.now()
        message.save(update_fields=["is_deleted", "deleted_by", "deleted_at"])
    else:
        message.delete()


def update_comment(
    message: Message,
    new_content: str,
    mark_edited: bool = True,
    edited_by=None,
):
    """
    Обновить текст комментария.

    Args:
        message: Message - комментарий для обновления
        new_content: str - новый текст
        mark_edited: bool - пометить как отредактированный
        edited_by: User - автор изменения для истории редактирования

    Examples:
        >>> update_comment(comment, "Новый текст")
    """
    from django.utils import timezone

    if message.content == new_content:
        return message

    if mark_edited:
        MessageEditHistory.objects.create(
            message=message,
            previous_content=message.content,
            edited_by=edited_by,
        )

    message.content = new_content

    if mark_edited:
        message.is_edited = True
        message.edited_at = timezone.now()
        message.save(update_fields=["content", "is_edited", "edited_at"])
    else:
        message.save(update_fields=["content"])

    return message


def get_comments_chat_if_exists(obj) -> Optional[Chat]:
    """
    Получить чат комментариев если он существует (без создания).

    Args:
        obj: Объект

    Returns:
        Chat or None
    """
    try:
        ct = ContentType.objects.get_for_model(obj)
        return Chat.objects.get(
            type="comments", context_content_type=ct, context_object_id=obj.id
        )
    except Chat.DoesNotExist:
        return None

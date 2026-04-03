# communications/serialization.py
"""
Утилиты сериализации для модуля communications.
Вынесены из consumers.py для переиспользования в API, WebSocket и других
местах.
"""

from django.conf import settings


def _get_author_url(author) -> str:
    """
    Получает URL профиля автора используя настройку из settings.

    Settings:
        COMMUNICATIONS_AUTHOR_URL_PATTERN (str): Шаблон URL для профиля автора.
            По умолчанию: '/api/v1/employees/{id}/' (проектно-специфичный)
            Для standalone: '/users/{id}/' или None (пустая строка)
            Должен содержать placeholder {id} для подстановки ID пользователя

    Args:
        author: Объект пользователя (User model)

    Returns:
        str: URL профиля автора или пустая строка

    Examples:
        >>> # settings.py
        >>> COMMUNICATIONS_AUTHOR_URL_PATTERN = '/users/{id}/'
        >>> _get_author_url(user)
        '/users/123/'
    """
    if not author:
        return ""

    url_pattern = getattr(
        settings,
        "COMMUNICATIONS_AUTHOR_URL_PATTERN",
        "/api/v1/employees/{id}/",  # backward compatibility
    )

    if url_pattern is None:
        return ""

    try:
        return url_pattern.format(id=author.id)
    except (KeyError, ValueError, AttributeError):
        return ""


def _is_message_read(m) -> bool:
    """True, если сообщение прочитал хотя бы один другой участник."""
    chat = getattr(m, "chat", None)
    if (
        not chat
        or not getattr(m, "id", None)
        or not getattr(m, "author_id", None)
    ):
        return False

    prefetched = getattr(chat, "_prefetched_objects_cache", {})
    read_states = prefetched.get("read_states")
    if read_states is not None:
        return any(
            state.user_id != m.author_id
            and state.last_read_message_id
            and state.last_read_message_id >= m.id
            for state in read_states
        )

    return chat.read_states.exclude(user_id=m.author_id).filter(
        last_read_message_id__gte=m.id
    ).exists()


def _get_user_avatar_url(user) -> str:
    if not user:
        return ""

    try:
        if getattr(user, "avatar", None) and user.avatar:
            return user.avatar.url
    except Exception:
        return ""

    return ""


def _serialize_reply_preview(reply_msg) -> dict:
    is_deleted = bool(getattr(reply_msg, "is_deleted", False))

    return {
        "id": reply_msg.id,
        "content": reply_msg.content[:100] if reply_msg.content else "",
        "author_name": (
            reply_msg.author.get_full_name()
            if reply_msg.author
            else "Неизвестный"
        ),
        "is_deleted": is_deleted,
        "has_attachments": bool(getattr(reply_msg, "has_attachments", False)),
    }


def _get_message_read_by(m) -> list[dict]:
    """Список участников, которые дочитали сообщение."""
    chat = getattr(m, "chat", None)
    if (
        not chat
        or not getattr(m, "id", None)
        or not getattr(m, "author_id", None)
    ):
        return []

    prefetched = getattr(chat, "_prefetched_objects_cache", {})
    read_states = prefetched.get("read_states")
    if read_states is None:
        read_states = chat.read_states.select_related("user").filter(
            last_read_message_id__gte=m.id
        )

    readers = []
    for state in read_states:
        if state.user_id == m.author_id:
            continue
        if not state.last_read_message_id or state.last_read_message_id < m.id:
            continue

        user = getattr(state, "user", None)
        if not user:
            continue

        readers.append(
            {
                "id": user.id,
                "name": user.get_full_name() or user.username,
                "avatar": _get_user_avatar_url(user),
            }
        )

    readers.sort(key=lambda item: item["name"].lower())
    return readers


def serialize_message(m) -> dict:
    """
    Сериализация сообщения с поддержкой всех полей.

    Поддерживаемые фичи:
    - Базовые поля (контент, автор, дата)
    - Редактирование и удаление
    - Пересылка сообщений (forward)
    - Реакции
    - Вложения (attachments)
    - Голосования (polls)
    - Ответы на сообщения (reply_to)
    """
    author = m.author
    author_name = author.get_full_name() or author.username
    avatar = _get_user_avatar_url(author)

    # Базовые поля
    data = {
        "id": m.id,
        "content": m.content,
        "author_id": author.id if author else None,
        "author_name": author_name,
        "author_url": _get_author_url(author),
        "avatar": avatar,
        "created": m.created_at.strftime("%d.%m.%Y %H:%M"),
        "created_ts": int(m.created_at.timestamp() * 1000),
        # Статусные поля
        "is_edited": m.is_edited,
        "edited_at": m.edited_at.isoformat() if m.edited_at else None,
        "is_read": _is_message_read(m),
        "read_by": _get_message_read_by(m),
        "is_deleted": m.is_deleted,
        "is_pinned": m.is_pinned,
        "is_forwarded": m.is_forwarded,
        "is_system": m.is_system,
        "has_attachments": m.has_attachments,
    }
    data["read_count"] = len(data["read_by"])

    # Информация о пересылке (используем forward_metadata)
    if m.is_forwarded:
        try:
            metadata = m.forward_metadata
            forwarded_data = {
                "author_id": metadata.original_author.id
                if metadata.original_author
                else None,
                "author_name": (
                    metadata.original_author.get_full_name()
                    if metadata.original_author
                    else metadata.original_author.username
                    if metadata.original_author
                    else "Неизвестно"
                ),
                "message_id": metadata.original_message_id
                if metadata.original_message
                else None,
            }

            # Добавляем дату оригинального сообщения
            if metadata.original_created_at:
                forwarded_data["created_at"] = (
                    metadata.original_created_at.strftime("%d.%m.%Y %H:%M")
                )
                forwarded_data["created_ts"] = int(
                    metadata.original_created_at.timestamp() * 1000
                )

            # Добавляем название исходного чата
            if metadata.original_chat_name:
                forwarded_data["chat_name"] = metadata.original_chat_name

            data["forwarded_from"] = forwarded_data
        except Exception:
            # Если метаданных нет, просто не добавляем информацию о пересылке
            pass

    # Реакции - сериализуем из связанной модели MessageReaction
    reactions_summary = {}
    for reaction in m.reactions.select_related("user"):
        emoji = reaction.emoji
        if emoji not in reactions_summary:
            reactions_summary[emoji] = {
                "count": 0,
                "users": [],
                "user_names": [],
            }
        reactions_summary[emoji]["count"] += 1
        reactions_summary[emoji]["users"].append(reaction.user_id)
        reactions_summary[emoji]["user_names"].append(
            reaction.user.get_full_name() or reaction.user.username
        )
    data["reactions_summary"] = reactions_summary

    # Вложения - всегда включаем поле attachments
    attachments = []
    if m.has_attachments:
        for att in m.attachments.all():
            attachments.append(
                {
                    "id": att.id,
                    "file_name": att.file_name,
                    "file_type": att.file_type,
                    "file_url": att.file.url,
                    "file_size": att.file_size,
                    "mime_type": att.mime_type,
                    "width": att.width,  # Размеры для CSS aspect-ratio
                    "height": att.height,
                    "thumbnail": (
                        att.thumbnail.url
                        if getattr(att, "thumbnail", None)
                        else None
                    ),
                }
            )
    data["attachments"] = attachments

    # Голосование
    if hasattr(m, "poll"):
        poll = m.poll
        poll_data = {
            "id": poll.id,
            "question": poll.question,
            "is_anonymous": poll.is_anonymous,
            "is_multiple_choice": poll.is_multiple_choice,
            "is_quiz": poll.is_quiz,
            "is_closed": poll.is_closed,
            "closes_at": poll.closes_at.isoformat() if poll.closes_at else None,
            "total_voters": poll.total_voters,
            "options": [],
        }
        for option in poll.options.all():
            poll_data["options"].append(
                {
                    "id": option.id,
                    "text": option.text,
                    "position": option.position,
                    "vote_count": option.vote_count,
                    "percentage": 0,  # Будет пересчитан на клиенте
                }
            )
        data["poll"] = poll_data

    # Ответ на сообщение
    if m.reply_to_id:
        try:
            reply_msg = m.reply_to if hasattr(m, "reply_to") else None
            if not reply_msg:
                from communications.models import Message as Msg

                reply_msg = Msg.objects.select_related("author").get(
                    pk=m.reply_to_id
                )

            data["reply_to"] = _serialize_reply_preview(reply_msg)
        except Exception:
            # Если не удалось загрузить reply_to, просто пропускаем
            pass

    # Информация о пересылке (legacy)
    if m.is_forwarded and hasattr(m, "forward_info"):
        fw = m.forward_info
        data["forward_info"] = {
            "original_author": fw.preserved_author_name,
            "forward_count": fw.forward_count,
        }

    return data

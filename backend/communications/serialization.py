# communications/serialization.py
"""
Утилиты сериализации для модуля communications.
Вынесены из consumers.py для переиспользования в API, WebSocket и других местах.
"""
from django.urls import reverse


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
    avatar = ""
    try:
        if getattr(author, "avatar", None) and author.avatar:
            avatar = author.avatar.url
    except Exception:
        avatar = ""

    # Базовые поля
    data = {
        "id": m.id,
        "content": m.content,
        "author_id": author.id if author else None,
        "author_name": author_name,
        "author_url": reverse("employees:employee_detail", args=[author.id]) if author else "",
        "avatar": avatar,
        "created": m.created_at.strftime("%d.%m.%Y %H:%M"),
        "created_ts": int(m.created_at.timestamp() * 1000),
        
        # Статусные поля
        "is_edited": m.is_edited,
        "edited_at": m.edited_at.isoformat() if m.edited_at else None,
        "is_deleted": m.is_deleted,
        "is_pinned": m.is_pinned,
        "is_forwarded": m.is_forwarded,
        "is_system": m.is_system,
        "has_attachments": m.has_attachments,
    }
    
    # Информация о пересылке (используем forward_metadata)
    if m.is_forwarded:
        try:
            metadata = m.forward_metadata
            forwarded_data = {
                "author_id": metadata.original_author.id if metadata.original_author else None,
                "author_name": (
                    metadata.original_author.get_full_name() if metadata.original_author
                    else metadata.original_author.username if metadata.original_author
                    else "Неизвестно"
                ),
                "message_id": metadata.original_message_id if metadata.original_message else None,
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
    for reaction in m.reactions.select_related('user'):
        emoji = reaction.emoji
        if emoji not in reactions_summary:
            reactions_summary[emoji] = {
                'count': 0,
                'users': [],
                'user_names': []
            }
        reactions_summary[emoji]['count'] += 1
        reactions_summary[emoji]['users'].append(reaction.user_id)
        reactions_summary[emoji]['user_names'].append(
            reaction.user.get_full_name() or reaction.user.username
        )
    data["reactions_summary"] = reactions_summary
    
    # Вложения - всегда включаем поле attachments
    attachments = []
    if m.has_attachments:
        for att in m.attachments.all():
            attachments.append({
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
            })
    data["attachments"] = attachments
    
    # Голосование
    if hasattr(m, 'poll'):
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
            "options": []
        }
        for option in poll.options.all():
            poll_data["options"].append({
                "id": option.id,
                "text": option.text,
                "position": option.position,
                "vote_count": option.vote_count,
                "percentage": 0  # Будет пересчитан на клиенте
            })
        data["poll"] = poll_data
    
    # Ответ на сообщение
    if m.reply_to_id:
        try:
            reply_msg = m.reply_to if hasattr(m, 'reply_to') else None
            if not reply_msg:
                from communications.models import Message as Msg
                reply_msg = Msg.objects.select_related('author').get(
                    pk=m.reply_to_id
                )

            data["reply_to"] = {
                "id": reply_msg.id,
                "content": (
                    reply_msg.content[:100] if reply_msg.content else ""
                ),
                "author_name": (
                    reply_msg.author.get_full_name()
                    if reply_msg.author
                    else "Неизвестный"
                )
            }
        except Exception as e:
            # Если не удалось загрузить reply_to, просто пропускаем
            pass
    
    # Информация о пересылке (legacy)
    if m.is_forwarded and hasattr(m, 'forward_info'):
        fw = m.forward_info
        data["forward_info"] = {
            "original_author": fw.preserved_author_name,
            "forward_count": fw.forward_count,
        }
    
    return data

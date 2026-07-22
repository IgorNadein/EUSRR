"""
Конфигурация уведомлений для модуля Documents.

Содержит:
- NotificationVerbs - глаголы для уведомлений
- MessageTemplates - шаблоны сообщений
- ActionURLs - URL-адреса действий
"""

from django.conf import settings


class NotificationVerbs:
    """Глаголы (verbs) для уведомлений documents."""

    DOCUMENT_READY = 'document_ready'
    DOCUMENT_SIGNED_ALL = 'document_signed_all'
    DOCUMENT_COMMENT = 'document_comment'
    DOCUMENT_COMMENT_REPLY = 'document_comment_reply'
    REGULATION_READY = 'regulation_ready'
    REGULATION_SIGNED_ALL = 'regulation_signed_all'
    REGULATION_COMMENT = 'regulation_comment'
    REGULATION_COMMENT_REPLY = 'regulation_comment_reply'

    @classmethod
    def ready(cls, is_regulation: bool) -> str:
        return cls.REGULATION_READY if is_regulation else cls.DOCUMENT_READY

    @classmethod
    def signed_all(cls, is_regulation: bool) -> str:
        return (
            cls.REGULATION_SIGNED_ALL
            if is_regulation
            else cls.DOCUMENT_SIGNED_ALL
        )


class MessageTemplates:
    """Шаблоны сообщений для уведомлений documents."""

    @staticmethod
    def document_ready(
        uploader_name: str,
        document_title: str,
        acknowledgement_required: bool = True,
        is_regulation: bool = False,
    ) -> str:
        """Шаблон для нового документа."""
        resource = 'регламент' if is_regulation else 'документ'
        action = 'опубликовал' if is_regulation else 'загрузил'
        message = f'{uploader_name} {action} {resource} "{document_title}".'
        if acknowledgement_required:
            return f"{message} Требуется ознакомление."
        return message

    @staticmethod
    def document_ready_title(
        acknowledgement_required: bool = True,
        is_regulation: bool = False,
    ) -> str:
        """Заголовок для нового документа."""
        resource = 'регламент' if is_regulation else 'документ'
        if not acknowledgement_required:
            return f'Новый {resource}'
        return f'Новый {resource} на ознакомление'

    @staticmethod
    def all_acknowledged(
        document_title: str,
        is_regulation: bool = False,
    ) -> str:
        """Шаблон для завершения ознакомления всеми."""
        resource = 'регламентом' if is_regulation else 'документом'
        return f'Все сотрудники ознакомились с {resource} "{document_title}"'

    @staticmethod
    def all_acknowledged_title(is_regulation: bool = False) -> str:
        """Заголовок для завершения ознакомления."""
        resource = 'регламентом' if is_regulation else 'документом'
        return f'Все ознакомились с {resource}'

    @staticmethod
    def comment(author_name: str, document_title: str) -> str:
        """Шаблон для нового комментария к документу."""
        return (
            f'{author_name} оставил комментарий '
            f'к вашему документу "{document_title}"'
        )

    @staticmethod
    def comment_title() -> str:
        """Заголовок для комментария к документу."""
        return 'Новый комментарий к документу'

    @staticmethod
    def comment_reply(author_name: str, document_title: str) -> str:
        """Шаблон для ответа на комментарий."""
        return (
            f'{author_name} ответил на ваш '
            f'комментарий к документу "{document_title}"'
        )

    @staticmethod
    def comment_reply_title() -> str:
        """Заголовок для ответа на комментарий."""
        return 'Ответ на ваш комментарий'


class ActionURLs:
    """URL-адреса для действий с документами."""

    DOCUMENTS = '/documents'

    @staticmethod
    def document_detail(
        document_id: int,
        is_regulation: bool = False,
    ) -> str:
        """Возвращает прямую ссылку на документ или регламент."""
        section = 'regulations' if is_regulation else 'folders'
        return f'/documents?section={section}&document={document_id}'


# ===== Константы =====

def get_bulk_threshold() -> int:
    """
    Возвращает порог для определения массовой рассылки.

    Returns:
        int: Количество получателей, начиная с которого используется bulk режим
    """
    return getattr(settings, 'NOTIFICATION_BULK_THRESHOLD', 10)


def get_uploader_name(uploaded_by) -> str:
    """
    Возвращает имя загрузившего документ пользователя.

    Args:
        uploaded_by: Объект Employee или None

    Returns:
        str: Полное имя или 'Администратор'
    """
    if uploaded_by:
        return uploaded_by.get_full_name() or uploaded_by.username
    return 'Администратор'

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


class MessageTemplates:
    """Шаблоны сообщений для уведомлений documents."""
    
    @staticmethod
    def document_ready(uploader_name: str, document_title: str) -> str:
        """Шаблон для нового документа на ознакомление."""
        return (
            f'{uploader_name} загрузил документ "{document_title}". '
            f'Требуется ознакомление.'
        )
    
    @staticmethod
    def document_ready_title() -> str:
        """Заголовок для нового документа."""
        return 'Новый документ на ознакомление'
    
    @staticmethod
    def all_acknowledged(document_title: str) -> str:
        """Шаблон для завершения ознакомления всеми."""
        return f'Все сотрудники ознакомились с документом "{document_title}"'
    
    @staticmethod
    def all_acknowledged_title() -> str:
        """Заголовок для завершения ознакомления."""
        return 'Все ознакомились с документом'
    
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
    def document_detail(document_id: int) -> str:
        """
        Возвращает URL-адрес документа.
        
        TODO: реализовать прямые ссылки на конкретные документы
        """
        return f'/documents?id={document_id}'


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

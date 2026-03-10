"""
Конфигурация уведомлений для модуля Feed.

Содержит:
- NotificationVerbs - глаголы для уведомлений
- MessageTemplates - шаблоны сообщений
- ActionURLs - URL-адреса действий
"""


class NotificationVerbs:
    """Глаголы (verbs) для уведомлений feed."""
    
    NEW_POST = 'feed_new_post'
    POST_COMMENT = 'feed_post_comment'
    POST_REACTION = 'feed_post_reaction'


class MessageTemplates:
    """Шаблоны сообщений для уведомлений feed."""
    
    @staticmethod
    def new_post_company() -> str:
        """Шаблон для новости компании."""
        return 'Новая публикация компании'
    
    @staticmethod
    def new_post_department(department_name: str) -> str:
        """Шаблон для новости отдела."""
        return f'Новая публикация отдела {department_name}'
    
    @staticmethod
    def new_post_employee(author_name: str) -> str:
        """Шаблон для личной публикации."""
        return f'Новая публикация от {author_name}'
    
    @staticmethod
    def comment(author_name: str, comment_text: str) -> str:
        """Шаблон для комментария к публикации."""
        return f'{author_name} прокомментировал: {comment_text}'
    
    @staticmethod
    def comment_title() -> str:
        """Заголовок для уведомления о комментарии."""
        return 'Новый комментарий к вашей публикации'
    
    @staticmethod
    def reaction(user_name: str, post_title: str) -> str:
        """Шаблон для реакции на публикацию."""
        return f'{user_name} понравилась публикация "{post_title}"'
    
    @staticmethod
    def reaction_title() -> str:
        """Заголовок для уведомления о реакции."""
        return 'Ваша публикация понравилась'


class ActionURLs:
    """URL-адреса для действий с публикациями."""
    
    # Пока все действия ведут на главную страницу
    # TODO: реализовать прямые ссылки на публикации
    FEED_HOME = '/'
    
    @staticmethod
    def post_detail(post_id: int) -> str:
        """
        Возвращает URL-адрес публикации.
        
        TODO: реализовать отдельную страницу публикации
        """
        return f'/?post={post_id}'  # Временное решение


def truncate_text(text: str, max_length: int = 100) -> str:
    """
    Обрезает текст до указанной длины.
    
    Args:
        text: Исходный текст
        max_length: Максимальная длина (по умолчанию 100)
    
    Returns:
        Обрезанный текст с многоточием если нужно
    """
    if not text:
        return ''
    
    text = text.strip()
    if len(text) <= max_length:
        return text
    
    return text[:max_length - 3] + '...'

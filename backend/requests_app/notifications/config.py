"""
Конфигурация уведомлений модуля Requests.

Определяет типы уведомлений (verbs), шаблоны сообщений и URL.
"""


# ===== Типы уведомлений (Verbs) =====

class NotificationVerbs:
    """Типы уведомлений для заявлений."""

    # Новое заявление (универсальный для всех ролей получателей)
    REQUEST_NEW = 'request_new'

    # Комментарий к заявлению
    REQUEST_COMMENT = 'request_comment'

    # Изменение статуса
    REQUEST_APPROVED = 'request_approved'
    REQUEST_REJECTED = 'request_rejected'
    REQUEST_STATUS_CHANGED = 'request_status_changed'


# ===== Шаблоны сообщений =====

class MessageTemplates:
    """Шаблоны сообщений для уведомлений."""

    @staticmethod
    def new_request_primary(
        author_name: str, request_type: str, comment_preview: str
    ) -> tuple[str, str]:
        """
        Шаблон для основных получателей заявления.

        Returns:
            tuple: (title, message)
        """
        title = f"📩 Вам адресовано заявление от {author_name}"
        message = f'Тип: "{request_type}". {comment_preview}'
        return title, message

    @staticmethod
    def new_request_cc(
        author_name: str, request_type: str, comment_preview: str
    ) -> tuple[str, str]:
        """
        Шаблон для получателей в копии.

        Returns:
            tuple: (title, message)
        """
        title = f"📋 Вы в копии заявления от {author_name}"
        message = f'Тип: "{request_type}". {comment_preview}'
        return title, message

    @staticmethod
    def new_request_approver(
        author_name: str, request_type: str, comment_preview: str
    ) -> tuple[str, str]:
        """
        Шаблон для согласующего.

        Returns:
            tuple: (title, message)
        """
        title = f"✅ Новое заявление на согласование от {author_name}"
        message = f'Тип: "{request_type}". {comment_preview}'
        return title, message

    @staticmethod
    def new_request_department(
        author_name: str, request_type: str, comment_preview: str
    ) -> tuple[str, str]:
        """
        Шаблон для руководителей отдела и обработчиков.

        Returns:
            tuple: (title, message)
        """
        title = f"📝 Новое заявление в отделе от {author_name}"
        message = f'Тип: "{request_type}". {comment_preview}'
        return title, message

    @staticmethod
    def comment(
        author_name: str,
        request_type: str,
        employee_name: str,
        comment_text: str,
    ) -> tuple[str, str]:
        """
        Шаблон для комментария.

        Returns:
            tuple: (title, description)
        """
        title = f'💬 Новый комментарий к заявлению от {employee_name}'
        description = (
            f'{author_name} прокомментировал заявление '
            f'"{request_type}": {comment_text[:100]}'
        )
        return title, description

    @staticmethod
    def status_approved(
        employee_name: str, request_type: str, approver_name: str
    ) -> tuple[str, str]:
        """
        Шаблон для одобрения заявления.

        Returns:
            tuple: (title, message)
        """
        title = f'✅ Заявление одобрено: {request_type}'
        message = (
            f'Заявление от {employee_name} "{request_type}" '
            f'одобрено пользователем {approver_name}'
        )
        return title, message

    @staticmethod
    def status_rejected(
        employee_name: str, request_type: str, approver_name: str
    ) -> tuple[str, str]:
        """
        Шаблон для отклонения заявления.

        Returns:
            tuple: (title, message)
        """
        title = f'❌ Заявление отклонено: {request_type}'
        message = (
            f'Заявление от {employee_name} "{request_type}" '
            f'отклонено пользователем {approver_name}'
        )
        return title, message

    @staticmethod
    def status_changed(
        employee_name: str,
        request_type: str,
        old_status: str,
        new_status: str,
    ) -> tuple[str, str]:
        """
        Шаблон для изменения статуса.

        Returns:
            tuple: (title, message)
        """
        title = f'🔄 Статус заявления изменен: {request_type}'
        message = (
            f'Статус заявления от {employee_name} "{request_type}" '
            f'изменен: {old_status} → {new_status}'
        )
        return title, message


# ===== URL для действий =====

class ActionURLs:
    """URL для переходов из уведомлений."""

    REQUESTS_LIST = '/requests'

    @staticmethod
    def request_detail(request_id: int) -> str:
        """URL детальной страницы заявления."""
        return f'/requests?request={request_id}'

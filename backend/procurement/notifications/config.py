"""
Конфигурация уведомлений модуля Procurement.

Определяет типы уведомлений (verbs), шаблоны сообщений и URLs.
"""


# ===== Типы уведомлений (Verbs) =====

class NotificationVerbs:
    """Типы уведомлений для заявок на закупку."""

    # Новая заявка
    NEW_REQUEST = 'procurement_new_request'
    DEPARTMENT_REQUEST = 'procurement_department_request'

    # Согласование
    PENDING_APPROVAL = 'procurement_pending_approval'
    STAGE_APPROVED = 'procurement_stage_approved'

    # Статусы
    APPROVED = 'procurement_approved'
    REJECTED = 'procurement_rejected'
    IN_PROGRESS = 'procurement_in_progress'
    EXECUTOR_REASSIGNED = 'procurement_executor_reassigned'
    COMPLETED = 'procurement_completed'
    CANCELLED = 'procurement_cancelled'

    # Позиции и комментарии
    ITEM_UPDATED = 'procurement_item_updated'
    REQUEST_COMMENTED = 'procurement_request_commented'
    ITEM_COMMENTED = 'procurement_item_commented'


# ===== Шаблоны сообщений =====

class MessageTemplates:
    """Шаблоны сообщений для уведомлений."""

    @staticmethod
    def new_request(title: str, total_cost: float) -> tuple[str, str]:
        """
        Шаблон для новой заявки.

        Returns:
            tuple: (notification_title, description)
        """
        notification_title = 'Новая заявка на закупку'
        description = f'Создана заявка "{title}" на сумму {total_cost}₽'
        return notification_title, description

    @staticmethod
    def department_request(
        title: str, department_name: str
    ) -> tuple[str, str]:
        notification_title = 'Новая заявка для отдела'
        description = (
            f'Заявка "{title}" направлена в отдел '
            f'{department_name}.'
        )
        return notification_title, description

    @staticmethod
    def pending_approval(
        title: str, total_cost: float
    ) -> tuple[str, str]:
        """
        Шаблон для запроса на согласование.

        Returns:
            tuple: (notification_title, description)
        """
        notification_title = 'Требуется согласование'
        description = (
            f'Заявка "{title}" ожидает вашего согласования. '
            f'Сумма: {total_cost}₽'
        )
        return notification_title, description

    @staticmethod
    def stage_approved(approver_name: str, title: str) -> tuple[str, str]:
        """
        Шаблон для одобрения этапа согласования.

        Returns:
            tuple: (notification_title, description)
        """
        notification_title = 'Этап согласования пройден'
        description = f'{approver_name} одобрил заявку "{title}".'
        return notification_title, description

    @staticmethod
    def approved(title: str) -> tuple[str, str]:
        """
        Шаблон для полного одобрения заявки.

        Returns:
            tuple: (notification_title, description)
        """
        notification_title = 'Заявка одобрена'
        description = (
            f'Ваша заявка "{title}" была одобрена. '
            f'Можно приступать к закупке.'
        )
        return notification_title, description

    @staticmethod
    def rejected(title: str, comment: str = None) -> tuple[str, str]:
        """
        Шаблон для отклонения заявки.

        Returns:
            tuple: (notification_title, description)
        """
        notification_title = 'Заявка отклонена'
        if comment:
            description = (
                f'Ваша заявка "{title}" была отклонена. '
                f'Причина: {comment}'
            )
        else:
            description = (
                f'Ваша заявка "{title}" была отклонена. '
                f'Проверьте комментарии согласующих.'
            )
        return notification_title, description

    @staticmethod
    def rejected_by_approver(
        approver_name: str, title: str, comment: str
    ) -> tuple[str, str]:
        """
        Шаблон для отклонения конкретным согласующим.

        Returns:
            tuple: (notification_title, description)
        """
        notification_title = 'Заявка отклонена'
        description = (
            f'{approver_name} отклонил заявку "{title}". '
            f'Причина: {comment}'
        )
        return notification_title, description

    @staticmethod
    def executor_reassigned(
        title: str, executor_name: str
    ) -> tuple[str, str]:
        notification_title = 'Заявку забрал другой сотрудник'
        description = (
            f'{executor_name} взял в работу заявку "{title}".'
        )
        return notification_title, description

    @staticmethod
    def in_progress(
        title: str, executor_name: str
    ) -> tuple[str, str]:
        """
        Шаблон для взятия заявки в работу.

        Returns:
            tuple: (notification_title, description)
        """
        notification_title = 'Заявка взята в работу'
        description = (
            f'Заявка "{title}" взята в работу '
            f'пользователем {executor_name}.'
        )
        return notification_title, description

    @staticmethod
    def in_progress_requestor(
        title: str, executor_name: str
    ) -> tuple[str, str]:
        """
        Шаблон для создателя заявки о взятии в работу.

        Returns:
            tuple: (notification_title, description)
        """
        notification_title = 'Ваша заявка взята в работу'
        description = (
            f'Заявка "{title}" взята в работу '
            f'пользователем {executor_name}.'
        )
        return notification_title, description

    @staticmethod
    def completed(title: str) -> tuple[str, str]:
        """
        Шаблон для завершения заявки.

        Returns:
            tuple: (notification_title, description)
        """
        notification_title = 'Заявка завершена'
        description = f'Закупка по заявке "{title}" завершена.'
        return notification_title, description

    @staticmethod
    def completed_approver(title: str) -> tuple[str, str]:
        """
        Шаблон для согласующих о завершении заявки.

        Returns:
            tuple: (notification_title, description)
        """
        notification_title = 'Заявка завершена'
        description = f'Заявка "{title}" успешно завершена.'
        return notification_title, description

    @staticmethod
    def cancelled(title: str, reason: str = 'не указана') -> tuple[str, str]:
        """
        Шаблон для отмены заявки.

        Returns:
            tuple: (notification_title, description)
        """
        notification_title = 'Заявка отменена'
        description = (
            f'Заявка "{title}" была отменена автором. '
            f'Причина: {reason}'
        )
        return notification_title, description

    @staticmethod
    def item_updated(
        title: str, item_name: str, actor_name: str
    ) -> tuple[str, str]:
        notification_title = 'Позиция закупки изменена'
        description = (
            f'{actor_name} изменил позицию "{item_name}" '
            f'в заявке "{title}".'
        )
        return notification_title, description

    @staticmethod
    def request_commented(
        title: str, actor_name: str
    ) -> tuple[str, str]:
        notification_title = 'Новый комментарий к закупке'
        description = (
            f'{actor_name} оставил комментарий к заявке "{title}".'
        )
        return notification_title, description

    @staticmethod
    def item_commented(
        title: str, item_name: str, actor_name: str
    ) -> tuple[str, str]:
        notification_title = 'Новый комментарий к позиции'
        description = (
            f'{actor_name} оставил комментарий к позиции "{item_name}" '
            f'в заявке "{title}".'
        )
        return notification_title, description


# ===== URL для действий =====

class ActionURLs:
    """URL для переходов из уведомлений."""

    PROCUREMENT_LIST = '/procurement'

    @staticmethod
    def request_detail(request_id: int) -> str:
        """URL детальной страницы заявки."""
        return f'/procurement?request={request_id}'

class NotificationVerbs:
    TASK_ASSIGNED = "task_assigned"
    TASK_REASSIGNED = "task_reassigned"
    TASK_COMMENT = "task_comment"
    TASK_DUE_DATE_CHANGED = "task_due_date_changed"
    TASK_DUE_SOON = "task_due_soon"
    TASK_OVERDUE = "task_overdue"
    TASK_COMPLETED = "task_completed"
    TASK_REOPENED = "task_reopened"
    TASK_LINKED_OBJECT_ADDED = "task_linked_object_added"
    TASK_BOARD_MEMBER_ADDED = "task_board_member_added"


class ActionURLs:
    @staticmethod
    def task_detail(task) -> str:
        return f"/tasks?board={task.board_id}&task={task.id}"

    @staticmethod
    def board_detail(board) -> str:
        return f"/tasks?board={board.id}"


class MessageTemplates:
    @staticmethod
    def task_assigned(task, actor_name: str) -> tuple[str, str]:
        return (
            "Вам назначена задача",
            f'{actor_name} назначил вам задачу #{task.id} "{task.title}".',
        )

    @staticmethod
    def task_reassigned(task, actor_name: str) -> tuple[str, str]:
        return (
            "Исполнитель задачи изменен",
            f'{actor_name} изменил исполнителя задачи #{task.id} "{task.title}".',
        )

    @staticmethod
    def task_comment(task, actor_name: str, text: str) -> tuple[str, str]:
        preview = text[:160]
        return (
            "Новый комментарий к задаче",
            f'{actor_name} прокомментировал задачу #{task.id} "{task.title}": {preview}',
        )

    @staticmethod
    def task_due_date_changed(
        task,
        actor_name: str,
        old_due_date,
        new_due_date,
    ) -> tuple[str, str]:
        old_value = old_due_date or "без срока"
        new_value = new_due_date or "без срока"
        return (
            "Срок задачи изменен",
            (
                f'{actor_name} изменил срок задачи #{task.id} "{task.title}": '
                f"{old_value} -> {new_value}."
            ),
        )

    @staticmethod
    def task_due_soon(task) -> tuple[str, str]:
        return (
            "Срок задачи сегодня",
            f'Сегодня срок задачи #{task.id} "{task.title}".',
        )

    @staticmethod
    def task_overdue(task) -> tuple[str, str]:
        return (
            "Задача просрочена",
            f'Просрочена задача #{task.id} "{task.title}".',
        )

    @staticmethod
    def task_completed(task, actor_name: str) -> tuple[str, str]:
        return (
            "Задача завершена",
            f'{actor_name} завершил задачу #{task.id} "{task.title}".',
        )

    @staticmethod
    def task_reopened(task, actor_name: str) -> tuple[str, str]:
        return (
            "Задача возвращена в работу",
            f'{actor_name} вернул в работу задачу #{task.id} "{task.title}".',
        )

    @staticmethod
    def task_linked_object_added(
        task,
        actor_name: str,
        object_type: str,
    ) -> tuple[str, str]:
        return (
            "К задаче добавлен связанный объект",
            (
                f'{actor_name} добавил объект "{object_type}" '
                f'к задаче #{task.id} "{task.title}".'
            ),
        )

    @staticmethod
    def board_member_added(board, actor_name: str) -> tuple[str, str]:
        return (
            "Вас добавили на доску",
            f'{actor_name} добавил вас на доску "{board.name}".',
        )

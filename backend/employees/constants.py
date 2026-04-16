# backend\employees\constants.py
GENDER_CHOICES = (
    (1, "Мужской"),
    (2, "Женский"),
    (0, "Не указан"),
)


ACTION_HIRED = "hired"
ACTION_DISMISSED = "dismissed"
ACTION_ON_LEAVE = "on_leave"
ACTION_RETURNED_FROM_LEAVE = "returned_from_leave"
ACTION_ON_MATERNITY = "on_maternity"
ACTION_RETURNED_FROM_MATERNITY = "returned_from_maternity"
ACTION_TRANSFERRED = "transferred"
ACTION_REHIRED = "rehired"

ACTION_CHOICES = [
    (ACTION_HIRED, "Принят"),
    (ACTION_DISMISSED, "Уволен"),
    (ACTION_ON_LEAVE, "В отпуске"),
    (ACTION_RETURNED_FROM_LEAVE, "Вернулся из отпуска"),
    (ACTION_ON_MATERNITY, "В декрете"),
    (ACTION_RETURNED_FROM_MATERNITY, "Вернулся из декрета"),
    (ACTION_TRANSFERRED, "Переведен"),
    (ACTION_REHIRED, "Восстановлен"),
]


class DeptPerm:
    MANAGE = "manage_department"
    CHANGE_HEAD = "change_department_head"
    ASSIGN_ROLE = "assign_department_role"
    MANAGE_FEED = "manage_department_feed"
    VIEW_REQUESTCOMMENT = "view_requestcomment"
    ADD_REQUESTCOMMENT = "add_requestcomment"
    VIEW_REQUEST = "view_request"
    CAN_PROCESS_REQUESTS = "can_process_requests"
    MANAGE_EQUIPMENT = "manage_department_equipment"

    CHOICES = (
        (MANAGE, "Управлять отделом"),
        (CHANGE_HEAD, "Назначать руководителя"),
        (ASSIGN_ROLE, "Назначать роли участникам"),
        (MANAGE_FEED, "Редактировать публикации отдела"),
        (VIEW_REQUESTCOMMENT, "Просмотр комментариев по заявлениям"),
        (ADD_REQUESTCOMMENT, "Добавление коментариев по заявлениям"),
        (VIEW_REQUEST, "Просмотр заявлений отдела"),
        (CAN_PROCESS_REQUESTS, "Рассмотрение заявлений отдела"),
        (MANAGE_EQUIPMENT, "Управлять оборудованием отдела"),
    )

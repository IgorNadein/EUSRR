# backend\employees\constants.py
GENDER_CHOICES = (
    (1, "Мужской"),
    (2, "Женский"),
    (0, "Не указан"),
)


ACTION_WORKING = "working"
ACTION_REMOTE = "remote"
ACTION_HIRED = "hired"
ACTION_DISMISSED = "dismissed"
ACTION_ON_LEAVE = "on_leave"
ACTION_RETURNED_FROM_LEAVE = "returned_from_leave"
ACTION_ON_SICK_LEAVE = "on_sick_leave"
ACTION_RETURNED_FROM_SICK_LEAVE = "returned_from_sick_leave"
ACTION_ON_DAY_OFF = "on_day_off"
ACTION_RETURNED_FROM_DAY_OFF = "returned_from_day_off"
ACTION_ON_MATERNITY = "on_maternity"
ACTION_RETURNED_FROM_MATERNITY = "returned_from_maternity"
ACTION_TRANSFERRED = "transferred"
ACTION_REHIRED = "rehired"

ACTION_LABELS = {
    ACTION_WORKING: "Работает",
    ACTION_REMOTE: "На удалёнке",
    ACTION_HIRED: "Принят",
    ACTION_DISMISSED: "Уволен",
    ACTION_ON_LEAVE: "В отпуске",
    ACTION_RETURNED_FROM_LEAVE: "Вернулся из отпуска",
    ACTION_ON_SICK_LEAVE: "На больничном",
    ACTION_RETURNED_FROM_SICK_LEAVE: "Вернулся с больничного",
    ACTION_ON_DAY_OFF: "В отгуле",
    ACTION_RETURNED_FROM_DAY_OFF: "Вернулся из отгула",
    ACTION_ON_MATERNITY: "В декрете",
    ACTION_RETURNED_FROM_MATERNITY: "Вернулся из декрета",
    ACTION_TRANSFERRED: "Переведен",
    ACTION_REHIRED: "Восстановлен",
}

PERMANENT_ACTIONS = {
    ACTION_WORKING,
    ACTION_REMOTE,
    ACTION_DISMISSED,
}

PERIOD_ACTIONS = {
    ACTION_ON_LEAVE,
    ACTION_ON_SICK_LEAVE,
    ACTION_ON_DAY_OFF,
    ACTION_ON_MATERNITY,
}

MARKER_ACTIONS = {
    ACTION_HIRED,
    ACTION_TRANSFERRED,
    ACTION_REHIRED,
    ACTION_RETURNED_FROM_LEAVE,
    ACTION_RETURNED_FROM_SICK_LEAVE,
    ACTION_RETURNED_FROM_DAY_OFF,
    ACTION_RETURNED_FROM_MATERNITY,
}

ACTIVATING_MARKER_ACTIONS = {
    ACTION_HIRED,
    ACTION_REHIRED,
}

RETURN_MARKER_ACTIONS = {
    ACTION_RETURNED_FROM_LEAVE,
    ACTION_RETURNED_FROM_SICK_LEAVE,
    ACTION_RETURNED_FROM_DAY_OFF,
    ACTION_RETURNED_FROM_MATERNITY,
}

TEMPORARY_START_ACTIONS = PERIOD_ACTIONS
TEMPORARY_RETURN_ACTIONS = RETURN_MARKER_ACTIONS

TEMPORARY_ACTION_PRIORITIES = {
    ACTION_ON_SICK_LEAVE: 0,
    ACTION_ON_MATERNITY: 1,
    ACTION_ON_LEAVE: 2,
    ACTION_ON_DAY_OFF: 3,
}

ACTION_CHOICES = [(action, ACTION_LABELS[action]) for action in ACTION_LABELS]


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

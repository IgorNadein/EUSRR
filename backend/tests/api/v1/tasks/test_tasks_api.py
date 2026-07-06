from unittest.mock import patch
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from communications.models import Chat, ChatMembership, Message
from employees.models import Department, EmployeeDepartment, RoleAssignment
from schedule.models import Calendar, CalendarRelation, Event
from tasks.models import Task, TaskBoard, TaskColumn
from tasks.realtime import get_task_board_recipient_ids

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    return User.objects.create_user(
        email="task-user@example.com",
        password="testpass123",
        phone_number="+79994440001",
        first_name="Иван",
        last_name="Задачев",
        is_active=True,
        email_verified=True,
        send_activation_email=False,
    )


def make_user(email, phone_number, **extra):
    defaults = {
        "password": "testpass123",
        "phone_number": phone_number,
        "first_name": "Тест",
        "last_name": "Сотрудник",
        "is_active": True,
        "email_verified": True,
        "send_activation_email": False,
    }
    defaults.update(extra)
    return User.objects.create_user(email=email, **defaults)


def test_default_board_creates_work_columns(api_client, user):
    api_client.force_authenticate(user=user)
    url = reverse("api:v1:tasks:task-board-default")

    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["name"] == "Рабочая доска"
    assert [column["name"] for column in response.data["columns"]] == [
        "Новые",
        "В работе",
        "На проверке",
        "Готово",
    ]
    assert TaskBoard.objects.count() == 1
    assert TaskColumn.objects.count() == 4


def test_create_task_and_move_to_done_column(api_client, user):
    api_client.force_authenticate(user=user)
    board_response = api_client.get(
        reverse("api:v1:tasks:task-board-default")
    )
    board_id = board_response.data["id"]
    columns = {column["name"]: column for column in board_response.data["columns"]}

    create_response = api_client.post(
        reverse("api:v1:tasks:task-list"),
        {
            "board": board_id,
            "column": columns["Новые"]["id"],
            "title": "Подготовить прототип доски",
            "description": "Собрать первый рабочий workflow",
            "assignee_id": user.id,
            "priority": "high",
        },
        format="json",
    )

    assert create_response.status_code == status.HTTP_201_CREATED
    task_id = create_response.data["id"]
    assert create_response.data["created_by"]["id"] == user.id
    assert create_response.data["assignee"]["id"] == user.id

    with patch("api.v1.tasks.views.send_task_board_update") as send_update:
        move_response = api_client.post(
            reverse("api:v1:tasks:task-move", kwargs={"pk": task_id}),
            {"column": columns["Готово"]["id"]},
            format="json",
        )

    assert move_response.status_code == status.HTTP_200_OK
    assert move_response.data["column"] == columns["Готово"]["id"]
    assert move_response.data["completed_at"] is not None
    send_update.assert_called_once()
    send_args, send_kwargs = send_update.call_args
    assert send_args[0].id == board_id
    assert send_args[1:4] == ("moved", "task", task_id)
    assert send_kwargs["extra"] == {"column_id": columns["Готово"]["id"]}

    task = Task.objects.get(id=task_id)
    assert task.column_id == columns["Готово"]["id"]
    assert task.completed_at is not None


def test_task_rejects_column_from_another_board(api_client, user):
    api_client.force_authenticate(user=user)
    first = api_client.get(reverse("api:v1:tasks:task-board-default")).data
    second_board = TaskBoard.objects.create(
        name="Вторая доска",
        created_by=user,
    )
    other_column = TaskColumn.objects.create(
        board=second_board,
        name="Чужая колонка",
        position=1000,
    )

    response = api_client.post(
        reverse("api:v1:tasks:task-list"),
        {
            "board": first["id"],
            "column": other_column.id,
            "title": "Невалидная задача",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "column" in response.data


def test_create_board_accepts_members_and_departments(api_client, user):
    member = make_user("task-member@example.com", "+79994440002")
    department = Department.objects.create(name="Проектный отдел")
    api_client.force_authenticate(user=user)

    response = api_client.post(
        reverse("api:v1:tasks:task-board-list"),
        {
            "name": "Приватная доска",
            "description": "Только для проектной группы",
            "members": [member.id],
            "departments": [department.id],
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["members"] == [member.id]
    assert response.data["member_details"][0]["id"] == member.id
    assert response.data["departments"] == [department.id]
    assert response.data["department_details"][0]["name"] == department.name
    assert TaskColumn.objects.filter(board_id=response.data["id"]).count() == 4


def test_board_member_can_access_private_board(api_client):
    owner = make_user("task-owner@example.com", "+79994440003")
    member = make_user("task-member-2@example.com", "+79994440004")
    outsider = make_user("task-outsider@example.com", "+79994440005")
    board = TaskBoard.objects.create(name="Закрытая доска", created_by=owner)
    board.members.add(member)
    column = TaskColumn.objects.create(board=board, name="Новые", position=1000)

    api_client.force_authenticate(user=member)
    member_list = api_client.get(reverse("api:v1:tasks:task-board-list"))
    assert member_list.status_code == status.HTTP_200_OK
    assert [item["id"] for item in member_list.data["results"]] == [board.id]

    create_response = api_client.post(
        reverse("api:v1:tasks:task-list"),
        {
            "board": board.id,
            "column": column.id,
            "title": "Задача участника",
        },
        format="json",
    )
    assert create_response.status_code == status.HTTP_201_CREATED

    api_client.force_authenticate(user=outsider)
    outsider_list = api_client.get(reverse("api:v1:tasks:task-board-list"))
    assert outsider_list.status_code == status.HTTP_200_OK
    assert [item["id"] for item in outsider_list.data["results"]] == []

    detail_response = api_client.get(
        reverse("api:v1:tasks:task-board-detail", kwargs={"pk": board.id})
    )
    assert detail_response.status_code == status.HTTP_404_NOT_FOUND

    hidden_create_response = api_client.post(
        reverse("api:v1:tasks:task-list"),
        {
            "board": board.id,
            "column": column.id,
            "title": "Чужая задача",
        },
        format="json",
    )
    assert hidden_create_response.status_code == status.HTTP_400_BAD_REQUEST
    assert "board" in hidden_create_response.data


def test_department_member_can_access_department_board(api_client):
    owner = make_user("task-board-owner@example.com", "+79994440006")
    department_user = make_user("task-department-user@example.com", "+79994440007")
    outsider = make_user("task-department-outsider@example.com", "+79994440008")
    department = Department.objects.create(name="Отдел внедрения")
    EmployeeDepartment.objects.create(
        employee=department_user,
        department=department,
        is_active=True,
    )
    board = TaskBoard.objects.create(name="Доска отдела", created_by=owner)
    board.departments.add(department)

    api_client.force_authenticate(user=department_user)
    department_response = api_client.get(reverse("api:v1:tasks:task-board-list"))
    assert department_response.status_code == status.HTTP_200_OK
    assert [item["id"] for item in department_response.data["results"]] == [board.id]

    api_client.force_authenticate(user=outsider)
    outsider_response = api_client.get(reverse("api:v1:tasks:task-board-list"))
    assert outsider_response.status_code == status.HTTP_200_OK
    assert [item["id"] for item in outsider_response.data["results"]] == []


def test_task_board_realtime_recipients_match_board_access():
    owner = make_user("task-rt-owner@example.com", "+79994440009")
    member = make_user("task-rt-member@example.com", "+79994440010")
    department_user = make_user("task-rt-dept@example.com", "+79994440011")
    role_user = make_user("task-rt-role@example.com", "+79994440012")
    outsider = make_user("task-rt-outsider@example.com", "+79994440013")
    admin = make_user(
        "task-rt-admin@example.com",
        "+79994440014",
        is_staff=True,
    )
    inactive_member = make_user(
        "task-rt-inactive@example.com",
        "+79994440015",
        is_active=False,
    )
    department = Department.objects.create(name="Realtime отдел")
    role = department.roles.create(name="Внешний участник")
    EmployeeDepartment.objects.create(
        employee=department_user,
        department=department,
        is_active=True,
    )
    RoleAssignment.objects.create(
        employee=role_user,
        role=role,
        is_active=True,
    )
    board = TaskBoard.objects.create(name="Закрытая realtime доска", created_by=owner)
    board.members.add(member, inactive_member)
    board.departments.add(department)

    recipients = get_task_board_recipient_ids(board)

    assert owner.id in recipients
    assert member.id in recipients
    assert department_user.id in recipients
    assert role_user.id in recipients
    assert admin.id in recipients
    assert outsider.id not in recipients
    assert inactive_member.id not in recipients


def test_public_task_board_realtime_recipients_include_active_users():
    owner = make_user("task-rt-public-owner@example.com", "+79994440016")
    active_user = make_user("task-rt-public-user@example.com", "+79994440017")
    inactive_user = make_user(
        "task-rt-public-inactive@example.com",
        "+79994440018",
        is_active=False,
    )
    board = TaskBoard.objects.create(name="Публичная realtime доска", created_by=owner)

    recipients = get_task_board_recipient_ids(board)

    assert owner.id in recipients
    assert active_user.id in recipients
    assert inactive_user.id not in recipients


def test_task_linked_message_is_visible_by_task_access(api_client):
    owner = make_user("task-link-owner@example.com", "+79994440019")
    board_member = make_user("task-link-member@example.com", "+79994440020")
    board = TaskBoard.objects.create(name="Доска со связями", created_by=owner)
    board.members.add(board_member)
    column = TaskColumn.objects.create(board=board, name="Новые", position=1000)
    task = Task.objects.create(
        board=board,
        column=column,
        title="Разобрать сообщение",
        created_by=owner,
    )
    chat = Chat.objects.create(name="Закрытый чат", type="group", created_by=owner)
    ChatMembership.objects.create(chat=chat, user=owner, role="admin")
    message = Message.objects.create(
        chat=chat,
        author=owner,
        content="Важный контекст для задачи",
    )

    api_client.force_authenticate(user=board_member)
    denied_response = api_client.post(
        reverse("api:v1:tasks:task-linked-messages", kwargs={"pk": task.id}),
        {"message_id": message.id},
        format="json",
    )
    assert denied_response.status_code == status.HTTP_403_FORBIDDEN

    api_client.force_authenticate(user=owner)
    link_response = api_client.post(
        reverse("api:v1:tasks:task-linked-messages", kwargs={"pk": task.id}),
        {"message_id": message.id},
        format="json",
    )
    assert link_response.status_code == status.HTTP_201_CREATED
    assert link_response.data["message"]["content"] == "Важный контекст для задачи"
    assert link_response.data["can_open"] is True
    assert link_response.data["object_url"] == (
        f"/messages/{chat.id}?message={message.id}"
    )

    api_client.force_authenticate(user=board_member)
    linked_response = api_client.get(
        reverse("api:v1:tasks:task-linked-messages", kwargs={"pk": task.id})
    )
    assert linked_response.status_code == status.HTTP_200_OK
    assert linked_response.data[0]["message_id"] == message.id
    assert linked_response.data[0]["message"]["content"] == "Важный контекст для задачи"
    assert linked_response.data[0]["can_open"] is False
    assert linked_response.data[0]["object_url"] is None


def test_task_linked_calendar_event_respects_event_access(api_client):
    owner = make_user("task-event-owner@example.com", "+79994440024")
    board_member = make_user("task-event-member@example.com", "+79994440025")
    board = TaskBoard.objects.create(name="Доска с событиями", created_by=owner)
    board.members.add(board_member)
    column = TaskColumn.objects.create(board=board, name="Новые", position=1000)
    task = Task.objects.create(
        board=board,
        column=column,
        title="Подготовить встречу",
        created_by=owner,
    )
    calendar = Calendar.objects.create(name="Закрытый календарь", slug="closed")
    CalendarRelation.objects.create(
        calendar=calendar,
        content_type=ContentType.objects.get_for_model(User),
        object_id=owner.id,
        distinction="owner",
        inheritable=True,
    )
    now = timezone.now()
    event = Event.objects.create(
        calendar=calendar,
        title="Встреча по задаче",
        description="Обсудить детали",
        start=now,
        end=now + timedelta(hours=1),
        creator=owner,
        color_event="#38bdf8",
    )

    api_client.force_authenticate(user=board_member)
    denied_response = api_client.post(
        reverse("api:v1:tasks:task-linked-events", kwargs={"pk": task.id}),
        {"event_id": event.id},
        format="json",
    )
    assert denied_response.status_code == status.HTTP_403_FORBIDDEN

    api_client.force_authenticate(user=owner)
    link_response = api_client.post(
        reverse("api:v1:tasks:task-linked-events", kwargs={"pk": task.id}),
        {"event_id": event.id},
        format="json",
    )
    assert link_response.status_code == status.HTTP_201_CREATED
    assert link_response.data["event"]["title"] == "Встреча по задаче"
    assert link_response.data["can_open"] is True
    assert link_response.data["object_url"] == (
        f"/calendar?calendar={calendar.id}&event={event.id}"
    )

    api_client.force_authenticate(user=board_member)
    linked_response = api_client.get(
        reverse("api:v1:tasks:task-linked-events", kwargs={"pk": task.id})
    )
    assert linked_response.status_code == status.HTTP_200_OK
    assert linked_response.data[0]["event_id"] == event.id
    assert linked_response.data[0]["event"]["title"] == "Встреча по задаче"
    assert linked_response.data[0]["can_open"] is False
    assert linked_response.data[0]["object_url"] is None

    reverse_linked_response = api_client.get(
        reverse("api:v1:tasks:task-linked-event-tasks"),
        {"event_id": event.id},
    )
    assert reverse_linked_response.status_code == status.HTTP_403_FORBIDDEN

    api_client.force_authenticate(user=owner)
    reverse_linked_response = api_client.get(
        reverse("api:v1:tasks:task-linked-event-tasks"),
        {"event_id": event.id},
    )
    assert reverse_linked_response.status_code == status.HTTP_200_OK
    assert reverse_linked_response.data[0]["id"] == task.id
    assert reverse_linked_response.data[0]["title"] == "Подготовить встречу"
    assert reverse_linked_response.data[0]["board_name"] == "Доска с событиями"


def test_task_activity_records_core_actions(api_client, user):
    api_client.force_authenticate(user=user)
    board_response = api_client.get(
        reverse("api:v1:tasks:task-board-default")
    )
    board_id = board_response.data["id"]
    columns = board_response.data["columns"]
    source_column = columns[0]
    target_column = columns[1]

    create_response = api_client.post(
        reverse("api:v1:tasks:task-list"),
        {
            "board": board_id,
            "column": source_column["id"],
            "title": "История задачи",
            "description": "",
            "priority": "medium",
        },
        format="json",
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    task_id = create_response.data["id"]

    update_response = api_client.patch(
        reverse("api:v1:tasks:task-detail", kwargs={"pk": task_id}),
        {"title": "История задачи обновлена"},
        format="json",
    )
    assert update_response.status_code == status.HTTP_200_OK

    move_response = api_client.post(
        reverse("api:v1:tasks:task-move", kwargs={"pk": task_id}),
        {"column": target_column["id"]},
        format="json",
    )
    assert move_response.status_code == status.HTTP_200_OK

    activity_response = api_client.get(
        reverse("api:v1:tasks:task-activity", kwargs={"pk": task_id})
    )
    assert activity_response.status_code == status.HTTP_200_OK
    actions = [item["action"] for item in activity_response.data]
    assert actions == ["moved", "updated", "created"]
    assert activity_response.data[0]["metadata"]["from_column"] == source_column["name"]
    assert activity_response.data[0]["metadata"]["to_column"] == target_column["name"]
    assert "title" in activity_response.data[1]["metadata"]["fields"]


def test_chat_message_serialization_shows_only_accessible_linked_tasks(api_client):
    owner = make_user("task-link-chat-owner@example.com", "+79994440021")
    visible_user = make_user("task-link-chat-visible@example.com", "+79994440022")
    hidden_user = make_user("task-link-chat-hidden@example.com", "+79994440023")
    board = TaskBoard.objects.create(name="Видимая доска", created_by=owner)
    board.members.add(visible_user)
    column = TaskColumn.objects.create(
        board=board,
        name="Новые",
        position=1000,
        color="#16a34a",
    )
    task = Task.objects.create(
        board=board,
        column=column,
        title="Задача из сообщения",
        created_by=owner,
        priority="critical",
    )
    chat = Chat.objects.create(name="Общий чат", type="group", created_by=owner)
    ChatMembership.objects.create(chat=chat, user=owner, role="admin")
    ChatMembership.objects.create(chat=chat, user=visible_user, role="member")
    ChatMembership.objects.create(chat=chat, user=hidden_user, role="member")
    message = Message.objects.create(
        chat=chat,
        author=owner,
        content="Сообщение с задачей",
    )

    api_client.force_authenticate(user=owner)
    api_client.post(
        reverse("api:v1:tasks:task-linked-messages", kwargs={"pk": task.id}),
        {"message_id": message.id},
        format="json",
    )

    api_client.force_authenticate(user=visible_user)
    visible_response = api_client.get(
        reverse("api:v1:chats-messages", kwargs={"pk": chat.id})
    )
    assert visible_response.status_code == status.HTTP_200_OK
    linked_task = visible_response.data["messages"][0]["linked_tasks"][0]
    assert linked_task["id"] == task.id
    assert linked_task["column_id"] == column.id
    assert linked_task["column_name"] == "Новые"
    assert linked_task["column_color"] == "#16a34a"
    assert linked_task["priority"] == "critical"
    assert linked_task["priority_display"] == "Критический"

    api_client.force_authenticate(user=hidden_user)
    hidden_response = api_client.get(
        reverse("api:v1:chats-messages", kwargs={"pk": chat.id})
    )
    assert hidden_response.status_code == status.HTTP_200_OK
    assert hidden_response.data["messages"][0]["linked_tasks"] == []
